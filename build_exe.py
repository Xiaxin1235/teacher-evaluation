#!/usr/bin/env python
"""构建 Windows 可分发目录 dist/TeacherEval/（onedir）。

用法：
  python build_exe.py

产物：
  dist/TeacherEval/TeacherEval.exe
  dist/TeacherEval/_internal/          运行库 + 演示数据 + 真实 SQLite + Web
用法：
  TeacherEval.exe                      起服务并打开对话台
  TeacherEval.exe serve --port 8600
  TeacherEval.exe eval --teacher T001
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def build(name="TeacherEval"):
    vendor = os.path.join(ROOT, "vendor_pkgs")
    env = os.environ.copy()
    if os.path.isdir(vendor):
        env["PYTHONPATH"] = vendor + os.pathsep + env.get("PYTHONPATH", "")

    datas = [
        ("data/demo", "data/demo"),
        ("data/real/education_digitization.sqlite", "data/real"),
        ("evaluation_templates", "evaluation_templates"),
        ("apps/web", "apps/web"),
        ("packages/llm_gateway/providers.json", "packages/llm_gateway"),
    ]
    data_args = []
    for src, dst in datas:
        full = os.path.join(ROOT, src)
        if os.path.exists(full):
            data_args += ["--add-data", f"{full}{os.pathsep}{dst}"]
        else:
            print(f"[warn] 跳过缺失资源：{full}")

    hidden = [
        "packages.core.frozen_paths",
        "packages.core.authz",
        "packages.indicator_engine.calibration",
        "packages.agent.planner",
        "packages.agent.critic",
        "packages.agent.composer",
        "packages.agent.indicator_catalog",
        "packages.agent.router",
        "packages.agent.tools",
        "packages.agent.tools.base",
        "packages.agent.tools.python_runner",
        "packages.agent.tools.chart_builder",
        "packages.agent.tools.registry",
        "packages.agent.tools.orchestrator",
        "packages.llm_gateway.gateway",
        "scripts.indicator_engine",
        "scripts.school_engine",
        "scripts.fact_engine",
        "scripts.region_engine",
        "apps.api.main",
        "yaml",
        "certifi",
        "fastapi",
        "starlette",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "matplotlib",
        "matplotlib.pyplot",
    ]

    excludes = [
        "torch",
        "torchvision",
        "torchaudio",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--clean", "--noconfirm",
        "--name", name,
        "--console",
        "--paths", ROOT,
        "--paths", vendor,
        *[f"--hidden-import={h}" for h in hidden],
        *[f"--exclude-module={e}" for e in excludes],
        *data_args,
        os.path.join(ROOT, "run_app.py"),
    ]
    exe_dir = os.path.join(ROOT, "dist", name)
    keep_names = ("llm_config.json",)
    saved = {}
    for fn in keep_names:
        src = os.path.join(exe_dir, fn)
        if os.path.isfile(src):
            with open(src, "rb") as f:
                saved[fn] = f.read()
            print(f"[keep] 已暂存用户配置：{src}")

    print(">>", " ".join(cmd))
    subprocess.check_call(cmd, env=env)

    exe = os.path.join(exe_dir, f"{name}.exe")
    if os.path.isfile(exe):
        for fn, blob in saved.items():
            dst = os.path.join(exe_dir, fn)
            if not os.path.isfile(dst):
                with open(dst, "wb") as f:
                    f.write(blob)
                print(f"[keep] 已写回用户配置：{dst}")
        print(f"\n构建成功：{exe}")
        print(f"大小：{os.path.getsize(exe) / 1e6:.1f} MB（另含 _internal）")
        print("请关闭正在运行的旧 exe 后，使用新目录 dist/TeacherEval/TeacherEval.exe")
        print("API 配置保存在 %APPDATA%\\TeacherEval\\llm_config.json，重新打包不会删除。")
        return 0
    print("构建失败：未找到 exe")
    return 1


if __name__ == "__main__":
    sys.exit(build())
