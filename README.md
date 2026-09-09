# 教师评估 AI 平台（模块化项目仓库）

> 定位：类似 "pi agent" 的多模型 Agent 平台，接入各类模型 API，对本地教师数据库做检索与分析，完成教学水平等指标的**量化、可追溯、有置信度**的评估。核心命题：**用户提问可以笼统宽泛，但系统必须通过证据链给出严谨结论**。
> **当前状态**：P0 归档完成（文档 + 指标引擎原型），进入模块化分步建设阶段。

---

## 一、如何用这套仓库分步干活（先读这个）

本仓库为 **"任意 agent 分步完成整个项目"** 设计。规则三件套：

1. **看板**：`python scripts/module_board.py` —— 实时告诉你"哪些模块 done、哪些 ready、下一步做哪个"。
2. **模块登记表**：`modules/registry.json` —— 机器可读：模块 id、状态、依赖、产出清单、验收命令，是协作的"指挥中心"。
3. **模块 SPEC**：`modules/<id>/SPEC.md` —— 每个模块一份**自包含构建说明书**（任务清单 + 验收命令 + 边界）。agent 只读自己那一份就能开工，做完跑通验收再在 registration 标记 done。

**工作纪律**（registry.json 的 `work_rule`）：
- 一个 agent 一次只认领一个 module id，交付 `produces` 清单、跑通 `verify` 才标记 done（防假状态）；
- 任何超出 SPEC 的假设必须先写回 SPEC 再执行；
- 先跑 `python scripts/doc_smoke.py` 守护仓库健康，再跑模块验收。

### 模块依赖图

```
M00 工作区/文档（done）
 ├─ M01 数据契约（done）→ M02 指标引擎（done）→ M03 冒烟基线（done）
 ├─ M06 模型网关（todo）
 M02 ── M04 评分校准（todo）   ← 下一步 ①
 M02 ── M05 复核/申诉 DDL（todo） ← 下一步 ①（可与 M04 并行）
 M02+M06 ─ M07 Agent 编排（blocked）
 M02+M07 ─ M08 证据合成器（blocked）
 M02+M07+M08 ─ M09 REST API（blocked）
 M09 ─ M10 Web 看板（blocked）／ M11 权限审计（blocked）
 M07+M08 ─ M12 Golden Set 回归（blocked）
```

---

## 二、看板操作速查

```bash
python scripts/module_board.py                    # 看板 + 下一步建议
python scripts/doc_smoke.py                       # 全仓库健康冒烟（每个 agent 收尾都跑）
python scripts/data_contract_validator.py --contract contracts/data_contract_v0.1.json --dir data/demo   # 数据体检
```

### 完成一个模块后的"交接动作"

1. 跑 `python scripts/doc_smoke.py`（含"done 模块产物必须存在"检查）；
2. 在 `modules/registry.json` 把该 `id` 的 `status` 改为 `"done"`；
3. 跑 `python scripts/module_board.py` 确认依赖链正确解锁下一个模块；
4. 若模块产出扩大契约/模板，同步更新 README 资产表。

---

## 三、当前资产

| 资产 | 位置 | 说明 |
|---|---|---|
| 项目大纲 | `docs/教师评估AI平台-项目大纲.md` | 愿景、六大子系统、路线图 P0~P4、风险、待决策项 |
| 需求确认单 | `docs/需求确认单.md` | 决策记录：**评估用途=考核性（已确认）**；其余待签字 |
| 系统设计 v0.1 | `docs/系统设计文档-v0.1.md` | 数据模型、指标体系、引擎时序、**§0 考核性基线 R1~R4**、API 草案 |
| 模块登记表 | `modules/registry.json` | 13 个模块：状态/依赖/产出/验收（机器可读） |
| 模块 SPEC | `modules/M00~M12/SPEC.md` | 每个模块自包含构建说明书 |
| 数据契约 | `contracts/data_contract_v0.1.json` | 9 张表最小字段集 + 跨表规则（发给数据方对接） |
| 数据校验器 | `scripts/data_contract_validator.py` | 数据交付一键体检，FAIL 阻塞管线 |
| 模拟数据 | `scripts/mock_transform.py` + `data/demo/` | 9 张虚构脱敏表 |
| 指标引擎 | `scripts/indicator_engine.py` + `evaluation_templates/2025-2026_v1.yaml` | 无模型评估管线：得分/置信度/证据块/报告 |
| 评分校准（M04） | `packages/indicator_engine/calibration.py` + `tests/test_calibration.py` | 考核性 R1：百分位排名 + z-score + 小样本回退（测试 6/6） |
| 复核/申诉 DDL（M05） | `data/ddl/05_review_appeal.sql` | 考核性 R2/R3：`human_review_checklist` + `appeal_record`（含 trace_json 结构） |
| 模型网关（M06） | `packages/llm_gateway/gateway.py` + `providers.json` | 多供应商路由/降级/双模型交叉校验；密钥只走环境变量 |
| Agent 编排（M07） | `packages/agent/planner.py` + `retriever.py` + `critic.py` + `bench.py` | 宽泛问题→子任务 DAG / 证据强制引用 / 规则批判（C1~C4）|
| 证据合成器（M08） | `packages/agent/composer.py` | 人类可读报告：内联证据、缺口披露、红线提示、弱项/趋势提示、免责声明 |
| REST API（M09） | `apps/api/main.py` + `requirements.txt` | `/api/v1/chat` 等 6 端点；fastapi 未装可降级（核心逻辑仍可用） |
| Web 对话台（M10） | `apps/web/index.html` | 零构建单页：对话评估 + 雷达图 + 看板趋势；无后端 mock 可演示 |
| 权限与审计（M11） | `packages/core/authz.py` + `data/ddl/11_auth_audit.sql` | 角色权限矩阵 + 红线最严访问 + 审计/访问日志 |
| Golden Set（M12） | `tests/golden/golden_set.json` + `run_eval.py` | 20 条回归用例；`--smoke` 纯规则跑（当前 18/18 非集成通过） |

## 四、快速运行（原型）

```bash
python scripts/mock_transform.py                     # 生成模拟数据
python scripts/indicator_engine.py --teacher T001 --json-out   # 综合 83.13 / 覆盖率 1.0
python scripts/indicator_engine.py --teacher T003 --json-out   # 红线触发 / 覆盖率 0.65
```

输出要点：综合得分（0~100，权重加权）／数据覆盖率（<0.6 明示"仅供参考"）／综合置信度（小样本、断档下调）／红线标记（一票否决，转人事）／证据引用列表（来源+周期+口径）。

## 四·五、exe 版（无需 Python，双击即用）

**产物**：`dist/TeacherEval/`（TeacherEval.exe + `_internal` 运行库，整个文件夹分发）

```bash
TeacherEval.exe                            # 双击：起本地 API + 自动打开对话台 http://127.0.0.1:8600
TeacherEval.exe serve                      # 只起服务
TeacherEval.exe eval --teacher T001        # 命令行评估，输出报告
TeacherEval.exe eval --teacher T003 --json-out   # 评估 + JSON 落到 exe 旁 output/
```

- 对话台/看板/API 全部内嵌（演示数据 + 评估模板 + Web 页面），无需任何外部文件或 Python 环境。
- 重新构建：`python build_exe.py`（细节与 onedir 决策见 `modules/M13-packaging/SPEC.md`）。

## 五、原型已验证的关键机制

1. **量纲统一**：教案覆盖率、评教（1~5×20）、成绩增值（基线差分）统一到 0~100 量表。
2. **增值口径 + 剔除自包含**：及格率改善 = 本班及格率 − 同年级同科目基线（剔除被评教师自己）。
3. **红线一票否决**：查实师德记录不进加权，单独标记转人事流程。
4. **不确定显式披露**：无数据维度 → 空缺 + 缺口说明 + 置信度下调，不编造数字。
5. **证据可追溯**：报告附证据块（来源表、时间范围、口径公式）。

## 六、项目状态

**M00–M13 已全部完成**（看板 `python scripts/module_board.py`，无待办模块）：

| 阶段 | 模块 | 状态 |
|---|---|---|
| 文档与契约 | M00 工作区 / M01 数据契约 / M03 冒烟基线 | done |
| 评估核心 | M02 指标引擎（无 LLM 数学底座） | done |
| 考核性保障 | M04 评分校准 R1 / M05 复核申诉 R2/R3 | done |
| AI 编排 | M06 模型网关 / M07 Agent（Planner/Retriever/Critic）/ M08 报告合成 | done |
| 应用层 | M09 REST API / M10 Web 对话台 / M11 权限审计 | done |
| 质量与交付 | M12 Golden Set 回归（18/18 通过）/ M13 exe 打包 | done |

**进入真实使用前还需**（需业务方参与）：
1. 用 `需求确认单.md` 签订其余决策（数据来源、权重口径、角色）；
2. 用 `contracts/data_contract_v0.1.json` + 校验器接入真实数据（当前全为虚构演示数据）；
3. 配置模型 key（环境变量，见 M06）启用对话式 LLM 解读；生产化（PostgreSQL、审计落库）。

> 说明：本仓库所有 CSV/JSON 为**虚构脱敏数据**，仅演示评估管线，不含任何真实教师或学生信息。模型密钥只允许来自环境变量（见 M06 契约），禁止写入仓库。