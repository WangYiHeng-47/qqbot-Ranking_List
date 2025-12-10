# -*- coding: utf-8 -*-
"""
数据可视化模块 - Material Design 3 风格
使用 HTML 渲染 + Playwright 截图
"""

import json
import logging
import io
import time
import asyncio
from typing import List, Tuple, Dict, Any, Optional
from collections import Counter

logger = logging.getLogger("Visualizer")

# 尝试导入分词依赖
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba 未安装，中文分词功能不可用")

# Playwright 浏览器实例（延迟初始化）
_browser = None
_playwright = None


async def get_browser():
    """获取或创建浏览器实例"""
    global _browser, _playwright
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
        logger.info("Playwright 浏览器已启动")
    return _browser


async def html_to_image(html_content: str, width: int = 800) -> Optional[io.BytesIO]:
    """将 HTML 渲染为图片"""
    try:
        browser = await get_browser()
        page = await browser.new_page(viewport={'width': width, 'height': 100})
        
        await page.set_content(html_content, wait_until='networkidle')
        
        # 等待图片加载
        await asyncio.sleep(0.5)
        
        # 获取内容实际高度
        content_height = await page.evaluate('document.body.scrollHeight')
        await page.set_viewport_size({'width': width, 'height': content_height + 40})
        
        # 截图
        screenshot = await page.screenshot(type='png', full_page=True)
        await page.close()
        
        buf = io.BytesIO(screenshot)
        return buf
    except Exception as e:
        logger.error(f"HTML 渲染失败: {e}")
        return None


# 渐变色组
GRADIENT_COLORS = [
    ['#6750A4', '#9A82DB'],  # 紫色
    ['#006A6A', '#4DB6AC'],  # 青色
    ['#7D5260', '#C48B9F'],  # 粉色
    ['#386A20', '#81C784'],  # 绿色
    ['#7D5700', '#FFB74D'],  # 橙色
]

# 基础 CSS 样式
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #F6F2FF 0%, #FEF7FF 50%, #FFF8F6 100%);
    padding: 24px;
    min-height: 100vh;
}

.card {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 28px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(103, 80, 164, 0.08), 
                0 8px 32px rgba(103, 80, 164, 0.12);
    backdrop-filter: blur(10px);
}

.card-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #E7E0EC;
}

.card-icon {
    width: 56px;
    height: 56px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    background: linear-gradient(135deg, #6750A4, #9A82DB);
    color: white;
    box-shadow: 0 4px 12px rgba(103, 80, 164, 0.3);
}

.card-title {
    font-size: 24px;
    font-weight: 700;
    color: #1D1B20;
    letter-spacing: -0.5px;
}

.card-subtitle {
    font-size: 14px;
    color: #49454F;
    margin-top: 4px;
}

.timestamp {
    font-size: 12px;
    color: #79747E;
    margin-left: auto;
    background: #F3EDF7;
    padding: 6px 12px;
    border-radius: 20px;
}
"""


class StatsVisualizer:
    """统计数据可视化器 - MD3 风格"""
    
    def __init__(self, font_path: str = None, stop_words: set = None):
        self.font_path = font_path
        self.stop_words = stop_words or set()
    
    def extract_text_from_messages(self, db_rows: List[Tuple]) -> str:
        """从数据库记录中提取文本内容"""
        corpus = []
        for row in db_rows:
            try:
                raw_content = row[0] if isinstance(row, tuple) else row
                segments = json.loads(raw_content)
                for seg in segments:
                    if seg.get('type') == 'text':
                        text = seg.get('data', {}).get('text', '').strip()
                        if text:
                            corpus.append(text)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return "\n".join(corpus)
    
    def segment_text(self, text: str) -> List[str]:
        """中文分词并过滤停用词"""
        if not JIEBA_AVAILABLE:
            return [w for w in text.split() if len(w) > 1]
        
        words = jieba.lcut(text)
        filtered_words = [
            w.strip() for w in words 
            if len(w.strip()) > 1 and w.strip() not in self.stop_words
        ]
        return filtered_words
    
    def _generate_word_frequency_html(self, top_words: List[Tuple], 
                                       total_words: int) -> str:
        """生成词频统计 HTML"""
        max_count = top_words[0][1] if top_words else 1
        
        word_items = ""
        for i, (word, count) in enumerate(top_words):
            percentage = (count / max_count) * 100
            gradient = GRADIENT_COLORS[i % len(GRADIENT_COLORS)]
            
            word_items += f"""
            <div class="word-item">
                <div class="word-rank">#{i + 1}</div>
                <div class="word-content">
                    <div class="word-info">
                        <span class="word-text">{word}</span>
                        <span class="word-count">{count} 次</span>
                    </div>
                    <div class="word-bar-bg">
                        <div class="word-bar" style="width: {percentage}%; background: linear-gradient(90deg, {gradient[0]}, {gradient[1]});"></div>
                    </div>
                </div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                {BASE_CSS}
                
                .word-item {{
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    padding: 12px 0;
                    border-bottom: 1px solid #F3EDF7;
                }}
                
                .word-item:last-child {{
                    border-bottom: none;
                }}
                
                .word-rank {{
                    width: 40px;
                    height: 40px;
                    border-radius: 12px;
                    background: linear-gradient(135deg, #F3EDF7, #E8DEF8);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: 700;
                    font-size: 14px;
                    color: #6750A4;
                    flex-shrink: 0;
                }}
                
                .word-item:nth-child(1) .word-rank {{
                    background: linear-gradient(135deg, #FFD700, #FFA500);
                    color: white;
                }}
                
                .word-item:nth-child(2) .word-rank {{
                    background: linear-gradient(135deg, #C0C0C0, #A8A8A8);
                    color: white;
                }}
                
                .word-item:nth-child(3) .word-rank {{
                    background: linear-gradient(135deg, #CD7F32, #B8860B);
                    color: white;
                }}
                
                .word-content {{
                    flex: 1;
                }}
                
                .word-info {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                }}
                
                .word-text {{
                    font-size: 16px;
                    font-weight: 500;
                    color: #1D1B20;
                }}
                
                .word-count {{
                    font-size: 14px;
                    color: #49454F;
                    font-weight: 500;
                }}
                
                .word-bar-bg {{
                    height: 8px;
                    background: #F3EDF7;
                    border-radius: 4px;
                    overflow: hidden;
                }}
                
                .word-bar {{
                    height: 100%;
                    border-radius: 4px;
                    transition: width 0.3s ease;
                }}
                
                .stats-footer {{
                    margin-top: 20px;
                    padding-top: 16px;
                    border-top: 1px solid #E7E0EC;
                    display: flex;
                    gap: 24px;
                }}
                
                .stat-chip {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 16px;
                    background: #F3EDF7;
                    border-radius: 20px;
                    font-size: 14px;
                    color: #49454F;
                }}
                
                .stat-chip-icon {{
                    font-size: 16px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📊</div>
                    <div>
                        <div class="card-title">今日热词统计</div>
                        <div class="card-subtitle">群聊高频词汇排行</div>
                    </div>
                    <div class="timestamp">{time.strftime('%H:%M')}</div>
                </div>
                
                <div class="word-list">
                    {word_items}
                </div>
                
                <div class="stats-footer">
                    <div class="stat-chip">
                        <span class="stat-chip-icon">💬</span>
                        <span>共分析 {total_words} 个词</span>
                    </div>
                    <div class="stat-chip">
                        <span class="stat-chip-icon">🔥</span>
                        <span>Top {len(top_words)} 热词</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def _generate_rank_html(self, user_stats: List[Dict], total_messages: int) -> str:
        """
        生成用户排行榜 HTML
        
        Args:
            user_stats: [{'user_id': 123, 'count': 50, 'nickname': '昵称'}, ...]
            total_messages: 今日总消息数
        """
        rank_items = ""
        medals = ['🥇', '🥈', '🥉']
        
        for i, user in enumerate(user_stats[:10]):
            user_id = user['user_id']
            count = user['count']
            nickname = user.get('nickname') or str(user_id)
            
            # 计算占总消息的百分比
            percentage = (count / total_messages * 100) if total_messages > 0 else 0
            gradient = GRADIENT_COLORS[i % len(GRADIENT_COLORS)]
            medal = medals[i] if i < 3 else ""
            
            # 为前三名添加特殊样式
            special_class = f"top-{i + 1}" if i < 3 else ""
            
            # 排名显示
            rank_display = medal if i < 3 else f"#{i + 1}"
            
            rank_items += f"""
            <div class="rank-item {special_class}">
                <div class="rank-position">
                    <span class="rank-medal">{rank_display}</span>
                </div>
                <div class="rank-avatar">
                    <img src="https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100" alt="avatar" 
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="avatar-fallback">👤</div>
                </div>
                <div class="rank-info">
                    <div class="rank-user-row">
                        <span class="rank-nickname">{nickname}</span>
                        <span class="rank-percentage">{percentage:.1f}%</span>
                    </div>
                    <div class="rank-bar-container">
                        <div class="rank-bar" style="width: {percentage}%; background: linear-gradient(90deg, {gradient[0]}, {gradient[1]});"></div>
                    </div>
                </div>
                <div class="rank-count">
                    <span class="count-number">{count}</span>
                    <span class="count-label">条</span>
                </div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                {BASE_CSS}
                
                .rank-item {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 14px 16px;
                    margin-bottom: 10px;
                    background: #FAFAFA;
                    border-radius: 20px;
                    transition: all 0.2s ease;
                }}
                
                .rank-item:last-child {{
                    margin-bottom: 0;
                }}
                
                .rank-item.top-1 {{
                    background: linear-gradient(135deg, #FFF8E1, #FFECB3);
                    box-shadow: 0 4px 16px rgba(255, 193, 7, 0.2);
                }}
                
                .rank-item.top-2 {{
                    background: linear-gradient(135deg, #FAFAFA, #F0F0F0);
                    box-shadow: 0 4px 16px rgba(158, 158, 158, 0.15);
                }}
                
                .rank-item.top-3 {{
                    background: linear-gradient(135deg, #FFF3E0, #FFE0B2);
                    box-shadow: 0 4px 16px rgba(255, 152, 0, 0.15);
                }}
                
                .rank-position {{
                    width: 36px;
                    flex-shrink: 0;
                    text-align: center;
                }}
                
                .rank-medal {{
                    font-size: 24px;
                }}
                
                .rank-item:not(.top-1):not(.top-2):not(.top-3) .rank-medal {{
                    font-size: 14px;
                    font-weight: 700;
                    color: #6750A4;
                    background: #F3EDF7;
                    border-radius: 10px;
                    padding: 6px 10px;
                }}
                
                .rank-avatar {{
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    overflow: hidden;
                    flex-shrink: 0;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
                    position: relative;
                    background: linear-gradient(135deg, #6750A4, #9A82DB);
                }}
                
                .rank-avatar img {{
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }}
                
                .avatar-fallback {{
                    display: none;
                    width: 100%;
                    height: 100%;
                    align-items: center;
                    justify-content: center;
                    font-size: 24px;
                    background: linear-gradient(135deg, #6750A4, #9A82DB);
                }}
                
                .rank-info {{
                    flex: 1;
                    min-width: 0;
                }}
                
                .rank-user-row {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }}
                
                .rank-nickname {{
                    font-size: 15px;
                    font-weight: 600;
                    color: #1D1B20;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    max-width: 150px;
                }}
                
                .rank-percentage {{
                    font-size: 13px;
                    font-weight: 600;
                    color: #6750A4;
                    background: rgba(103, 80, 164, 0.1);
                    padding: 2px 8px;
                    border-radius: 10px;
                }}
                
                .rank-bar-container {{
                    height: 8px;
                    background: rgba(103, 80, 164, 0.1);
                    border-radius: 4px;
                    overflow: hidden;
                }}
                
                .rank-bar {{
                    height: 100%;
                    border-radius: 4px;
                    min-width: 4px;
                }}
                
                .rank-count {{
                    text-align: right;
                    flex-shrink: 0;
                    min-width: 50px;
                }}
                
                .count-number {{
                    display: block;
                    font-size: 20px;
                    font-weight: 700;
                    color: #6750A4;
                    line-height: 1.2;
                }}
                
                .count-label {{
                    font-size: 12px;
                    color: #79747E;
                }}
                
                .stats-footer {{
                    margin-top: 20px;
                    padding-top: 16px;
                    border-top: 1px solid #E7E0EC;
                    display: flex;
                    justify-content: center;
                    gap: 24px;
                }}
                
                .stat-chip {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 16px;
                    background: #F3EDF7;
                    border-radius: 20px;
                    font-size: 14px;
                    color: #49454F;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">👑</div>
                    <div>
                        <div class="card-title">今日发言排行</div>
                        <div class="card-subtitle">活跃用户 TOP {len(user_stats[:10])}</div>
                    </div>
                    <div class="timestamp">{time.strftime('%H:%M')}</div>
                </div>
                
                <div class="rank-list">
                    {rank_items}
                </div>
                
                <div class="stats-footer">
                    <div class="stat-chip">
                        <span>💬</span>
                        <span>今日共 {total_messages} 条消息</span>
                    </div>
                    <div class="stat-chip">
                        <span>👥</span>
                        <span>{len(user_stats)} 人参与</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def _generate_hourly_html(self, hourly_counts: Dict[int, int]) -> str:
        """生成24小时活跃度 HTML"""
        max_count = max(hourly_counts.values()) if hourly_counts else 1
        total_count = sum(hourly_counts.values())
        
        # 找出最活跃的时段
        peak_hour = max(hourly_counts, key=hourly_counts.get) if hourly_counts else 0
        
        bars = ""
        for hour in range(24):
            count = hourly_counts.get(hour, 0)
            percentage = (count / max_count * 100) if max_count > 0 else 0
            is_peak = hour == peak_hour and count > 0
            
            bars += f"""
            <div class="hour-col {'peak' if is_peak else ''}">
                <div class="hour-bar-container">
                    <div class="hour-bar" style="height: {max(percentage, 2)}%;"></div>
                </div>
                <div class="hour-label">{hour:02d}</div>
                <div class="hour-count">{count}</div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                {BASE_CSS}
                
                .chart-container {{
                    display: flex;
                    align-items: flex-end;
                    gap: 4px;
                    height: 200px;
                    padding: 20px 0;
                }}
                
                .hour-col {{
                    flex: 1;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 8px;
                }}
                
                .hour-bar-container {{
                    flex: 1;
                    width: 100%;
                    display: flex;
                    align-items: flex-end;
                    justify-content: center;
                }}
                
                .hour-bar {{
                    width: 70%;
                    background: linear-gradient(180deg, #6750A4, #9A82DB);
                    border-radius: 4px 4px 0 0;
                    min-height: 4px;
                    transition: all 0.3s ease;
                }}
                
                .hour-col.peak .hour-bar {{
                    background: linear-gradient(180deg, #FF6B6B, #FFE66D);
                    box-shadow: 0 0 20px rgba(255, 107, 107, 0.4);
                }}
                
                .hour-label {{
                    font-size: 11px;
                    color: #79747E;
                    font-weight: 500;
                }}
                
                .hour-col.peak .hour-label {{
                    color: #6750A4;
                    font-weight: 700;
                }}
                
                .hour-count {{
                    font-size: 10px;
                    color: #CAC4D0;
                    display: none;
                }}
                
                .hour-col.peak .hour-count {{
                    display: block;
                    color: #6750A4;
                    font-weight: 600;
                }}
                
                .stats-summary {{
                    display: flex;
                    gap: 16px;
                    margin-top: 24px;
                    padding-top: 20px;
                    border-top: 1px solid #E7E0EC;
                }}
                
                .summary-card {{
                    flex: 1;
                    padding: 16px;
                    background: linear-gradient(135deg, #F3EDF7, #E8DEF8);
                    border-radius: 16px;
                    text-align: center;
                }}
                
                .summary-icon {{
                    font-size: 24px;
                    margin-bottom: 8px;
                }}
                
                .summary-value {{
                    font-size: 24px;
                    font-weight: 700;
                    color: #6750A4;
                }}
                
                .summary-label {{
                    font-size: 12px;
                    color: #49454F;
                    margin-top: 4px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">⏰</div>
                    <div>
                        <div class="card-title">24小时活跃度</div>
                        <div class="card-subtitle">消息分布统计</div>
                    </div>
                    <div class="timestamp">{time.strftime('%H:%M')}</div>
                </div>
                
                <div class="chart-container">
                    {bars}
                </div>
                
                <div class="stats-summary">
                    <div class="summary-card">
                        <div class="summary-icon">💬</div>
                        <div class="summary-value">{total_count}</div>
                        <div class="summary-label">今日总消息</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-icon">🔥</div>
                        <div class="summary-value">{peak_hour:02d}:00</div>
                        <div class="summary-label">最活跃时段</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-icon">📈</div>
                        <div class="summary-value">{hourly_counts.get(peak_hour, 0)}</div>
                        <div class="summary-label">峰值消息数</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def _generate_stats_html(self, stats: Dict[str, Any]) -> str:
        """生成统计概览 HTML"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                {BASE_CSS}
                
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 16px;
                }}
                
                .stat-card {{
                    padding: 24px;
                    border-radius: 24px;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }}
                
                .stat-card:nth-child(1) {{
                    background: linear-gradient(135deg, #E8DEF8, #D0BCFF);
                }}
                
                .stat-card:nth-child(2) {{
                    background: linear-gradient(135deg, #D0F8CE, #A8E6CF);
                }}
                
                .stat-card:nth-child(3) {{
                    background: linear-gradient(135deg, #FFE5D0, #FFCC80);
                }}
                
                .stat-card:nth-child(4) {{
                    background: linear-gradient(135deg, #D4E5FF, #90CAF9);
                }}
                
                .stat-icon {{
                    font-size: 40px;
                    margin-bottom: 12px;
                }}
                
                .stat-value {{
                    font-size: 36px;
                    font-weight: 700;
                    color: #1D1B20;
                    margin-bottom: 4px;
                }}
                
                .stat-label {{
                    font-size: 14px;
                    color: #49454F;
                    font-weight: 500;
                }}
                
                .footer-info {{
                    margin-top: 20px;
                    padding: 16px;
                    background: #F3EDF7;
                    border-radius: 16px;
                    text-align: center;
                    font-size: 13px;
                    color: #49454F;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📈</div>
                    <div>
                        <div class="card-title">群聊统计概览</div>
                        <div class="card-subtitle">数据统计摘要</div>
                    </div>
                    <div class="timestamp">{time.strftime('%H:%M')}</div>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">💬</div>
                        <div class="stat-value">{stats.get('total_messages', 0):,}</div>
                        <div class="stat-label">总消息数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">📅</div>
                        <div class="stat-value">{stats.get('today_messages', 0):,}</div>
                        <div class="stat-label">今日消息</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">👥</div>
                        <div class="stat-value">{stats.get('total_users', 0):,}</div>
                        <div class="stat-label">活跃用户</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">🖼️</div>
                        <div class="stat-value">{stats.get('total_images', 0):,}</div>
                        <div class="stat-label">图片总数</div>
                    </div>
                </div>
                
                <div class="footer-info">
                    统计时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    async def generate_word_frequency(self, db_rows: List[Tuple], 
                                      top_n: int = 15) -> Optional[io.BytesIO]:
        """生成词频统计图"""
        full_text = self.extract_text_from_messages(db_rows)
        if not full_text:
            logger.warning("没有可分析的文本内容")
            return None
        
        words = self.segment_text(full_text)
        if not words:
            logger.warning("分词后没有有效词汇")
            return None
        
        word_counts = Counter(words)
        top_words = word_counts.most_common(top_n)
        
        if not top_words:
            return None
        
        html = self._generate_word_frequency_html(top_words, len(words))
        return await html_to_image(html, width=600)
    
    async def generate_user_activity_chart(self, user_stats: List[Tuple],
                                           user_names: Dict[int, str] = None,
                                           top_n: int = 10) -> Optional[io.BytesIO]:
        """
        生成用户排行榜图
        
        Args:
            user_stats: [(user_id, count), ...]
            user_names: {user_id: nickname, ...} 用户昵称映射
            top_n: 显示前N名
        """
        if not user_stats:
            return None
        
        user_names = user_names or {}
        
        # 计算总消息数
        total_messages = sum(count for _, count in user_stats)
        
        # 构建用户数据列表
        users_data = []
        for user_id, count in user_stats[:top_n]:
            users_data.append({
                'user_id': user_id,
                'count': count,
                'nickname': user_names.get(user_id) or str(user_id)
            })
        
        html = self._generate_rank_html(users_data, total_messages)
        return await html_to_image(html, width=550)
    
    async def generate_hourly_activity_chart(self, hourly_counts: Dict[int, int]) -> Optional[io.BytesIO]:
        """生成24小时活跃度图"""
        if not hourly_counts:
            return None
        
        html = self._generate_hourly_html(hourly_counts)
        return await html_to_image(html, width=800)
    
    async def generate_stats_image(self, stats: Dict[str, Any]) -> Optional[io.BytesIO]:
        """生成统计概览图"""
        html = self._generate_stats_html(stats)
        return await html_to_image(html, width=500)
    
    def generate_stats_summary(self, stats: Dict[str, Any]) -> str:
        """生成文字统计摘要（保留文字版本作为后备）"""
        lines = [
            "📈 群聊统计概览",
            "─" * 20,
            f"💬 总消息数: {stats.get('total_messages', 0):,}",
            f"📅 今日消息: {stats.get('today_messages', 0):,}",
            f"👥 活跃用户: {stats.get('total_users', 0):,}",
            f"🖼️ 图片总数: {stats.get('total_images', 0):,}",
            "─" * 20,
            f"⏱️ 统计时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        return "\n".join(lines)
