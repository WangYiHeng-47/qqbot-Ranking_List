# -*- coding: utf-8 -*-
"""
QQ群聊数据统计机器人 - 主程序入口
基于 OneBot V11 协议，使用正向 WebSocket 连接 NapCatQQ
"""

import asyncio
import json
import logging
import base64
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import websockets

from config import settings
from lib.db_manager import DatabaseManager
from lib.async_utils import AssetDownloader
from lib.visualizer import StatsVisualizer
from lib.protocol import OneBotProtocol, MessageSegment, GroupMessage


def setup_logging():
    """配置日志系统"""
    # 确保日志目录存在
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 创建格式化器
    formatter = logging.Formatter(settings.LOG_FORMAT)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 文件处理器 (轮转日志，最大10MB，保留5个备份)
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger("Main")


class QQStatBot:
    """QQ群聊数据统计机器人"""
    
    def __init__(self):
        self.logger = logging.getLogger("QQStatBot")
        
        # 初始化组件
        self.db = DatabaseManager(settings.DB_PATH)
        self.downloader = AssetDownloader(
            settings.IMAGE_PATH, 
            max_concurrency=settings.MAX_DOWNLOAD_CONCURRENCY
        )
        self.visualizer = StatsVisualizer(
            font_path=settings.FONT_PATH,
            stop_words=settings.STOP_WORDS
        )
        self.protocol = OneBotProtocol()
        
        # WebSocket 连接
        self.ws = None
        self.self_id = None  # 机器人 QQ 号
        
        # 命令前缀
        self.cmd_prefix = "/"
        
        self.logger.info("机器人初始化完成")
    
    async def connect(self):
        """建立 WebSocket 连接"""
        from urllib.parse import quote
        
        uri = settings.WS_URI
        
        # 在 URI 中添加 token 参数（需要 URL 编码特殊字符）
        if settings.TOKEN:
            encoded_token = quote(settings.TOKEN, safe='')
            separator = "&" if "?" in uri else "?"
            uri = f"{uri}{separator}access_token={encoded_token}"
        
        self.logger.info(f"正在连接 {settings.WS_URI}...")
        
        self.ws = await websockets.connect(
            uri,
            ping_interval=settings.PING_INTERVAL,
            ping_timeout=settings.PING_TIMEOUT
        )
        
        self.logger.info("WebSocket 连接成功!")
        return self.ws
    
    async def handle_group_message(self, msg: GroupMessage):
        """处理群消息"""
        group_id = msg.group_id
        user_id = msg.user_id
        
        # 检查是否在监听列表中
        if settings.MONITOR_GROUPS and group_id not in settings.MONITOR_GROUPS:
            return
        
        # 1. 异步存储消息到数据库
        msg_data = {
            'message_id': msg.message_id,
            'group_id': group_id,
            'user_id': user_id,
            'message': [seg.to_dict() for seg in msg.message],
            'time': msg.time
        }
        asyncio.create_task(self.db.insert_message(msg_data))
        
        # 2. 保存用户信息（昵称/群名片）
        sender = msg.sender
        if sender:
            nickname = sender.get('card') or sender.get('nickname') or str(user_id)
            asyncio.create_task(self.db.update_user_info(user_id, nickname))
        
        # 3. 处理图片下载
        for image in msg.get_images():
            url = image.get('url')
            file_id = image.get('file')
            if url:
                asyncio.create_task(self._download_and_save_image(url, file_id))
        
        # 4. 处理命令
        text = msg.get_plain_text()
        if text.startswith(self.cmd_prefix):
            await self._handle_command(msg, text[len(self.cmd_prefix):])
    
    async def _download_and_save_image(self, url: str, file_id: str):
        """下载并保存图片"""
        try:
            local_path, md5, size = await self.downloader.download_image(url, file_id)
            if local_path and md5:
                await self.db.insert_image(
                    file_id=file_id or md5,
                    url=url,
                    md5=md5,
                    local_path=local_path,
                    size_bytes=size
                )
        except Exception as e:
            self.logger.error(f"保存图片失败: {e}")
    
    async def _handle_command(self, msg: GroupMessage, cmd: str):
        """处理机器人命令"""
        group_id = msg.group_id
        cmd_lower = cmd.lower().strip()
        
        self.logger.info(f"收到命令: /{cmd} (群: {group_id}, 用户: {msg.user_id})")
        
        if cmd_lower == "stat" or cmd_lower == "统计":
            await self._cmd_stat(group_id)
        elif cmd_lower == "rank" or cmd_lower == "排行":
            await self._cmd_rank(group_id)
        elif cmd_lower == "active" or cmd_lower == "活跃":
            await self._cmd_active(group_id)
        elif cmd_lower == "help" or cmd_lower == "帮助":
            await self._cmd_help(group_id)
        elif cmd_lower == "info" or cmd_lower == "信息":
            await self._cmd_info(group_id)
    
    async def _cmd_stat(self, group_id: int):
        """处理统计命令 - 生成词频统计图"""
        try:
            # 获取今日消息
            rows = await self.db.get_today_messages(group_id)
            
            if not rows:
                await self.send_group_message(group_id, "📊 今日暂无消息记录")
                return
            
            # 生成词频图 (异步)
            img_buf = await self.visualizer.generate_word_frequency(
                rows, 
                top_n=settings.TOP_WORDS_COUNT
            )
            
            if img_buf:
                # Base64 编码并发送
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "📊 今日消息文本不足以生成统计图")
                
        except Exception as e:
            self.logger.error(f"生成统计图失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成统计图时出错")
    
    async def _cmd_rank(self, group_id: int):
        """处理排行命令 - 生成发言排行榜"""
        try:
            import time
            # 计算今日0点时间戳
            now = time.time()
            local_time = time.localtime(now)
            today_start = int(time.mktime(time.struct_time((
                local_time.tm_year, local_time.tm_mon, local_time.tm_mday,
                0, 0, 0, 0, 0, -1
            ))))
            
            user_stats = await self.db.get_user_message_count(group_id, today_start)
            
            if not user_stats:
                await self.send_group_message(group_id, "👑 今日暂无发言记录")
                return
            
            # 获取用户昵称信息
            user_ids = [uid for uid, _ in user_stats]
            user_names = await self.db.get_users_info_batch(user_ids)
            
            # 生成排行榜图 (异步)
            img_buf = await self.visualizer.generate_user_activity_chart(
                user_stats, 
                user_names=user_names,
                top_n=10
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                # 降级为文字版
                lines = ["👑 今日发言排行榜：", "─" * 15]
                for i, (uid, count) in enumerate(user_stats[:10], 1):
                    name = user_names.get(uid) or str(uid)
                    lines.append(f"第{i}名: {name} ({count}条)")
                await self.send_group_message(group_id, "\n".join(lines))
                
        except Exception as e:
            self.logger.error(f"生成排行榜失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成排行榜时出错")
    
    async def _cmd_active(self, group_id: int):
        """处理活跃度命令 - 生成24小时活跃度图"""
        try:
            import time
            now = time.time()
            local_time = time.localtime(now)
            today_start = int(time.mktime(time.struct_time((
                local_time.tm_year, local_time.tm_mon, local_time.tm_mday,
                0, 0, 0, 0, 0, -1
            ))))
            
            hourly_counts = await self.db.get_hourly_message_count(group_id, today_start)
            
            if not any(hourly_counts.values()):
                await self.send_group_message(group_id, "⏰ 今日暂无消息记录")
                return
            
            # 异步生成
            img_buf = await self.visualizer.generate_hourly_activity_chart(hourly_counts)
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成活跃度图时出错")
                
        except Exception as e:
            self.logger.error(f"生成活跃度图失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成活跃度图时出错")
    
    async def _cmd_info(self, group_id: int):
        """处理信息命令 - 显示统计概览"""
        try:
            stats = await self.db.get_total_stats(group_id)
            # 生成图片版统计
            img_buf = await self.visualizer.generate_stats_image(stats)
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                # 降级为文字版
                summary = self.visualizer.generate_stats_summary(stats)
                await self.send_group_message(group_id, summary)
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 获取统计信息时出错")
    
    async def _cmd_help(self, group_id: int):
        """处理帮助命令"""
        help_text = """📖 QQ群聊统计机器人 - 帮助
─────────────────
/stat 或 /统计 - 查看今日热词统计
/rank 或 /排行 - 查看今日发言排行榜
/active 或 /活跃 - 查看24小时活跃度
/info 或 /信息 - 查看群统计概览
/help 或 /帮助 - 显示本帮助信息
─────────────────
💡 机器人会自动记录群聊消息和图片"""
        await self.send_group_message(group_id, help_text)
    
    async def handle_file_upload(self, notice):
        """处理群文件上传通知"""
        try:
            file_data = {
                'id': notice.file.get('id', ''),
                'group_id': notice.group_id,
                'uploader_id': notice.user_id,
                'name': notice.file.get('name', 'unknown'),
                'size': notice.file.get('size', 0),
                'busid': notice.file.get('busid'),
                'upload_time': notice.time
            }
            await self.db.insert_file(file_data)
            self.logger.info(f"记录群文件: {file_data['name']} ({file_data['size']} bytes)")
        except Exception as e:
            self.logger.error(f"记录群文件失败: {e}")
    
    async def send_group_message(self, group_id: int, message):
        """发送群消息"""
        if self.ws is None:
            self.logger.error("WebSocket 未连接")
            return
        
        payload = self.protocol.build_send_group_msg(group_id, message)
        await self.ws.send(payload)
        self.logger.debug(f"发送群消息: {group_id}")
    
    async def dispatch_event(self, data: dict):
        """分发事件到对应的处理器"""
        event = self.protocol.parse_event(data)
        
        if event is None:
            return
        
        event_type = event.get('event_type')
        event_data = event.get('data')
        
        if event_type == 'group_message':
            await self.handle_group_message(event_data)
        elif event_type == 'group_upload':
            await self.handle_file_upload(event_data)
        elif event_type == 'heartbeat':
            # 心跳包，可以用于监控
            pass
        elif event_type == 'lifecycle':
            sub_type = data.get('sub_type')
            if sub_type == 'connect':
                self.self_id = data.get('self_id')
                self.logger.info(f"机器人已上线: {self.self_id}")
    
    async def run(self):
        """运行机器人主循环"""
        while True:
            try:
                await self.connect()
                
                async for message in self.ws:
                    try:
                        data = json.loads(message)
                        await self.dispatch_event(data)
                    except json.JSONDecodeError:
                        self.logger.warning(f"无效的 JSON 数据: {message[:100]}")
                    except Exception as e:
                        self.logger.error(f"处理消息时出错: {e}", exc_info=True)
                        
            except websockets.exceptions.ConnectionClosed as e:
                self.logger.warning(f"连接已关闭: {e}. {settings.RECONNECT_DELAY}秒后重连...")
                await asyncio.sleep(settings.RECONNECT_DELAY)
            except ConnectionRefusedError:
                self.logger.error(f"连接被拒绝. NapCat 是否在 {settings.WS_PORT} 端口运行?")
                await asyncio.sleep(settings.RECONNECT_DELAY)
            except Exception as e:
                self.logger.critical(f"未预期的错误: {e}", exc_info=True)
                await asyncio.sleep(settings.RECONNECT_DELAY)
            finally:
                self.ws = None


async def main():
    """主函数"""
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("QQ群聊数据统计机器人启动")
    logger.info("=" * 50)
    
    bot = QQStatBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n机器人已停止")
