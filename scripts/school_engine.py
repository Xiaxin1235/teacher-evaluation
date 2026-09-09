"""学校数字化评估引擎（真实数据）。

数据源：data/real/education_digitization.sqlite
模板：evaluation_templates/school_digitization_v1.yaml

口径：
  单题得分 = normalized_value × 100（0~100）
  维度得分 = 该维度已作答题的等权均值（题权当前全为 1）
  综合得分 = 已覆盖一级维度按模板权重加权
  覆盖率   = 已作答题数 / 模板总题数
  缺口     = 无答案的题，显式列出（最多 8 条）
"""

import os
import sqlite3
import sys
from collections import defaultdict
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from packages.core.frozen_paths import resource_root  # noqa: E402


def _db_path():
    candidates = [
        os.path.join(resource_root(), "data", "real", "education_digitization.sqlite"),
        os.path.join(ROOT, "data", "real", "education_digitization.sqlite"),
        os.path.join(os.path.dirname(sys.executable), "data", "real", "education_digitization.sqlite")
        if getattr(sys, "frozen", False) else "",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return candidates[0]


def connect():
    p = _db_path()
    if not os.path.isfile(p):
        raise FileNotFoundError(
            f"未找到真实库 {p}。请先运行 python scripts/import_real_data.py")
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=4)
def load_school_template():
    try:
        import yaml
    except ImportError:
        return None
    path = os.path.join(resource_root(), "evaluation_templates", "school_digitization_v1.yaml")
    if not os.path.isfile(path):
        path = os.path.join(ROOT, "evaluation_templates", "school_digitization_v1.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_schools(keyword, year=None, limit=20):
    conn = connect()
    like = f"%{keyword}%"
    if year:
        rows = conn.execute(
            "SELECT id, school_name, province, city, district, year, school_type, region "
            "FROM schools WHERE school_name LIKE ? AND year=? LIMIT ?",
            (like, str(year), limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, school_name, province, city, district, year, school_type, region "
            "FROM schools WHERE school_name LIKE ? ORDER BY year DESC LIMIT ?",
            (like, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_school(school_id):
    conn = connect()
    row = conn.execute("SELECT * FROM schools WHERE id=?", (int(school_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def evaluate_school(school_id, template=None):
    template = template or load_school_template()
    if template is None:
        return {"error": "学校数字化评估模板不可用"}
    school = get_school(school_id)
    if not school:
        return {"error": f"学校 {school_id} 不存在"}

    conn = connect()
    answers = {r["question_id"]: r for r in conn.execute(
        "SELECT question_id, value, normalized_value FROM answers WHERE school_id=?",
        (int(school_id),)).fetchall()}
    conn.close()

    dims_out = []
    total = 0.0
    covered_w = 0.0
    weight_sum = 0.0
    n_metrics = 0
    n_answered = 0

    for dim in template.get("dimensions", []):
        metrics = dim.get("metrics") or []
        n_metrics += len(metrics)
        scores = []
        evidence = []
        gaps = []
        for m in metrics:
            qid = int(m["id"])
            ans = answers.get(qid)
            if ans is None or ans["normalized_value"] is None:
                gaps.append(m.get("content") or f"题{qid}")
                continue
            n_answered += 1
            nv = float(ans["normalized_value"])
            sc = max(0.0, min(100.0, nv * 100.0))
            scores.append(sc)
            evidence.append({
                "metric": f"q{qid}",
                "label": m.get("content"),
                "raw": round(nv, 4),
                "source": "answers.normalized_value",
                "period": [school.get("year")],
                "formula": "normalized_value × 100",
            })
        dim_score = round(sum(scores) / len(scores), 2) if scores else None
        conf = round(len(scores) / len(metrics), 2) if metrics else 0.0
        w = float(dim.get("weight") or 0)
        weight_sum += w
        if dim_score is not None:
            total += dim_score * w
            covered_w += w
        dims_out.append({
            "dimension": dim.get("name"),
            "is_redline": False,
            "score": dim_score,
            "confidence": conf,
            "weight": w,
            "evidence": evidence,
            "gap": gaps[:8],
        })

    coverage = n_answered / n_metrics if n_metrics else 0.0
    total_score = round(total / covered_w, 2) if covered_w else None
    overall_conf = round(covered_w / weight_sum, 2) if weight_sum else 0.0

    return {
        "object_type": "school",
        "teacher_id": str(school["id"]),          # composer 复用字段名
        "teacher_dept": f"{school.get('province')}/{school.get('city')}",
        "school_id": school["id"],
        "school_name": school.get("school_name"),
        "school_years": [school.get("year")],
        "template": (template.get("template") or {}).get("name"),
        "total_score": total_score,
        "overall_confidence": overall_conf,
        "data_coverage": round(coverage, 2),
        "redline_flagged": False,
        "dimensions": dims_out,
        "answered": n_answered,
        "total_metrics": n_metrics,
    }


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    hits = find_schools("长沙县成绩小学", year="2020", limit=3)
    print("hits:", hits)
    if hits:
        from packages.agent.composer import render_markdown
        res = evaluate_school(hits[0]["id"])
        print(render_markdown(res))
