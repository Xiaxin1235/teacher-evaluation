"""M09 · REST API（FastAPI，可降级）。

FastAPI 未安装时降级为 BaseApp（仅提供 serve() 提示 + 核心逻辑可直接 import）；
安装 fastapi+uvicorn 后提供完整端点（对齐《系统设计文档-v0.1.md》§6 API 草案）：

  POST /api/v1/chat              对话式评估入口（宽泛问题 → 结构报告+证据）
  POST /api/v1/evaluations       发起批量评估（同步；队列化留待后续）
  GET  /api/v1/evaluations/{id}  取单份结果
  GET  /api/v1/teachers/{id}/reports   教师历次报告
  GET  /api/v1/teachers/{id}/trends    多周期趋势（雷达数据，供 M10 用）
  GET  /api/v1/templates         模板列表（评估框架即配置的读接口）
  GET  /api/v1/teachers          演示教师列表
  GET  /api/v1/teachers/{id}/profile  教师简介（档案+数据覆盖）
  GET  /api/v1/schools           按校名检索
  GET  /api/v1/schools/{id}/profile   学校简介（档案+作答覆盖）
  GET  /api/v1/llm/status            模型密钥配置状态（不回完整 key）
  POST /api/v1/llm/config            保存官方/中转 API 地址与密钥
  POST /api/v1/llm/ping              探测模型接口是否通

只读原则：本模块不写任何业务库，结果驻留内存（持久化交给 M05/M11 之后）。
权限为占位（get_current_user 桩 + TODO），完整授权在 M11。
"""

import csv
import os
import sys
import uuid
from typing import List, Optional

_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from packages.core.frozen_paths import resource_root  # noqa: E402
from scripts.indicator_engine import evaluate_teacher, load_yaml  # noqa: E402
from packages.agent.planner import parse_question, plan  # noqa: E402
from packages.agent.critic import review as critic_review  # noqa: E402
from packages.agent.composer import compose, render_markdown  # noqa: E402
from packages.indicator_engine.calibration import attach_calibration  # noqa: E402
from packages.agent.router import route_query  # noqa: E402

ROOT = resource_root()

_MEMORY: dict = {}          # result_id -> 结果
_TEACHERS: List[str] = []
_TEMPLATE_CACHE = {}


def _load_teachers():
    global _TEACHERS
    if not _TEACHERS:
        p = os.path.join(ROOT, "data", "demo", "teacher.csv")
        try:
            with open(p, newline="", encoding="utf-8") as f:
                _TEACHERS = [r["teacher_id"] for r in csv.DictReader(f)]
        except Exception:
            _TEACHERS = []
    return _TEACHERS


def _load_tpl():
    if "tpl" not in _TEMPLATE_CACHE:
        _TEMPLATE_CACHE["tpl"] = load_yaml("2025-2026_v1")
    return _TEMPLATE_CACHE["tpl"]


def _run_evaluation(teacher_id: str, years: List[str]):
    tpl = _load_tpl()
    if tpl is None:
        raise ValueError("评估模板不可用（PyYAML 未安装或模板文件缺失）")
    res = evaluate_teacher(teacher_id, years, tpl)
    if "error" in res:
        raise ValueError(res["error"])
    attach_calibration(res, group_col="dept_id")
    result_id = str(uuid.uuid4())
    _MEMORY[result_id] = {"_id": result_id, **res}
    return _MEMORY[result_id]


def _finish(result: dict) -> dict:
    report = compose(result)
    evidence = []
    for d in result.get("dimensions", []):
        evidence.extend(d.get("evidence", []))
    c = critic_review(result, evidence, with_llm=False)

    # 模块化 Agent 工具调用编排：自动调用本地 Python 工具画图
    tool_calls = []
    charts = []
    try:
        from packages.agent.tools import orchestrator
        orch_res = orchestrator.orchestrate_visualization(result)
        tool_calls = orch_res.get("tool_calls", [])
        charts = orch_res.get("charts", [])
        report["tool_calls"] = tool_calls
        report["charts"] = charts
    except Exception as e:
        tool_calls = [{"tool": "orchestrator", "success": False, "error": str(e)}]

    return {
        "clarify": False,
        "result_id": result["_id"],
        "result": result,
        "report": report,
        "critic": c,
        "markdown": render_markdown(result),
        "tool_calls": tool_calls,
        "charts": charts,
    }


def _run_school_evaluation(keyword: str, years: List[str]) -> dict:
    from scripts.school_engine import find_schools, evaluate_school, get_school
    year = years[0] if years else None
    sid = None
    if keyword.startswith("id:"):
        sid = int(keyword.split(":", 1)[1])
        school = get_school(sid)
        if not school:
            raise ValueError(f"学校 id={sid} 不存在")
    else:
        hits = find_schools(keyword, year=year, limit=8)
        if not hits:
            raise ValueError(f"未找到学校「{keyword}」" + (f"（年份 {year}）" if year else ""))
        if len(hits) > 1 and not year:
            names = [f"{h['school_name']}（{h['year']}，id={h['id']}）" for h in hits[:6]]
            raise ValueError("匹配到多条学校记录，请补充年份或学校 id：" + "；".join(names))
        sid = hits[0]["id"]
    res = evaluate_school(sid)
    if "error" in res:
        raise ValueError(res["error"])
    result_id = str(uuid.uuid4())
    _MEMORY[result_id] = {"_id": result_id, **res}
    return _MEMORY[result_id]


def _run_school_fact(school_keyword: str, metric_info: dict, year: Optional[str] = None) -> dict:
    from scripts.fact_engine import query_school_fact
    res = query_school_fact(school_keyword, metric_info, year=year)
    if "error" in res:
        raise ValueError(res["error"])
    result_id = str(uuid.uuid4())
    packed = {"_id": result_id, **res}
    _MEMORY[result_id] = packed
    return packed


_SESSIONS: dict = {}


def _run_region_evaluation(region_keyword: str, year: Optional[str] = None) -> dict:
    from scripts.region_engine import evaluate_region
    res = evaluate_region(region_keyword, year=year)
    if "error" in res:
        raise ValueError(res["error"])
    result_id = str(uuid.uuid4())
    packed = {"_id": result_id, **res}
    _MEMORY[result_id] = packed
    return packed


def _run_school_ranking(school_keyword: str, region_keyword: Optional[str] = None, year: Optional[str] = None) -> dict:
    from scripts.region_engine import query_school_ranking
    res = query_school_ranking(school_keyword, region_keyword=region_keyword, year=year)
    if "error" in res:
        raise ValueError(res["error"])
    result_id = str(uuid.uuid4())
    packed = {"_id": result_id, **res}
    _MEMORY[result_id] = packed
    return packed


def chat(question: str, session_id: Optional[str] = "default") -> dict:
    """开放式多意图对话评估入口（支持多轮上下文与实体继承）：
    自由提问 → 上下文消解与路由 → 教师评估 / 学校评估 / 事实指标问答 / 区域大盘 / 相对排位。

    返回 dict：
      {clarify: true, question, next_prompt, session_id}          需澄清引导
      {result_id, result, report, critic, markdown, session_id}   完成
    """
    sid = session_id or "default"
    ctx = _SESSIONS.setdefault(sid, {})

    routed = route_query(question, context=ctx)
    intent = routed.get("intent")

    if intent == "clarify":
        missing_prompts = routed.get("missing", ["请提供更具体的评估对象（教师、学校或行政区划）"])
        return {
            "clarify": True,
            "question": routed,
            "next_prompt": "；".join(missing_prompts),
            "session_id": sid,
        }

    try:
        if intent == "school_fact":
            result = _run_school_fact(
                routed["school"],
                routed["metric"],
                year=routed.get("year"),
            )
        elif intent == "school_ranking":
            result = _run_school_ranking(
                routed["school"],
                region_keyword=routed.get("region"),
                year=routed.get("year"),
            )
        elif intent == "region_eval":
            result = _run_region_evaluation(
                routed["region"],
                year=routed.get("year"),
            )
        elif intent == "school_eval":
            result = _run_school_evaluation(
                routed["school"],
                routed.get("years", []),
            )
        else:
            # 默认：教师综合评估
            teacher_id = routed.get("teacher_id")
            if not teacher_id:
                # 兼容旧式 planner 解析兜底
                q = parse_question(question)
                if q.clarify_needed:
                    return {
                        "clarify": True,
                        "question": q.__dict__,
                        "next_prompt": f"请补充：{', '.join(q.missing)}",
                        "session_id": sid,
                    }
                teacher_id = q.objects[0]
                years = q.years or ["2023-2024", "2024-2025"]
            else:
                years = routed.get("years") or ["2023-2024", "2024-2025"]
            result = _run_evaluation(teacher_id, years)

    except ValueError as e:
        return {"clarify": True, "question": routed, "next_prompt": str(e), "session_id": sid}

    # 记忆上下文更新
    if result.get("school_name"):
        ctx["last_school"] = result["school_name"]
    if result.get("short_name") or result.get("region_name"):
        ctx["last_region"] = result.get("short_name") or result.get("region_name")
    if result.get("year"):
        ctx["last_year"] = result["year"]
    elif result.get("school_years"):
        ctx["last_year"] = result["school_years"][0]
    if result.get("teacher_id"):
        ctx["last_teacher"] = result["teacher_id"]

    out = _finish(result)
    out["session_id"] = sid
    try:
        from packages.llm_gateway.gateway import interpret_report, public_status
        if public_status().get("configured"):
            out["llm"] = interpret_report(out.get("markdown") or "", question)
    except Exception as e:
        out["llm"] = {"error": str(e)}
    return out


def batch_evaluate(teacher_ids: List[str], years: List[str]) -> dict:
    """批量评估（同步）。返回 {results: [{teacher_id, result_id, total_score, error?}]}。"""
    out = []
    for tid in teacher_ids:
        try:
            r = _run_evaluation(tid, years)
            out.append({"teacher_id": tid, "result_id": r["_id"],
                        "total_score": r.get("total_score")})
        except ValueError as e:
            out.append({"teacher_id": tid, "error": str(e)})
    return {"results": out}


def get_result(result_id: str) -> dict:
    if result_id not in _MEMORY:
        raise KeyError(f"result_id {result_id} 不存在")
    return _MEMORY[result_id]


def teacher_reports(teacher_id: str) -> dict:
    """该教师历次结果（原型：内存中该教师的结果按时间逆序）。"""
    rows = [v for v in _MEMORY.values() if v.get("teacher_id") == teacher_id]
    rows.sort(key=lambda v: v.get("school_years", []), reverse=True)
    return {"teacher_id": teacher_id, "reports": rows}


def teacher_trends(teacher_id: str, years: List[str]) -> dict:
    """多周期趋势（雷达数据，供 M10 用）。原型：近年结果聚合。"""
    rows = [v for v in _MEMORY.values() if v.get("teacher_id") == teacher_id]
    # 按学年维度聚合平均得分（原型简化为取最近一条；多条时做平均）
    per_year = {}
    for v in rows:
        for y in v.get("school_years", []):
            per_year.setdefault(y, []).append(v.get("total_score", 0))
    trend = {y: round(sum(s) / len(s), 2) for y, s in per_year.items() if s}
    return {"teacher_id": teacher_id, "trend": trend,
            "radar_last": _radar(rows[-1] if rows else None)}


def _radar(result) -> dict:
    if not result:
        return {}
    dims = {}
    for d in result.get("dimensions", []):
        if not d.get("is_redline") and d.get("score") is not None:
            dims[d["dimension"]] = d["score"]
    return dims


def templates() -> dict:
    tpl = _load_tpl()
    return {"templates": [{"name": (tpl.get("template") or {}).get("name"),
                           "school_year": (tpl.get("template") or {}).get("school_year")}]}


def _read_csv(name: str):
    p = os.path.join(ROOT, "data", "demo", name)
    if not os.path.isfile(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


TEACHER_NAME_MAP = {
    "T001": "张老师",
    "T002": "李老师",
    "T003": "王老师",
    "T004": "赵老师",
}

TEACHER_TITLE_MAP = {
    "高级": "高级教师 (正高级/高级职称)",
    "中级": "一级教师 (中级职称)",
    "初级": "二级/初级教师",
}


def list_teachers() -> dict:
    teachers = []
    for r in _read_csv("teacher.csv"):
        t = dict(r)
        tid = t.get("teacher_id", "")
        t["name"] = TEACHER_NAME_MAP.get(tid, "示例教师")
        t["title_desc"] = TEACHER_TITLE_MAP.get(t.get("title", ""), t.get("title", ""))
        teachers.append(t)
    return {"teachers": teachers}


def teacher_profile(teacher_id: str) -> dict:
    """演示库教师简介：档案 + 各源数据条数（便于查询，不含评分）。"""
    row = next((r for r in _read_csv("teacher.csv") if r.get("teacher_id") == teacher_id), None)
    if not row:
        raise KeyError(f"教师 {teacher_id} 不存在")

    def _count(name):
        return [r for r in _read_csv(name) if r.get("teacher_id") == teacher_id]

    courses = _count("course_period.csv")
    years = sorted({r.get("school_year") for r in courses if r.get("school_year")})
    title = row.get("title", "")
    return {
        "object_type": "teacher",
        "teacher_id": teacher_id,
        "name": TEACHER_NAME_MAP.get(teacher_id, "示例教师"),
        "name_hash": row.get("name_hash"),
        "dept_id": row.get("dept_id"),
        "title": title,
        "title_desc": TEACHER_TITLE_MAP.get(title, title),
        "hire_year": row.get("hire_year"),
        "is_active": row.get("is_active"),
        "years": years,
        "coverage": {
            "course_period": len(courses),
            "lesson_plan": len(_count("lesson_plan.csv")),
            "class_observation": len(_count("class_observation.csv")),
            "exam_score": len(_count("exam_score.csv")),
            "research_record": len(_count("research_record.csv")),
            "student_survey": len(_count("student_survey.csv")),
            "complaint_record": len(_count("complaint_record.csv")),
            "discipline_record": len(_count("discipline_record.csv")),
        },
        "note": "演示数据为脱敏虚构档案；真实学校数字化数据请走学校简介。",
    }


def _llm_public() -> dict:
    try:
        from packages.llm_gateway.gateway import public_status
        return public_status()
    except Exception as e:
        return {"configured": False, "error": str(e)}


def school_profile(school_id: int) -> dict:
    from scripts.school_engine import connect, get_school
    school = get_school(school_id)
    if not school:
        raise KeyError(f"学校 {school_id} 不存在")
    conn = connect()
    n_ans = conn.execute(
        "SELECT COUNT(*) AS n FROM answers WHERE school_id=?", (int(school_id),)
    ).fetchone()["n"]
    n_q = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
    years = [r["year"] for r in conn.execute(
        "SELECT year FROM schools WHERE school_name=? ORDER BY year",
        (school.get("school_name"),)).fetchall()]
    conn.close()
    return {
        "object_type": "school",
        **school,
        "answered": n_ans,
        "total_questions": n_q,
        "same_name_years": years,
        "note": "真实数字化问卷档案；评分请走学校评估报告。",
    }


# ---------------------------------------------------------------- FastAPI 层
try:
    from fastapi import FastAPI, HTTPException, Query  # noqa: F401
    from pydantic import BaseModel, Field  # noqa: F401

    class ChatIn(BaseModel):
        question: str = Field(..., min_length=2, description="宽泛评估问题")
        session_id: Optional[str] = Field(default="default", description="多轮上下文会话ID")

    class BatchIn(BaseModel):
        teacher_ids: List[str]
        years: List[str] = Field(default_factory=lambda: ["2023-2024", "2024-2025"])

    class TrendIn(BaseModel):
        years: List[str] = Field(default_factory=lambda: ["2023-2024", "2024-2025"])

    class LlmConfigIn(BaseModel):
        provider: str = Field(default="custom", description="deepseek/qwen/kimi/openai/custom")
        api_base: str = Field(default="", description="官方或中转站 OpenAI 兼容地址")
        api_key: str = Field(default="", description="API Key；留空表示不改已有密钥")
        model: str = Field(default="", description="模型名，如 deepseek-chat")
        name: str = Field(default="", description="配置名称，保存整套档案用")
        id: str = Field(default="", description="已有档案 id；仅 overwrite=true 时用来覆盖选中项")
        overwrite: bool = False
        clear_key: bool = False

    class LlmProfileIn(BaseModel):
        id: str

    class LlmDiscoverIn(BaseModel):
        api_base: str = ""
        api_key: str = ""
        save: bool = False
        provider: str = "custom"

    app = FastAPI(title="教师评估 AI 平台 API", version="0.1",
                  description="只读评估服务；结果驻留内存（原型）")
    try:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except Exception:
        pass

    # 权限：接 M11 authz（原型鉴权仍宽松——默认 admin；真实鉴权由部署方对接 SSO 后在
    # get_current_user 中注入用户对象，并用 can_view/can_view_redline 做数据范围闸门）。
    def get_current_user():
        user = {"user_id": "prototype", "role": "admin", "scope": None,
                "note": "M11 后请由部署方注入真实用户对象"}
        return user

    def _require_view(user, teacher_id):
        from packages.core.authz import can_view
        if not can_view(user.get("role", "admin"), teacher_id, user.get("scope")):
            raise HTTPException(status_code=403, detail="无权查看该教师数据")

    @app.get("/health")
    def health():
        real_db = os.path.join(ROOT, "data", "real", "education_digitization.sqlite")
        db_stats = {}
        if os.path.isfile(real_db):
            try:
                from scripts.school_engine import connect
                conn = connect()
                s_count = conn.execute("SELECT count(*) FROM schools").fetchone()[0]
                q_count = conn.execute("SELECT count(*) FROM questions").fetchone()[0]
                a_count = conn.execute("SELECT count(*) FROM answers").fetchone()[0]
                conn.close()
                db_stats = {
                    "schools_count": s_count,
                    "questions_count": q_count,
                    "answers_count": a_count,
                    "ready": True
                }
            except Exception as e:
                db_stats = {"error": str(e), "ready": False}
        return {
            "status": "ok",
            "teachers": _load_teachers(),
            "real_db": os.path.isfile(real_db),
            "db_stats": db_stats,
            "llm": _llm_public(),
            "endpoints": [
                "GET /health",
                "POST /api/v1/chat",
                "GET /api/v1/teachers",
                "GET /api/v1/teachers/{id}/profile",
                "GET /api/v1/teachers/{id}/trends",
                "GET /api/v1/schools?q=&year=",
                "GET /api/v1/schools/{id}/profile",
                "GET /api/v1/schools/{id}/report",
                "GET /api/v1/llm/status",
                "POST /api/v1/llm/config",
                "POST /api/v1/llm/ping",
            ],
        }

    @app.post("/api/v1/chat")
    def api_chat(body: ChatIn):
        try:
            return chat(body.question, session_id=body.session_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/evaluations")
    def api_batch(body: BatchIn):
        return batch_evaluate(body.teacher_ids, body.years)

    @app.get("/api/v1/evaluations/{result_id}")
    def api_result(result_id: str):
        try:
            return get_result(result_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="result 不存在")

    @app.get("/api/v1/teachers")
    def api_teachers():
        return list_teachers()

    @app.get("/api/v1/teachers/{teacher_id}/profile")
    def api_teacher_profile(teacher_id: str):
        try:
            return teacher_profile(teacher_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/api/v1/teachers/{teacher_id}/reports")
    def api_reports(teacher_id: str):
        return teacher_reports(teacher_id)

    @app.get("/api/v1/teachers/{teacher_id}/trends")
    def api_trends(teacher_id: str):
        return teacher_trends(teacher_id, ["2023-2024", "2024-2025"])

    @app.get("/api/v1/templates")
    def api_templates():
        return templates()

    @app.get("/api/v1/schools")
    def api_schools(q: str = Query(..., min_length=1), year: Optional[str] = None, limit: int = 20):
        from scripts.school_engine import find_schools
        return {"schools": find_schools(q, year=year, limit=min(limit, 50))}

    @app.get("/api/v1/schools/{school_id}/profile")
    def api_school_profile(school_id: int):
        try:
            return school_profile(school_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/api/v1/schools/{school_id}/report")
    def api_school_report(school_id: int):
        from scripts.school_engine import evaluate_school
        res = evaluate_school(school_id)
        if "error" in res:
            raise HTTPException(status_code=404, detail=res["error"])
        result_id = str(uuid.uuid4())
        packed = {"_id": result_id, **res}
        _MEMORY[result_id] = packed
        return _finish(packed)

    @app.get("/api/v1/llm/status")
    def api_llm_status():
        return _llm_public()

    @app.post("/api/v1/llm/config")
    def api_llm_config(body: LlmConfigIn):
        from packages.llm_gateway.gateway import save_user_config
        return save_user_config(body.model_dump())

    @app.post("/api/v1/llm/ping")
    def api_llm_ping():
        from packages.llm_gateway.gateway import ping
        return ping()

    @app.post("/api/v1/llm/models")
    def api_llm_models(body: LlmDiscoverIn):
        from packages.llm_gateway.gateway import list_models, save_user_config
        if body.save and (body.api_key or body.api_base):
            save_user_config({
                "provider": body.provider or "custom",
                "api_base": body.api_base,
                "api_key": body.api_key,
            })
        return list_models(api_base=body.api_base, api_key=body.api_key)

    @app.get("/api/v1/llm/models")
    def api_llm_models_saved():
        from packages.llm_gateway.gateway import list_models
        return list_models()

    @app.post("/api/v1/llm/profiles/activate")
    def api_llm_activate(body: LlmProfileIn):
        from packages.llm_gateway.gateway import activate_profile
        try:
            return activate_profile(body.id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/v1/llm/profiles/delete")
    def api_llm_delete(body: LlmProfileIn):
        from packages.llm_gateway.gateway import delete_profile
        return delete_profile(body.id)

    @app.get("/api/v1/charts/{filename}")
    def api_chart_image(filename: str):
        from fastapi.responses import FileResponse
        safe_fn = os.path.basename(filename)
        from packages.core.frozen_paths import app_dir
        chart_path = os.path.join(app_dir(), "output", "charts", safe_fn)
        if not os.path.isfile(chart_path):
            raise HTTPException(status_code=404, detail="图表文件未找到或已清理")
        return FileResponse(chart_path, media_type="image/png")

    @app.get("/api/v1/tools")
    def api_tools():
        from packages.agent.tools import default_registry
        return {"tools": default_registry.get_schemas()}

    @app.post("/api/v1/llm/interpret")
    def api_llm_interpret(body: dict):
        from packages.llm_gateway.gateway import interpret_report
        markdown = body.get("markdown", "")
        question = body.get("question", "")
        try:
            return interpret_report(markdown, question)
        except Exception as e:
            return {"error": str(e)}


    FASTAPI_AVAILABLE = True

except ImportError:
    # fastapi 未安装：降级。BaseApp.serve() 提示安装；核心逻辑（chat/batch/...）仍可直接调用。
    FASTAPI_AVAILABLE = False

    class BaseApp:
        """fastapi 未安装时的降级壳。"""

        def serve(self):
            print("[M09] fastapi 未安装，无法启动 HTTP 服务。")
            print("     安装：pip install -r apps/api/requirements.txt")
            print("     启动：uvicorn apps.api.main:app --reload")

        def health(self):
            return {"status": "ok (degrated, no fastapi)",
                    "teachers": _load_teachers(),
                    "install": "pip install -r apps/api/requirements.txt"}

    app = BaseApp()


if __name__ == "__main__":
    # 命令行冒烟：走核心逻辑（不需要 fastapi）
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("fastapi:", "available" if FASTAPI_AVAILABLE else "not installed (degraded)")
    r = chat("T001 2024-2025 教学水平？")
    print("chat clarify:", r.get("clarify"), "| result_id:", r.get("result_id"))
    print("batch:", batch_evaluate(["T001", "T003"], ["2023-2024"])["results"])
    print("trends:", teacher_trends("T001", ["2023-2024"])["trend"])