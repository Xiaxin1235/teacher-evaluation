# 智能教育数字化与教师评估 Agent 平台 (TeacherEval)

> **定位**：面向教育行政主管部门、督导评估机构及学校管理者的**智能多意图对话评估与分析平台**。
> 平台结合**百万级真实作答数据库**、**可追溯确定性规则引擎**、**自主 Python 绘图工具链（Agent Code Interpreter）** 与 **多大模型智能解读网关**，实现：**提问自由开放、事实精确可溯、图表动态生成、诊断深度智能**。

---

## 目录
- [一、核心特色与设计原则](#一核心特色与设计原则)
- [二、核心功能矩阵](#二核心功能矩阵)
- [三、系统架构与数据流转](#三系统架构与数据流转)
- [四、快速上手与使用指南](#四快速上手与使用指南)
  - [方式 1：独立可执行版（免安装，双击即用）](#方式-1独立可执行版免安装双击即用推荐)
  - [方式 2：Python 源码开发运行](#方式-2python-源码开发运行)
  - [方式 3：命令行 CLI 模式](#方式-3命令行-cli-模式)
- [五、典型对话提问范例](#五典型对话提问范例)
- [六、代码库与模块布局](#六代码库与模块布局)
- [七、数据安全与考核合规底线](#七数据安全与考核合规底线)

---

## 一、核心特色与设计原则

```
用户自由提问 ────────► 意图路由器 (Router)
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
① 微观设备事实       ② 区域宏观大盘       ③ 学校排位对比 / 教师评估
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             ▼
             底层真实数据库 (SQLite 150万+作答数据)
                             │
                             ▼
            Agent 编排器 (Tool Orchestrator)
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
   Python 绘图解释器                       大模型诊断网关
 (Matplotlib 动态高清图表)               (政策建议 / 容错自愈)
        │                                         │
        └────────────────────┬────────────────────┘
                             ▼
                极简现代化 Web 交互台
```

1. **确定性数字 vs 生成式语言解耦（数字绝不幻觉）**：
   * 所有学校得分、指标数值、排名位次、梯队分布与图表数据，**100% 由本地 SQLite 真实数据库计算生成**；
   * 大模型仅基于经过严格校验的事实证据提供宏观政策建议与研判说明，**严禁大模型捏造篡改任何数字**。
2. **现代 Agent 工具调用架构（In-Process Code Interpreter）**：
   * 采用类似 Advanced Data Analysis 模式，Agent 根据查询场景自主生成专业 Python 绘图脚本并执行；
   * 采用**进程内安全沙箱**，不依赖宿主机系统命令，打包移植到任何未安装 Python 的陌生电脑依然 100% 正常绘图；
   * 前端直接内嵌超清矢量图表（支持放大与下载），并提供**可折叠的 Python 代码透视抽屉**，直观展示 Agent 绘图源码与运行耗时。
3. **智能多轮对话与代词消解**：
   * 具备上下文实体记忆槽位，支持自然语言多轮追问与指代消解（如第一轮问某校设备，第二轮追问“那它在区里排第几名？”、“它的数字化水平呢？”，系统自动继承目标学校与评测年份）。
4. **大模型网关韧性与自愈机制**：
   * 兼容 OpenAI、DeepSeek、通义千问、Kimi、Grok 等多种主流协议；
   * 针对外部中转站偶发的 `502/503/504`、`Upstream service temporarily unavailable`，底层具备 3 次阶梯式退避自动重试；
   * 前端设计了优雅降级提示卡片与**「重新解读 ↻」**按钮，网络中断时核心数据图表毫发无损，恢复后可一键无刷新重新唤起大模型。

---

## 二、核心功能矩阵

| 功能板块 | 支持场景与提问方式 | 底层支撑能力 |
|---|---|---|
| **① 微观设备事实核查** | *“七台河市新兴区罗泉学校给老师配置了多少台平板电脑？”*<br>*“武汉市蔡甸区横龙小学有几间计算机网络教室？”* | 跨年份题库映射、师生配置比测算、历年跨学年增长折线图 + 配置横向对比图 |
| **② 区域数字化宏观大盘** | *“湖北省 2021 数字化大盘怎么样？”*<br>*“武汉市的数字化水平怎么样？”* | 省/市/区县三级自适应聚合、六大维度综合得分、优良中差梯队分布、Top 5 标杆示范校与 Bottom 5 帮扶校名单、双联全景透视图 |
| **③ 区域相对排位与对比** | *“新兴区罗泉学校在区里排第几名？”*<br>*“某某学校在全省处于什么位置？”* | 区域全量学校百分位排位、超越全区比例、分维度领先/落后差值分析、高亮梯队阶梯条形图 |
| **④ 整校数字化深度评估** | *“罗泉学校数字化水平怎么样？”*<br>*“某学校六个维度表现如何？”* | 覆盖“数字资源、教育教学、数字素养、基础设施、教育治理、保障机制”六大维度多轴雷达图 |
| **⑤ 教师多维教学与人事评估** | *“评估张老师 2024-2025 学年的教学水平”*<br>*支持在简介查询页按教师直接检索* | 教学设计、课堂听课、及格率增值、科研积分、学生评教等全中文证据链；**师德师风红线一票否决**（触发红线总分归零转独立人事流程） |
| **⑥ 个人与系统安全配置** | *多套模型 Profile 一键切换*<br>*本地无感保存* | 密钥存放在本机的 `%APPDATA%\TeacherEval\llm_config.json`，重新打包或移动程序绝不丢失配置 |

---

## 三、系统架构与数据流转

### 1. 业务数据层
- **核心数据库**：[`data/real/education_digitization.sqlite`](file:///d:/teacher%20evaluation/data/real/education_digitization.sqlite)（涵盖全国 37 万+所学校次、150 万+作答事实记录、标准化题库映射表）；
- **教师评估规范**：[`evaluation_templates/2025-2026_v1.yaml`](file:///d:/teacher%20evaluation/evaluation_templates/2025-2026_v1.yaml) 与模拟教师档案库。

### 2. 智能调度与工具层
- **意图路由与代词继承**：[`packages/agent/router.py`](file:///d:/teacher%20evaluation/packages/agent/router.py)
- **Agent 工具调用体系**：
  - 工具定义基类：[`packages/agent/tools/base.py`](file:///d:/teacher%20evaluation/packages/agent/tools/base.py)
  - 动态绘图脚本生成器：[`packages/agent/tools/chart_builder.py`](file:///d:/teacher%20evaluation/packages/agent/tools/chart_builder.py)
  - 进程内 Python 隔离执行器：[`packages/agent/tools/python_runner.py`](file:///d:/teacher%20evaluation/packages/agent/tools/python_runner.py)
  - 工具注册与编排中枢：[`packages/agent/tools/orchestrator.py`](file:///d:/teacher%20evaluation/packages/agent/tools/orchestrator.py)
- **多模型网关与重试器**：[`packages/llm_gateway/gateway.py`](file:///d:/teacher%20evaluation/packages/llm_gateway/gateway.py)

### 3. 用户交互层
- **Web 对话前端**：[`apps/web/index.html`](file:///d:/teacher%20evaluation/apps/web/index.html)（收敛为“对话台”、“简介查询”、“模型密钥” 3 大页面，初次登入不自动发起查询以节省用户 API 额度）；
- **后端服务**：[`apps/api/main.py`](file:///d:/teacher%20evaluation/apps/api/main.py)（基于 FastAPI，支持 REST API 与图表静态资源托管）。

---

## 四、快速上手与使用指南

### 方式 1：独立可执行版（免安装，双击即用，推荐）
适合直接分发或在无 Python 环境的 Windows 电脑上运行：

1. 打开目录 [`dist/TeacherEval/`](file:///d:/teacher%20evaluation/dist/TeacherEval/)；
2. 双击运行 **`TeacherEval.exe`**；
3. 系统将自动启动本地服务并调起默认浏览器访问 `http://127.0.0.1:8600`。

> **移植说明**：如果需要复制到其他电脑，只需将整个 `dist/TeacherEval` 文件夹复制过去即可。内嵌完整的 Python 3.12 虚拟环境、SQLite 数据库及所有依赖，**目标机完全不需要安装 Python**。

### 方式 2：Python 源码开发运行
适合开发者进行二次开发或调试：

```bash
# 1. 确保安装基础依赖
pip install -r apps/api/requirements.txt

# 2. 启动服务（自动打开浏览器）
python run_app.py

# 或仅以后台方式启动服务：
python run_app.py serve --port 8600 --no-browser
```

### 方式 3：命令行 CLI 模式
支持在终端直接进行评估计算与报告导出：

```bash
# 教师教学水平评估导出
python run_app.py eval --teacher T001
python run_app.py eval --teacher T003 --json-out

# 指定学校评估
python run_app.py eval --school "七台河市新兴区罗泉学校" --year 2021
```

---

## 五、典型对话提问范例

在系统前端的提问框中，您可以直接输入以下类型的自然语言问题：

### 1. 微观设备事实与办学规模
* `七台河市新兴区罗泉学校给老师配置了多少台平板电脑？`
* `横龙小学有多少台学生平板？`
* `罗泉学校有几台台式计算机？`

### 2. 区域数字化宏观大盘透视
* `湖北省 2021 数字化大盘怎么样？`
* `武汉市数字化水平怎么样？`
* `七台河市新兴区数字化水平如何？`

### 3. 区域相对排位与差距分析
* `七台河市新兴区罗泉学校在区里排第几名？`
* `黄梅县第一小学在全省排在什么位置？`

### 4. 连续多轮代词追问示例
```text
用户：七台河市新兴区罗泉学校给老师配置了多少台平板电脑？
系统：[给出 14 台数据，并自动绘制历年配置趋势图与设备规模对比图]

用户：那学生平板呢？
系统：[自动继承罗泉学校实体，回答配置 18 台，并刷新图表]

用户：它在区里排第几名？
系统：[自动识别“它”代表罗泉学校，输出在全区 10 所学校中排第 2 名，绘制排位阶梯图]

用户：它的数字化水平怎么样？
系统：[深入进行整校六维综合评估，输出多维能力雷达图]
```

---

## 六、代码库与模块布局

```text
teacher-evaluation/
├── apps/
│   ├── api/
│   │   ├── main.py              # FastAPI 核心服务接口（Chat、评估、图表下载）
│   │   └── requirements.txt     # 核心 Python 依赖
│   └── web/
│       └── index.html           # 现代化零构建响应式前端（对话台/简介查询/模型密钥）
├── data/
│   ├── demo/                    # 教师评估模拟脱敏数据
│   └── real/
│       └── education_digitization.sqlite  # 百万级真实学校数字化作答数据库
├── evaluation_templates/        # 评估维度配置（YAML 格式，定义权重与指标规则）
├── packages/
│   ├── agent/
│   │   ├── router.py            # 开放式多意图路由器与多轮代词消解中枢
│   │   ├── composer.py          # 证据合成器（格式化生成 Markdown 报告与事实卡片）
│   │   ├── critic.py            # 规则与合规性审查器
│   │   └── tools/               # 模块化 Agent 工具调用体系
│   │       ├── base.py          # 工具抽象基类与 ToolResult 规范
│   │       ├── chart_builder.py # 动态 Python 绘图代码生成专家
│   │       ├── python_runner.py # 进程内隔离 Python 解释器沙箱
│   │       ├── orchestrator.py  # 工具调用调度器
│   │       └── registry.py      # 工具注册表
│   ├── core/
│   │   ├── authz.py             # 角色权限与红线安全访问控制
│   │   └── frozen_paths.py      # PyInstaller 打包环境路径自适应解析
│   ├── indicator_engine/        # 评分校准、百分位与 z-score 统计校准
│   └── llm_gateway/
│       ├── gateway.py           # 多大模型统一网关（Bearer 鉴权、自动重试、密钥持久化）
│       └── providers.json       # 预设模型提供商配置
├── scripts/
│   ├── fact_engine.py           # 微观指标事实提取引擎
│   ├── region_engine.py         # 区域大盘统计与学校相对排位计算引擎
│   ├── school_engine.py         # 学校六维评估计算引擎
│   ├── indicator_engine.py      # 教师教学评估核心计算底座
│   ├── test_tools.py            # Agent 工具链自动化测试
│   └── test_multiturn.py        # 多轮对话与实体继承自动化测试
├── build_exe.py                 # PyInstaller 一键编译打包脚本
├── TeacherEval.spec             # 编译规范配置文件
└── README.md                    # 本文档
```

---

## 七、数据安全与考核合规底线

1. **真实数据真实呈现**：
   * 本系统严格遵守**“数据不编造、来源可查验、计算可追溯”**原则。
   * 所有报告均明确注明数据来源、统计年份、有效样本数与置信度。
2. **师德师风一票否决（红线机制）**：
   * 教师评估模块若触发师德师风红线（查实违法违纪或重大信访违规），系统将直接触发红线拦截，**总分不参与加权，强制转交人事纪检部门独立处理**。
3. **API 密钥本地化隔离**：
   * 用户在大模型设置界面填写的 API Key 仅保存在本机操作系统的用户个人应用数据目录（Windows: `%APPDATA%\TeacherEval\llm_config.json`）；
   * 密钥不上传、不入代码库，重新打包或分发程序时绝不会泄露任何个人凭证。