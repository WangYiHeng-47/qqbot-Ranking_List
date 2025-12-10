# -*- coding: utf-8 -*-
"""
QQ群聊数据统计机器人 - 配置文件
"""

from pathlib import Path

# ==================== 路径配置 ====================
# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "db"
IMAGE_DIR = DATA_DIR / "images"
LOG_DIR = DATA_DIR / "logs"
FONT_DIR = DATA_DIR / "fonts"

# 数据库文件路径
DB_PATH = str(DB_DIR / "chat_log.sqlite")

# 图片存储路径
IMAGE_PATH = IMAGE_DIR

# 中文字体路径 (请放置思源黑体或其他中文字体)
FONT_PATH = str(FONT_DIR / "SourceHanSansCN-Regular.otf")

# ==================== WebSocket 配置 ====================
# NapCatQQ WebSocket 服务器地址
WS_HOST = "你的服务器地址"
WS_PORT = 3001
WS_URI = f"ws://{WS_HOST}:{WS_PORT}"

# 鉴权 Token (必须与 napcat.json 中的 token 一致)
TOKEN = "你的token"

# ==================== 功能配置 ====================
# 图片下载最大并发数
MAX_DOWNLOAD_CONCURRENCY = 5

# 心跳间隔 (秒)
PING_INTERVAL = 20
PING_TIMEOUT = 20

# 重连等待时间 (秒)
RECONNECT_DELAY = 5

# ==================== 统计配置 ====================
# 词云/统计图显示的热词数量
TOP_WORDS_COUNT = 15

# 停用词列表 (可根据需要扩展)
STOP_WORDS = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "什么", "但", "被", "让", "把", "还", "吗", "呢", "吧", "啊",
    "哈", "嗯", "哦", "呀", "啦", "哟", "嘛", "噢", "唉", "喔", "哎", "哇", "呵",
    "图片", "表情", "动画表情"
}

# ==================== 日志配置 ====================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = str(LOG_DIR / "bot.log")

# ==================== 监听群配置 ====================
# 如果为空列表，则监听所有群
# 如果指定群号，则只监听指定的群
MONITOR_GROUPS = [991936775]  # 例如: [123456789, 987654321]
