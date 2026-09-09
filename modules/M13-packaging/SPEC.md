# M13 · 单文件 exe 打包（PyInstaller）

> 状态：`done`（与 modules/registry.json 同步）　依赖：M09, M10

## 目标
把整个项目（评估引擎 + Agent 编排 + API + Web 对话台 + 演示数据）打包成可双击运行的 exe，让**不装 Python 也能用**。

## 已交付
- `run_app.py` —— exe 入口（三种模式：默认起服务+开浏览器 / `serve` 只起服务 / `eval` 命令行评估）
- `build_exe.py` —— 一键构建脚本
- `packages/core/frozen_paths.py` —— frozen 环境路径适配（`_MEIPASS` 只读资源 vs exe 旁可写输出）
- `dist/TeacherEval/TeacherEval.exe` —— **产物（onedir 模式）**

## 产物用法（分发给用户）
```
TeacherEval.exe                # 双击：起本地 API + 自动打开对话台（http://127.0.0.1:8600）
TeacherEval.exe serve          # 只起服务
TeacherEval.exe eval --teacher T001          # 命令行直接评估，输出报告
TeacherEval.exe eval --teacher T003 --json-out
```

## 关键决策（构建 exe 前必读）
1. **用 onedir 而非 onefile**：onefile 启动时把整个包解压到系统临时目录，在受限环境/杀软下常报
   `Failed to create parent directory structure`；onedir 直接运行 exe + 旁侧 `_internal`，不预解压，
   稳定得多。产物是一个 `TeacherEval\` 文件夹（exe + _internal），整文件夹发给用户即可。
2. **路径三态**：
   - `resource_root()`：只读资源（演示数据/模板/Web 页面）→ frozen 读 `_MEIPASS`/`_internal`，源码读仓库根；
   - `app_dir()`：可写输出（评估 JSON 报告）→ frozen 为 exe 所在目录；
   - `output_dir()`：`app_dir()/output`，自动建目录。
3. **依赖装到 `vendor_pkgs/`**（本机 `--user` 写 Roaming 被策略拦截，`--target` 到工作区绕开）；
   构建时 `--paths vendor_pkgs` 让 PyInstaller 能发现 fastapi/uvicorn/pyinstaller 本体。
4. **PyInstaller 隐式 import**：`uvicorn.*`、`packages.*`、`scripts.indicator_engine` 都列了
   `--hidden-import`，防止打包时追踪不到。

## 验收（已通过）
```bash
dist/TeacherEval/TeacherEval.exe eval --teacher T001     # 输出完整报告（83.88 分 + 证据 + 弱点提示）
# serve 模式：/health 200、/api/v1/chat 200、/ 200（Web 页面挂载）
```

## 边界
- onedir 产物不是"单文件"而是"文件夹 + exe"，体积约 60MB（含 _internal 运行库）；
  如必须压缩成单文件，在无此环境限制的机器上改用 `--onefile`（构建脚本两处开关）。
- 演示数据内嵌，用户无需任何外部文件；真实学校数据接入见 README §六。
- 重新构建：`python build_exe.py`（需先保证 fastapi/uvicorn/pyinstaller 可导入）。