# -*- coding: utf-8 -*-
"""
QQ群聊数据统计机器人 - 主程序入口
基于 OneBot V11 协议，使用正向 WebSocket 连接 NapCatQQ

功能特性:
- 每日热词/发言排行/活跃度统计
- 周报/月报定时推送
- 用户画像分析
- 情感分析/关键词提取
- 复读机检测
- 撤回统计
"""

import asyncio
import json
import logging
import base64
import sys
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import websockets

from config import settings
from lib.db_manager import DatabaseManager
from lib.async_utils import AssetDownloader
from lib.visualizer import StatsVisualizer
from lib.protocol import OneBotProtocol, MessageSegment, GroupMessage
from lib.commands import CommandRegistry, CommandContext, CommandInfo
from lib.renderer import renderer
from lib.nlp_analyzer import NLPAnalyzer

# 定时任务支持
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False


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
        self.nlp = NLPAnalyzer()  # NLP 分析器
        
        # 命令注册系统
        self.commands = CommandRegistry()
        self._register_commands()
        
        # WebSocket 连接
        self.ws = None
        self.self_id = None  # 机器人 QQ 号
        
        # 命令前缀
        self.cmd_prefix = "/"
        
        # 定时任务调度器
        self.scheduler = None
        if SCHEDULER_AVAILABLE:
            self.scheduler = AsyncIOScheduler()
            self._setup_scheduler()
        
        self.logger.info("机器人初始化完成")
    
    def _setup_scheduler(self):
        """设置定时任务"""
        if not self.scheduler:
            return
        
        # 每日 23:00 发送日报
        self.scheduler.add_job(
            self._scheduled_daily_report,
            'cron',
            hour=23,
            minute=0,
            id='daily_report'
        )
        
        # 每周日 22:00 发送周报
        self.scheduler.add_job(
            self._scheduled_weekly_report,
            'cron',
            day_of_week='sun',
            hour=22,
            minute=0,
            id='weekly_report'
        )
        
        self.logger.info("定时任务已配置")
    
    async def _scheduled_daily_report(self):
        """定时发送日报"""
        self.logger.info("执行定时日报任务")
        for group_id in settings.MONITOR_GROUPS:
            try:
                await self._cmd_stat_impl(group_id)
            except Exception as e:
                self.logger.error(f"日报推送失败 (群 {group_id}): {e}")
            await asyncio.sleep(2)  # 防止发送过快
    
    async def _scheduled_weekly_report(self):
        """定时发送周报"""
        self.logger.info("执行定时周报任务")
        for group_id in settings.MONITOR_GROUPS:
            try:
                await self._cmd_week_impl(group_id)
            except Exception as e:
                self.logger.error(f"周报推送失败 (群 {group_id}): {e}")
            await asyncio.sleep(2)
    
    def _register_commands(self):
        """注册所有命令"""
        # /stat - 热词统计
        self.commands.register(CommandInfo(
            name='stat',
            aliases=['统计'],
            description='查看今日热词统计',
            handler=self._cmd_stat
        ))
        
        # /rank - 发言排行
        self.commands.register(CommandInfo(
            name='rank',
            aliases=['排行'],
            description='查看今日发言排行榜',
            handler=self._cmd_rank
        ))
        
        # /active - 活跃度
        self.commands.register(CommandInfo(
            name='active',
            aliases=['活跃'],
            description='查看24小时活跃度',
            handler=self._cmd_active
        ))
        
        # /info - 统计概览
        self.commands.register(CommandInfo(
            name='info',
            aliases=['信息'],
            description='查看群统计概览',
            handler=self._cmd_info
        ))
        
        # /help - 帮助
        self.commands.register(CommandInfo(
            name='help',
            aliases=['帮助'],
            description='显示帮助信息',
            handler=self._cmd_help
        ))
        
        # /week - 周报
        self.commands.register(CommandInfo(
            name='week',
            aliases=['周报'],
            description='查看本周群聊周报',
            handler=self._cmd_week
        ))
        
        # /month - 月报
        self.commands.register(CommandInfo(
            name='month',
            aliases=['月报'],
            description='查看本月群聊月报',
            handler=self._cmd_month
        ))
        
        # /profile - 用户画像
        self.commands.register(CommandInfo(
            name='profile',
            aliases=['画像', '我的'],
            description='查看个人画像 (@某人可查看他人)',
            handler=self._cmd_profile
        ))
        
        # /sentiment - 情感分析
        self.commands.register(CommandInfo(
            name='sentiment',
            aliases=['情感', '心情'],
            description='查看群聊情感分析',
            handler=self._cmd_sentiment
        ))
        
        # /repeater - 复读机统计
        self.commands.register(CommandInfo(
            name='repeater',
            aliases=['复读', '复读机'],
            description='查看复读机排行榜',
            handler=self._cmd_repeater
        ))
        
        # /recall - 撤回统计
        self.commands.register(CommandInfo(
            name='recall',
            aliases=['撤回'],
            description='查看撤回消息排行',
            handler=self._cmd_recall
        ))
        
        self.logger.info(f"已注册 {len(self.commands.commands)} 个命令")
    
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
    
    async def handle_notice(self, notice: dict):
        """处理通知事件"""
        notice_type = notice.get('notice_type')
        
        # 群消息撤回
        if notice_type == 'group_recall':
            group_id = notice.get('group_id')
            user_id = notice.get('user_id')
            operator_id = notice.get('operator_id')
            message_id = notice.get('message_id')
            
            if group_id and user_id:
                await self.db.record_recall(group_id, user_id, int(time.time()))
                self.logger.info(f"记录撤回: 群 {group_id}, 用户 {user_id}")
    
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
        """处理机器人命令（使用命令注册系统）"""
        group_id = msg.group_id
        cmd_parts = cmd.strip().split(maxsplit=1)
        cmd_name = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""
        
        self.logger.info(f"收到命令: /{cmd_name} (群: {group_id}, 用户: {msg.user_id})")
        
        # 创建命令上下文
        ctx = CommandContext(
            group_id=group_id,
            user_id=msg.user_id,
            message=msg,
            args=args,
            bot=self
        )
        
        # 查找并执行命令
        cmd_info = self.commands.get(cmd_name)
        if cmd_info:
            try:
                await cmd_info.handler(ctx)
            except Exception as e:
                self.logger.error(f"命令执行失败: {e}", exc_info=True)
                await self.send_group_message(group_id, f"❌ 命令执行出错: {str(e)[:50]}")
        else:
            # 未知命令，不做响应或提示
            pass
    
    async def _cmd_stat(self, ctx: CommandContext):
        """处理统计命令 - 生成词频统计图"""
        await self._cmd_stat_impl(ctx.group_id)
    
    async def _cmd_stat_impl(self, group_id: int):
        """统计命令实现"""
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
    
    async def _cmd_rank(self, ctx: CommandContext):
        """处理排行命令 - 生成发言排行榜"""
        group_id = ctx.group_id
        try:
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
    
    async def _cmd_active(self, ctx: CommandContext):
        """处理活跃度命令 - 生成24小时活跃度图"""
        group_id = ctx.group_id
        try:
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
    
    async def _cmd_info(self, ctx: CommandContext):
        """处理信息命令 - 显示统计概览"""
        group_id = ctx.group_id
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
    
    async def _cmd_help(self, ctx: CommandContext):
        """处理帮助命令"""
        help_text = self.commands.generate_help(self.cmd_prefix)
        await self.send_group_message(ctx.group_id, help_text)
    
    # ==================== 新增命令 ====================
    
    async def _cmd_week(self, ctx: CommandContext):
        """周报命令"""
        await self._cmd_week_impl(ctx.group_id)
    
    async def _cmd_week_impl(self, group_id: int):
        """周报实现"""
        try:
            # 获取最近 7 天数据
            stats = await self.db.get_period_stats(group_id, days=7)
            if stats['total_messages'] == 0:
                await self.send_group_message(group_id, "📅 本周暂无消息记录")
                return
            
            # 获取排行
            user_ranking = await self.db.get_period_user_ranking(group_id, days=7, limit=10)
            user_ids = [uid for uid, _ in user_ranking]
            user_names = await self.db.get_users_info_batch(user_ids)
            
            total_msgs = stats['total_messages']
            top_users = []
            for uid, count in user_ranking:
                top_users.append({
                    'user_id': uid,
                    'nickname': user_names.get(uid, str(uid)),
                    'count': count,
                    'percentage': (count / total_msgs * 100) if total_msgs > 0 else 0
                })
            
            # 获取每日消息数
            daily_counts = await self.db.get_period_daily_counts(group_id, days=7)
            daily_stats = list(daily_counts.values())
            
            # 获取热词
            messages = await self.db.get_period_messages(group_id, days=7)
            texts = self._extract_texts(messages)
            hot_words = self.nlp.extract_keywords_tfidf(texts, top_n=10)
            
            # 峰值日
            if daily_counts:
                peak_day = max(daily_counts.items(), key=lambda x: x[1])
                peak_day_str = f"{peak_day[0]} ({peak_day[1]}条)"
            else:
                peak_day_str = "无"
            
            # 日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=6)
            date_range = f"{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}"
            
            # 渲染图片
            img_buf = await renderer.render_report(
                period_type='week',
                date_range=date_range,
                total_messages=stats['total_messages'],
                active_users=stats['active_users'],
                daily_avg=stats['total_messages'] / 7,
                peak_day=peak_day_str,
                top_users=top_users,
                daily_stats=daily_stats,
                hot_words=hot_words,
                image_count=stats.get('image_count', 0),
                days=7
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成周报时出错")
                
        except Exception as e:
            self.logger.error(f"生成周报失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成周报时出错")
    
    async def _cmd_month(self, ctx: CommandContext):
        """月报命令"""
        group_id = ctx.group_id
        try:
            # 获取最近 30 天数据
            stats = await self.db.get_period_stats(group_id, days=30)
            if stats['total_messages'] == 0:
                await self.send_group_message(group_id, "📆 本月暂无消息记录")
                return
            
            # 获取排行
            user_ranking = await self.db.get_period_user_ranking(group_id, days=30, limit=10)
            user_ids = [uid for uid, _ in user_ranking]
            user_names = await self.db.get_users_info_batch(user_ids)
            
            total_msgs = stats['total_messages']
            top_users = []
            for uid, count in user_ranking:
                top_users.append({
                    'user_id': uid,
                    'nickname': user_names.get(uid, str(uid)),
                    'count': count,
                    'percentage': (count / total_msgs * 100) if total_msgs > 0 else 0
                })
            
            # 获取每日消息数
            daily_counts = await self.db.get_period_daily_counts(group_id, days=30)
            daily_stats = list(daily_counts.values())
            
            # 获取热词
            messages = await self.db.get_period_messages(group_id, days=30)
            texts = self._extract_texts(messages)
            hot_words = self.nlp.extract_keywords_tfidf(texts, top_n=10)
            
            # 峰值日
            if daily_counts:
                peak_day = max(daily_counts.items(), key=lambda x: x[1])
                peak_day_str = f"{peak_day[0]} ({peak_day[1]}条)"
            else:
                peak_day_str = "无"
            
            # 日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=29)
            date_range = f"{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}"
            
            # 渲染图片
            img_buf = await renderer.render_report(
                period_type='month',
                date_range=date_range,
                total_messages=stats['total_messages'],
                active_users=stats['active_users'],
                daily_avg=stats['total_messages'] / 30,
                peak_day=peak_day_str,
                top_users=top_users,
                daily_stats=daily_stats,
                hot_words=hot_words,
                image_count=stats.get('image_count', 0),
                days=30
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成月报时出错")
                
        except Exception as e:
            self.logger.error(f"生成月报失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成月报时出错")
    
    async def _cmd_profile(self, ctx: CommandContext):
        """用户画像命令"""
        group_id = ctx.group_id
        # 检查是否 @ 了其他用户
        target_user = ctx.user_id
        if ctx.message:
            for seg in ctx.message.message:
                if seg.type == 'at':
                    target_user = int(seg.data.get('qq', ctx.user_id))
                    break
        
        try:
            # 获取用户统计
            user_stats = await self.db.get_user_stats(group_id, target_user)
            if not user_stats or user_stats['total_messages'] == 0:
                await self.send_group_message(group_id, "📊 该用户暂无消息记录")
                return
            
            # 获取昵称
            user_info = await self.db.get_users_info_batch([target_user])
            nickname = user_info.get(target_user, str(target_user))
            
            # 获取小时分布
            hourly_stats = await self.db.get_user_hourly_stats(group_id, target_user)
            
            # 获取用户消息用于词云
            messages = await self.db.get_user_messages(group_id, target_user, limit=500)
            texts = self._extract_texts(messages)
            word_cloud = self.nlp.get_user_word_cloud(texts, top_n=15)
            
            # 计算用户类型和徽章（get_user_type 只需要小时统计）
            user_type = self.nlp.get_user_type(hourly_stats)
            badges = self._calculate_badges(user_stats, hourly_stats)
            
            # 渲染图片
            img_buf = await renderer.render_profile(
                user_id=target_user,
                nickname=nickname,
                user_type=user_type,
                total_messages=user_stats['total_messages'],
                daily_avg=user_stats.get('daily_avg', 0),
                active_days=user_stats.get('active_days', 0),
                hourly_stats=hourly_stats,
                badges=badges,
                word_cloud=word_cloud
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成用户画像时出错")
                
        except Exception as e:
            self.logger.error(f"生成用户画像失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 生成用户画像时出错")
    
    async def _cmd_sentiment(self, ctx: CommandContext):
        """情感分析命令"""
        group_id = ctx.group_id
        try:
            # 获取今日消息
            rows = await self.db.get_today_messages(group_id)
            if not rows:
                await self.send_group_message(group_id, "😊 今日暂无消息记录")
                return
            
            texts = self._extract_texts(rows)
            if not texts:
                await self.send_group_message(group_id, "😊 今日消息文本不足")
                return
            
            # 情感分析
            sentiment_result = self.nlp.analyze_sentiment(texts)
            keywords = self.nlp.extract_keywords_tfidf(texts, top_n=8)
            
            # 确定心情 emoji 和描述（SentimentResult 是 dataclass，用属性访问）
            score = sentiment_result.average_score
            if score >= 0.7:
                mood_emoji, mood_text = "😄", "群聊氛围很积极！"
            elif score >= 0.55:
                mood_emoji, mood_text = "😊", "群聊氛围较为正面"
            elif score >= 0.45:
                mood_emoji, mood_text = "😐", "群聊氛围比较平和"
            elif score >= 0.3:
                mood_emoji, mood_text = "😔", "群聊氛围有些低落"
            else:
                mood_emoji, mood_text = "😢", "群聊氛围比较消极"
            
            # 渲染图片
            img_buf = await renderer.render_sentiment(
                period_name="今日情感分析",
                mood_emoji=mood_emoji,
                mood_text=mood_text,
                positive_pct=sentiment_result.positive_ratio,
                neutral_pct=sentiment_result.neutral_ratio,
                negative_pct=sentiment_result.negative_ratio,
                sentiment_score=score,
                keywords=keywords,
                total_messages=len(texts)
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成情感分析时出错")
                
        except Exception as e:
            self.logger.error(f"情感分析失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 情感分析时出错")
    
    async def _cmd_repeater(self, ctx: CommandContext):
        """复读机检测命令"""
        group_id = ctx.group_id
        try:
            # 获取今日消息（包含用户信息）
            rows = await self.db.get_today_messages(group_id)
            if not rows:
                await self.send_group_message(group_id, "🔁 今日暂无消息记录")
                return
            
            # 提取消息列表 (text, user_id)
            messages_with_users = []
            for row in rows:
                row_dict = dict(row) if hasattr(row, 'keys') else {'message': row[0], 'user_id': row[1] if len(row) > 1 else 0}
                msg_content = row_dict.get('message', '')
                user_id = row_dict.get('user_id', 0)
                
                if isinstance(msg_content, str):
                    try:
                        msg_list = json.loads(msg_content)
                    except:
                        msg_list = [{'type': 'text', 'data': {'text': msg_content}}]
                else:
                    msg_list = msg_content
                
                text = ''
                for seg in msg_list:
                    if isinstance(seg, dict) and seg.get('type') == 'text':
                        text += seg.get('data', {}).get('text', '')
                
                if text.strip():
                    messages_with_users.append((text.strip(), user_id))
            
            if len(messages_with_users) < 5:
                await self.send_group_message(group_id, "🔁 今日消息不足以检测复读")
                return
            
            # 检测复读
            repeats = self.nlp.detect_repeaters(messages_with_users, min_repeat=2)
            
            if not repeats:
                await self.send_group_message(group_id, "🔁 今日暂无复读行为")
                return
            
            # 获取用户昵称
            all_users = set()
            for r in repeats:
                all_users.update(r.get('users', []))
            user_names = await self.db.get_users_info_batch(list(all_users))
            
            # 为每个复读添加用户昵称
            for r in repeats:
                r['user_names'] = [user_names.get(uid, str(uid)) for uid in r.get('users', [])]
            
            # 渲染图片
            img_buf = await renderer.render_repeater(
                repeats=repeats[:10],
                total_messages=len(messages_with_users)
            )
            
            if img_buf:
                b64_str = base64.b64encode(img_buf.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                await self.send_group_message(group_id, "❌ 生成复读机报告时出错")
                
        except Exception as e:
            self.logger.error(f"复读检测失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 复读检测时出错")
    
    async def _cmd_recall(self, ctx: CommandContext):
        """撤回统计命令"""
        group_id = ctx.group_id
        try:
            ranking = await self.db.get_recall_ranking(group_id, days=7, limit=10)
            
            if not ranking:
                await self.send_group_message(group_id, "🗑️ 最近7天暂无撤回记录")
                return
            
            user_ids = [uid for uid, _ in ranking]
            user_names = await self.db.get_users_info_batch(user_ids)
            
            # 渲染为图片并发送
            image_buffer = await renderer.render_recall(ranking, user_names, days=7)
            if image_buffer:
                b64_str = base64.b64encode(image_buffer.getvalue()).decode()
                await self.send_group_message(group_id, [
                    MessageSegment.image_base64(b64_str)
                ])
            else:
                # 降级为文本输出
                lines = ["🗑️ 撤回消息排行 (最近7天)：", "─" * 18]
                for i, (uid, count) in enumerate(ranking, 1):
                    name = user_names.get(uid, str(uid))
                    lines.append(f"第{i}名: {name} - {count}次")
                await self.send_group_message(group_id, "\n".join(lines))
                
        except Exception as e:
            self.logger.error(f"撤回统计失败: {e}", exc_info=True)
            await self.send_group_message(group_id, "❌ 撤回统计时出错")
    
    # ==================== 辅助方法 ====================
    
    def _extract_texts(self, rows) -> List[str]:
        """从消息行中提取文本"""
        texts = []
        for row in rows:
            # 处理 sqlite Row 对象或普通元组
            if hasattr(row, 'keys'):
                msg_content = row['message']
            else:
                msg_content = row[0] if row else ''
            
            if isinstance(msg_content, str):
                try:
                    msg_list = json.loads(msg_content)
                except:
                    msg_list = [{'type': 'text', 'data': {'text': msg_content}}]
            else:
                msg_list = msg_content
            
            for seg in msg_list:
                if isinstance(seg, dict) and seg.get('type') == 'text':
                    text = seg.get('data', {}).get('text', '').strip()
                    if text and len(text) > 1:
                        texts.append(text)
        return texts
    
    def _calculate_badges(self, user_stats: dict, hourly_stats: dict) -> List[Dict]:
        """计算用户徽章"""
        badges = []
        total = user_stats.get('total_messages', 0)
        
        # 消息量徽章
        if total >= 10000:
            badges.append({'icon': '💎', 'name': '传说', 'desc': '消息破万'})
        elif total >= 5000:
            badges.append({'icon': '👑', 'name': '话痨王', 'desc': '消息5000+'})
        elif total >= 1000:
            badges.append({'icon': '🏆', 'name': '活跃达人', 'desc': '消息1000+'})
        elif total >= 100:
            badges.append({'icon': '⭐', 'name': '常驻成员', 'desc': '消息100+'})
        
        # 时间段徽章
        if hourly_stats:
            night_msgs = sum(hourly_stats.get(h, 0) for h in range(0, 6))
            morning_msgs = sum(hourly_stats.get(h, 0) for h in range(6, 12))
            afternoon_msgs = sum(hourly_stats.get(h, 0) for h in range(12, 18))
            evening_msgs = sum(hourly_stats.get(h, 0) for h in range(18, 24))
            
            total_hourly = sum(hourly_stats.values())
            if total_hourly > 0:
                if night_msgs / total_hourly > 0.3:
                    badges.append({'icon': '🌙', 'name': '夜猫子', 'desc': '深夜活跃'})
                if morning_msgs / total_hourly > 0.4:
                    badges.append({'icon': '🌅', 'name': '早起鸟', 'desc': '上午活跃'})
        
        return badges[:4]  # 最多显示4个徽章
    
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
        # 处理通知事件
        post_type = data.get('post_type')
        if post_type == 'notice':
            await self.handle_notice(data)
            return
        
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
        # 启动定时任务调度器
        if self.scheduler:
            self.scheduler.start()
            self.logger.info("定时任务调度器已启动")
        
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
    
    async def shutdown(self):
        """关闭机器人（静默处理异常）"""
        self.logger.info("正在关闭机器人...")
        
        # 停止定时任务
        if self.scheduler:
            try:
                self.scheduler.shutdown(wait=False)
            except Exception:
                pass
        
        # 关闭渲染器
        try:
            await renderer.close()
        except Exception:
            pass
        
        # 关闭数据库
        try:
            await self.db.close()
        except Exception:
            pass
        
        self.logger.info("机器人已关闭")


async def main():
    """主函数"""
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("QQ群聊数据统计机器人启动")
    logger.info("=" * 50)
    
    bot = QQStatBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")  # 屏蔽警告
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # 静默退出
    except SystemExit:
        pass
