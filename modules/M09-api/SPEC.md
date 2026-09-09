# M09 · REST API（FastAPI）

> 状态：`todo`　依赖：M02, M07, M08　验收：`import apps.api.main` 无报错

## 目标
把评估能力暴露成 REST API（对齐《系统设计文档-v0.1.md》§6 的 API 草案），供 Web/批量任务/外部系统使用。

## 任务清单
1. 新建 `apps/api/`（FastAPI 应用 + `main.py`、`requirements.txt` 标注可选安装）。
2. 实现（先做核心，权限占位）：
   - `POST /api/v1/chat` —— 对话式评估入口（接收宽泛问题文本，走 M07 pipeline，返回结构化报告 + evidence）；
   - `POST /api/v1/evaluations` —— 发起批量评估任务（先同步执行，队列化留待后续）；
   - `GET /api/v1/evaluations/{result_id}` —— 取单份结果；
   - `GET /api/v1/teachers/{teacher_id}/reports` / `/trends` —— 教师报告与趋势（多周期雷达数据，M10 用）；
   - `GET /api/v1/templates` —— 模板列表（评估框架即配置的读接口）。
3. 请求/响应用 Pydantic 模型定契约；错误统一 `{"detail": ...}`。
4. 只读原则：本模块 API 不写任何业务库；结果内存/内存队列即可（持久化交给 M05/M11 之后）。

## 验收
```bash
python -c "import sys; sys.path.insert(0,'.'); import apps.api.main; print('ok')"   # 期望 ok
# 有性能余力时可用 fastapi TestClient 写分钟级冒烟（不强求）
```

## 依赖与边界
- 权限/审计是 M11，本模块只做权限占位（`get_current_user` 桩 + TODO）。
- 不接真实数据库持久化（原型结果放内存/临时存储）。