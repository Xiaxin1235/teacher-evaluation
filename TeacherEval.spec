# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/teacher evaluation/run_app.py'],
    pathex=['D:/teacher evaluation', 'D:/teacher evaluation/vendor_pkgs'],
    binaries=[],
    datas=[('D:/teacher evaluation/data/demo', 'data/demo'), ('D:/teacher evaluation/data/real/education_digitization.sqlite', 'data/real'), ('D:/teacher evaluation/evaluation_templates', 'evaluation_templates'), ('D:/teacher evaluation/apps/web', 'apps/web'), ('D:/teacher evaluation/packages/llm_gateway/providers.json', 'packages/llm_gateway')],
    hiddenimports=['packages.core.frozen_paths', 'packages.core.authz', 'packages.indicator_engine.calibration', 'packages.agent.planner', 'packages.agent.critic', 'packages.agent.composer', 'packages.agent.indicator_catalog', 'packages.agent.router', 'packages.agent.tools', 'packages.agent.tools.base', 'packages.agent.tools.python_runner', 'packages.agent.tools.chart_builder', 'packages.agent.tools.registry', 'packages.agent.tools.orchestrator', 'packages.llm_gateway.gateway', 'scripts.indicator_engine', 'scripts.school_engine', 'scripts.fact_engine', 'scripts.region_engine', 'apps.api.main', 'yaml', 'certifi', 'fastapi', 'starlette', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on', 'matplotlib', 'matplotlib.pyplot'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TeacherEval',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TeacherEval',
)
