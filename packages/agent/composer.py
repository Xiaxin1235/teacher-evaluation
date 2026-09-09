"""M08 · 证据合成器（Composer）：结果 + 证据 → 严谨可读报告。

每维度输出：
  - 结论句（含内联证据引用 [证据: source | period | formula]）
  - 缺口披露（gap 显式列出）
  - 低置信/小样本 → 只给"趋势性提示"，不给硬结论
红线 → 显著提示，不参与评分。
固定免责声明："辅助参考材料，供评审委员会人工复核使用"（考核性 R4）。
两种出口：render_markdown() / render_json()。
"""

import json
from typing import Dict, List, Optional


def _fmt_evidence(e: dict) -> str:
    label = e.get("label") or e.get("metric", "指标依据")
    period = e.get("period")
    if isinstance(period, (list, tuple)):
        period_str = ", ".join(str(p) for p in period)
    else:
        period_str = str(period or "")
    formula = str(e.get("formula", "")).strip()
    if period_str and formula:
        return f"[证据: {label} | 学年: {period_str} | {formula}]"
    elif period_str:
        return f"[证据: {label} | 学年: {period_str}]"
    return f"[证据: {label} | {formula}]"


def _dimension_conclusion(d: dict) -> str:
    """单维度叙事（不带维度名前缀，渲染层统一加）。score=None → 数据缺口；低置信 → 趋势提示。"""
    if d.get("is_redline"):
        if d.get("flagged"):
            return "已触发红线标记，本维度不参与评分，转独立人事流程。"
        return "未触发红线标记。"

    score = d.get("score")
    conf = d.get("confidence")
    if score is None:
        gaps = "；".join(d.get("gap", [])) or "数据缺失"
        return f"数据不足以支持结论，无数据支撑（缺口：{gaps}）。"
    # 低置信/小样本 → 趋势性提示
    if conf is not None and conf < 0.5:
        return f"仅作趋势性提示（置信度 {conf} 偏低，样本或覆盖不足），参考值约 {score} 分。"
    return f"得分 {score} 分（置信度 {conf}）。"


def compose(result: dict, evidence: Optional[List[dict]] = None) -> dict:
    """输入评估结果（M02/M07 结构），输出统一报告 dict。

    证据优先级：result.dimensions[*].evidence > 外部 evidence 参数。
    """
    evidence = evidence or []
    dims = result.get("dimensions", [])
    ev_by_dim = {id(d): d.get("evidence", []) for d in dims}
    # 外部证据作为兜底（同名维度合并）
    for e in evidence:
        pass  # 保留扩展点；当前从维度内取证据

    sections = []
    for d in dims:
        conclusion = _dimension_conclusion(d)
        ev_list = ev_by_dim.get(id(d), d.get("evidence", []))
        refs = [_fmt_evidence(e) for e in ev_list]
        sec = {
            "dimension": d.get("dimension"),
            "is_redline": bool(d.get("is_redline")),
            "conclusion": conclusion,
            "score": d.get("score"),
            "confidence": d.get("confidence"),
            "evidence_refs": refs,
            "gaps": d.get("gap", []),
        }
        sections.append(sec)

    redline = bool(result.get("redline_flagged"))

    # 相对最弱维度提示（仅在有 ≥2 个可比维度时；低置信维度排除，避免误导）
    comparable = [s for s in sections
                  if not s["is_redline"] and s["score"] is not None
                  and (s["confidence"] or 0) >= 0.5]
    weakest = min(comparable, key=lambda s: s["score"]) if len(comparable) >= 2 else None

    # 多学年趋势提示（仅列周期与总分，不做无据推断；单周期则无趋势段）
    years = result.get("school_years") or []
    obj_type = result.get("object_type") or "teacher"

    # 1. 区域宏观报告
    if obj_type == "region":
        return {
            "title": f"区域数字化宏观评估报告 · {result.get('region_name')}",
            "overview": {
                "object_type": "region",
                "region_name": result.get("region_name"),
                "short_name": result.get("short_name"),
                "school_years": years,
                "school_count": result.get("school_count"),
                "total_score": result.get("total_score"),
                "max_score": result.get("max_score"),
                "min_score": result.get("min_score"),
                "median_score": result.get("median_score"),
                "strongest_dim": result.get("strongest_dim"),
                "weakest_dim": result.get("weakest_dim"),
                "conclusion": result.get("conclusion"),
                "data_coverage": 1.0,
                "overall_confidence": 1.0,
            },
            "radar_data": result.get("radar_data", {}),
            "dimensions": result.get("dimensions", []),
            "sections": result.get("dimensions", []),
            "tiers": result.get("tiers", []),
            "top_schools": result.get("top_schools", []),
            "bottom_schools": result.get("bottom_schools", []),
            "disclaimer": "本报告由区域全量中小学数字化作答数据统计聚合生成，仅供教育行政主管部门决策参考。",
        }

    # 2. 具体指标事实报告
    if obj_type == "school_fact":
        return {
            "title": f"学校指标事实查询 · {result.get('school_name')}",
            "overview": {
                "object_type": "school_fact",
                "school_name": result.get("school_name"),
                "school_id": result.get("school_id"),
                "school_years": years,
                "province": result.get("province"),
                "city": result.get("city"),
                "district": result.get("district"),
                "school_type": result.get("school_type"),
                "metric_name": result.get("metric_name"),
                "target_value": result.get("target_value"),
                "unit": result.get("unit"),
                "normalized_score": result.get("normalized_score"),
                "question_id": result.get("question_id"),
                "question_content": result.get("question_content"),
                "dimension": result.get("dimension"),
                "direct_answer": result.get("direct_answer"),
                "total_score": result.get("normalized_score"),
                "data_coverage": 1.0,
                "overall_confidence": 1.0,
            },
            "direct_answer": result.get("direct_answer"),
            "context_facts": result.get("context_facts", []),
            "history": result.get("history", []),
            "sections": [],
            "disclaimer": "本数据源自学校在国家/省级教育数字化问卷的官方填报作答库，供核查参考。",
        }

    # 2.5 学校区域排位与对比报告
    if obj_type == "school_ranking":
        return {
            "title": f"学校区域数字化排位与对比 · {result.get('school_name')}",
            "overview": {
                "object_type": "school_ranking",
                "school_name": result.get("school_name"),
                "school_id": result.get("school_id"),
                "school_years": years,
                "region_name": result.get("region_name"),
                "short_name": result.get("short_name"),
                "region_type": result.get("region_type"),
                "rank": result.get("rank"),
                "total_schools": result.get("total_schools"),
                "top_pct": result.get("top_pct"),
                "beat_pct": result.get("beat_pct"),
                "percentile": result.get("percentile"),
                "total_score": result.get("total_score"),
                "region_avg": result.get("region_avg"),
                "diff": result.get("diff"),
                "direct_answer": result.get("direct_answer"),
                "data_coverage": 1.0,
                "overall_confidence": 1.0,
            },
            "direct_answer": result.get("direct_answer"),
            "dimensions_comparison": result.get("dimensions_comparison", []),
            "radar_data": result.get("radar_data", {}),
            "radar_region_data": result.get("radar_region_data", {}),
            "peer_schools": result.get("peer_schools", []),
            "sections": [],
            "disclaimer": "本排名基于区域全量中小学在国家/省数字化问卷官方填报作答折算均分，供教育视导与学校定位参考。",
        }

    # 3. 学校或教师综合评估报告
    is_school = obj_type == "school"
    subject = "该校" if is_school else "该教师"
    report = {
        "title": (
            "学校数字化评估报告（辅助参考材料）"
            if is_school else "教师评估报告（辅助参考材料）"
        ),
        "overview": {
            "teacher_id": result.get("teacher_id"),
            "teacher_dept": result.get("teacher_dept"),
            "school_name": result.get("school_name"),
            "school_years": years,
            "template": result.get("template"),
            "total_score": result.get("total_score"),
            "overall_confidence": result.get("overall_confidence"),
            "data_coverage": result.get("data_coverage"),
            "redline_flagged": redline,
            "object_type": obj_type,
        },
        "trend_note": (
            f"趋势提示：本报告覆盖 {len(years)} 个学年（{'、'.join(str(y) for y in years)}）；"
            "跨学年趋势结论需逐周期单独评估后对比，本报告不做外推。" if len(years) >= 2 else None),
        "weakest_note": (
            f"相对最弱维度：{weakest['dimension']}（{weakest['score']} 分，"
            f"相对{subject}其他已覆盖维度而言，非全样本排名）。" if weakest else None),
        "sections": sections,
        "calibration": result.get("calibration"),
        "disclaimer": "本报告为辅助参考材料，供评审委员会人工复核使用；"
                      "不构成人事裁决的独立依据（考核性 R4）。",
    }
    return report


def render_json(result: dict, evidence: Optional[List[dict]] = None) -> str:
    return json.dumps(compose(result, evidence), ensure_ascii=False, indent=2)


def render_markdown(result: dict, evidence: Optional[List[dict]] = None) -> str:
    r = compose(result, evidence)
    o = r["overview"]
    obj_type = o.get("object_type")

    # 1. 区域报告
    if obj_type == "region":
        lines = [
            f"# {r['title']}",
            "",
            f"**监测地区**：{o['region_name']}　**监测学年**：{', '.join(o['school_years'])}　**监测校总数**：{o['school_count']} 所",
            "",
            f"- 区域综合均分：**{o['total_score']} 分**（最高分 {o['max_score']} 分，最低分 {o['min_score']} 分，中位数 {o['median_score']} 分）",
            f"- 优势维度：**{o['strongest_dim']}**　薄弱短板：**{o['weakest_dim']}**",
            "",
            "## 核心结论",
            "",
            o.get("conclusion") or "",
            "",
            "## 分维度均分表现",
            "",
        ]
        for d in r.get("dimensions", []):
            lines.append(f"- **{d['dimension']}**：{d.get('score')} 分")
        lines.extend([
            "",
            "## 标杆示范学校 (Top 5)",
            "",
        ])
        for s in r.get("top_schools", []):
            lines.append(f"{s['rank']}. **{s['school_name']}**（{s['school_type']}）· **{s['score']} 分**")
        lines.extend([
            "",
            "## 免责声明",
            "",
            r["disclaimer"],
            "",
        ])
        return "\n".join(lines)

    # 2. 事实报告
    if obj_type == "school_fact":
        lines = [
            f"# {r['title']}",
            "",
            f"**学校**：{o['school_name']}（{o['province']}/{o['city']}/{o['district']}）　**学年**：{', '.join(o['school_years'])}",
            "",
            f"### 核心事实",
            f"> **{o['direct_answer']}**",
            "",
            "### 关联规模与配置背景",
            "",
        ]
        for c in r.get("context_facts", []):
            lines.append(f"- **{c['label']}**：{c['value']}")
        if r.get("history"):
            lines.extend([
                "",
                "### 历史配置记录",
                "",
            ])
            for h in r.get("history"):
                lines.append(f"- **{h['year']} 年**：{h['value']}")
        lines.extend([
            "",
            "## 免责声明",
            "",
            r["disclaimer"],
            "",
        ])
    # 2.5 学校区域排位报告
    if obj_type == "school_ranking":
        lines = [
            f"# {r['title']}",
            "",
            f"**学校**：{o['school_name']}　**对比区域**：{o['region_name']}　**学年**：{', '.join(o['school_years'])}",
            "",
            "### 核心排位结论",
            f"> **{o['direct_answer']}**",
            "",
            f"- 区域综合排位：**第 {o['rank']} 名** / 共 {o['total_schools']} 所学校（位居全区前 {o['top_pct']}%）",
            f"- 该校数字化均分：**{o['total_score']} 分**　全区均分：**{o['region_avg']} 分**（分差 {o['diff']:+0.2f} 分）",
            "",
            "### 六大维度与区域均值对照",
            "",
        ]
        for dc in r.get("dimensions_comparison", []):
            lead_tag = "领先" if dc.get("is_lead") else "落后"
            lines.append(f"- **{dc['dimension']}**：该校 {dc['school_score']} 分 vs 区域均分 {dc['region_avg']} 分（{lead_tag} {dc['diff']:+0.2f} 分）")
        if r.get("peer_schools"):
            lines.extend([
                "",
                "### 梯队临近学校参考",
                "",
            ])
            for ps in r.get("peer_schools"):
                star = " ★ (本校)" if ps.get("is_target") else ""
                lines.append(f"{ps['rank']}. **{ps['school_name']}**（{ps['school_type']}）· {ps['score']} 分{star}")
        lines.extend([
            "",
            "## 免责声明",
            "",
            r["disclaimer"],
            "",
        ])
        return "\n".join(lines)

    # 3. 教师/学校综合评估
    if o.get('object_type') == 'school':
        header_target = f"学校：{o.get('school_name')}"
    else:
        tid = o.get('teacher_id') or "教师"
        alias = {"T001": "张老师", "T002": "李老师", "T003": "王老师", "T004": "赵老师"}.get(tid, "")
        header_target = f"教师：{tid}（{alias} · {o.get('teacher_dept') or '任课组'}）" if alias else f"教师：{tid}（{o.get('teacher_dept') or ''}）"
    lines = [
        f"# {r['title']}",
        "",
        f"{header_target}　"
        f"评估学年：{', '.join(o['school_years'] or [])}　模板：{o.get('template') or ''}",
        "",
        f"- 综合得分：**{o['total_score']}**　数据覆盖率：{o['data_coverage']}　综合置信度：{o['overall_confidence']}",
    ]
    if o.get("redline_flagged"):
        lines += ["", "> ⚠️ **红线标记已触发**：本报告总分不参与评分，请转独立人事流程。"]

    if r.get("trend_note"):
        lines += ["", f"> {r['trend_note']}"]
    if r.get("weakest_note"):
        lines += ["", f"> {r['weakest_note']}"]

    lines += ["", "## 分维度结论", ""]
    for s in r["sections"]:
        lines.append(f"- **{s['dimension']}**：{s['conclusion']}")
        for ref in s.get("evidence_refs", []):
            lines.append(f"  - {ref}")
        if s.get("gaps"):
            lines.append(f"  - 缺口：{ '；'.join(s['gaps']) }")
        lines.append("")

    lines += ["", "## 免责声明", "", r["disclaimer"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    # 最小拼接 demo：直接消费 M02 结果
    import os, sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from scripts.indicator_engine import evaluate_teacher, load_yaml
    from packages.indicator_engine.calibration import attach_calibration
    res = evaluate_teacher("T003", ["2023-2024", "2024-2025"], load_yaml("2025-2026_v1"))
    attach_calibration(res, group_col="dept_id")
    print(render_markdown(res))