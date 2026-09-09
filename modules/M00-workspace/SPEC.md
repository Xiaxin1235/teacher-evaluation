# M00 · 工作区与文档归档

> 状态：`done`（与 modules/registry.json 同步）　依赖：无

## 目标
建立项目工作区：三份主设计文档 + README 入口，作为后续所有模块的"必读上下文"。

## 已交付
- `docs/教师评估AI平台-项目大纲.md` —— 愿景、六大子系统、路线图 P0~P4、风险清单
- `docs/需求确认单.md` —— 业务方决策记录（**评估用途已确认：考核性**）
- `docs/系统设计文档-v0.1.md` —— 数据模型、指标体系、引擎时序、API 草案、**§0 考核性设计基线（R1~R4）**
- `README.md` —— 仓库入口

## 后续 agent 的阅读顺序
1. `README.md`（全局）
2. `docs/系统设计文档-v0.1.md` §0（考核性基线）+ 你负责模块引用的章节
3. `modules/registry.json`（看板与依赖）

## 验收
```bash
# docs 三份文档 + README 存在且非空（由 scripts/doc_smoke.py 自动检查）
python scripts/doc_smoke.py
```

## 明确不做
- 不在此模块修改任何代码；文档修订走编辑对应文档并在其中注明版本。
