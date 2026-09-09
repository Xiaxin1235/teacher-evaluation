# -*- coding: utf-8 -*-
"""PythonInterpreterTool · 本地 Python 数据分析与绘图执行工具。

功能特性：
1. 类似市面上现代 Agent（Code Interpreter / Advanced Data Analysis）：
   - 支持动态执行 Python 代码，自动捕获标准输出与绘图生成物；
2. 绘图能力专精（Matplotlib / Seaborn / Pandas）：
   - 自动预配置中文字体（Microsoft YaHei, SimHei, DengXian），彻底杜绝方块乱码 (□□□)；
   - 注入契合前端 Claude 温暖极简美学的统一配色与画布样式；
   - 强制使用无头模式 ('Agg')，绝不弹出阻塞窗口；
3. 输出标准化：
   - 自动抓取当前所有活动 Figure，输出高分辨率 PNG；
   - 双通道交付：本地文件 (output/charts/<id>.png) + 内联 Base64 Data URI（保证内网穿透/离线秒开）；
   - 详细记录执行耗时、标准输出与工具调用轨迹。
"""

import base64
import contextlib
import io
import os
import sys
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from packages.agent.tools.base import BaseTool, ToolResult
from packages.core.frozen_paths import app_dir


def _charts_dir() -> str:
    """持久化图表存放目录：<app_dir>/output/charts/"""
    cdir = os.path.join(app_dir(), "output", "charts")
    os.makedirs(cdir, exist_ok=True)
    return cdir


class PythonInterpreterTool(BaseTool):
    """本地 Python 代码执行与绘图工具。"""

    name: str = "python_interpreter"
    description: str = (
        "本地 Python 解释器与作图工具。可执行包含 matplotlib、pandas、numpy 的数据分析与作图代码，"
        "自动捕获生成的图表并保存为高清图片，返回图表访问路径与 Base64 编码，用于在报告中直观呈现。"
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的完整 Python 代码。作图需使用 matplotlib.pyplot，无需额外配置字体和后端。",
            },
            "chart_title": {
                "type": "string",
                "description": "可选的图表意图或说明标签，如「学校五维能力雷达图」",
            },
        },
        "required": ["code"],
    }

    def execute(self, code: str, chart_title: Optional[str] = None, **kwargs) -> ToolResult:
        t0 = time.time()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        artifacts = []

        # 1. 预设安全与便利的执行环境
        env_globals: Dict[str, Any] = {
            "__name__": "__main__",
            "__builtins__": __builtins__,
        }

        # 尝试静默导入主流库至沙箱命名空间
        try:
            import numpy as np
            import pandas as pd
            import matplotlib
            matplotlib.use("Agg")  # 强制无头后台渲染
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm

            # 配置中文字体优先级
            plt.rcParams["font.sans-serif"] = [
                "Microsoft YaHei", "SimHei", "DengXian", "PingFang SC", "Hiragino Sans GB", "sans-serif"
            ]
            plt.rcParams["axes.unicode_minus"] = False

            # 配置美学风格：柔和网格、无杂边框、清晰字重
            plt.rcParams["figure.facecolor"] = "#ffffff"
            plt.rcParams["axes.facecolor"] = "#fdfcfb"
            plt.rcParams["axes.edgecolor"] = "#e8e6df"
            plt.rcParams["axes.linewidth"] = 0.8
            plt.rcParams["grid.color"] = "#f0eee8"
            plt.rcParams["grid.linestyle"] = "--"
            plt.rcParams["grid.alpha"] = 0.7
            plt.rcParams["text.color"] = "#201f1d"
            plt.rcParams["axes.labelcolor"] = "#201f1d"
            plt.rcParams["xtick.color"] = "#6f6c65"
            plt.rcParams["ytick.color"] = "#6f6c65"

            env_globals.update({
                "np": np,
                "pd": pd,
                "plt": plt,
                "matplotlib": matplotlib,
            })
            plt.close("all")  # 清空旧状态
        except Exception as e:
            stderr_buf.write(f"[warn] 绘图支持库预载入提示: {e}\n")

        # 2. 捕获重定向 stdout/stderr 并执行代码
        exec_err = None
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                # 预处理代码字符串，去除前后空白
                clean_code = code.strip()
                exec(clean_code, env_globals)
            except Exception as e:
                exec_err = e
                traceback.print_exc(file=stderr_buf)

        # 3. 收集并抽取 Matplotlib 生成的所有图表
        charts_saved = 0
        try:
            import matplotlib.pyplot as plt
            fig_nums = plt.get_fignums()
            if fig_nums:
                out_dir = _charts_dir()
                for fnum in fig_nums:
                    fig = plt.figure(fnum)
                    chart_id = f"chart_{uuid.uuid4().hex[:10]}"
                    filename = f"{chart_id}.png"
                    filepath = os.path.join(out_dir, filename)

                    # 导出高分辨率 PNG 文件
                    fig.savefig(filepath, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")

                    # 导出内存 Base64
                    img_buf = io.BytesIO()
                    fig.savefig(img_buf, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
                    img_buf.seek(0)
                    b64_str = base64.b64encode(img_buf.getvalue()).decode("ascii")
                    data_uri = f"data:image/png;base64,{b64_str}"

                    artifacts.append({
                        "id": chart_id,
                        "title": chart_title or f"图表 #{fnum}",
                        "type": "image/png",
                        "filename": filename,
                        "file_path": filepath,
                        "url": f"/api/v1/charts/{filename}",
                        "base64": data_uri,
                        "dpi": 160,
                    })
                    charts_saved += 1
                plt.close("all")
        except Exception as e:
            stderr_buf.write(f"[warn] 抽取图表产物失败: {e}\n")

        out_str = stdout_buf.getvalue()
        err_str = stderr_buf.getvalue()
        duration = (time.time() - t0) * 1000.0

        if charts_saved > 0:
            if not out_str:
                out_str = f"已成功生成 {charts_saved} 张高清图表（Matplotlib 160 DPI）。"
            else:
                out_str += f"\n[Agent] 已成功生成 {charts_saved} 张图表。"

        success = (exec_err is None)
        return ToolResult(
            tool_name=self.name,
            success=success,
            stdout=out_str.strip(),
            stderr=err_str.strip(),
            data={
                "code": code,
                "chart_title": chart_title,
                "charts_count": len(artifacts),
            },
            artifacts=artifacts,
            error=str(exec_err) if exec_err else None,
            duration_ms=duration,
        )
