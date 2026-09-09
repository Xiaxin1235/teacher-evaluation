"""区域数字化宏观评估引擎 (Region Engine)。

支持按区县、地级市、省份汇总区域内全量学校的数字化作答大盘：
- 区域综合均分与多维指标表现
- 六大维度均分（数字资源、教育教学、数字素养、基础设施、教育治理、保障机制）
- 区域学校数字化发展分层与比例分布
- 标杆示范学校排行榜 (Top 5) 与薄弱帮扶名单 (Bottom 5)
- 区域数字化主要优势与瓶颈短板诊断
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.school_engine import connect

STANDARD_DIMENSIONS = [
    "数字资源",
    "教育教学",
    "数字素养",
    "基础设施",
    "教育治理",
    "保障机制",
]


PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"
]


def detect_region(keyword: str) -> Optional[Dict[str, Any]]:
    """从关键词中识别行政区划（区县 > 地级市 > 省份），支持组合与自然语言提取。"""
    import re

    clean = re.sub(r"20\d{2}\s*年?", "", keyword)
    for p in ["评估", "查看", "分析", "查询", "测算", "了解", "请问", "想问", "给我", "帮我", "说说", "看一下", "总结", "诊断", "我想看", "想看"]:
        if clean.startswith(p):
            clean = clean[len(p):].strip()
    for w in [
        "的教学水平", "的数字化水平", "的数字化", "的教学", "的教育水平", "的水平",
        "教学水平", "数字化水平", "数字化", "水平", "怎么样", "大盘", "情况",
        "如何", "怎样", "表现", "？", "?", "整校", "整体", "具体", "有哪些",
        "有什么", "指标", "概况", "数据", "报告", "的"
    ]:
        clean = clean.replace(w, "")
    clean = clean.strip()
    if not clean or len(clean) < 2:
        return None

    # 提取行政区划单元 (如 七台河市、新兴区、长沙县、武汉市)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,4}(?:省|市|县|区|旗|州|盟)", clean)
    if clean and clean not in tokens:
        tokens.append(clean)

    conn = connect()

    city_cand = None
    dist_cand = None
    prov_cand = None
    for t in tokens:
        if t.endswith(("区", "县", "旗")) and not dist_cand:
            dist_cand = t
        elif t.endswith("市") and not city_cand:
            city_cand = t
        elif t.endswith("省") and not prov_cand:
            prov_cand = t

    # 1. 组合情况：City + District (如：七台河市新兴区、武汉市蔡甸区)
    if city_cand and dist_cand:
        row = conn.execute(
            "SELECT province, city, district, COUNT(*) as cnt FROM schools "
            "WHERE city LIKE ? AND district LIKE ? AND city NOT LIKE '%学校%' GROUP BY district ORDER BY cnt DESC LIMIT 1",
            (f"%{city_cand}%", f"%{dist_cand}%"),
        ).fetchone()
        if row:
            conn.close()
            clean_city = city_cand
            prov = row["province"] or ""
            return {
                "where_sql": "city LIKE ? AND district LIKE ?",
                "where_params": (f"%{city_cand}%", f"%{dist_cand}%"),
                "name": f"{city_cand}{dist_cand}",
                "province": prov,
                "city": clean_city,
                "district": row["district"],
                "region_type": "区县",
                "full_name": f"{prov} {clean_city} {row['district']}".strip(),
            }

    # 2. 地市匹配优先（若包含市级特征，如 武汉市、七台河市、长沙市）
    cand_cities = ([city_cand] if city_cand else []) + [t for t in tokens if t.endswith("市") or not t.endswith(("区", "县", "旗", "省"))]
    for cand in cand_cities:
        if not cand or cand.endswith("省"):
            continue
        row = conn.execute(
            "SELECT province, city, COUNT(*) as cnt FROM schools "
            "WHERE (city=? OR city LIKE ?) AND city NOT LIKE '%学校%' AND city NOT LIKE '%小学%' AND city NOT LIKE '%中学%' AND city NOT LIKE '%幼儿园%' GROUP BY city ORDER BY cnt DESC LIMIT 1",
            (cand, f"%{cand}%"),
        ).fetchone()
        if row and row["city"] and row["cnt"] > 5:
            conn.close()
            c_name = row["city"]
            prov = row["province"] or ""
            disp_name = c_name.replace(prov, "").strip() or c_name
            full_name = f"{prov} {disp_name}".strip()
            return {
                "where_sql": "city LIKE ?",
                "where_params": (f"%{cand}%",),
                "name": disp_name,
                "province": prov,
                "city": disp_name,
                "district": None,
                "region_type": "地级市",
                "full_name": full_name,
            }

    # 3. 单独区县匹配 (如 新兴区、长沙县、蔡甸区)
    cand_districts = ([dist_cand] if dist_cand else []) + [t for t in tokens if t.endswith(("区", "县", "旗"))]
    for cand in cand_districts:
        if not cand:
            continue
        row = conn.execute(
            "SELECT province, city, district, COUNT(*) as cnt FROM schools "
            "WHERE (district=? OR district LIKE ?) AND district NOT LIKE '%学校%' AND district NOT LIKE '%小学%' GROUP BY district ORDER BY cnt DESC LIMIT 1",
            (cand, f"%{cand}%"),
        ).fetchone()
        if row and row["district"] and not row["district"].endswith("省"):
            # 获取该区县所属的规范地级市名称（排除混入学校名称的脏数据）
            clean_city_row = conn.execute(
                "SELECT city, COUNT(*) as cnt FROM schools "
                "WHERE district=? AND city NOT LIKE '%学校%' AND city NOT LIKE '%小学%' AND city NOT LIKE '%中学%' AND city NOT LIKE '%号%' AND city NOT LIKE '%路%' AND city != province GROUP BY city ORDER BY cnt DESC LIMIT 1",
                (row["district"],),
            ).fetchone()
            clean_city = clean_city_row["city"] if clean_city_row else ""
            prov = row["province"] or ""
            conn.close()
            full_name_parts = [prov, clean_city, row["district"]]
            return {
                "where_sql": "district=?",
                "where_params": (row["district"],),
                "name": row["district"],
                "province": prov,
                "city": clean_city,
                "district": row["district"],
                "region_type": "区县",
                "full_name": " ".join([p for p in full_name_parts if p]).strip(),
            }

    # 4. 省份匹配
    if prov_cand or any(p in clean for p in PROVINCES):
        p_match = next((p for p in PROVINCES if p in (prov_cand or clean)), None)
        if p_match:
            row = conn.execute(
                "SELECT province, COUNT(*) as cnt FROM schools "
                "WHERE province LIKE ? GROUP BY province ORDER BY cnt DESC LIMIT 1",
                (f"%{p_match}%",),
            ).fetchone()
            if row:
                conn.close()
                return {
                    "where_sql": "province LIKE ?",
                    "where_params": (f"%{p_match}%",),
                    "name": row["province"],
                    "province": row["province"],
                    "city": None,
                    "district": None,
                    "region_type": "省份",
                    "full_name": row["province"],
                }

    conn.close()
    return None


def evaluate_region(region_keyword: str, year: Optional[str] = None) -> Dict[str, Any]:
    """对指定区域开展宏观数字化水平评估。"""
    reg = detect_region(region_keyword)
    if not reg:
        return {"error": f"未能识别地区「{region_keyword}」（支持如：长沙县、七台河市、湖南省等区县、地级市与省份名称）"}

    where_sql = reg["where_sql"]
    where_params = reg["where_params"]

    conn = connect()

    # 1. 探查该地区所有有记录的学年与学校数量
    year_rows = conn.execute(
        f"SELECT year, COUNT(*) as cnt FROM schools WHERE {where_sql} GROUP BY year ORDER BY cnt DESC",
        where_params,
    ).fetchall()
    if not year_rows:
        conn.close()
        return {"error": f"未检索到地区「{reg['name']}」的学校建档数据"}

    all_years = sorted(list({str(r["year"]) for r in year_rows}))
    active_year = str(year) if year and str(year) in all_years else str(year_rows[0]["year"])

    # 2. 统计当前学年学校总数及学段构成
    full_where_sql = f"({where_sql}) AND year=?"
    full_where_params = where_params + (active_year,)

    schools_in_year = conn.execute(
        f"SELECT id, school_name, school_type, teacher_num, student_num FROM schools WHERE {full_where_sql}",
        full_where_params,
    ).fetchall()
    school_count = len(schools_in_year)
    if school_count == 0:
        conn.close()
        return {"error": f"地区「{reg['name']}」在 {active_year} 年无监测学校记录（可用学年：{', '.join(all_years)}）"}

    # 3. 统计各校平均得分并排序
    s_where = f"({where_sql.replace('city', 's.city').replace('district', 's.district').replace('province', 's.province')}) AND s.year=?"
    school_scores_rows = conn.execute(
        f"""
        SELECT s.id, s.school_name, s.school_type, s.school_area_type,
               ROUND(AVG(a.normalized_value)*100, 2) as avg_score,
               COUNT(a.value) as answered_cnt
        FROM schools s
        JOIN answers a ON s.id = a.school_id
        WHERE {s_where}
        GROUP BY s.id
        ORDER BY avg_score DESC
        """,
        full_where_params,
    ).fetchall()

    scores = [float(r["avg_score"]) for r in school_scores_rows if r["avg_score"] is not None]
    if not scores:
        conn.close()
        return {"error": f"地区「{reg['name']}」在 {active_year} 年尚未录入有效问卷作答"}

    avg_score = round(sum(scores) / len(scores), 2)
    max_score = max(scores)
    min_score = min(scores)
    sorted_scores = sorted(scores)
    median_score = round(sorted_scores[len(sorted_scores) // 2], 2)

    # 4. 六大维度均分汇总
    dim_rows = conn.execute(
        f"""
        SELECT q.level1_name,
               ROUND(AVG(a.normalized_value)*100, 2) as dim_score,
               COUNT(a.value) as cnt
        FROM schools s
        JOIN answers a ON s.id = a.school_id
        JOIN questions q ON a.question_id = q.id
        WHERE {s_where}
        GROUP BY q.level1_name
        """,
        full_where_params,
    ).fetchall()

    dim_map = {r["level1_name"]: float(r["dim_score"]) for r in dim_rows}
    dimensions_out = []
    dim_radar = {}
    for d_name in STANDARD_DIMENSIONS:
        sc = dim_map.get(d_name, 0.0)
        dimensions_out.append({
            "dimension": d_name,
            "score": sc,
            "weight": round(1.0 / len(STANDARD_DIMENSIONS), 4),
            "conclusion": f"区域均分 {sc} 分",
        })
        dim_radar[d_name] = sc

    # 5. 分层结构统计 (按相对分层)
    # 计算优(≥20)、良(15~20)、中(10~15)、起步(<10)
    tiers = [
        {"tier": "优秀梯队 (≥20分)", "min": 20.0, "max": 999.0, "count": 0},
        {"tier": "良好梯队 (15~20分)", "min": 15.0, "max": 20.0, "count": 0},
        {"tier": "平稳发展 (10~15分)", "min": 10.0, "max": 15.0, "count": 0},
        {"tier": "薄弱待建 (<10分)", "min": 0.0, "max": 10.0, "count": 0},
    ]
    for s in scores:
        for t in tiers:
            if t["min"] <= s < t["max"] or (s == t["max"] and t["max"] == 999.0):
                t["count"] += 1
                break

    for t in tiers:
        t["pct"] = f"{(t['count'] / len(scores) * 100):.1f}%"

    # 6. Top 5 与 Bottom 5 学校
    top_schools = [
        {
            "rank": idx + 1,
            "id": r["id"],
            "school_name": r["school_name"],
            "school_type": r["school_type"] or "中小学",
            "score": r["avg_score"],
            "avg_score": r["avg_score"],
            "total_score": r["avg_score"],
        }
        for idx, r in enumerate(school_scores_rows[:5])
    ]

    bottom_schools = [
        {
            "rank": len(school_scores_rows) - idx,
            "id": r["id"],
            "school_name": r["school_name"],
            "school_type": r["school_type"] or "中小学",
            "score": r["avg_score"],
            "avg_score": r["avg_score"],
            "total_score": r["avg_score"],
        }
        for idx, r in enumerate(reversed(school_scores_rows[-5:]))
    ]

    # 7. 寻找优势与短板维度
    sorted_dims = sorted(dim_map.items(), key=lambda x: x[1], reverse=True)
    strongest_dim = sorted_dims[0] if sorted_dims else ("-", 0)
    weakest_dim = sorted_dims[-1] if sorted_dims else ("-", 0)

    conn.close()

    result = {
        "object_type": "region",
        "region_name": reg["full_name"],
        "short_name": reg["name"],
        "region_type": reg["region_type"],
        "school_years": [active_year],
        "all_years": all_years,
        "school_count": school_count,
        "total_score": avg_score,
        "max_score": max_score,
        "min_score": min_score,
        "median_score": median_score,
        "strongest_dim": f"{strongest_dim[0]}（{strongest_dim[1]}分）",
        "weakest_dim": f"{weakest_dim[0]}（{weakest_dim[1]}分）",
        "dimensions": dimensions_out,
        "radar_data": dim_radar,
        "tiers": tiers,
        "top_schools": top_schools,
        "bottom_schools": bottom_schools,
        "data_coverage": 1.0,
        "overall_confidence": 1.0,
        "conclusion": (
            f"{reg['full_name']} 在 {active_year} 年共有 {school_count} 所中小学校纳入数字化监测评估，"
            f"区域数字化综合均分为 **{avg_score} 分**（最高分 {max_score} 分，最低分 {min_score} 分）。"
            f"其中相对优势维度为【{strongest_dim[0]}】（{strongest_dim[1]}分），"
            f"最主要的发展短板为【{weakest_dim[0]}】（{weakest_dim[1]}分）。"
        ),
    }
    return result


def query_school_ranking(
    school_keyword_or_id: Any,
    region_keyword: Optional[str] = None,
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """查询某所学校在所属区县或指定区域内的数字化综合排位、百分位及与区域均值对比。"""
    from scripts.school_engine import find_schools, get_school

    school = None
    if isinstance(school_keyword_or_id, int) or (
        isinstance(school_keyword_or_id, str) and school_keyword_or_id.isdigit()
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
    active_year = str(school.get("year") or year or "2023")

    # 确定对比区域
    reg = None
    if region_keyword:
        reg = detect_region(region_keyword)
    if not reg:
        if school.get("district"):
            reg = detect_region(school["district"])
        elif school.get("city"):
            reg = detect_region(school["city"])

    if not reg:
        return {"error": f"学校「{school_name}」档案缺少所属区县或地市信息，无法计算区域排位"}

    where_sql = reg["where_sql"]
    where_params = reg["where_params"]
    s_where = f"({where_sql.replace('city', 's.city').replace('district', 's.district').replace('province', 's.province')}) AND s.year=?"
    full_where_params = where_params + (active_year,)

    conn = connect()

    # 1. 区域内所有学校得分排行榜
    school_scores_rows = conn.execute(
        f"""
        SELECT s.id, s.school_name, s.school_type,
               ROUND(AVG(a.normalized_value)*100, 2) as avg_score
        FROM schools s
        JOIN answers a ON s.id = a.school_id
        WHERE {s_where}
        GROUP BY s.id
        ORDER BY avg_score DESC
        """,
        full_where_params,
    ).fetchall()

    if not school_scores_rows:
        conn.close()
        return {"error": f"区域「{reg['name']}」在 {active_year} 年无有效作答记录"}

    total_schools = len(school_scores_rows)
    all_scores = [float(r["avg_score"]) for r in school_scores_rows if r["avg_score"] is not None]
    region_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    target_rank = None
    target_score = None
    for idx, r in enumerate(school_scores_rows):
        if r["id"] == school_id:
            target_rank = idx + 1
            target_score = float(r["avg_score"])
            break

    if target_rank is None:
        conn.close()
        return {
            "error": f"学校「{school_name}」在 {active_year} 年尚未录入有效作答，无法在区域「{reg['name']}」中计算排位"
        }

    top_pct = round(target_rank / total_schools * 100, 1)
    beat_pct = round((total_schools - target_rank) / total_schools * 100, 1)
    diff_from_avg = round(target_score - region_avg, 2)

    # 2. 该校六维得分 vs 区域六维均分
    school_dim_rows = conn.execute(
        """
        SELECT q.level1_name, ROUND(AVG(a.normalized_value)*100, 2) as dim_score
        FROM answers a
        JOIN questions q ON a.question_id = q.id
        WHERE a.school_id = ?
        GROUP BY q.level1_name
        """,
        (school_id,),
    ).fetchall()
    school_dim_map = {r["level1_name"]: float(r["dim_score"]) for r in school_dim_rows}

    reg_dim_rows = conn.execute(
        f"""
        SELECT q.level1_name, ROUND(AVG(a.normalized_value)*100, 2) as dim_score
        FROM schools s
        JOIN answers a ON s.id = a.school_id
        JOIN questions q ON a.question_id = q.id
        WHERE {s_where}
        GROUP BY q.level1_name
        """,
        full_where_params,
    ).fetchall()
    reg_dim_map = {r["level1_name"]: float(r["dim_score"]) for r in reg_dim_rows}

    dim_comparison = []
    radar_school = {}
    radar_region = {}
    for d_name in STANDARD_DIMENSIONS:
        sc_s = school_dim_map.get(d_name, 0.0)
        sc_r = reg_dim_map.get(d_name, 0.0)
        radar_school[d_name] = sc_s
        radar_region[d_name] = sc_r
        d_diff = round(sc_s - sc_r, 2)
        dim_comparison.append({
            "dimension": d_name,
            "school_score": sc_s,
            "region_avg": sc_r,
            "diff": d_diff,
            "is_lead": d_diff >= 0,
        })

    # 3. 取目标校前后各 2 所临近学校展示梯度
    start_idx = max(0, target_rank - 3)
    end_idx = min(total_schools, target_rank + 2)
    peer_schools = [
        {
            "rank": i + 1,
            "id": school_scores_rows[i]["id"],
            "school_name": school_scores_rows[i]["school_name"],
            "school_type": school_scores_rows[i]["school_type"],
            "score": school_scores_rows[i]["avg_score"],
            "is_target": school_scores_rows[i]["id"] == school_id,
        }
        for i in range(start_idx, end_idx)
    ]

    conn.close()

    lead_str = f"高于全区均分 +{diff_from_avg} 分" if diff_from_avg >= 0 else f"低于全区均分 {diff_from_avg} 分"

    return {
        "object_type": "school_ranking",
        "school_id": school_id,
        "school_name": school_name,
        "school_years": [active_year],
        "year": active_year,
        "region_name": reg["full_name"],
        "short_name": reg["name"],
        "region_type": reg["region_type"],
        "rank": target_rank,
        "total_schools": total_schools,
        "top_pct": top_pct,
        "beat_pct": beat_pct,
        "percentile": top_pct,
        "total_score": target_score,
        "region_avg": region_avg,
        "diff": diff_from_avg,
        "direct_answer": (
            f"**{school_name}** 在 {reg['full_name']} {active_year} 年共 {total_schools} 所监测学校中综合排位为 **第 {target_rank} 名**"
            f"（位列全区前 **{top_pct}%**，超越全区 **{beat_pct}%** 的学校）。"
            f"该校综合得分 **{target_score} 分**，{lead_str}（全区均分为 {region_avg} 分）。"
        ),
        "dimensions_comparison": dim_comparison,
        "radar_data": radar_school,
        "radar_region_data": radar_region,
        "peer_schools": peer_schools,
        "data_coverage": 1.0,
        "overall_confidence": 1.0,
        "disclaimer": "本排名基于区域全量中小学在国家/省数字化问卷官方填报作答折算均分，供教育视导与学校定位参考。",
    }

