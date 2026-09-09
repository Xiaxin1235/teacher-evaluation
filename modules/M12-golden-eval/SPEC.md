# M12 · Golden Set 回归评测

> 状态：`todo`　依赖：M07, M08　验收：`python tests/golden/run_eval.py --smoke` 通过

## 目标
建立"事实不回退"的回归护栏：Golden Set（标准问答 + 期望要点）+ 评测器。任何 agent 改完 M07/M08 或模板后，跑一遍确保质量不回退。

## 任务清单
1. `tests/golden/golden_set.json`：≥20 条用例，字段 `{id, question, expect:{total_range, dims:{...}, must_mention:[], no_hallucinate:"数据不可编造", redline_case:bool}}`。覆盖：综合评估、单维聚焦、边界（无数据教师、小样本、红线、宽泛缺对象）。
2. `tests/golden/run_eval.py`：
   - `--smoke` 模式：只跑 F(快速) 用例 × 纯规则管线（M07 的 retriever+composer，不依赖外部模型）；
   - `--full` 模式：接模型时跑全部（模型联调标注 integration）。
   - 输出每用例 pass/fail + 原因；exit 1 当存在 fail。
3. 断言规则：
   - 总分须落在 `expect.total_range`；
   - 红线段必须出现红线说明；非红线不允许误报；
   - 缺口披露：无数据维度必须出现"无数据/无支撑"措辞；
   - 幻觉检查：报告中的数字必须能在证据块中找到。

## 验收
```bash
python tests/golden/run_eval.py --smoke
# 期望：通过且 exit 0
```

## 依赖与边界
- 不要求外部模型即可跑 mock 版；真实模型评测用例标注 integration 不阻塞验收。
- Golden Set 内容是验收的核心资产，每次模板权重改动后建议重跑。