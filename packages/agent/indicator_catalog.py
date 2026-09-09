"""83 题数字化问卷指标目录与智能同义词匹配器。

将自然语言中的硬件配置、教学软件、人员培训等词汇映射到具体的问卷题号或学校属性。
支持：
- 精确同义词/关键词匹配
- 教师端与学生端区分（如教师平板 vs 学生平板）
- 复合指标定义（如生机比、师机比、终端总量）
- 题面通用全文检索（TF-IDF / 分词重合度）
"""

import re
from typing import Dict, List, Optional, Tuple, Any

# 常用预置指标规则：(正则或关键词列表, 目标题号, 单位, 维度说明, 关联题号)
PRESET_RULES: List[Dict[str, Any]] = [
    # 教师平板电脑
    {
        "keys": ["教师平板", "老师平板", "教师用平板", "老师的平板", "给老师配置.*平板", "教师.*ipad", "老师.*ipad"],
        "qid": 70,
        "unit": "台",
        "name": "学校统一配备的教师用平板电脑数量",
        "related": [67, 68, 69, 66],
    },
    # 学生平板电脑
    {
        "keys": ["学生平板", "学生用平板", "学生的平板", "给学生配置.*平板", "学生.*ipad"],
        "qid": 66,
        "unit": "台",
        "name": "学校统一配备的学生用平板电脑数量",
        "related": [63, 64, 65, 70],
    },
    # 教师台式机
    {
        "keys": ["教师台式", "老师台式", "教师用台式", "老师.*台式电脑", "教师电脑"],
        "qid": 67,
        "unit": "台",
        "name": "学校统一配备的教师用台式机数量",
        "related": [68, 69, 70],
    },
    # 学生台式机
    {
        "keys": ["学生台式", "学生用台式", "机房电脑", "计算机教室电脑", "学生电脑"],
        "qid": 63,
        "unit": "台",
        "name": "学校统一配备的学生用台式机数量",
        "related": [64, 65, 66],
    },
    # 教师笔记本电脑
    {
        "keys": ["教师笔记本", "老师笔记本", "教师用笔记本", "老师.*笔记本电脑"],
        "qid": 69,
        "unit": "台",
        "name": "学校统一配备的教师用笔记本电脑数量",
        "related": [67, 68, 70],
    },
    # 学生笔记本电脑
    {
        "keys": ["学生笔记本", "学生用笔记本"],
        "qid": 65,
        "unit": "台",
        "name": "学校统一配备的学生用笔记本数量",
        "related": [63, 64, 66],
    },
    # 教师移动终端
    {
        "keys": ["教师移动终端", "老师移动终端"],
        "qid": 68,
        "unit": "台",
        "name": "学校统一配备的教师用移动终端数量",
        "related": [67, 69, 70],
    },
    # 学生移动终端
    {
        "keys": ["学生移动终端"],
        "qid": 64,
        "unit": "台",
        "name": "学校统一配备的学生用移动终端数量",
        "related": [63, 65, 66],
    },
    # 网络带宽
    {
        "keys": ["带宽", "网速", "网络出口", "出口带宽", "网络总带宽", "校园网速", "mbps"],
        "qid": 60,
        "unit": "Mbps",
        "name": "学校网络出口总带宽",
        "related": [20],
    },
    # 无线网络覆盖
    {
        "keys": ["无线网络", "wifi", "wi-fi", "无线覆盖", "无线网"],
        "qid": 20,
        "unit": "",
        "name": "学校无线网络覆盖情况",
        "related": [60],
    },
    # 班级教室数与多媒体设备
    {
        "keys": ["交互式多媒体", "一体机", "电子白板", "多媒体设备教室", "多媒体教室数"],
        "qid": 62,
        "unit": "间",
        "name": "含有交互式多媒体设备的教室数",
        "related": [61, 17],
    },
    {
        "keys": ["班级教室数", "普通教室", "教室总数"],
        "qid": 61,
        "unit": "间",
        "name": "学校班级教室数",
        "related": [62],
    },
    {
        "keys": ["多媒体教室使用率", "多媒体使用率", "多媒体教室平均使用率"],
        "qid": 17,
        "unit": "%",
        "name": "多媒体教室平均使用率",
        "related": [62],
    },
    # 三个课堂
    {
        "keys": ["三个课堂", "专递课堂", "名师课堂", "名校网络课堂"],
        "qid": 5,
        "unit": "个",
        "name": "学校开展的三个课堂应用数量",
        "related": [6, 46, 47],
    },
    {
        "keys": ["专递课堂课时", "主讲教室课时", "专递课堂.*课时"],
        "qid": 46,
        "unit": "课时/周",
        "name": "专递课堂本学期平均每周主讲教室开课课时数",
        "related": [47, 5],
    },
    # 教师培训
    {
        "keys": ["校本培训", "信息化培训次数", "校本研修"],
        "qid": 41,
        "unit": "次",
        "name": "学校组织的信息化校本培训次数",
        "related": [42, 43, 56],
    },
    {
        "keys": ["培训覆盖率", "校本培训覆盖", "培训覆盖教师比例"],
        "qid": 43,
        "unit": "",
        "name": "学校组织的信息化校本培训覆盖教师比例",
        "related": [41, 56],
    },
    # 教师晒课
    {
        "keys": ["晒课", "一师一优课", "晒课数量", "云平台晒课"],
        "qid": 45,
        "unit": "堂",
        "name": "学校教师在教育云平台中晒课数量",
        "related": [1],
    },
    # 机考与在线考试
    {
        "keys": ["机考", "在线考试", "在线测评", "机考学科"],
        "qid": 49,
        "unit": "个",
        "name": "学校近一年已开展机考在线考试的学科数",
        "related": [50],
    },
    # 人工智能课程
    {
        "keys": ["人工智能课程", "ai课程", "人工智能课"],
        "qid": 13,
        "unit": "",
        "name": "学校人工智能课程开设形式",
        "related": [14],
    },
    # 一卡通
    {
        "keys": ["一卡通", "校园卡"],
        "qid": 25,
        "unit": "种",
        "name": "校园卡(含一卡通)已经实现的功能种数",
        "related": [26],
    },
    # 经费投入
    {
        "keys": ["经费投入", "信息化经费", "信息化投入占比", "经费占比"],
        "qid": 31,
        "unit": "%",
        "name": "信息化经费总计投入占同期教育总经费支出比例",
        "related": [32, 33, 34, 35, 36, 48],
    },
    # 信息技术教师
    {
        "keys": ["信息技术老师", "信息技术教师", "计算机老师", "微机老师"],
        "qid": 38,
        "unit": "人",
        "name": "学校信息技术课程教师人数",
        "related": [39, 80, 81],
    },
    # 数字化管理与专职技术人员
    {
        "keys": ["数字化工作人员", "数字化人员", "专任数字化", "网络管理员", "网管"],
        "qid": 80,
        "unit": "人",
        "name": "学校数字化工作部门专任工作人员总数",
        "related": [81, 38],
    },
    # 智能学习空间 / 智慧教室 / 录播教室
    {
        "keys": ["智能学习空间", "智慧教室", "录播教室", "创客教室", "录播室"],
        "qid": 18,
        "unit": "间",
        "name": "学校建有的智能学习空间总数",
        "related": [19, 53, 62],
    },
    # 校园安防监控
    {
        "keys": ["安防监控", "校园监控", "摄像头", "安全监控系统"],
        "qid": 27,
        "unit": "种",
        "name": "学校安全监控系统校园覆盖范围",
        "related": [55],
    },
    # 数字化管理规章制度
    {
        "keys": ["数字化制度", "规章制度", "管理办法", "管理制度"],
        "qid": 82,
        "unit": "",
        "name": "学校是否制定数字化工作和管理的相关制度规章",
        "related": [79, 80],
    },
    # 配套数字资源学科数
    {
        "keys": ["数字资源", "配套资源", "资源库", "教材配套"],
        "qid": 1,
        "unit": "个",
        "name": "拥有与教材完整配套数字教育资源的学科数量",
        "related": [9, 10],
    },
    # 教师教学常态化应用学科数
    {
        "keys": ["辅助课堂教学", "常态化应用", "信息技术教学"],
        "qid": 2,
        "unit": "个",
        "name": "利用信息技术辅助课堂教学实现常态化应用的学科数量",
        "related": [4, 59],
    },
    # 教师数字素养 / 开展教学教师比例
    {
        "keys": ["教师数字素养", "开展教学的教师比例", "开展教学的学科教师比例"],
        "qid": 4,
        "unit": "",
        "name": "能够利用信息技术开展教学的学科教师比例",
        "related": [56, 59],
    },
]

# 复合计算指标定义（例如“生机比”、“师机比”、“终端总数”）
COMPOUND_METRICS: Dict[str, Dict[str, Any]] = {
    "生机比": {
        "name": "学生机生比（生均计算机台数）",
        "desc": "在校生总数与学生用各类计算机终端总数（台式+移动+笔记本+平板）的比值",
        "qids": [63, 64, 65, 66],
        "school_field": "student_num",
        "formula": "student_num / (Q63 + Q64 + Q65 + Q66)",
        "unit": "人/台",
    },
    "师机比": {
        "name": "教师机师比（师均计算机台数）",
        "desc": "专任教师用各类终端总数（台式+移动+笔记本+平板）与教师总数的比值",
        "qids": [67, 68, 69, 70],
        "school_field": "teacher_num",
        "formula": "(Q67 + Q68 + Q69 + Q70) / teacher_num",
        "unit": "台/人",
    },
    "学生终端总量": {
        "name": "学生用终端总数",
        "desc": "包括学生用台式机、移动终端、笔记本、平板电脑总和",
        "qids": [63, 64, 65, 66],
        "unit": "台",
    },
    "教师终端总量": {
        "name": "教师用终端总数",
        "desc": "包括教师用台式机、移动终端、笔记本电脑、平板电脑总和",
        "qids": [67, 68, 69, 70],
        "unit": "台",
    },
}

# 学校基础属性关键词映射
SCHOOL_FIELD_KEYWORDS: Dict[str, Tuple[str, str]] = {
    "教师人数": ("teacher_num", "人"),
    "老师人数": ("teacher_num", "人"),
    "专任教师": ("teacher_num", "人"),
    "学生人数": ("student_num", "人"),
    "在校生": ("student_num", "人"),
    "学生总数": ("student_num", "人"),
    "班级数": ("class_num", "个"),
    "班级总数": ("class_num", "个"),
    "城乡类型": ("school_area_type", ""),
    "办学性质": ("school_type", ""),
    "学段": ("school_type", ""),
}


def _search_indicator_fallback(text: str) -> Optional[Dict[str, Any]]:
    """若预置规则未命中，对 83 题题库进行语义分词倒排检索。"""
    try:
        from scripts.school_engine import connect
        conn = connect()
        # 提取有意义中文片段
        stop = {"学校", "老师", "学生", "多少", "具体", "配置", "建设", "情况", "水平", "怎么样", "如何", "数字化", "有无", "是否", "几个", "几种", "有没有"}
        tokens = [t for t in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text) if t not in stop]
        if not tokens:
            conn.close()
            return None
        rows = conn.execute("SELECT id, content, level1_name, level2_name FROM questions").fetchall()
        best_score = 0
        best_row = None
        for r in rows:
            c = (r["content"] or "") + " " + (r["level2_name"] or "")
            score = sum(len(t) * (2 if t in r["content"] else 1) for t in tokens if t in c)
            if score > best_score:
                best_score = score
                best_row = r
        conn.close()
        if best_row and best_score >= 4:
            return {
                "type": "question",
                "qid": best_row["id"],
                "name": best_row["content"],
                "unit": "项" if "多少" in best_row["content"] else "",
                "related": [],
            }
    except Exception:
        pass
    return None


def match_indicator(text: str) -> Optional[Dict[str, Any]]:
    """从文本中检测用户询问的具体指标。

    返回值结构：
    - type: "question" | "compound" | "school_field"
    - qid: int (单题时)
    - qids: list (复合题时)
    - field: str (学校属性时)
    - name: str
    - unit: str
    - related: list
    """
    clean = text.lower().replace("？", "").replace("?", "").strip()

    # 1. 检查复合指标
    for c_name, c_conf in COMPOUND_METRICS.items():
        if c_name in clean:
            return {"type": "compound", "compound_key": c_name, **c_conf}

    # 2. 检查基础属性
    for k, (f, u) in SCHOOL_FIELD_KEYWORDS.items():
        if k in clean:
            return {"type": "school_field", "field": f, "name": k, "unit": u}

    # 3. 检查预置规则（正则/关键词）
    for r in PRESET_RULES:
        for k in r["keys"]:
            if re.search(k, clean):
                return {
                    "type": "question",
                    "qid": r["qid"],
                    "name": r["name"],
                    "unit": r.get("unit", ""),
                    "related": r.get("related", []),
                }

    # 4. 泛化：若提到“平板电脑”但未区分师生，优先给教师平板，附带学生平板
    if "平板" in clean or "ipad" in clean:
        return {
            "type": "question",
            "qid": 70,
            "name": "学校统一配备的教师用平板电脑数量",
            "unit": "台",
            "related": [66, 67, 69],
        }

    # 5. 全库 83 题智能语义检索兜底
    fallback = _search_indicator_fallback(clean)
    if fallback:
        return fallback

    return None
