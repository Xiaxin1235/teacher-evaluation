# -*- coding: utf-8 -*-
"""EducationalChartBuilder · 教育评估可视化代码专家生成器。

为各类评估场景生成结构优雅、带完整中文标注的 Matplotlib Python 脚本：
1. build_radar_code: 多维能力雷达图（支持单实体与双线对比）；
2. build_ranking_code: 区域梯队排位与基准线对照条形图；
3. build_equipment_fact_code: 办学规模与终端设备客观指标横纵对比图；
4. build_region_macro_code: 区域宏观大盘（多维能力雷达 + 顶尖标杆校排行榜）。
"""

import json
from typing import Dict, List, Optional, Tuple


class EducationalChartBuilder:
    """教育数字化评估图表 Python 脚本生成器。"""

    @staticmethod
    def build_radar_code(
        title: str,
        dimensions: List[str],
        values: List[float],
        comp_title: Optional[str] = None,
        comp_values: Optional[List[float]] = None,
        max_val: Optional[float] = None,
    ) -> str:
        """生成极坐标多维雷达图代码。"""
        dims_json = json.dumps(dimensions, ensure_ascii=False)
        vals_json = json.dumps([round(float(v), 2) for v in values])
        comp_vals_json = json.dumps([round(float(v), 2) for v in comp_values]) if comp_values else "None"
        comp_title_str = repr(comp_title) if comp_title else "None"

        # 动态计算雷达图上限刻度
        all_vals = list(values) + (list(comp_values) if comp_values else [])
        highest = max(all_vals) if all_vals else 20.0
        ceil_val = max_val or (round(highest * 1.25) if highest > 10 else 20.0)

        return f'''# 绘制多维数字化能力雷达图
import numpy as np
import matplotlib.pyplot as plt

dimensions = {dims_json}
values = {vals_json}
comp_values = {comp_vals_json}
comp_title = {comp_title_str}

N = len(dimensions)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
# 闭合曲线
angles_closed = angles + angles[:1]
vals_closed = values + values[:1]

fig, ax = plt.subplots(figsize=(6.5, 5.5), subplot_kw=dict(polar=True), dpi=160)
ax.set_theta_offset(np.pi / 2)
ax.set_theta_direction(-1)

# 设置刻度网格
plt.xticks(angles, dimensions, size=11, weight='bold', color='#201f1d')
ax.set_rlabel_position(0)
ax.set_ylim(0, {ceil_val})
plt.yticks(color='#6f6c65', size=9)

# 主体数据线
ax.plot(angles_closed, vals_closed, color='#c96442', linewidth=2.2, linestyle='solid', label='评估得分')
ax.fill(angles_closed, vals_closed, color='#c96442', alpha=0.25)
ax.scatter(angles, values, color='#c96442', s=45, zorder=5)

# 对比参考线（如全区均值）
if comp_values and len(comp_values) == N:
    comp_closed = comp_values + comp_values[:1]
    lbl = comp_title or '全区基准均值'
    ax.plot(angles_closed, comp_closed, color='#d97706', linewidth=1.8, linestyle='--', label=lbl)
    ax.fill(angles_closed, comp_closed, color='#d97706', alpha=0.12)
    ax.scatter(angles, comp_values, color='#d97706', s=30, zorder=4)

ax.grid(color='#e8e6df', linestyle='--', linewidth=0.8, alpha=0.8)
ax.spines['polar'].set_color('#dedbd2')
plt.title('{title}', size=14, weight='bold', pad=22, color='#201f1d')
plt.legend(loc='upper right', bbox_to_anchor=(1.22, 1.12), frameon=True, facecolor='#ffffff', edgecolor='#e8e6df', fontsize=10)
plt.tight_layout()
print(f"雷达图生成完成：涵盖 {{N}} 个维度")
'''

    @staticmethod
    def build_ranking_code(
        title: str,
        school_name: str,
        target_score: float,
        region_avg: float,
        peer_schools: List[Dict[str, any]],
        rank: int,
        total_schools: int,
    ) -> str:
        """生成区域学校排位梯队水平对比条形图。"""
        # 准备数据：提取临近梯队校名和得分
        names = []
        scores = []
        is_target_list = []

        for p in peer_schools:
            names.append(p.get("school_name", "未知学校"))
            scores.append(round(float(p.get("score", 0.0)), 2))
            is_target_list.append(bool(p.get("is_target", False)))

        # 若目标校不在梯队里，补充进去
        if not any(is_target_list):
            names.insert(0, school_name)
            scores.insert(0, round(float(target_score), 2))
            is_target_list.insert(0, True)

        names_json = json.dumps(names, ensure_ascii=False)
        scores_json = json.dumps(scores)
        is_target_repr = repr(is_target_list)

        return f'''# 绘制区域学校排位梯队横向对比图
import matplotlib.pyplot as plt
import numpy as np

names = {names_json}
scores = {scores_json}
is_targets = {is_target_repr}
region_avg = {round(float(region_avg), 2)}

# 倒序排列使高分排在上方
names = names[::-1]
scores = scores[::-1]
is_targets = is_targets[::-1]

y_pos = np.arange(len(names))
colors = ['#c96442' if t else '#dedbd2' for t in is_targets]

fig, ax = plt.subplots(figsize=(7.2, max(4.0, len(names) * 0.55)), dpi=160)
bars = ax.barh(y_pos, scores, color=colors, height=0.55, edgecolor='none')

# 标注全区均值参考线
ax.axvline(region_avg, color='#d97706', linestyle='--', linewidth=1.5, alpha=0.9,
           label=f'全区均值 ({{region_avg}} 分)')

# 柱顶数值标签
for bar, score, is_t in zip(bars, scores, is_targets):
    w = bar.get_width()
    txt = f" {{score}}分" + (" (当前学校)" if is_t else "")
    fcolor = '#c96442' if is_t else '#6f6c65'
    fweight = 'bold' if is_t else 'normal'
    ax.text(w + 0.15, bar.get_y() + bar.get_height()/2, txt,
            va='center', ha='left', color=fcolor, weight=fweight, fontsize=10)

ax.set_yticks(y_pos)
ax.set_yticklabels(names, fontsize=10.5, color='#201f1d')
ax.set_xlabel('数字化综合得分', fontsize=11, color='#6f6c65')
ax.set_title('{title}\\n(第 {rank} 名 / 全区共 {total_schools} 所)', fontsize=13.5, weight='bold', pad=14, color='#201f1d')

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#dedbd2')
ax.spines['bottom'].set_color('#dedbd2')
ax.grid(axis='x', color='#f0eee8', linestyle='--', alpha=0.8)

# 动态扩展 x 轴留出标签空间
max_s = max(scores + [region_avg])
ax.set_xlim(0, max_s * 1.25)
ax.legend(loc='lower right', frameon=True, facecolor='#ffffff', edgecolor='#e8e6df', fontsize=10)
plt.tight_layout()
print("排位梯队对比柱状图生成完毕")
'''

    @staticmethod
    def build_equipment_fact_code(
        school_name: str,
        metric_name: str,
        target_value: float,
        unit: str,
        context_facts: List[Dict[str, any]],
        history: Optional[List[Dict[str, any]]] = None,
    ) -> str:
        """生成具体指标事实与办学规模对比柱状图/折线图。"""
        # 整合要对比的几项核心指标
        labels = [metric_name]
        values = [float(target_value)]

        for c in context_facts[:4]:
            lbl = c.get("label", "")
            val_str = str(c.get("value", "0"))
            # 提取纯数字
            num = ""
            for ch in val_str:
                if ch.isdigit() or ch == '.':
                    num += ch
                elif num:
                    break
            if num:
                labels.append(lbl)
                values.append(float(num))

        labels_json = json.dumps(labels, ensure_ascii=False)
        values_json = json.dumps(values)

        # 检查是否有跨年度历史
        hist_years = []
        hist_vals = []
        if history and len(history) > 1:
            for h in history:
                y = h.get("year")
                v = h.get("value")
                if y and v is not None:
                    v_str = str(v)
                    num = ""
                    for ch in v_str:
                        if ch.isdigit() or ch == '.':
                            num += ch
                        elif num:
                            break
                    if num:
                        try:
                            val_f = float(num)
                            hist_years.append(str(y))
                            hist_vals.append(val_f)
                        except (ValueError, TypeError):
                            pass

        hist_years_json = json.dumps(hist_years)
        hist_vals_json = json.dumps(hist_vals)

        return f'''# 绘制学校设备配置指标与关联规模图
import matplotlib.pyplot as plt
import numpy as np

labels = {labels_json}
values = {values_json}
hist_years = {hist_years_json}
hist_vals = {hist_vals_json}

has_hist = len(hist_years) > 1

if has_hist:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.5), dpi=160)
else:
    fig, ax1 = plt.subplots(1, 1, figsize=(6.8, 4.5), dpi=160)
    ax2 = None

# 图1：核心指标与办学配置
x_pos = np.arange(len(labels))
bar_colors = ['#c96442'] + ['#e2ded5'] * (len(labels) - 1)
bars = ax1.bar(x_pos, values, color=bar_colors, width=0.55, edgecolor='none')

for bar, val in zip(bars, values):
    h = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, h + (max(values)*0.02 or 0.5),
             f"{{int(val) if val.is_integer() else val}}",
             ha='center', va='bottom', fontsize=10.5, weight='bold', color='#201f1d')

ax1.set_xticks(x_pos)
ax1.set_xticklabels(labels, rotation=15, ha='right', fontsize=9.5, color='#201f1d')
ax1.set_title('{school_name}\\n指标核查与规模概况', fontsize=12.5, weight='bold', pad=12, color='#201f1d')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_color('#dedbd2')
ax1.spines['bottom'].set_color('#dedbd2')
ax1.grid(axis='y', color='#f0eee8', linestyle='--', alpha=0.8)
ax1.set_ylim(0, max(values) * 1.18 if max(values) > 0 else 10)

# 图2（若有跨年）：历史演进走势
if ax2 and has_hist:
    ax2.plot(hist_years, hist_vals, color='#c96442', marker='o', linewidth=2.2, markersize=7, label='{metric_name}')
    for y, v in zip(hist_years, hist_vals):
        ax2.text(y, v + (max(hist_vals)*0.03 or 0.5), f"{{int(v) if v.is_integer() else v}}",
                 ha='center', va='bottom', fontsize=10, weight='bold', color='#c96442')
    ax2.set_title('历史跨年度演进监测', fontsize=12.5, weight='bold', pad=12, color='#201f1d')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_color('#dedbd2')
    ax2.spines['bottom'].set_color('#dedbd2')
    ax2.grid(color='#f0eee8', linestyle='--', alpha=0.8)
    ax2.set_ylim(0, max(hist_vals) * 1.25 if max(hist_vals) > 0 else 10)

plt.tight_layout()
print("指标事实与配置规模图表生成完成")
'''

    @staticmethod
    def build_region_macro_code(
        region_name: str,
        year: str,
        total_score: float,
        school_count: int,
        dimension_scores: Dict[str, float],
        top_schools: List[Dict[str, any]],
    ) -> str:
        """生成区域宏观双联综合图：左侧五维能力雷达，右侧顶尖学校排行榜。"""
        dims = list(dimension_scores.keys())
        dim_vals = [round(float(v), 2) for v in dimension_scores.values()]

        # 顶尖学校
        top_n = min(len(top_schools), 6)
        school_names = [s.get("school_name", "") for s in top_schools[:top_n]][::-1]
        def _get_school_score(item: dict) -> float:
            for k in ("score", "avg_score", "total_score"):
                v = item.get(k)
                if v is not None:
                    try:
                        return round(float(v), 2)
                    except (ValueError, TypeError):
                        pass
            return 0.0
        school_scores = [_get_school_score(s) for s in top_schools[:top_n]][::-1]

        dims_json = json.dumps(dims, ensure_ascii=False)
        dim_vals_json = json.dumps(dim_vals)
        school_names_json = json.dumps(school_names, ensure_ascii=False)
        school_scores_json = json.dumps(school_scores)

        max_dim = max(dim_vals) if dim_vals else 10.0
        ceil_dim = round(max_dim * 1.25) if max_dim > 10 else 20.0

        return f'''# 绘制区域宏观双联综合图：五维能力雷达 + 顶尖领跑学校榜
import matplotlib.pyplot as plt
import numpy as np

dimensions = {dims_json}
dim_vals = {dim_vals_json}
school_names = {school_names_json}
school_scores = {school_scores_json}

fig = plt.figure(figsize=(11.5, 5.2), dpi=160)

# 子图1：五维能力雷达
ax1 = plt.subplot(1, 2, 1, polar=True)
N = len(dimensions)
if N > 0:
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles_closed = angles + angles[:1]
    vals_closed = dim_vals + dim_vals[:1]

    ax1.set_theta_offset(np.pi / 2)
    ax1.set_theta_direction(-1)
    plt.xticks(angles, dimensions, size=10.5, weight='bold', color='#201f1d')
    ax1.set_ylim(0, {ceil_dim})
    plt.yticks(color='#6f6c65', size=8.5)

    ax1.plot(angles_closed, vals_closed, color='#c96442', linewidth=2.2, linestyle='solid')
    ax1.fill(angles_closed, vals_closed, color='#c96442', alpha=0.25)
    ax1.scatter(angles, dim_vals, color='#c96442', s=45, zorder=5)
    ax1.grid(color='#e8e6df', linestyle='--', linewidth=0.8, alpha=0.8)
    ax1.spines['polar'].set_color('#dedbd2')
ax1.set_title('{region_name} 数字化能力五维均值', fontsize=12.5, weight='bold', pad=18, color='#201f1d')

# 子图2：区域顶尖标杆校排行榜
ax2 = plt.subplot(1, 2, 2)
if school_names:
    y_pos = np.arange(len(school_names))
    bars = ax2.barh(y_pos, school_scores, color='#d97706', height=0.55, edgecolor='none', alpha=0.9)

    for bar, score in zip(bars, school_scores):
        w = bar.get_width()
        ax2.text(w + 0.15, bar.get_y() + bar.get_height()/2, f" {{score}}分",
                 va='center', ha='left', color='#d97706', weight='bold', fontsize=10)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(school_names, fontsize=10, color='#201f1d')
    ax2.set_xlabel('数字化综合得分', fontsize=10.5, color='#6f6c65')
    ax2.set_title('区域数字化领跑标杆学校 TOP', fontsize=12.5, weight='bold', pad=14, color='#201f1d')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_color('#dedbd2')
    ax2.spines['bottom'].set_color('#dedbd2')
    ax2.grid(axis='x', color='#f0eee8', linestyle='--', alpha=0.8)
    if school_scores and max(school_scores) > 0:
        ax2.set_xlim(0, max(school_scores) * 1.25)
    else:
        ax2.set_xlim(0, 30)

plt.suptitle('{region_name} · {year}年区域数字化全景透视 (参评学校共 {school_count} 所，大盘均分 {total_score}分)',
             fontsize=13.5, weight='bold', y=0.98, color='#201f1d')
plt.tight_layout(rect=[0, 0, 1, 0.95])
print("区域宏观综合透视图生成完成")
'''
