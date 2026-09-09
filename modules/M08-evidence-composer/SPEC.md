# M08 · 证据合成器（报告 Composer）

> 状态：`todo`　依赖：M02, M07　验收：`import packages.agent.composer` 无报错

## 目标
把 M07 产出的"维度得分 + 证据块 + 置信度"合成为**人类可读的严谨报告**：每条结论内联证据引用；缺失/低置信显式披露；红线显著提示；固定标注"辅助参考材料，供评审委员会人工复核使用"（考核性 R4）。

## 任务清单
1. `composer.py`：
   - `compose(result) → dict/report_text`：输入评估结果（M02 结构 + M07 分析 + M08 前的证据），输出：
     - 概览（总分、覆盖率、综合置信度、红线标记）；
     - 分维度段落：结论句 + `[证据: source, period, formula]` 内联引用；
     - 缺口清单 + 置信度说明；
     - 固定免责声明："辅助参考材料，供评审委员会人工复核使用"；
     - 可选 `render_markdown()` / `render_json()` 两种出口。
2. 复用 M02 的 `render_report` 思路但不依赖其 print 实现；输出为可序列化结构 + markdown。
3. 小样本/低置信维度输出"趋势性提示"而非结论（对齐 M02 §4.3 置信度规则）。

## 验收
```bash
python -c "from packages.agent.composer import compose; print('ok')"
python scripts/indicator_engine.py --teacher T003 --json-out
# 期望：结果 JSON 可被 compose 消费（本模块配套写一个最小拼接 demo 验证 T003 的红线与缺口披露）
python scripts/doc_smoke.py  # 不破坏冒烟
```

## 依赖与边界
- 不引入装版库（Markdown 手写即可）；PDF/Word 导出是 M10 或后续模块的事。
- 不改评估计算；只负责"怎么说"。