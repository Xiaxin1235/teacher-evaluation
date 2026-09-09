# 项目长期记忆 · teacher evaluation

## 数据源层级（重要）

1. **权威源**：`教育数字化数据库/<乱码目录>/sql/`
   - `转换sql/dump-test_number-202605201442.sql`（973 MB）— 库 `test_number`，
     `school_answers` **31,115,621 行** = 374,887 校 × 83 题全矩阵；`schools` 374,887；
     `questions` 83；`question_min_max` 83
   - `原始sql/dump-regional-202609071748.sql`（747 MB）— 库 `regional`，
     `school_data` 374,887 行 × 97 列（原始文本答案）
2. **派生库**：`data/real/education_digitization.sqlite`（121 MB）
   由 `scripts/import_real_data.py` 从 `data/real/*.csv` 生成。
   ⚠️ **只保留了 9.26% 的有效作答**（1,509,896 / 16,301,215），
   Q6–Q83 只剩 10 所学校。**不可用于评估数据覆盖度**。

## 长期有效的数据事实

- **归一化**：`normalized_value = (value - min_val)/(max_val - min_val)`，量程取自
  `question_min_max`。但该表是**实测极值**而非理论满分 → 12 题量程 ≥1e6 被脏值主导，
  27 题（32.5%）压缩 >100 倍。**复用 normalized_value 前必须先修复量程**。
- **问卷分年份改版**：全年份可比的只有 **22 题**（共 83 题）。跨年趋势必须限定这 22 题。
- **全矩阵零值填充占 47.61%**，统计一律加 `WHERE value > 0`。
- **原始答案是多选题选项列表**（`[\B.语文\,\C.数学\]`），数值化规则 = 选项个数。
- 三级权重恒为 1.0 → 当前评分为等权算术平均，权重体系未启用。

## 项目约定与坑

- `教育数字化数据库/` 下嵌套目录名是**编码损坏的乱码**，无法键入路径，
  必须用 `os.walk` 动态定位，不要硬编码。
- `教育数字化数据库.zip`（265 MB，项目根目录）含 csv/ 与 sql/ 全量备份，可恢复。
- `data/real/*.csv`、`data/demo/*.csv` 是管线输入，被 `import_real_data.py`、
  `build_real_template.py`、`indicator_engine.py`、`doc_smoke.py` 依赖，**勿删**。
- `data/ddl/*.sql` 是 PostgreSQL 草案（复核/申诉/权限审计），尚未落库。
- 解析大 dump 的可行做法：按 `INSERT INTO` 逐行 + `body[1:-1].split('),(')` 拆分，
  31M 行约 43 秒；行计数用 `),(` 计数法比正则更可靠（正则遇特殊字符会丢行）。

## 已有产出

- `docs/数据库数据特征分析报告.md/.html` — SQLite 派生库画像（结论已被下述报告修正）
- `docs/MySQL完整数据特征分析报告.md/.html` — MySQL 完整数据画像（**以此为准**）
