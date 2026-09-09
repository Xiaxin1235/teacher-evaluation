"""学校具体指标与客观事实查询引擎 (Fact Engine)。

针对开放式提问中的微观指标（如平板电脑配置、网络带宽、生机比、教师人数等），
从 SQLite 底层 answers / schools / questions 提取高置信度事实数据与背景上下文。
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from packages.agent.indicator_catalog import match_indicator
from scripts.school_engine import connect, find_schools, get_school


def query_school_fact(
    school_keyword_or_id: Union[str, int],
    metric_or_text: Union[str, Dict[str, Any]],
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """查询某所学校的具体指标事实。

    参数:
      school_keyword_or_id: 学校名关键词或学校 ID
      metric_or_text: match_indicator 返回的 dict，或者用户原始文本
      year: 指定年份（如 "2023"），若为 None 则默认最新年份
    """
    # 1. 规范化指标信息
    if isinstance(metric_or_text, dict):
        metric_info = metric_or_text
    else:
        metric_info = match_indicator(str(metric_or_text))

    if not metric_info:
        return {"error": f"未能从提问中识别出具体指标项（支持：平板电脑、台式机、带宽、三个课堂、培训、师机比等）"}

    # 2. 定位目标学校
    school = None
    if isinstance(school_keyword_or_id, int) or (
        isinstance(school_keyword_or_id, str)
        and school_keyword_or_id.isdigit()
    ):
        school = get_school(int(school_keyword_or_id))
    elif isinstance(school_keyword_or_id, str) and school_keyword_or_id.startswith("id:"):
        school = get_school(int(school_keyword_or_id.split(":", 1)[1]))
    else:
        hits = find_schools(str(school_keyword_or_id).strip(), year=year, limit=5)
        if not hits:
            return {"error": f"未检索到匹配的学校「{school_keyword_or_id}」" + (f"（年份 {year}）" if year else "")}
        school = hits[0]

    if not school:
        return {"error": "未找到有效学校档案"}

    school_id = school["id"]
    school_name = school["school_name"]
    active_year = school.get("year") or year or "2023"

    conn = connect()

    # 3. 查寻同名学校全部建档历史，用于展示跨学年追踪
    hist_schools = conn.execute(
        "SELECT id, year, teacher_num, student_num, class_num FROM schools WHERE school_name=? ORDER BY year ASC",
        (school_name,),
    ).fetchall()
    hist_dict = {str(r["year"]): dict(r) for r in hist_schools}

    out: Dict[str, Any] = {
        "object_type": "school_fact",
        "school_id": school_id,
        "school_name": school_name,
        "school_years": [active_year],
        "year": active_year,
        "province": school.get("province"),
        "city": school.get("city"),
        "district": school.get("district"),
        "school_type": school.get("school_type"),
        "school_area_type": school.get("school_area_type"),
        "teacher_num": school.get("teacher_num"),
        "student_num": school.get("student_num"),
        "class_num": school.get("class_num"),
        "fact_type": metric_info["type"],
        "metric_name": metric_info.get("name"),
        "unit": metric_info.get("unit", ""),
        "context_facts": [],
        "history": [],
    }

    # 4. 分支执行
    if metric_info["type"] == "school_field":
        field = metric_info["field"]
        raw_val = school.get(field) or "0"
        unit = metric_info.get("unit", "")
        out["target_value"] = raw_val
        out["direct_answer"] = f"{school_name}（{active_year}年）的【{metric_info['name']}】为 **{raw_val} {unit}**。"
        # 历史趋势
        for y, h in hist_dict.items():
            out["history"].append({"year": y, "value": f"{h.get(field, '-')} {unit}"})

    elif metric_info["type"] == "question":
        qid = metric_info["qid"]
        q_row = conn.execute(
            "SELECT id, content, level1_name, level2_name FROM questions WHERE id=?", (qid,)
        ).fetchone()
        q_content = q_row["content"] if q_row else metric_info["name"]
        l1 = q_row["level1_name"] if q_row else "基础设施"
        l2 = q_row["level2_name"] if q_row else "终端"

        ans_row = conn.execute(
            "SELECT value, normalized_value FROM answers WHERE school_id=? AND question_id=?",
            (school_id, qid),
        ).fetchone()
        val = ans_row["value"] if ans_row else None
        norm = ans_row["normalized_value"] if ans_row else None

        unit = metric_info.get("unit", "台")
        display_val = int(val) if val is not None and val == int(val) else val
        norm_score = round(norm * 100, 1) if norm is not None else None

        out["question_id"] = qid
        out["question_content"] = q_content
        out["dimension"] = l1
        out["sub_dimension"] = l2
        out["target_value"] = display_val if display_val is not None else 0
        out["normalized_score"] = norm_score

        if display_val is not None:
            out["direct_answer"] = (
                f"{school_name} 在 {active_year} 年官方登记配置的【{metric_info['name']}】具体为 **{display_val} {unit}**"
                + (f"（标准化得分 {norm_score} 分）" if norm_score is not None else "")
                + "。"
            )
        else:
            out["direct_answer"] = f"{school_name} 在 {active_year} 年未作答此项指标（数据缺口）。"

        # 关联题号上下文提取（如查教师平板，一并查出台式机、笔记本、学生平板等）
        related_qids = metric_info.get("related", [])
        if related_qids:
            q_placeholders = ",".join("?" for _ in related_qids)
            rel_rows = conn.execute(
                f"SELECT q.id, q.content, a.value FROM questions q "
                f"LEFT JOIN answers a ON q.id=a.question_id AND a.school_id=? "
                f"WHERE q.id IN ({q_placeholders}) ORDER BY q.id",
                [school_id] + related_qids,
            ).fetchall()
            for r in rel_rows:
                v = r["value"]
                v_disp = int(v) if v is not None and v == int(v) else (v if v is not None else "未填")
                clean_name = r["content"].replace("学校统一配备的", "").replace("数量", "")
                out["context_facts"].append({"qid": r["id"], "label": clean_name, "value": f"{v_disp} 台"})

        # 跨学年历史数据
        for y, h in hist_dict.items():
            sid_hist = h["id"]
            h_ans = conn.execute(
                "SELECT value FROM answers WHERE school_id=? AND question_id=?", (sid_hist, qid)
            ).fetchone()
            hv = h_ans["value"] if h_ans else None
            hv_disp = int(hv) if hv is not None and hv == int(hv) else (hv if hv is not None else "-")
            out["history"].append({"year": y, "value": f"{hv_disp} {unit}"})

    elif metric_info["type"] == "compound":
        qids = metric_info["qids"]
        q_placeholders = ",".join("?" for _ in qids)
        rows = conn.execute(
            f"SELECT question_id, value FROM answers WHERE school_id=? AND question_id IN ({q_placeholders})",
            [school_id] + qids,
        ).fetchall()
        val_map = {r["question_id"]: (r["value"] or 0.0) for r in rows}
        total_dev = sum(val_map.values())
        total_dev_disp = int(total_dev) if total_dev == int(total_dev) else total_dev

        out["target_value"] = total_dev_disp
        ckey = metric_info.get("compound_key")
        unit = metric_info.get("unit", "")

        if ckey == "生机比":
            s_num = float(school.get("student_num") or 0)
            if total_dev > 0 and s_num > 0:
                ratio = round(s_num / total_dev, 2)
                per_student = round(total_dev / s_num, 3)
                out["ratio"] = ratio
                out["direct_answer"] = (
                    f"{school_name}（{active_year}年）在校学生 {int(s_num)} 人，各类学生终端配置共 **{total_dev_disp} 台**。"
                    f"折合生机比约为 **{ratio} 人/台**（平均每名在校生配置 {per_student} 台终端设备）。"
                )
            else:
                out["direct_answer"] = f"{school_name} 暂无完整的学生机总数或在校生数据（在校生: {s_num}, 学生机: {total_dev_disp} 台）。"

        elif ckey == "师机比":
            t_num = float(school.get("teacher_num") or 0)
            if t_num > 0 and total_dev > 0:
                ratio = round(total_dev / t_num, 2)
                out["ratio"] = ratio
                out["direct_answer"] = (
                    f"{school_name}（{active_year}年）专任教师 {int(t_num)} 人，各类教师教学终端共 **{total_dev_disp} 台**。"
                    f"折合师均终端配置比为 **{ratio} 台/人**。"
                )
            else:
                out["direct_answer"] = f"{school_name} 专任教师 {int(t_num)} 人，记录教师终端配置共 {total_dev_disp} 台。"
        else:
            out["direct_answer"] = f"{school_name}（{active_year}年）的【{metric_info['name']}】合计为 **{total_dev_disp} {unit}**。"

    # 补充基础规模上下文
    out["context_facts"].insert(0, {"label": "专任教师数", "value": f"{school.get('teacher_num') or '-'} 人"})
    out["context_facts"].insert(1, {"label": "在校学生数", "value": f"{school.get('student_num') or '-'} 人"})
    out["context_facts"].insert(2, {"label": "教学班级数", "value": f"{school.get('class_num') or '-'} 个"})

    conn.close()
    return out
