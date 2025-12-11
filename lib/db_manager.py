# -*- coding: utf-8 -*-
"""
数据库管理模块
实现 SQLite 数据库的连接、初始化和 CRUD 操作
使用 WAL 模式提升并发性能
"""

import sqlite3
import json
import logging
import asyncio
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger("DBManager")


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        # 确保数据库目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库结构，同步执行"""
        try:
            with self._get_connection() as conn:
                # 开启 WAL 模式，允许并发读写
                conn.execute("PRAGMA journal_mode = WAL;")
                # 开启外键约束支持
                conn.execute("PRAGMA foreign_keys = ON;")
                
                # 1. 消息主表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL UNIQUE,
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        msg_type TEXT NOT NULL,
                        raw_content TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        processed BOOLEAN DEFAULT 0
                    )
                """)
                
                # 消息表索引：加速按群、按时间的查询
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_group_time 
                    ON messages (group_id, created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_time 
                    ON messages (user_id, created_at)
                """)
                
                # 2. 图片资产表 (用于去重与归档)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assets_images (
                        file_id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        local_path TEXT,
                        md5 CHAR(32) NOT NULL,
                        size_bytes INTEGER,
                        download_status INTEGER DEFAULT 0,
                        first_seen_at INTEGER
                    )
                """)
                
                # 图片表索引：加速基于 MD5 的去重查询
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_img_md5 
                    ON assets_images (md5)
                """)
                
                # 3. 大文件元数据表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assets_files (
                        file_id TEXT PRIMARY KEY,
                        group_id INTEGER NOT NULL,
                        uploader_id INTEGER NOT NULL,
                        file_name TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        bus_id INTEGER,
                        upload_time INTEGER,
                        dead_time INTEGER
                    )
                """)
                
                # 4. 用户信息缓存表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_info (
                        user_id INTEGER PRIMARY KEY,
                        nickname TEXT,
                        card TEXT,
                        last_updated INTEGER
                    )
                """)
                
                # 5. 群信息缓存表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS group_info (
                        group_id INTEGER PRIMARY KEY,
                        group_name TEXT,
                        member_count INTEGER,
                        last_updated INTEGER
                    )
                """)
                
                conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.critical(f"数据库初始化失败: {e}")
            raise
    
    async def insert_message(self, msg_data: dict) -> bool:
        """异步插入消息"""
        def _insert():
            try:
                with self._get_connection() as conn:
                    # 判断消息类型
                    message = msg_data.get('message', [])
                    msg_types = set()
                    for seg in message:
                        msg_types.add(seg.get('type', 'unknown'))
                    
                    if len(msg_types) == 1 and 'text' in msg_types:
                        msg_type = 'text'
                    elif len(msg_types) == 1 and 'image' in msg_types:
                        msg_type = 'image'
                    else:
                        msg_type = 'mixed'
                    
                    conn.execute(
                        """INSERT OR IGNORE INTO messages 
                           (message_id, group_id, user_id, msg_type, raw_content, created_at) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            msg_data['message_id'],
                            msg_data.get('group_id', 0),
                            msg_data['user_id'],
                            msg_type,
                            json.dumps(message, ensure_ascii=False),
                            msg_data['time']
                        )
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"插入消息失败: {e}")
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def insert_image(self, file_id: str, url: str, md5: str, 
                          local_path: str = None, size_bytes: int = None) -> bool:
        """异步插入图片记录"""
        def _insert():
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO assets_images 
                           (file_id, url, local_path, md5, size_bytes, download_status, first_seen_at) 
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            file_id,
                            url,
                            local_path,
                            md5,
                            size_bytes,
                            1 if local_path else 0,
                            int(time.time())
                        )
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"插入图片记录失败: {e}")
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def insert_file(self, file_data: dict) -> bool:
        """异步插入文件记录"""
        def _insert():
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO assets_files 
                           (file_id, group_id, uploader_id, file_name, file_size, bus_id, upload_time, dead_time) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            file_data.get('id', ''),
                            file_data.get('group_id', 0),
                            file_data.get('uploader_id', 0),
                            file_data.get('name', 'unknown'),
                            file_data.get('size', 0),
                            file_data.get('busid'),
                            file_data.get('upload_time'),
                            file_data.get('dead_time')
                        )
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"插入文件记录失败: {e}")
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def check_image_exists(self, md5: str) -> Optional[str]:
        """检查图片是否已存在（通过MD5去重）"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT local_path FROM assets_images WHERE md5 = ? AND download_status = 1",
                    (md5,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        
        return await asyncio.to_thread(_query)
    
    async def get_today_messages(self, group_id: int) -> List[Dict]:
        """获取今日群消息用于统计"""
        def _query():
            # 计算今日0点时间戳
            now = time.time()
            local_time = time.localtime(now)
            today_start = int(time.mktime(time.struct_time((
                local_time.tm_year, local_time.tm_mon, local_time.tm_mday,
                0, 0, 0, 0, 0, -1
            ))))
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT raw_content, user_id, created_at FROM messages WHERE group_id = ? AND created_at >= ?",
                    (group_id, today_start)
                )
                rows = cursor.fetchall()
                return [
                    {
                        'message': row[0],
                        'raw_content': row[0],
                        'user_id': row[1],
                        'created_at': row[2]
                    }
                    for row in rows
                ]
        
        return await asyncio.to_thread(_query)
    
    async def get_messages_by_date_range(self, group_id: int, 
                                         start_time: int, end_time: int) -> List[Tuple]:
        """获取指定时间范围内的群消息"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT raw_content, user_id, created_at 
                       FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?
                       ORDER BY created_at""",
                    (group_id, start_time, end_time)
                )
                return cursor.fetchall()
        
        return await asyncio.to_thread(_query)
    
    async def get_user_message_count(self, group_id: int, 
                                     start_time: int = None) -> List[Tuple]:
        """获取群成员发言统计"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if start_time:
                    cursor.execute(
                        """SELECT user_id, COUNT(*) as count 
                           FROM messages 
                           WHERE group_id = ? AND created_at >= ?
                           GROUP BY user_id 
                           ORDER BY count DESC""",
                        (group_id, start_time)
                    )
                else:
                    cursor.execute(
                        """SELECT user_id, COUNT(*) as count 
                           FROM messages 
                           WHERE group_id = ?
                           GROUP BY user_id 
                           ORDER BY count DESC""",
                        (group_id,)
                    )
                return cursor.fetchall()
        
        return await asyncio.to_thread(_query)
    
    async def get_hourly_message_count(self, group_id: int, 
                                       start_time: int) -> Dict[int, int]:
        """获取按小时统计的消息数量"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT created_at FROM messages 
                       WHERE group_id = ? AND created_at >= ?""",
                    (group_id, start_time)
                )
                rows = cursor.fetchall()
                
                hourly_counts = {i: 0 for i in range(24)}
                for row in rows:
                    hour = time.localtime(row[0]).tm_hour
                    hourly_counts[hour] += 1
                
                return hourly_counts
        
        return await asyncio.to_thread(_query)
    
    async def get_total_stats(self, group_id: int) -> Dict[str, Any]:
        """获取群统计总览"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总消息数
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE group_id = ?",
                    (group_id,)
                )
                total_messages = cursor.fetchone()[0]
                
                # 今日消息数
                now = time.time()
                local_time = time.localtime(now)
                today_start = int(time.mktime(time.struct_time((
                    local_time.tm_year, local_time.tm_mon, local_time.tm_mday,
                    0, 0, 0, 0, 0, -1
                ))))
                
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE group_id = ? AND created_at >= ?",
                    (group_id, today_start)
                )
                today_messages = cursor.fetchone()[0]
                
                # 活跃用户数
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id = ?",
                    (group_id,)
                )
                total_users = cursor.fetchone()[0]
                
                # 图片数
                cursor.execute("SELECT COUNT(*) FROM assets_images")
                total_images = cursor.fetchone()[0]
                
                return {
                    'total_messages': total_messages,
                    'today_messages': today_messages,
                    'total_users': total_users,
                    'total_images': total_images
                }
        
        return await asyncio.to_thread(_query)
    
    async def update_user_info(self, user_id: int, nickname: str) -> bool:
        """更新用户信息缓存"""
        def _update():
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO user_info 
                           (user_id, nickname, last_updated) 
                           VALUES (?, ?, ?)""",
                        (user_id, nickname, int(time.time()))
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"更新用户信息失败: {e}")
                return False
        
        return await asyncio.to_thread(_update)
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT nickname, card FROM user_info WHERE user_id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'nickname': row[0] or str(user_id),
                        'card': row[1]
                    }
                return None
        
        return await asyncio.to_thread(_query)
    
    async def get_users_info_batch(self, user_ids: List[int]) -> Dict[int, str]:
        """批量获取用户昵称"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(user_ids))
                cursor.execute(
                    f"SELECT user_id, nickname, card FROM user_info WHERE user_id IN ({placeholders})",
                    user_ids
                )
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    # 优先使用群名片，其次昵称
                    result[row[0]] = row[2] or row[1] or str(row[0])
                return result
        
        return await asyncio.to_thread(_query)

    # ==================== 周报/月报相关 ====================
    
    async def get_period_stats(self, group_id: int, days: int = 7, 
                                start_time: int = None, end_time: int = None) -> Dict[str, Any]:
        """获取指定时间段的统计数据
        
        Args:
            group_id: 群号
            days: 天数（如果不指定 start_time/end_time，则使用最近 N 天）
            start_time: 开始时间戳（可选）
            end_time: 结束时间戳（可选）
        """
        import time
        
        # 如果没有指定时间范围，使用最近 N 天
        if end_time is None:
            end_time = int(time.time())
        if start_time is None:
            start_time = end_time - days * 86400
        
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总消息数
                cursor.execute(
                    """SELECT COUNT(*) FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?""",
                    (group_id, start_time, end_time)
                )
                total_messages = cursor.fetchone()[0]
                
                # 活跃用户数
                cursor.execute(
                    """SELECT COUNT(DISTINCT user_id) FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?""",
                    (group_id, start_time, end_time)
                )
                active_users = cursor.fetchone()[0]
                
                # 图片数
                cursor.execute(
                    """SELECT COUNT(*) FROM assets_images 
                       WHERE first_seen_at >= ? AND first_seen_at < ?""",
                    (start_time, end_time)
                )
                image_count = cursor.fetchone()[0]
                
                return {
                    'total_messages': total_messages,
                    'active_users': active_users,
                    'image_count': image_count
                }
        
        return await asyncio.to_thread(_query)
    
    async def get_period_user_ranking(self, group_id: int, days: int = 7,
                                       start_time: int = None, end_time: int = None,
                                       limit: int = 10) -> List[Tuple]:
        """获取指定时间段的用户发言排行"""
        import time
        
        if end_time is None:
            end_time = int(time.time())
        if start_time is None:
            start_time = end_time - days * 86400
            
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT user_id, COUNT(*) as count 
                       FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?
                       GROUP BY user_id 
                       ORDER BY count DESC
                       LIMIT ?""",
                    (group_id, start_time, end_time, limit)
                )
                return cursor.fetchall()
        
        return await asyncio.to_thread(_query)
    
    async def get_period_daily_counts(self, group_id: int, days: int = 7,
                                       start_time: int = None, end_time: int = None) -> Dict[str, int]:
        """获取指定时间段每天的消息数，返回 {日期: 数量}"""
        import time as time_module
        from datetime import datetime, timedelta
        
        if end_time is None:
            end_time = int(time_module.time())
        if start_time is None:
            start_time = end_time - days * 86400
            
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT created_at FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?""",
                    (group_id, start_time, end_time)
                )
                rows = cursor.fetchall()
                
                # 按天统计
                daily_counts = {}
                for row in rows:
                    day = time_module.strftime('%m/%d', time_module.localtime(row[0]))
                    daily_counts[day] = daily_counts.get(day, 0) + 1
                
                # 生成连续日期字典
                start_date = datetime.fromtimestamp(start_time)
                end_date = datetime.fromtimestamp(end_time)
                
                result = {}
                current = start_date
                while current < end_date:
                    day_str = current.strftime('%m/%d')
                    result[day_str] = daily_counts.get(day_str, 0)
                    current += timedelta(days=1)
                
                return result
        
        return await asyncio.to_thread(_query)
    
    async def get_period_messages(self, group_id: int, days: int = 7,
                                   start_time: int = None, end_time: int = None) -> List[Dict]:
        """获取指定时间段的所有消息（用于NLP分析）"""
        import time as time_module
        
        if end_time is None:
            end_time = int(time_module.time())
        if start_time is None:
            start_time = end_time - days * 86400
            
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT message_id, user_id, raw_content, created_at 
                       FROM messages 
                       WHERE group_id = ? AND created_at >= ? AND created_at < ?
                       ORDER BY created_at""",
                    (group_id, start_time, end_time)
                )
                rows = cursor.fetchall()
                return [
                    {
                        'message_id': row[0],
                        'user_id': row[1],
                        'message': row[2],  # 兼容 _extract_texts 方法
                        'raw_content': row[2],
                        'created_at': row[3]
                    }
                    for row in rows
                ]
        
        return await asyncio.to_thread(_query)
    
    async def get_user_stats(self, group_id: int, user_id: int) -> Dict[str, Any]:
        """获取特定用户的统计数据"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总消息数
                cursor.execute(
                    """SELECT COUNT(*) FROM messages 
                       WHERE group_id = ? AND user_id = ?""",
                    (group_id, user_id)
                )
                total_messages = cursor.fetchone()[0]
                
                # 活跃天数
                cursor.execute(
                    """SELECT COUNT(DISTINCT date(created_at, 'unixepoch', 'localtime')) 
                       FROM messages 
                       WHERE group_id = ? AND user_id = ?""",
                    (group_id, user_id)
                )
                active_days = cursor.fetchone()[0]
                
                # 首次发言时间
                cursor.execute(
                    """SELECT MIN(created_at) FROM messages 
                       WHERE group_id = ? AND user_id = ?""",
                    (group_id, user_id)
                )
                first_msg = cursor.fetchone()[0]
                
                return {
                    'total_messages': total_messages,
                    'active_days': active_days,
                    'first_message_time': first_msg
                }
        
        return await asyncio.to_thread(_query)
    
    async def get_user_hourly_stats(self, group_id: int, user_id: int) -> Dict[int, int]:
        """获取用户各时段发言统计"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT created_at FROM messages 
                       WHERE group_id = ? AND user_id = ?""",
                    (group_id, user_id)
                )
                rows = cursor.fetchall()
                
                hourly_counts = {i: 0 for i in range(24)}
                for row in rows:
                    hour = time.localtime(row[0]).tm_hour
                    hourly_counts[hour] += 1
                
                return hourly_counts
        
        return await asyncio.to_thread(_query)
    
    async def get_user_messages(self, group_id: int, user_id: int, limit: int = 1000) -> List[Dict]:
        """获取用户的消息（用于词云等）"""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT message_id, raw_content, created_at 
                       FROM messages 
                       WHERE group_id = ? AND user_id = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (group_id, user_id, limit)
                )
                rows = cursor.fetchall()
                return [
                    {
                        'message_id': row[0],
                        'user_id': user_id,
                        'message': row[1],  # 兼容 _extract_texts 方法
                        'raw_content': row[1],
                        'created_at': row[2]
                    }
                    for row in rows
                ]
        
        return await asyncio.to_thread(_query)
    
    # ==================== 撤回消息统计 ====================
    
    async def record_recall(self, group_id: int, user_id: int, recall_time: int, message_id: int = None):
        """记录撤回消息
        
        Args:
            group_id: 群号
            user_id: 撤回者 QQ
            recall_time: 撤回时间戳
            message_id: 消息 ID（可选）
        """
        def _insert():
            try:
                with self._get_connection() as conn:
                    # 确保 recall_stats 表存在
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS recall_stats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            group_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            message_id INTEGER,
                            recall_time INTEGER NOT NULL
                        )
                    """)
                    conn.execute(
                        """INSERT INTO recall_stats (group_id, user_id, message_id, recall_time) 
                           VALUES (?, ?, ?, ?)""",
                        (group_id, user_id, message_id, recall_time)
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"记录撤回失败: {e}")
                return False
        
        return await asyncio.to_thread(_insert)
    
    async def get_recall_ranking(self, group_id: int, days: int = 7, 
                                  start_time: int = None, limit: int = 10) -> List[Tuple]:
        """获取撤回次数排行
        
        Args:
            group_id: 群号
            days: 统计天数
            start_time: 开始时间戳（可选，如果不指定则使用 days）
            limit: 返回数量限制
        """
        import time as time_module
        
        if start_time is None:
            start_time = int(time_module.time()) - days * 86400
            
        def _query():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查表是否存在
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='recall_stats'"
                )
                if not cursor.fetchone():
                    return []
                
                cursor.execute(
                    """SELECT user_id, COUNT(*) as count 
                       FROM recall_stats 
                       WHERE group_id = ? AND recall_time >= ?
                       GROUP BY user_id 
                       ORDER BY count DESC
                       LIMIT ?""",
                    (group_id, start_time, limit)
                )
                return cursor.fetchall()
        
        return await asyncio.to_thread(_query)

