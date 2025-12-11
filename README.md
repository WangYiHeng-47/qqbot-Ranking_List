# QQ群聊数据统计机器人

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/OneBot-V11-green.svg" alt="OneBot">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

一个基于 Python 异步编程的 QQ 群聊数据统计机器人，使用 OneBot V11 协议通过正向 WebSocket 连接 NapCatQQ。采用 Material Design 3 风格渲染精美的统计图表。

## ✨ 功能特性

### 📊 基础统计
- **消息统计** - 自动记录群聊消息，生成热词统计图
- **发言排行** - 统计群成员发言数量排行榜（显示头像和昵称）
- **活跃分析** - 生成 24 小时活跃度柱状图
- **图片归档** - 自动下载并去重存储群聊图片
- **文件记录** - 记录群文件上传元数据

### 📅 周期报告
- **周报** - 每周群聊数据汇总（热词、排行、趋势图）
- **月报** - 每月群聊数据汇总
- **定时推送** - 自动在指定时间推送日报/周报

### 👤 用户画像
- **个人画像** - 查看用户消息统计、活跃时段、个人词云
- **用户类型** - 智能识别夜猫子、早起鸟等用户类型
- **徽章系统** - 根据发言量和习惯授予特殊徽章

### 🧠 智能分析
- **情感分析** - 基于 SnowNLP 的群聊情感倾向分析
- **关键词提取** - TF-IDF 算法提取群聊热点话题
- **复读机检测** - 统计群内复读行为和参与者
- **撤回统计** - 记录和统计消息撤回行为

### 🎨 界面设计
- **MD3 风格** - Material Design 3 风格的精美图表
- **Jinja2 模板** - 灵活可定制的 HTML 模板系统
- **高性能渲染** - Playwright 浏览器上下文复用，提升渲染速度

## 📁 项目结构

```
qq-stat-bot/
├── config/
│   ├── __init__.py           # 配置模块初始化
│   ├── napcat.json           # NapCatQQ 连接配置
│   ├── napcat_example.json   # NapCatQQ 配置示例
│   ├── settings.py           # 机器人业务配置
│   └── settings_example.py   # 业务配置示例
├── data/
│   ├── db/                   # SQLite 数据库目录
│   ├── images/               # 图片存储目录
│   ├── fonts/                # 字体文件目录（可选）
│   └── logs/                 # 运行日志目录
├── lib/
│   ├── __init__.py           # 库模块初始化
│   ├── commands.py           # 命令注册系统（装饰器模式）
│   ├── db_manager.py         # 数据库管理模块
│   ├── async_utils.py        # 异步工具模块
│   ├── nlp_analyzer.py       # NLP 分析模块（情感/关键词/复读）
│   ├── renderer.py           # Jinja2 + Playwright 渲染器
│   ├── visualizer.py         # 数据可视化模块 (MD3 + Playwright)
│   └── protocol.py           # OneBot V11 协议解析模块
├── templates/
│   ├── base.html             # Jinja2 基础模板
│   ├── profile.html          # 用户画像模板
│   ├── sentiment.html        # 情感分析模板
│   ├── repeater.html         # 复读机报告模板
│   └── report.html           # 周报/月报模板
├── main.py                   # 程序主入口
├── requirements.txt          # Python 依赖清单
├── .gitignore                # Git 忽略规则
└── README.md                 # 项目说明文档
```

## 📋 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 推荐 3.11+ |
| NapCatQQ | 最新版 | OneBot V11 协议端 |
| Chromium | 自动安装 | Playwright 管理 |

## 🚀 快速开始

### 第一步：克隆项目

```bash
git clone https://github.com/WangYiHeng-47/qqbot-Ranking_List.git
cd qqbot-Ranking_List
```

### 第二步：创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Windows CMD:
.\.venv\Scripts\activate.bat

# Linux / macOS:
source .venv/bin/activate
```

### 第三步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 第四步：安装 Playwright 浏览器

根据你的操作系统选择对应的安装方式：

<details>
<summary><b>🪟 Windows 系统</b></summary>

Windows 系统安装非常简单，只需一条命令：

```powershell
playwright install chromium
```

等待下载完成即可，无需额外配置。

</details>

<details>
<summary><b>🐧 Linux 系统 (Ubuntu/Debian)</b></summary>

Linux 系统需要安装 Chromium 依赖库和虚拟显示服务：

```bash
# 1. 安装 Playwright 系统依赖（推荐）
sudo $(which playwright) install-deps chromium

# 或者手动安装依赖
sudo apt-get update
sudo apt-get install -y \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

# 2. 安装 Xvfb 虚拟显示（服务器环境必需）
sudo apt-get install -y xvfb

# 3. 安装 Chromium 浏览器
playwright install chromium
```

**启动机器人时需要使用 Xvfb：**

```bash
# 方式一：使用 xvfb-run（推荐）
xvfb-run python main.py

# 方式二：后台启动 Xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
python main.py
```

</details>

<details>
<summary><b>🐧 Linux 系统 (CentOS/RHEL/Fedora)</b></summary>

CentOS/RHEL 系列需要安装以下依赖：

```bash
# 1. 安装系统依赖
sudo yum install -y \
    nspr \
    nss \
    atk \
    at-spi2-atk \
    cups-libs \
    libdrm \
    libxkbcommon \
    libXcomposite \
    libXdamage \
    libXfixes \
    libXrandr \
    mesa-libgbm \
    alsa-lib

# 2. 安装 Xvfb 虚拟显示（服务器环境必需）
sudo yum install -y xorg-x11-server-Xvfb

# 3. 安装 Chromium 浏览器
playwright install chromium
```

**启动机器人时需要使用 Xvfb：**

```bash
# 方式一：使用 xvfb-run（推荐）
xvfb-run python main.py

# 方式二：后台启动 Xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
python main.py
```

</details>

<details>
<summary><b>🍎 macOS 系统</b></summary>

macOS 系统安装非常简单：

```bash
playwright install chromium
```

</details>

### 第五步：配置 NapCatQQ

1. 复制示例配置文件：

```bash
# Linux / macOS
cp config/napcat_example.json config/napcat.json

# Windows PowerShell
Copy-Item config/napcat_example.json config/napcat.json
```

2. 编辑 `config/napcat.json`，将以下内容添加到 NapCatQQ 的网络配置中：

```json
{
  "network": {
    "websocketServers": [
      {
        "name": "QQStatBot",
        "enable": true,
        "host": "0.0.0.0",
        "port": 3001,
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "token": "你的安全Token"
      }
    ]
  }
}
```

> ⚠️ **重要**：请将 `token` 修改为一个安全的随机字符串，用于验证连接身份。

### 第六步：配置机器人

1. 复制示例配置文件：

```bash
# Linux / macOS
cp config/settings_example.py config/settings.py

# Windows PowerShell
Copy-Item config/settings_example.py config/settings.py
```

2. 编辑 `config/settings.py`：

```python
# -*- coding: utf-8 -*-
"""机器人配置文件"""

# WebSocket 连接地址
WS_URI = "ws://127.0.0.1:3001"  # NapCatQQ 运行在本机
# WS_URI = "ws://192.168.1.100:3001"  # NapCatQQ 运行在其他机器

# 访问令牌（必须与 napcat.json 中的 token 一致）
TOKEN = "你的安全Token"

# 监控的群号列表（空列表表示监控所有群）
MONITOR_GROUPS = []
# MONITOR_GROUPS = [123456789, 987654321]  # 只监控指定的群

# 管理员 QQ 号列表
ADMIN_USERS = [10000]  # 替换为你的 QQ 号

# 命令前缀
COMMAND_PREFIX = "/"
```

### 第七步：启动机器人

确保 NapCatQQ 已经启动并正常运行，然后：

```bash
python main.py
```

看到以下日志表示启动成功：

```
2024-xx-xx xx:xx:xx [INFO] Main: 机器人初始化完成
2024-xx-xx xx:xx:xx [INFO] QQStatBot: 正在连接 ws://127.0.0.1:3001...
2024-xx-xx xx:xx:xx [INFO] QQStatBot: WebSocket 连接成功
2024-xx-xx xx:xx:xx [INFO] QQStatBot: 机器人已上线，QQ: xxxxxxxx
```

## 📖 使用方法

在群聊中发送以下命令：

### 基础命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/stat` | `/统计` | 查看今日热词统计（TOP 15） |
| `/rank` | `/排行` | 查看今日发言排行榜（TOP 10） |
| `/active` | `/活跃` | 查看 24 小时活跃度分布图 |
| `/info` | `/信息` | 查看群统计概览 |
| `/help` | `/帮助` | 显示帮助信息 |

### 周期报告

| 命令 | 别名 | 说明 |
|------|------|------|
| `/week` | `/周报` | 查看本周群聊周报 |
| `/month` | `/月报` | 查看本月群聊月报 |

### 智能分析

| 命令 | 别名 | 说明 |
|------|------|------|
| `/profile` | `/画像` `/我的` | 查看个人画像（@某人可查看他人） |
| `/sentiment` | `/情感` `/心情` | 查看今日群聊情感分析 |
| `/repeater` | `/复读` `/复读机` | 查看今日复读机排行榜 |
| `/recall` | `/撤回` | 查看最近7天撤回消息排行 |

## 🎨 效果预览

### 发言排行榜
- 🏅 前三名显示金银铜牌
- 👤 显示用户 QQ 头像（圆形）
- 📛 显示用户昵称/群名片
- 📊 进度条显示占今日总发言的百分比
- 🔢 右侧显示消息条数

### 热词统计
- 📊 柱状图展示词频
- 🎨 渐变色彩设计
- 🔢 显示出现次数

### 24 小时活跃度
- 📈 柱状图展示各时段消息量
- 🔥 峰值时段高亮显示
- 📊 统计摘要信息

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        QQ 客户端                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   NapCatQQ (协议端)                         │
│                   OneBot V11 Protocol                       │
└─────────────────────────────────────────────────────────────┘
                              │
                    WebSocket (正向连接)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    QQ 统计机器人                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │  main.py  │  │ protocol  │  │ db_manager│              │
│  │  主程序   │◄─┤  协议解析 │  │ 数据库    │              │
│  └───────────┘  └───────────┘  └───────────┘              │
│        │                              │                     │
│        ▼                              ▼                     │
│  ┌───────────┐               ┌───────────────┐             │
│  │visualizer │               │    SQLite     │             │
│  │ MD3 渲染  │               │   WAL 模式    │             │
│  └───────────┘               └───────────────┘             │
│        │                                                    │
│        ▼                                                    │
│  ┌───────────┐                                             │
│  │Playwright │                                             │
│  │ Chromium  │                                             │
│  └───────────┘                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心技术栈

| 模块 | 技术 | 说明 |
|------|------|------|
| 通信层 | websockets | 异步 WebSocket 客户端 |
| 协议层 | OneBot V11 | 标准化 QQ 协议 |
| 数据层 | SQLite + WAL | 高性能本地数据库 |
| 可视化 | Playwright + HTML | MD3 风格图表渲染 |
| 分词 | jieba | 中文分词引擎 |

## ⚠️ 常见问题

<details>
<summary><b>Q: VS Code 打开 templates/ 目录下的 HTML 文件显示红色报错</b></summary>

这是**正常现象，不影响运行**！

`templates/` 目录下的 `.html` 文件实际上是 **Jinja2 模板文件**，包含 `{{ }}` 和 `{% %}` 这样的模板语法。VS Code 默认的 HTML 验证器不认识这些语法，所以会报错。

**解决方法（可选）：**

1. 安装 VS Code 扩展 **"Better Jinja"**（ID: `samuelcolvin.jinjahtml`）

2. 项目已包含 `.vscode/settings.json` 配置文件，安装扩展后会自动将 `templates/*.html` 识别为 Jinja 模板

3. 如果仍有红色波浪线，按 `Ctrl+Shift+P` → 输入 `Reload Window` 重新加载窗口

**或者直接忽略这些警告**，它们不会影响机器人的正常运行。

</details>

<details>
<summary><b>Q: Linux 上报错 "libnspr4.so: cannot open shared object file"</b></summary>

这是因为缺少 Chromium 运行所需的系统库。请按照上方 Linux 安装步骤安装系统依赖：

```bash
# Ubuntu/Debian
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2

# 或者使用 Playwright 自动安装
sudo $(which playwright) install-deps chromium
```

</details>

<details>
<summary><b>Q: Linux 上报错 "Page.screenshot: Timeout" 或渲染超时</b></summary>

这通常是因为 Linux 服务器没有图形界面环境。需要安装 Xvfb 虚拟显示：

```bash
# Ubuntu/Debian
sudo apt-get install -y xvfb

# CentOS/RHEL
sudo yum install -y xorg-x11-server-Xvfb
```

然后使用 `xvfb-run` 启动机器人：

```bash
xvfb-run python main.py
```

</details>

<details>
<summary><b>Q: WebSocket 连接失败 / 连接被拒绝</b></summary>

1. 确认 NapCatQQ 已启动并正常运行
2. 检查 `config/settings.py` 中的 `WS_URI` 地址和端口是否正确
3. 检查 NapCatQQ 配置中是否启用了 WebSocket 服务器
4. 检查防火墙是否放行了对应端口
5. 确保 Token 配置一致

</details>

<details>
<summary><b>Q: 排行榜不显示昵称，只显示 QQ 号</b></summary>

昵称需要从消息中获取并缓存到数据库。新用户在首次发言后，机器人会自动记录其昵称。已存在的用户会在下次发言时更新昵称信息。

</details>

<details>
<summary><b>Q: 图表中文显示为方块或乱码</b></summary>

可视化模块使用 Google Fonts 在线加载 "Noto Sans SC" 字体。如果服务器无法访问 `fonts.googleapis.com`，可以：

1. 配置服务器代理
2. 修改 `lib/visualizer.py` 中的字体 CSS 为本地字体

</details>

<details>
<summary><b>Q: 如何让机器人后台运行？</b></summary>

**Linux 系统：**

```bash
# 使用 nohup + xvfb-run
nohup xvfb-run python main.py > /dev/null 2>&1 &

# 使用 screen + xvfb-run
screen -S qqbot
xvfb-run python main.py
# 按 Ctrl+A+D 分离会话

# 使用 systemd（推荐生产环境）
# 创建 /etc/systemd/system/qqbot.service
# 在 ExecStart 中使用: /usr/bin/xvfb-run /path/to/venv/bin/python main.py
```

**Windows 系统：**

可以使用任务计划程序或将程序注册为 Windows 服务。

</details>

<details>
<summary><b>Q: 数据库文件在哪里？如何备份？</b></summary>

数据库文件位于 `data/db/chat_log.sqlite`。

备份方法：

```bash
# 直接复制（建议在机器人停止时进行）
cp data/db/chat_log.sqlite data/db/chat_log_backup.sqlite

# 使用 SQLite 命令行工具
sqlite3 data/db/chat_log.sqlite ".backup data/db/backup.sqlite"
```

</details>

## 🔧 进阶配置

### 停用词配置

编辑 `config/settings.py` 中的 `STOP_WORDS` 集合，添加不需要统计的词汇：

```python
STOP_WORDS = {
    "的", "是", "在", "了", "和", "与",
    "我", "你", "他", "她", "它",
    "这", "那", "哪", "什么", "怎么",
    # 添加更多停用词...
}
```

### 自定义监控群

```python
# 监控所有群
MONITOR_GROUPS = []

# 只监控特定群
MONITOR_GROUPS = [123456789, 987654321]
```

## 📝 更新日志

### v1.0.0 (2024-12)
- 🎉 首次发布
- ✨ 支持消息记录、热词统计、发言排行、活跃度分析
- 🎨 Material Design 3 风格可视化
- 👤 排行榜显示用户头像和昵称
- 📊 进度条显示占总消息百分比

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) - OneBot 协议实现
- [Playwright](https://playwright.dev/) - 浏览器自动化
- [jieba](https://github.com/fxsjy/jieba) - 中文分词
- [Material Design 3](https://m3.material.io/) - 设计规范
