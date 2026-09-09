# M04 · 评分校准（考核性 R1）

> 状态：`todo`　依赖：M02　验收：`pytest tests/test_calibration.py`

## 目标
考核性场景禁止"不同教研组原始分直接横比"。本模块实现 R1：把各项指标原始分输出为 **原始分 + 百分位排名 + 组内 z-score** 三件套，杜绝部门间宽松/严厉差异扭曲排名。

## 任务清单
1. 新建 `packages/indicator_engine/` 包（含 `__init__.py`），把 M02 的 `scripts/indicator_engine.py` 中的评分逻辑迁移/包装进来，保持现有 CLI 可用（可保留 scripts 里的入口作薄壳）。
2. 实现 `calibration.py`：
   - `calibrate(df, group_col='dept_id', value_col='score') → DataFrame`：新增列 `pct_rank`（同组百分位）、`z_score`（同组 z-score）。
   - 分桶规则：同校×同学科×同周期（原型以 `dept_id` 模拟学科组）。
   - **小样本规则**：组内样本 < 5 时，z-score 基于全校（跨学科合并）计算并显著标注 `small_sample=True`。
3. 输出集成：评估报告 JSON 增加 `calibration` 区块（原始分 / pct_rank / z_score / small_sample）。
4. 单元测试 `tests/test_calibration.py`（可先用模拟 DataFrame）：
   - 大样本组：z-score 正确性（均值≈0，标准差≈1 的组内标准化）；
   - 小样本组：`small_sample=True` 且回退到全校口径；
   - 边界：空组、单样本组不崩溃。

## 验收（必须本地跑通，不需要真实数据/API key）
```bash
python -m pytest tests/test_calibration.py -q
# 期望：全部通过
python scripts/indicator_engine.py --teacher T001 --json-out
# 期望：报告 JSON 含 calibration 区块
```

## 依赖与边界
- 只读本仓库；不要求真实数据库。
- 不改评估模板权重（业务方签字的配置），只做"输出前校准"。
- 产出物路径：`packages/indicator_engine/`、`tests/test_calibration.py`。
- 完成后在 registry.json 把 M04 置 `done`，并确认依赖 M02 的产物仍在。