"""模型网关（M06）：统一多厂商接入、任务路由、降级容错。

设计：
- 供应商配置在 providers.json（密钥只来自环境变量 key_env，禁止硬编码）。
- route(task)：按 capable_tasks + priority 选主供应商；失败自动切换备份。
- cross_check(prompt, n=2)：双模型交叉校验（高利害评估题用），返回各响应与是否一致。
- 依赖 OpenAI 兼容客户端：有 openai 库用之，否则退化为 httpx；两者都没有时抛清晰的
  GatewayUnavailable 提示而非烂堆栈。

本模块验收只要求可导入、路由逻辑正确（不需要真实 API key）。
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import openai
except ImportError:
    openai = None
try:
    import httpx
except ImportError:
    httpx = None


class GatewayError(Exception):
    """统一网关异常。"""

    def __init__(self, msg, provider=None, cause=None):
        super().__init__(msg)
        self.provider = provider
        self.cause = cause


class GatewayUnavailable(GatewayError):
    """没有任何可用供应商/客户端（缺 key 或缺库）。"""


@dataclass
class ChatRequest:
    provider: str
    task: str = "chat"
    model: Optional[str] = None
    messages: List[dict] = field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 2048
    api_base: Optional[str] = None
    api_key: Optional[str] = None


def _builtin_providers_path():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "providers.json")
    if os.path.isfile(here):
        return here
    try:
        from packages.core.frozen_paths import resource_root
        alt = os.path.join(resource_root(), "packages", "llm_gateway", "providers.json")
        if os.path.isfile(alt):
            return alt
    except Exception:
        pass
    return here


def user_config_path():
    try:
        from packages.core.frozen_paths import llm_config_path
        return llm_config_path()
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "llm_config.json")


def load_store() -> dict:
    """完整配置仓库：{active, profiles[]}。兼容旧版扁平字段。"""
    path = user_config_path()
    if not os.path.isfile(path):
        return {"active": "", "profiles": []}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f) or {}
    except Exception:
        return {"active": "", "profiles": []}
    if isinstance(raw.get("profiles"), list):
        return {
            "active": raw.get("active") or "",
            "profiles": [p for p in raw["profiles"] if isinstance(p, dict)],
        }
    # 旧格式：单套配置 → 迁成一条默认档案
    if raw.get("api_key") or raw.get("api_base"):
        pid = "legacy"
        profile = {
            "id": pid,
            "name": raw.get("name") or "默认配置",
            "provider": raw.get("provider") or "custom",
            "api_base": raw.get("api_base") or "",
            "api_key": raw.get("api_key") or "",
            "model": raw.get("model") or "",
        }
        return {"active": pid, "profiles": [profile]}
    return {"active": "", "profiles": []}


def _write_store(store: dict) -> None:
    path = user_config_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "active": store.get("active") or "",
            "profiles": store.get("profiles") or [],
        }, f, ensure_ascii=False, indent=2)


def load_user_config() -> dict:
    """当前启用的那一套（扁平，供发请求用）。"""
    store = load_store()
    profiles = store.get("profiles") or []
    if not profiles:
        return {}
    active = store.get("active")
    for p in profiles:
        if p.get("id") == active:
            return dict(p)
    return dict(profiles[0])


PRESETS = {
    "deepseek": {"api_base": "https://api.deepseek.com/v1", "model": "deepseek-chat", "key_env": "DEEPSEEK_API_KEY"},
    "qwen": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key_env": "QWEN_API_KEY"},
    "kimi": {"api_base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key_env": "KIMI_API_KEY"},
    "openai": {"api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
}


def normalize_key(raw: str) -> str:
    """去掉粘贴带来的引号、Bearer、空白、零宽字符。"""
    if raw is None:
        return ""
    s = str(raw)
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\xa0"):
        s = s.replace(ch, "")
    s = s.strip().strip("\"'").strip()
    if s.lower().startswith("bearer "):
        s = s[7:].strip()
    s = "".join(s.split())  # 去掉中间换行/空格
    return s


def normalize_base(raw: str) -> str:
    """统一成 OpenAI 兼容根地址（尽量落到 .../v1），不要带 /chat/completions。"""
    if not raw:
        return ""
    s = str(raw).strip().strip("\"'").rstrip("/")
    s = s.replace("\\", "/")
    if s and not s.lower().startswith("http"):
        s = "https://" + s
    lower = s.lower()
    for suffix in ("/chat/completions", "/completions", "/models"):
        if lower.endswith(suffix):
            s = s[: -len(suffix)].rstrip("/")
            lower = s.lower()
            break
    while lower.endswith("/v1/v1"):
        s = s[:-3].rstrip("/")
        lower = s.lower()
    # 中转站填首页（如 https://ican-gpt.com）时自动补 /v1
    if s and "/v1" not in lower:
        s = s.rstrip("/") + "/v1"
    return s


def _ssl_context():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _auth_header_sets(api_key: str):
    if not api_key:
        return [{"Accept": "application/json"}]
    # 标准 OpenAI 兼容中转及官方 API 均必须携带 Bearer
    if api_key.startswith("sk-") or len(api_key) >= 16:
        return [
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        ]
    return [
        {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        {"Authorization": api_key, "Accept": "application/json"},
        {"x-api-key": api_key, "Accept": "application/json"},
    ]


def _http_json(method: str, url: str, api_key: str, payload=None, timeout: int = 45) -> dict:
    import ssl
    import urllib.error
    import urllib.request
    last_err = None
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    contexts = [_ssl_context()]
    try:
        contexts.append(ssl._create_unverified_context())
    except Exception:
        pass
    for ctx in contexts:
        for headers in _auth_header_sets(api_key):
            h = dict(headers)
            h["User-Agent"] = "TeacherEval/1.0"
            if body is not None:
                h["Content-Type"] = "application/json"
            class _NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    raise GatewayError(
                        f"{url} 被重定向到 {newurl}（HTTP {code}）。"
                        f"中转站应直接提供 /v1/chat/completions，不要跳到网站首页。"
                    )

            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx),
                urllib.request.HTTPHandler(),
                _NoRedirect(),
            )
            req = urllib.request.Request(url, data=body, method=method, headers=h)
            try:
                with opener.open(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                if _looks_html(raw):
                    raise GatewayError(f"{url} 返回网页而非 API JSON")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    raise GatewayError(f"{url} 返回不是 JSON：{raw[:200]}")
                if isinstance(data, dict) and data.get("error"):
                    raise GatewayError(_api_error_message(raw) or str(data["error"]))
                return data if isinstance(data, dict) else {"data": data}
            except GatewayError as e:
                last_err = e
                if "限流" in str(e) or "rate_limit" in str(e).lower():
                    raise e
                continue
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
                api_msg = _api_error_message(raw, e.code)
                if api_msg:
                    raise GatewayError(f"{api_msg} @ {url}", cause=e)
                if _looks_html(raw):
                    last_err = GatewayError(f"HTTP {e.code} @ {url} 返回网页而非 API JSON", cause=e)
                    continue
                last_err = GatewayError(f"HTTP {e.code} {e.reason} @ {url}：{raw[:400]}", cause=e)
                if e.code in (401, 403, 404):
                    continue
                break
            except Exception as e:
                last_err = GatewayError(f"{type(e).__name__} @ {url}：{e}", cause=e)
                continue
    raise last_err or GatewayError(f"请求失败：{url}")


def _looks_html(raw: str) -> bool:
    s = (raw or "").lstrip().lower()
    return s.startswith("<!doctype") or s.startswith("<html")


def _api_error_message(raw: str, status: int = 0) -> str:
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    err = data.get("error") or data.get("message") or data.get("msg")
    if isinstance(err, dict):
        msg = err.get("message") or err.get("msg") or str(err)
        typ = err.get("type") or ""
    else:
        msg = str(err or "")
        typ = data.get("type") or ""
    if not msg:
        return ""
    if status == 429 or "rate_limit" in str(typ):
        return f"中转站限流（429）：{msg}。接口是通的，请稍后再试，不要改地址。"
    return msg


def _candidate_bases(api_base: str) -> list:
    """用户已写 /v1 时只打这一条，避免落到网站前端 HTML。"""
    base = normalize_base(api_base)
    if not base:
        return []
    out = []

    def add(b):
        b = (b or "").rstrip("/")
        if b and b not in out:
            out.append(b)

    lower = base.lower()
    has_v1 = lower.endswith("/v1") or "/v1/" in lower
    if has_v1:
        add(base)
        return out
    add(base + "/v1")
    add(base + "/api/v1")
    add(base + "/openai/v1")
    return out


def _chat_url(api_base: str) -> str:
    base = _candidate_bases(api_base)[0] if _candidate_bases(api_base) else normalize_base(api_base)
    if base.lower().endswith("/chat/completions"):
        return base
    return base.rstrip("/") + "/chat/completions"


def _new_id() -> str:
    import uuid
    return uuid.uuid4().hex[:10]


def _public_profile(p: dict) -> dict:
    key = p.get("api_key") or ""
    return {
        "id": p.get("id") or "",
        "name": p.get("name") or "未命名",
        "provider": p.get("provider") or "custom",
        "api_base": p.get("api_base") or "",
        "model": p.get("model") or "",
        "api_key": key,  # 仅本机 127.0.0.1 页面回填，避免「导入后密钥消失」
        "api_key_masked": _mask(key),
        "has_api_key": bool(normalize_key(key)),
    }


def save_user_config(cfg: dict) -> dict:
    """按名称保存整套配置。

    - 名称已存在：只更新这一套
    - 名称不存在：新建一套（不会改其他档案）
    - overwrite=True 且带 id：才覆盖下拉框选中的那一套
    """
    store = load_store()
    profiles = store.get("profiles") or []
    name = (cfg.get("name") or "").strip()
    pid = (cfg.get("id") or "").strip()
    overwrite = bool(cfg.get("overwrite"))

    if cfg.get("clear_key") and not (cfg.get("api_base") or name or pid):
        _write_store({"active": "", "profiles": []})
        return public_status()

    target = None
    if overwrite and pid:
        target = next((p for p in profiles if p.get("id") == pid), None)
    if target is None and name:
        target = next((p for p in profiles if (p.get("name") or "") == name), None)
    if target is None:
        target = {"id": _new_id()}
        profiles.append(target)

    key = normalize_key(cfg.get("api_key") or "")
    if not key:
        key = normalize_key(target.get("api_key") or "")
    if cfg.get("clear_key"):
        key = ""
    provider = (cfg.get("provider") or target.get("provider") or "custom").strip() or "custom"
    preset = PRESETS.get(provider, {})
    base = normalize_base(cfg.get("api_base") or "") or normalize_base(target.get("api_base") or "") or preset.get("api_base", "")
    model = (cfg.get("model") or "").strip() or (target.get("model") or "").strip() or preset.get("model", "")

    target["provider"] = provider
    target["api_base"] = base
    target["api_key"] = key
    target["model"] = model
    if name:
        target["name"] = name
    elif not target.get("name"):
        target["name"] = f"{provider} / {model or '未选模型'}"

    store["profiles"] = profiles
    store["active"] = target["id"]
    _write_store(store)
    return public_status()


def activate_profile(profile_id: str) -> dict:
    store = load_store()
    if not any(p.get("id") == profile_id for p in store.get("profiles") or []):
        raise KeyError(f"配置 {profile_id} 不存在")
    store["active"] = profile_id
    _write_store(store)
    return public_status()


def delete_profile(profile_id: str) -> dict:
    store = load_store()
    profiles = [p for p in (store.get("profiles") or []) if p.get("id") != profile_id]
    active = store.get("active")
    if active == profile_id:
        active = profiles[0]["id"] if profiles else ""
    _write_store({"active": active, "profiles": profiles})
    return public_status()


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]


def active_endpoint() -> Optional[dict]:
    """当前真正用来发请求的地址/密钥（用户配置优先，不依赖供应商 id 匹配）。"""
    user = load_user_config()
    provider = (user.get("provider") or "custom").strip() or "custom"
    preset = PRESETS.get(provider, {})
    key = normalize_key(user.get("api_key") or "")
    if not key:
        env_name = preset.get("key_env")
        if env_name:
            key = normalize_key(os.environ.get(env_name) or "")
    if not key:
        for env_name in ("DEEPSEEK_API_KEY", "QWEN_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY"):
            key = normalize_key(os.environ.get(env_name) or "")
            if key:
                break
    base = normalize_base(user.get("api_base") or "") or preset.get("api_base", "")
    model = (user.get("model") or "").strip() or preset.get("model") or "deepseek-chat"
    if not key or not base:
        return None
    return {"provider": provider, "api_base": base, "api_key": key, "model": model}


def public_status() -> dict:
    """给本机前端的状态；含完整密钥以便回填输入框（仅 127.0.0.1）。"""
    cfg = load_user_config()
    ep = active_endpoint()
    key = normalize_key(cfg.get("api_key") or "")
    env_keys = {
        "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "qwen": bool(os.environ.get("QWEN_API_KEY")),
        "kimi": bool(os.environ.get("KIMI_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }
    store = load_store()
    return {
        "configured": bool(ep),
        "id": cfg.get("id") or "",
        "name": cfg.get("name") or "",
        "provider": (ep or {}).get("provider") or cfg.get("provider") or "",
        "api_base": (ep or {}).get("api_base") or cfg.get("api_base") or "",
        "model": (ep or {}).get("model") or cfg.get("model") or "",
        "api_key": key or ((ep or {}).get("api_key") or ""),
        "api_key_masked": _mask(key or ((ep or {}).get("api_key") or "")),
        "has_api_key": bool(key or (ep and ep.get("api_key"))),
        "env_keys": env_keys,
        "config_path": user_config_path(),
        "chat_url": _chat_url(ep["api_base"]) if ep else "",
        "active": store.get("active") or "",
        "profiles": [_public_profile(p) for p in store.get("profiles") or []],
        "note": "整套配置（地址/密钥/模型）保存在本机 llm_config.json，可多套切换。",
    }


def _load_providers(path=None):
    if path is None:
        path = _builtin_providers_path()
    with open(path, encoding="utf-8") as f:
        providers = json.load(f)["providers"]
    user = load_user_config()
    if user.get("api_key") or user.get("api_base"):
        custom = {
            "id": user.get("provider") or "custom",
            "api_base": user.get("api_base") or "",
            "model": user.get("model") or "deepseek-chat",
            "key_env": None,
            "api_key": user.get("api_key") or "",
            "priority": 0,
            "capable_tasks": ["chat", "reasoning", "analysis"],
        }
        # 若用户选了内置供应商，覆盖其 api_base/model/key
        replaced = False
        out = []
        for p in providers:
            if p["id"] == custom["id"]:
                merged = dict(p)
                if custom["api_base"]:
                    merged["api_base"] = custom["api_base"]
                if custom["model"]:
                    merged["model"] = custom["model"]
                if custom["api_key"]:
                    merged["api_key"] = custom["api_key"]
                merged["priority"] = 0
                out.append(merged)
                replaced = True
            else:
                out.append(p)
        if not replaced:
            out.insert(0, custom)
        return out
    return providers


def _get_key(provider_cfg) -> Optional[str]:
    """优先用户配置文件，其次环境变量。"""
    if provider_cfg.get("api_key"):
        return provider_cfg["api_key"]
    user = load_user_config()
    if user.get("api_key") and (
        not user.get("provider") or user.get("provider") in (provider_cfg.get("id"), "custom")
    ):
        return user["api_key"]
    env = provider_cfg.get("key_env")
    if env:
        return os.environ.get(env)
    return None


def _client_for(provider_cfg):
    """按可用库构造客户端。返回 (client, kind)。kind ∈ {'openai','httpx','urllib'}"""
    if openai is not None:
        return openai, "openai"
    if httpx is not None:
        return httpx, "httpx"
    return None, "urllib"


def _extract_content(data) -> str:
    if not isinstance(data, dict):
        raise GatewayError(f"接口返回非 JSON 对象：{str(data)[:200]}")
    if data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            raise GatewayError(err.get("message") or str(err))
        raise GatewayError(str(err))
    choices = data.get("choices") or []
    if not choices:
        raise GatewayError(f"接口未返回 choices：{str(data)[:300]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if content is None:
        raise GatewayError(f"接口未返回 content：{str(data)[:300]}")
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _urllib_call(req: ChatRequest):
    import time
    payload = {
        "model": req.model,
        "messages": req.messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    last = None
    tried = []
    for base in _candidate_bases(req.api_base):
        url = base.rstrip("/") + "/chat/completions"
        tried.append(url)
        # 对临时上游不可用（502/503/504/temporarily unavailable/overloaded）自动重试 3 次
        for attempt in range(3):
            try:
                data = _http_json("POST", url, req.api_key, payload, timeout=60)
                return _extract_content(data)
            except GatewayError as e:
                last = e
                msg = str(e).lower()
                is_transient = (
                    "temporarily unavailable" in msg
                    or "502" in msg
                    or "503" in msg
                    or "504" in msg
                    or "overloaded" in msg
                    or "busy" in msg
                    or "timed out" in msg
                    or "gateway timeout" in msg
                    or "bad gateway" in msg
                )
                if is_transient and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                # 已经打到真 API（限流直接报出，不盲目切换路径）
                if "限流" in str(e) or "rate_limit" in msg:
                    raise
                if is_transient:
                    raise GatewayError(f"上游模型服务集群瞬时繁忙（{e}）。系统已自动重试 3 次，请稍后点击「重新解读」发起复试。")
                if "@ http" in msg:
                    raise
                break
    raise GatewayError((str(last) if last else "调用失败") + "；已尝试：" + " 、 ".join(tried))


def _http_call(client, req: ChatRequest):
    """httpx 路径：OpenAI 兼容 /chat/completions。"""
    url = _chat_url(req.api_base)
    payload = {
        "model": req.model,
        "messages": req.messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    headers = {"Authorization": f"Bearer {req.api_key}", "Content-Type": "application/json"}
    resp = client.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code >= 400:
        raise GatewayError(f"HTTP {resp.status_code}：{(resp.text or '')[:400]}")
    return _extract_content(resp.json())


def _openai_call(client, req: ChatRequest):
    """openai 库路径（OpenAI 兼容 api_base）。"""
    c = client.OpenAI(api_key=req.api_key, base_url=normalize_base(req.api_base))
    data = c.chat.completions.create(
        model=req.model,
        messages=req.messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    return data.choices[0].message.content


def call(req: ChatRequest) -> str:
    """调用单个供应商。缺 key / 网络错误抛 GatewayError（含 provider）。"""
    ep = active_endpoint()
    if ep and (not req.api_key or not req.api_base):
        req.provider = req.provider or ep["provider"]
        req.api_key = normalize_key(req.api_key or ep["api_key"])
        req.api_base = normalize_base(req.api_base or ep["api_base"])
        req.model = req.model or ep["model"]
    else:
        providers = {p["id"]: p for p in _load_providers()}
        cfg = providers.get(req.provider) if req.provider else None
        if cfg:
            req.api_key = normalize_key(req.api_key or _get_key(cfg) or "")
            req.api_base = normalize_base(req.api_base or cfg.get("api_base") or "")
            req.model = req.model or cfg.get("model")
        else:
            req.api_key = normalize_key(req.api_key or "")
            req.api_base = normalize_base(req.api_base or "")
    if not req.api_key:
        raise GatewayError("缺少 API Key：请在「模型密钥」页填写官方或中转站密钥", provider=req.provider)
    if not req.api_base:
        raise GatewayError("缺少 API 地址：请填写官方或中转站地址（例如 https://api.deepseek.com/v1）", provider=req.provider)
    req.model = req.model or "deepseek-chat"
    try:
        # 中转站对 openai SDK 的 base_url 更挑剔，默认走 urllib，兼容性最好
        return _urllib_call(req)
    except GatewayError:
        raise
    except Exception as e:
        raise GatewayError(f"调用失败: {e}", provider=req.provider, cause=e)


def route(task: str = "chat", fallback: bool = True) -> Optional[dict]:
    """按任务选主供应商。用户 llm_config.json 优先于内置列表。"""
    ep = active_endpoint()
    if ep:
        return {"provider": ep["provider"], "model": ep["model"]}
    providers = sorted(_load_providers(), key=lambda p: p.get("priority", 99))
    for p in providers:
        if task in p.get("capable_tasks", []) and _get_key(p):
            return {"provider": p["id"], "model": p["model"]}
    if not fallback:
        return None
    for p in providers:
        if task in p.get("capable_tasks", []):
            return {"provider": p["id"], "model": p["model"]}
    return None


def cross_check(prompt: str, n: int = 2) -> dict:
    """双模型交叉校验：取前 n 个 capable 供应商各自独立作答。

    返回 {responses: [{provider, text}], agreed: bool}。
    高利害评估题默认开启（M07 调用）。无可用模型返回 responses=[]。
    """
    providers = sorted(_load_providers(), key=lambda p: p.get("priority", 99))
    picked = [p for p in providers if "chat" in p.get("capable_tasks", [])][:n]
    responses = []
    for p in picked:
        try:
            text = call(ChatRequest(provider=p["id"], task="chat", messages=[
                {"role": "user", "content": prompt},
            ]))
            responses.append({"provider": p["id"], "text": text})
        except GatewayError:
            continue
    agreed = len(responses) >= 2 and responses[0]["text"].strip() == responses[1]["text"].strip()
    return {"responses": responses, "agreed": agreed}


def interpret_report(markdown: str, question: str) -> dict:
    """用已配置模型解读评估或事实报告。数字仍以引擎为准，模型只写说明。"""
    routed = route("chat")
    if not routed:
        raise GatewayUnavailable("未配置模型：请在「接口配置」填写官方或中转站 API 地址与密钥")

    if "学校指标事实查询" in markdown:
        prompt = (
            "你是教育数字化评估与问答助手。下面是规则引擎从官方作答库查出的学校具体指标事实（数字真实确凿，不得篡改）。\n"
            "请用中文直接、自然、专业地回答用户提问：\n"
            "1）第一句话直接准确给出该校该指标的具体配置数量/数值；\n"
            "2）结合报告中的关联设备配置与师生规模做客观简评（如师均配比、充裕程度）；\n"
            "3）提及历史对比（若有历史数据）。严禁捏造报告中没有的数字。\n"
            f"用户提问：{question}\n\n事实数据报告：\n{markdown[:6000]}"
        )
    elif "区域数字化宏观评估报告" in markdown:
        prompt = (
            "你是区域教育数字化监测与决策咨询专家。下面是规则引擎根据区域全量中小学真实作答统计生成的区域大盘数据（数字已由系统计算，不得篡改）。\n"
            "请用中文进行宏观诊断解读：\n"
            "1）评述该区域整体数字化发展水平与学校分层结构（优良中差梯队）；\n"
            "2）重点剖析该区域的突出优势维度与核心制约短板；\n"
            "3）结合标杆学校经验，为教育局/管理者提出针对性的区域数字化推进建议。不要编造数字。\n"
            f"用户提问：{question}\n\n区域大盘数据：\n{markdown[:6000]}"
        )
    elif "学校区域数字化排位与对比" in markdown:
        prompt = (
            "你是教育视导与学校发展咨询专家。下面是规则引擎根据真实作答库计算出的学校在所属区域的排位对比报告（数字真实确凿，不得篡改）。\n"
            "请用中文直接、客观测度并回答用户提问：\n"
            "1）第一句话明确告知该校在全区的综合排位、超越比例及综合得分；\n"
            "2）详细评述该校相对于全区均值的领先优势维度与相对滞后短板；\n"
            "3）为该校校长和教研团队提出切实可行的针对性改进建议。严禁捏造报告中没有的数字。\n"
            f"用户提问：{question}\n\n排位对比数据：\n{markdown[:6000]}"
        )
    else:
        prompt = (
            "你是教育评估助手。下面是规则引擎算出的评估报告（数字已由系统计算，不得改数）。\n"
            "请用中文简要解读：1）总分与覆盖率含义；2）最弱维度及可能原因；"
            "3）给评审委员会的复核要点。不要编造报告中没有的数字。\n"
            f"用户问题：{question}\n\n报告：\n{markdown[:6000]}"
        )

    text = call(ChatRequest(
        provider=routed["provider"],
        model=routed.get("model"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800,
    ))
    return {"provider": routed["provider"], "model": routed.get("model"), "text": text}


def _model_id(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("id") or item.get("name") or item.get("model") or "").strip()
    return ""


def list_models(api_base: str = "", api_key: str = "") -> dict:
    """用地址+密钥拉取 OpenAI 兼容 /models 列表。"""
    ep = active_endpoint() or {}
    base = normalize_base(api_base) or ep.get("api_base") or ""
    key = normalize_key(api_key) or ep.get("api_key") or ""
    if not base or not key:
        return {"ok": False, "models": [], "error": "请先填写 API 地址和密钥（可先保存，或在拉取时一并提交）。"}
    last = None
    data = None
    url = ""
    tried = []
    for b in _candidate_bases(base):
        url = b.rstrip("/") + "/models"
        tried.append(url)
        try:
            data = _http_json("GET", url, key, timeout=30)
            break
        except GatewayError as e:
            last = e
            data = None
    if data is None:
        return {"ok": False, "models": [], "error": str(last) if last else "识别失败",
                "url": url, "tried": tried, "api_base": base, "api_key_masked": _mask(key)}
    raw = []
    if isinstance(data, dict):
        raw = data.get("data") or data.get("models") or data.get("result") or []
    elif isinstance(data, list):
        raw = data
    ids = []
    seen = set()
    for item in raw:
        mid = _model_id(item)
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
    ids.sort()
    current = (ep.get("model") or "").strip()
    return {
        "ok": True,
        "models": ids,
        "count": len(ids),
        "current": current if current in ids else (ids[0] if ids else current),
        "url": url,
        "api_base": base,
        "api_key_masked": _mask(key),
    }


def ping() -> dict:
    """探测当前配置能否打通官方/中转站。"""
    ep = active_endpoint()
    if not ep:
        st = public_status()
        return {"ok": False, "error": "未识别到密钥。请同时填写 API 地址和 API Key 后点「保存密钥」。",
                "config_path": st.get("config_path")}
    try:
        text = call(ChatRequest(
            provider=ep["provider"],
            model=ep["model"],
            api_base=ep["api_base"],
            api_key=ep["api_key"],
            messages=[{"role": "user", "content": "只回复：ok"}],
            temperature=0,
            max_tokens=8,
        ))
        return {"ok": True, "provider": ep["provider"], "model": ep["model"],
                "api_base": ep["api_base"], "chat_url": _chat_url(ep["api_base"]),
                "tried": [b.rstrip("/") + "/chat/completions" for b in _candidate_bases(ep["api_base"])],
                "api_key_masked": _mask(ep["api_key"]),
                "reply": (text or "")[:80]}
    except GatewayError as e:
        return {"ok": False, "provider": ep["provider"], "model": ep["model"],
                "api_base": ep["api_base"], "chat_url": _chat_url(ep["api_base"]),
                "tried": [b.rstrip("/") + "/chat/completions" for b in _candidate_bases(ep["api_base"])],
                "api_key_masked": _mask(ep["api_key"]),
                "error": str(e)}


if __name__ == "__main__":
    print("可用模型路由（chat 任务）：", route("chat"))