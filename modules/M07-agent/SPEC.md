# M07 · Agent 编排（Planner / Retriever / Critic）

> 状态：`todo`　依赖：M02, M06　验收：`import packages.agent.planner` 无报错

## 目标
实现"宽泛提问 → 严谨回答"的编排核心：Planner 把宽泛问题拆成结构化子任务 DAG；Retriever 只负责从契约表/指标引擎取证据（**无证据不回答**）；Critic 做 LLM-as-judge 校验（幻觉/矛盾/过度解读检测），不通过打回重写（≤2 轮）。

## 任务清单
1. 新建 `packages/agent/` 包（含 `__init__.py`）。
2. `planner.py`：
   - `parse_question(text) → Question{objects:[teacher_id], years, intent, missing:[]}`；解析失败或 missing 含关键项 → 返回 `clarify_needed=True` 与候选澄清问题（反问机制）。
   - `plan(question, template) → DAG[Task{}]`：按模板维度生成并行子任务（红线维单独）。
   - 产出 JSON 结构（非自由文本计划），可审计。
3. `retriever.py`：
   - `retrieve(task, tables) → Evidence[]`：优先指标仓库缓存，未命中走 M02 引擎计算；返回证据块（含 source/period/formula）。
   - **硬规则：Evidence 为空的任务，下游不得编造数值，只能输出 gap。**
4. `critic.py`：
   - `review(report, evidence) → {verdict: pass|needs_revision, findings[]}`：检查器集：数字无证据来源、维度间矛盾、小样本下趋势断言、红线表述中性化（不做人格化评价）。
   - critic 策略：原型阶段可用**规则判定 + 可选 LLM 复核**（LLM 复核在 M06 网关存在时启用，否则纯规则）。
5. `bench.py`：对一个示例宽泛问题（如"张老师近三年教学水平怎么样？"）走完整 pipeline 的演示入口（只在有/无模型两种模式下都能跑）。

## 验收
```bash
# 注意：示例问题"张老师近三年教学水平怎么样？"无 T 系列 ID 也无 20xx-20xx 年份，
# 在匿名化数据（名字→ID 映射不可用）下 parse_question 应返回 clarify_needed=True 与缺失项
# （这是反问机制的正确行为）。带 ID 的示例：parse_question('T001 2024-2025 教学水平？') 应解析出对象与年份。
python -c "from packages.agent.planner import parse_question; print(parse_question('T001 2024-2025 教学水平？'))"
# 期望：objects=['T001'], years=['2024-2025'], clarify=False
python -c "from packages.agent.critic import review; print(review({'dimensions':[]}, []))"
# 期望：{'verdict': 'pass', 'findings': []}
python scripts/doc_smoke.py   # 不破坏现有冒烟
```

## 依赖与边界
- 不接对话 UI（M10）；不做报告成稿与排版（M08）。
- 依赖 M02 提供的证据语义、M06 提供的网关接口（无 key 时走纯规则）。
- 新增的模块产物不以实名/隐私进代码注释。