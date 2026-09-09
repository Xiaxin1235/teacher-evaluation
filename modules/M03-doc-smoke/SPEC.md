# M03 · 文档冒烟与回归基线

> 状态：`done`（与 modules/registry.json 同步）　依赖：M02

## 目标
一条命令守护全仓库基本健康度：文档在、契约合法、登记表自洽、脚本可编译、模拟数据在。后续任何 agent 动完代码，先跑它再交。

## 已交付
- `scripts/doc_smoke.py` —— 零依赖冒烟检查：
  1. 三份主文档 + README 存在且非空；
  2. `contracts/data_contract_v0.1.json` 可解析且版本为 0.1；
  3. `modules/registry.json` 完整性：模块 id 唯一、依赖引用存在、**每个 done 模块的 produces 文件必须真实存在**（防"标了 done 但文件不存在"的假状态）；
  4. `scripts/*.py` 全部可编译（py_compile，不执行）；
  5. 评估模板 YAML 可解析；
  6. `data/demo/` 9 张模拟表存在且非空。

## 设计要点
- 冒烟**只读不写**：不重新生成模拟数据、不跑引擎（那是各模块 verify 的职责）。
- 新增顶层目录/脚本后，若应纳入守护范围，需同步扩展本脚本。

## 验收
```bash
python scripts/doc_smoke.py    # 期望：全部 PASS，exit 0
```

## 明确不做
- 不做网络检查、不装依赖。
