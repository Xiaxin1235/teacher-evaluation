# M01 · 数据契约与校验器

> 状态：`done`（与 modules/registry.json 同步）　依赖：M00

## 目标
数据未到位时先把"数据长什么样"固化成**机器可读契约**，数据一到即可自动体检，FAIL 的表不允许进入评估管线。

## 已交付
- `contracts/data_contract_v0.1.json` —— 9 张表（teacher / course_period / exam_score / student_survey / class_observation / lesson_plan / research_record / complaint_record / discipline_record）的最小字段集、类型、取值范围、业务唯一键（`key`）或明细表标记（`uniqueness: "row_level"`）、跨表引用规则。
- `scripts/data_contract_validator.py` —— 校验器。

## 设计要点（改代码前必读）
- 表分两类：**聚合表**（有业务唯一键 `key`，如 lesson_plan 按 teacher+school_year 唯一）和**明细表**（`uniqueness: "row_level"`，一行一条记录，不查重）——这个区分曾真实抓出 lesson_plan 主键重复 bug，勿混淆。
- 校验分级：FAIL（缺字段/主键重复/类型错/跨表引用断裂）阻塞管线；WARN（样本过小等）只提示。
- `load_contract()` 目前断言 `contract_version == "0.1"`；扩展契约时需同步升版本号并保持向后兼容。

## 验收
```bash
python scripts/data_contract_validator.py --dir data/demo --contract contracts/data_contract_v0.1.json
# 期望：9 张表全部 PASS
```

## 明确不做
- 不引入 pandas/jsonschema 等三方依赖（保持零依赖可跑）。
- 不做自动修复，只报告。
