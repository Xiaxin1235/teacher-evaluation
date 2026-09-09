"""统一多意图与实体路由器 (Intent Router)。

将用户的开放式自然语言提问分流至对应的处理引擎：
1. INTENT_TEACHER_EVAL: 教师多维综合评估 (indicator_engine)
2. INTENT_SCHOOL_FACT:  具体指标事实问答 (fact_engine)
3. INTENT_REGION_EVAL:  区域数字化宏观评估 (region_engine)
4. INTENT_SCHOOL_EVAL:  整校多维综合评估 (school_engine)
5. INTENT_CLARIFY:      缺少必要实体，给出精准引导提示
"""

import re
from typing import Any, Dict, List, Optional

from packages.agent.indicator_catalog import match_indicator
from scripts.region_engine import detect_region

_TEACHER_RE = re.compile(r"\b(T\d{2,})\b")
_YEAR_RE = re.compile(r"20\d{2}-20\d{2}")
_CAL_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_SCHOOL_RE = re.compile(r"[\u4e00-\u9fff0-9A-Za-z]{2,40}(?:小学|中学|学校|幼儿园|学院|高中)")
_SCHOOL_ID_RE = re.compile(r"\b(?:S|学校|id:?)(\d{1,8})\b", re.I)


def _extract_years(text: str) -> List[str]:
    """从提问中提取学年或日历年。"""
    ranges = _YEAR_RE.findall(text)
    if ranges:
        return ranges
    cal = _CAL_YEAR_RE.findall(text)
    if cal:
        return cal
    # 宽泛时间识别
    if any(k in text for k in ("近三年", "近3年")):
        return ["2021", "2022", "2023"]
    if any(k in text for k in ("近两年", "近2年")):
        return ["2022", "2023"]
    return []


_RANKING_PATTERNS = [
    "排第几", "排名", "排位", "位次", "名次", "在区里", "在县里", "在市里",
    "全区平均", "全县平均", "全市平均", "平均水平相比", "对比全区", "对比全县",
]

_LEADERBOARD_PATTERNS = [
    "最好的学校", "标杆学校", "排名前", "前三", "前五", "前10", "前十",
    "排名靠前", "最薄弱", "最差的学校", "后五", "后三", "榜单",
]


def route_query(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """主路由函数：输入用户提问与上一轮上下文，输出意图与结构化参数。"""
    q_text = text.strip()
    years = _extract_years(q_text)
    active_year = years[0] if years else None

    ctx = context or {}
    last_school = ctx.get("last_school")
    last_region = ctx.get("last_region")
    last_teacher = ctx.get("last_teacher")
    last_year = ctx.get("last_year")
    if not active_year and last_year:
        active_year = last_year

    # 代词消解准备 (它、该校、该地区、该老师)
    has_school_pronoun = bool(re.search(r"(它|该校|这所学校|该学校|此校|该校的)", q_text))
    has_region_pronoun = bool(re.search(r"(该地区|该县|该区|该市|这个地区|这片区域)", q_text))
    has_teacher_pronoun = bool(re.search(r"(该教师|这位老师|该老师|他|她)", q_text))

    # 1. 判定教师提问 (T001 等或代词继承)
    teachers = _TEACHER_RE.findall(q_text)
    if teachers:
        return {
            "intent": "teacher_eval",
            "teacher_id": teachers[0],
            "years": years or ["2023-2024", "2024-2025"],
            "original": q_text,
        }
    if has_teacher_pronoun and last_teacher:
        return {
            "intent": "teacher_eval",
            "teacher_id": last_teacher,
            "years": years or ["2023-2024", "2024-2025"],
            "original": q_text,
        }

    # 2. 检查具体指标项匹配
    metric_info = match_indicator(q_text)

    # 3. 提取学校实体
    school_matches = [
        m for m in _SCHOOL_RE.findall(q_text)
        if not any(m.endswith(w) or m.startswith(w) for w in (
            "好的学校", "差的学校", "标杆学校", "所有学校", "全部学校", "薄弱学校",
            "哪些学校", "什么学校", "一所学校", "每个学校", "各学校", "该学校", "这所学校",
            "某学校", "的学校", "些学校", "类学校"
        ))
    ]
    school_ids = _SCHOOL_ID_RE.findall(q_text)
    target_school = None
    if school_matches:
        target_school = school_matches[0]
    elif school_ids:
        target_school = f"id:{school_ids[0]}"
    elif (has_school_pronoun or not target_school) and last_school:
        if has_school_pronoun or metric_info or any(p in q_text for p in _RANKING_PATTERNS):
            target_school = last_school

    # 4. 检查是否在询问学校排位 / 相对排名
    is_ranking = any(p in q_text for p in _RANKING_PATTERNS)
    if is_ranking:
        target_r_school = target_school or last_school
        if target_r_school:
            # 探测是否指定了对比区域
            reg_cand = detect_region(q_text)
            r_name = reg_cand["name"] if reg_cand else None
            return {
                "intent": "school_ranking",
                "school": target_r_school,
                "region": r_name,
                "year": active_year,
                "original": q_text,
            }

    # 5. 若检测到具体指标意图：
    if metric_info:
        if target_school:
            return {
                "intent": "school_fact",
                "school": target_school,
                "metric": metric_info,
                "year": active_year,
                "original": q_text,
            }
        else:
            return {
                "intent": "clarify",
                "missing": ["请指定具体的学校全名（例如：七台河市新兴区罗泉学校、长沙县成绩小学）"],
                "metric": metric_info,
                "original": q_text,
            }

    # 6. 检查是否在询问区域大盘或区域榜单
    region_info = detect_region(q_text)
    if not region_info and (has_region_pronoun or any(p in q_text for p in _LEADERBOARD_PATTERNS)) and last_region:
        region_info = detect_region(last_region)

    if region_info:
        if not target_school:
            return {
                "intent": "region_eval",
                "region": region_info["name"],
                "region_info": region_info,
                "year": active_year,
                "original": q_text,
            }

    # 7. 整校综合评估 (含代词追问继承)
    if target_school:
        return {
            "intent": "school_eval",
            "school": target_school,
            "years": [active_year] if active_year else [],
            "original": q_text,
        }

    # 8. 未能识别到任何实体
    missing = []
    if "地区" in q_text:
        missing.append("请补充具体地区名称（例如：长沙县、七台河市、湖南省等）")
    elif "学校" in q_text:
        missing.append("请补充具体学校名称（例如：长沙县成绩小学、罗泉学校等）")
    elif "老师" in q_text or "教师" in q_text:
        missing.append("请提供教师ID（例如：T001、T002）或学校名称")
    else:
        missing.append("未识别到查询对象。您可以自由提问：①微观配置（如：罗泉学校配置了多少台教师平板电脑？）；②区域大盘（如：长沙县2021数字化水平怎么样？）；③相对排名（如：罗泉学校在区里排第几？）；④整校评估（如：长沙县成绩小学2020数字化水平）")

    return {
        "intent": "clarify",
        "missing": missing,
        "original": q_text,
    }
