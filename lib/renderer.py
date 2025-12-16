# -*- coding: utf-8 -*-
"""
可视化渲染器 - Jinja2 + Playwright
支持浏览器上下文复用，提升渲染性能
"""

import io
import logging
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("Renderer")

# Jinja2 模板引擎
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logger.warning("jinja2 未安装")

# Playwright
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright 未安装")


class TemplateRenderer:
    """模板渲染器"""
    
    _instance = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _playwright = None
    _env = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._env is None and JINJA2_AVAILABLE:
            # 模板目录
            template_dir = Path(__file__).parent.parent / "templates"
            template_dir.mkdir(exist_ok=True)
            
            self._env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml']),
                enable_async=True
            )
            logger.info(f"Jinja2 模板引擎已初始化，模板目录: {template_dir}")
    
    async def _ensure_browser(self):
        """确保浏览器已启动"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright 未安装")
        
        if self._browser is None or not self._browser.is_connected():
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={'width': 800, 'height': 600},
                device_scale_factor=2  # 高清渲染
            )
            logger.info("Playwright 浏览器上下文已创建")
    
    async def render_template(self, template_name: str, **context) -> str:
        """渲染 Jinja2 模板"""
        if not JINJA2_AVAILABLE:
            raise RuntimeError("jinja2 未安装")
        
        template = self._env.get_template(template_name)
        return await template.render_async(**context)
    
    async def render_html_to_image(self, html: str, width: int = 800) -> Optional[io.BytesIO]:
        """将 HTML 渲染为图片"""
        try:
            await self._ensure_browser()
            
            page = await self._context.new_page()
            
            try:
                # 设置视口宽度
                await page.set_viewport_size({'width': width, 'height': 100})
                
                # 设置内容
                await page.set_content(html, wait_until='networkidle')
                
                # 等待图片和字体加载
                await asyncio.sleep(0.3)
                
                # 获取实际内容高度
                content_height = await page.evaluate('document.body.scrollHeight')
                await page.set_viewport_size({'width': width, 'height': min(content_height + 40, 4000)})
                
                # 截图
                screenshot = await page.screenshot(type='png', full_page=True)
                
                return io.BytesIO(screenshot)
                
            finally:
                await page.close()
                
        except Exception as e:
            logger.error(f"HTML 渲染失败: {e}")
            return None
    
    async def render_template_to_image(self, template_name: str, width: int = 800, **context) -> Optional[io.BytesIO]:
        """渲染模板并转为图片"""
        try:
            html = await self.render_template(template_name, **context)
            return await self.render_html_to_image(html, width)
        except Exception as e:
            logger.error(f"模板渲染失败: {e}")
            return None
    
    async def close(self):
        """关闭浏览器（静默处理异常）"""
        try:
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass  # 忽略已关闭的错误
                self._context = None
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
        except Exception:
            pass  # 静默处理所有关闭异常
    
    # ==================== 便捷渲染方法 ====================
    
    async def render_profile(
        self,
        user_id: int,
        nickname: str,
        user_type: str,
        total_messages: int,
        daily_avg: float,
        active_days: int,
        hourly_stats: Dict[int, int],
        badges: List[Dict],
        word_cloud: List[Tuple[str, int]] = None
    ) -> Optional[io.BytesIO]:
        """渲染用户画像"""
        max_hourly = max(hourly_stats.values()) if hourly_stats else 1
        
        return await self.render_template_to_image(
            'profile.html',
            width=500,
            user_id=user_id,
            nickname=nickname,
            user_type=user_type,
            total_messages=total_messages,
            daily_avg=f"{daily_avg:.1f}",
            active_days=active_days,
            hourly_stats=hourly_stats,
            max_hourly=max_hourly,
            badges=badges,
            word_cloud=word_cloud or [],
            timestamp=time.strftime('%H:%M')
        )
    
    async def render_sentiment(
        self,
        period_name: str,
        mood_emoji: str,
        mood_text: str,
        positive_pct: float,
        neutral_pct: float,
        negative_pct: float,
        sentiment_score: float,
        keywords: List[Tuple[str, float]],
        total_messages: int
    ) -> Optional[io.BytesIO]:
        """渲染情感分析报告"""
        return await self.render_template_to_image(
            'sentiment.html',
            width=500,
            period_name=period_name,
            mood_emoji=mood_emoji,
            mood_text=mood_text,
            positive_pct=positive_pct * 100,
            neutral_pct=neutral_pct * 100,
            negative_pct=negative_pct * 100,
            sentiment_score=sentiment_score,
            keywords=keywords,
            total_messages=total_messages,
            timestamp=time.strftime('%H:%M')
        )
    
    async def render_repeater(
        self,
        repeats: List[Dict],
        total_messages: int
    ) -> Optional[io.BytesIO]:
        """渲染复读机报告"""
        total_repeats = sum(r['count'] for r in repeats)
        total_users = len(set(u for r in repeats for u in r.get('users', [])))
        
        return await self.render_template_to_image(
            'repeater.html',
            width=500,
            repeats=repeats,
            total_repeats=total_repeats,
            total_users=total_users,
            total_messages=total_messages,
            timestamp=time.strftime('%H:%M')
        )
    
    async def render_report(
        self,
        period_type: str,  # 'week' 或 'month'
        date_range: str,
        total_messages: int,
        active_users: int,
        daily_avg: float,
        peak_day: str,
        top_users: List[Dict],
        daily_stats: List[int],
        hot_words: List[Tuple[str, int]],
        image_count: int,
        days: int
    ) -> Optional[io.BytesIO]:
        """渲染周报/月报"""
        if period_type == 'week':
            icon = '📅'
            title = '群聊周报'
            period_name = '本周统计'
        else:
            icon = '📆'
            title = '群聊月报'
            period_name = '本月统计'
        
        max_daily = max(daily_stats) if daily_stats else 1
        
        return await self.render_template_to_image(
            'report.html',
            width=550,
            icon=icon,
            title=title,
            period_name=period_name,
            date_range=date_range,
            total_messages=total_messages,
            active_users=active_users,
            daily_avg=f"{daily_avg:.0f}",
            peak_day=peak_day,
            top_users=top_users,
            daily_stats=daily_stats,
            max_daily=max_daily,
            hot_words=hot_words,
            image_count=image_count,
            days=days,
            timestamp=time.strftime('%H:%M')
        )
    
    async def render_recall(
        self,
        ranking: List[Tuple[int, int]],
        user_names: Dict[int, str],
        days: int = 7
    ) -> Optional[io.BytesIO]:
        """渲染撤回统计报告
        
        Args:
            ranking: 撤回排行榜 [(user_id, count), ...]
            user_names: 用户ID到昵称的映射
            days: 统计天数
        """
        # 转换为模板需要的格式
        ranking_data = []
        for i, (user_id, count) in enumerate(ranking, 1):
            ranking_data.append({
                'rank': i,
                'user_id': user_id,
                'nickname': user_names.get(user_id, str(user_id)),
                'count': count
            })
        
        total_recalls = sum(count for _, count in ranking)
        total_users = len(ranking)
        
        return await self.render_template_to_image(
            'recall.html',
            width=500,
            ranking=ranking_data,
            total_recalls=total_recalls,
            total_users=total_users,
            days=days,
            timestamp=time.strftime('%H:%M')
        )


# 全局渲染器实例
renderer = TemplateRenderer()
