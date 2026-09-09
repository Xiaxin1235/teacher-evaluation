# M02 · 指标计算引擎（原型）

> 状态：`done`（与 modules/registry.json 同步）　依赖：M01

## 目标
不接任何 LLM，跑通核心链路：**多源数据 → 拆维度 → 聚合计算 → 得分+置信度 → 证据块 → 综合报告**。这是全系统的"数学底座"，LLM 永远不参与算数。

## 已交付
- `evaluation_templates/2025-2026_v1.yaml` —— 评估模板（维度/权重/红线），"评估框架即配置"的落地样例。
- `scripts/indicator_engine.py` —— 引擎主体：`METRIC_FUNCS` 注册表 + `evaluate_teacher()` + `render_report()`。
- `scripts/mock_transform.py` —— 生成 9 张虚构脱敏模拟表到 `data/demo/`。

## 设计要点（改代码前必读）
1. **量纲统一**：所有指标归一到 0~100（教案覆盖率 ×100；评教 1~5 分 ×20；成绩增值按基线差分映射）。
2. **增值口径**：及格率改善 = 本班及格率 − 同年级同科目基线，**基线剔除被评教师自己的班**（防自包含偏差）。
3. **红线一票否决**：师德类查实记录不进加权，单独标记转人事流程。
4. **不确定显式披露**：无数据维度 → 得分空缺 + gap 说明 + 置信度扣减（penalty），禁止编造数字。
5. **证据块**：每条结论挂 `{metric, raw, source, period, formula}`，正式版供 LLM 强制引用。
6. 运行环境注意：Windows 控制台 GBK，入口已做 `sys.stdout.reconfigure(encoding="utf-8")`，新增脚本照做。

## 验收
```bash
python scripts/mock_transform.py                                  # 9 张表
python scripts/indicator_engine.py --teacher T001 --json-out      # 综合 83.13 / 覆盖率 1.0
python scripts/indicator_engine.py --teacher T003 --json-out      # 红线触发 / 覆盖率 0.65
```

## 明确不做
- 不接真实数据库（真实数据适配是后续模块的事）；不改模板权重（那是业务方签字的配置）。
