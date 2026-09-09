# M05 · 人工复核与申诉闭环（考核性 R2/R3）

> 状态：`todo`　依赖：M02　验收：DDL 文件含两张表

## 目标
考核性场景必须有人工介入与异议回路。本模块实现 R2/R3 的**数据结构层**：
- R2 人工复核清单：过程性维度（课堂教学、教学设计）强制教研组长人工确认；
- R3 申诉追溯：教师对结果有异议时，系统只出具"哪些数据参与、什么口径、为什么取这个值"的追溯说明，不改分，由评审委员会终裁。

## 任务清单
1. 新建 `data/ddl/` 目录，写 `05_review_appeal.sql`（PostgreSQL 语法）：
   - `human_review_checklist`：`id, result_id(FK), dimension, item, value, score, confidence, reviewed_by, reviewed_at`；
   - `appeal_record`：`appeal_id, result_id(FK), teacher_id, appeal_reason, trace_json, committee_result, adjustment(jsonb), status, created_at, resolved_at`。
   - 字段对齐《系统设计文档-v0.1.md》§2 中的数据模型定义。
2. `trace_json` 的结构在 SQL 注释或单独 `docs/M05-trace-schema.md` 中定义：`{inputs:[{table, filter, used_range}], results:[{metric, value, formula}], caveats:[...]}`。
3. 在 `docs/系统设计文档-v0.1.md` §0 的 R2/R3 后追加一行"实现状态：见 M05"。

## 验收
```bash
# 文件存在、包含两张表的 CREATE TABLE、含 result_id FK 和审核字段
python scripts/doc_smoke.py    # 不破坏现有冒烟
```
（如本地有 psql 可额外做语法校验，但没有不阻塞——SQL 为草案基线，正式迁移在 M11 之后统一评审。）

## 依赖与边界
- 只产出 DDL 与追溯结构定义，**不做**申诉 API（那是 M09/M11 的职责）。
- 不改变 M02 的评分逻辑。