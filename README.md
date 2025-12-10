# QQ群聊数据统计机器人

一个基于 Python 异步编程的 QQ 群聊数据统计机器人，使用 OneBot V11 协议通过正向 WebSocket 连接 NapCatQQ。

## 功能特性

- 📊 **消息统计** - 自动记录群聊消息，生成热词统计图
- 👑 **发言排行** - 统计群成员发言数量排行榜（显示头像和昵称）
- ⏰ **活跃分析** - 生成 24 小时活跃度柱状图
- 🖼️ **图片归档** - 自动下载并去重存储群聊图片
- 📁 **文件记录** - 记录群文件上传元数据
- 🎨 **MD3 风格** - Material Design 3 风格的精美图表

## 项目结构

```
qq-stat-bot/
├── config/
│   ├── napcat.json       # NapCatQQ 配置文件
│   └── settings.py       # 机器人业务配置
├── data/
│   ├── db/               # SQLite 数据库
│   ├── images/           # 图片存储目录
│   ├── fonts/            # 中文字体文件
│   └── logs/             # 运行日志
├── lib/
│   ├── db_manager.py     # 数据库管理模块
│   ├── async_utils.py    # 异步工具模块
│   ├── visualizer.py     # 数据可视化模块
│   └── protocol.py       # OneBot 协议解析模块
├── main.py               # 程序入口
├── requirements.txt      # 依赖清单
└── README.md             # 项目说明
```

## 环境要求

- Python 3.10+
- NapCatQQ (支持 OneBot V11 协议)
- Chromium (Playwright 自动安装)

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 3. 配置 NapCatQQ

将 `config/napcat.json` 的内容复制到 NapCatQQ 的配置文件中，或确保 NapCatQQ 的配置包含以下关键设置：

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
        "token": "你的Token"
      }
    ]
  }
}
```

### 4. 修改机器人配置

编辑 `config/settings.py`：

```python
# 修改 Token（必须与 napcat.json 一致）
TOKEN = "你的Token"

# 可选：指定监听的群
MONITOR_GROUPS = [123456789]  # 空列表表示监听所有群
```

### 5. 启动机器人

```bash
python main.py
```

## 使用方法

在群聊中发送以下命令：

| 命令 | 说明 |
|------|------|
| `/stat` 或 `/统计` | 查看今日热词统计 |
| `/rank` 或 `/排行` | 查看今日发言排行榜 |
| `/active` 或 `/活跃` | 查看24小时活跃度 |
| `/info` 或 `/信息` | 查看群统计概览 |
| `/help` 或 `/帮助` | 显示帮助信息 |

## 技术架构

### 协议层
- 使用 NapCatQQ 作为 NTQQ 协议端
- 通过正向 WebSocket (Forward WS) 在 3001 端口通信
- 严格遵循 OneBot V11 标准协议

### 通信层
- 使用 `websockets` 库实现底层 WebSocket 通信
- 支持自动重连和心跳保持
- Token 鉴权保障安全性

### 数据层
- SQLite 数据库 + WAL 模式
- 异步数据库操作，不阻塞事件循环
- 图片 MD5 去重存储
- 用户昵称缓存，提升显示体验

### 可视化层
- **Playwright + Chromium** 渲染 HTML 生成图片
- **Material Design 3** 风格设计
- 动态加载 QQ 头像
- jieba 中文分词
- 内存流输出，无临时文件

## 注意事项

1. **首次运行** - 确保 NapCatQQ 已启动并监听 3001 端口
2. **Playwright 安装** - 首次运行需执行 `playwright install chromium`
3. **性能优化** - 图片下载使用 Semaphore 限制并发，防止资源耗尽
4. **日志查看** - 运行日志保存在 `data/logs/bot.log`

## 排行榜功能说明

排行榜图片会显示：
- 👤 **用户头像** - 自动从 QQ 服务器获取
- 📛 **用户昵称** - 显示群名片或昵称（首次发言后记录）
- 📊 **占比进度条** - 显示该用户消息占今日总消息的百分比
- 🔢 **消息条数** - 该用户今日发送的消息总数

## 开发说明

本项目遵循以下设计原则：

- **极简依赖** - 不使用 NoneBot2 等重型框架
- **全异步 I/O** - 使用 Python asyncio 原语
- **类型安全** - 使用 dataclass 和类型注解

## License

MIT License
