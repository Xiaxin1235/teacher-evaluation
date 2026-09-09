# M06 · 模型网关

> 状态：`todo`　依赖：M00　验收：`import packages.llm_gateway.gateway` 无报错

## 目标
统一多厂商模型接入（"pi agent"式能力）：一个 OpenAI 兼容适配层，屏蔽各家 API 差异；支持多供应商配置、按任务路由、降级容错。**本模块只要求可导入、结构正确，不要求真实 API key 可用**（真实联调由后续模块/运行环境配置 providers.json 完成）。

## 任务清单
1. 新建 `packages/llm_gateway/` 包（含 `__init__.py`）。
2. `providers.json`：示例多供应商配置（provider id、`api_base`、`model`、`key_env` 环境变量名、`priority`、`capable_tasks`）。**密钥只允许来自环境变量，绝不允许硬编码进 JSON**。
3. `gateway.py`：
   - `ChatRequest`（Dataclass）：provider/task/model/llm args；`call()` 发起请求（OpenAI 兼容客户端，可用 `httpx` 或 `openai` 库，**安装即为可选**——未装时调用应报清晰的提示而非烂堆栈）。
   - `route(task, fallback=True)`：按 `capable_tasks` + `priority` 选主供应商；主供应商失败/超时自动切换备份。
   - 统一 `GatewayError` 异常，带 `provider`、`cause` 字段。
   - 双模型校验钩子：`cross_check(prompt, n=2)` 返回 `{responses, agreed: bool}`（供高利害评估题使用，M07 会调用）。

## 验收
```bash
python -c "from packages.llm_gateway.gateway import route, cross_check; print('ok')"
# 期望：print ok，无语法错误
```
（不在本模块真实调用外部 API；联调用例写好但标记 `@pytest.mark.integration`。）

## 依赖与边界
- 生产上建议用 LiteLLM，但本模块先零/极依赖实现，避免环境负担。
- 不处理评估业务逻辑；只做"调模型"这一件事。