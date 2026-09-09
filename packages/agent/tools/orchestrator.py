# -*- coding: utf-8 -*-
"""AgentToolOrchestrator · Agent 工具调用编排执行器。

职责：
1. 分析评估结果对象类型（微观事实/排位对比/区域宏观/整校评估/教师评估）；
2. 调度 EducationalChartBuilder 自动编写 Matplotlib 绘图脚本；
3. 调度 ToolRegistry / PythonInterpreterTool 执行代码并捕获高清图表物料；
4. 组装标准化的 tool_calls 轨迹与 charts 产物，无缝注入 API 报告。
"""

from typing import Any, Dict, List, Optional
from packages.agent.tools.chart_builder import EducationalChartBuilder
from packages.agent.tools.registry import default_registry


class AgentToolOrchestrator:
    """Agent 工具调用编排器。"""

    def __init__(self, registry=None):
        self.registry = registry or default_registry
        self.chart_builder = EducationalChartBuilder()

    def orchestrate_visualization(self, result: Dict[str, Any], question: Optional[str] = None) -> Dict[str, Any]:
        """对评估结果进行工具调用编排，自动生成 Python 作图任务并执行。

        返回:
          {
            "tool_calls": List[dict],
            "charts": List[dict],
          }
        """
        tool_calls = []
        charts = []

        overview = result.get("overview") or result
        obj_type = overview.get("object_type") or "teacher"

        code = ""
        chart_title = ""

        # 场景 1：学校微观指标客观事实（如平板电脑台数）
        if obj_type == "school_fact":
            school_name = overview.get("school_name") or "目标学校"
            metric_name = overview.get("metric_name") or "核查指标"
            val = overview.get("target_value") or 0
            unit = overview.get("unit") or "台"
            context_facts = result.get("context_facts") or []
            history = result.get("history") or []

            chart_title = f"{school_name} · {metric_name} 配置对比"
            code = self.chart_builder.build_equipment_fact_code(
                school_name=school_name,
                metric_name=metric_name,
                target_value=val,
                unit=unit,
                context_facts=context_facts,
                history=history,
            )

        # 场景 2：区域学校相对排位与综合对比
        elif obj_type == "school_ranking":
            school_name = overview.get("school_name") or "目标学校"
            target_score = overview.get("total_score") or 0.0
            region_avg = overview.get("region_avg") or 0.0
            peers = result.get("peer_schools") or []
            rank = overview.get("rank") or 1
            total_schools = overview.get("total_schools") or 1

            chart_title = f"{school_name} · 区域排位与梯队对比"
            code = self.chart_builder.build_ranking_code(
                title=chart_title,
                school_name=school_name,
                target_score=target_score,
                region_avg=region_avg,
                peer_schools=peers,
                rank=rank,
                total_schools=total_schools,
            )

        # 场景 3：区域宏观数字化评估（如武汉市、新兴区大盘）
        elif obj_type == "region":
            reg_name = overview.get("region_name") or "评估区域"
            years = overview.get("school_years") or result.get("school_years") or []
            year = str(overview.get("year") or (years[0] if years else "2021"))
            total_score = overview.get("total_score") or 0.0
            count = overview.get("school_count") or 0
            dims_dict = {}
            for d in result.get("dimensions", []):
                dims_dict[d.get("dimension", "")] = float(d.get("score", 0.0))

            top_schools = result.get("top_schools") or []
            chart_title = f"{reg_name} · 区域宏观数字化综合透视"
            code = self.chart_builder.build_region_macro_code(
                region_name=reg_name,
                year=year,
                total_score=total_score,
                school_count=count,
                dimension_scores=dims_dict,
                top_schools=top_schools,
            )

        # 场景 4：整校数字化综合评估 或 教师多维评估
        else:
            name = overview.get("school_name") or overview.get("teacher_id") or "评估对象"
            tid = overview.get("teacher_id")
            if tid:
                teacher_alias = {"T001": "张老师", "T002": "李老师", "T003": "王老师", "T004": "赵老师"}.get(tid, "")
                if teacher_alias:
                    name = f"教师 {tid}（{teacher_alias}）"
            dims = []
            vals = []
            for d in result.get("dimensions", []):
                score = d.get("score")
                if score is not None and not d.get("is_redline"):
                    try:
                        vals.append(float(score))
                        dims.append(d.get("dimension", ""))
                    except (ValueError, TypeError):
                        pass

            chart_title = f"{name} · 教学业务与能力多维雷达图" if tid else f"{name} · 数字化能力多维雷达图"
            if dims and vals:
                code = self.chart_builder.build_radar_code(
                    title=chart_title,
                    dimensions=dims,
                    values=vals,
                )

        # 若生成了有效的作图代码，则调用本地 python_interpreter 工具执行
        if code:
            tool_res = self.registry.call(
                "python_interpreter",
                code=code,
                chart_title=chart_title,
            )
            tool_calls.append(tool_res.to_dict())
            if tool_res.artifacts:
                charts.extend(tool_res.artifacts)

        return {
            "tool_calls": tool_calls,
            "charts": charts,
        }


# 全局编排器单例
orchestrator = AgentToolOrchestrator()


def get_orchestrator() -> AgentToolOrchestrator:
    return orchestrator
