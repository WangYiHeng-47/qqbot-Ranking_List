# -*- coding: utf-8 -*-
"""
异步工具模块
实现图片下载、压缩、文件哈希等异步操作
使用 Semaphore 进行背压控制
"""

import aiohttp
import hashlib
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("AsyncUtils")

# 尝试导入 OpenCV
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV 未安装，图片压缩功能不可用")


class AssetDownloader:
    """资源下载器"""
    
    # 压缩配置
    MAX_IMAGE_SIZE = 1920      # 最大边长（像素）
    JPEG_QUALITY = 85          # JPEG 压缩质量 (1-100)
    COMPRESS_THRESHOLD = 100 * 1024  # 超过 100KB 才压缩
    
    def __init__(self, save_dir: Path, max_concurrency: int = 5):
        self.save_dir = save_dir
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # HTTP 会话配置
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def download_image(self, url: str, file_id: str = None) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        下载图片
        
        Args:
            url: 图片URL
            file_id: OneBot提供的文件ID（可选）
            
        Returns:
            Tuple[本地路径, MD5哈希, 文件大小] 或 (None, None, None)
        """
        async with self.semaphore:  # 限制并发数
            try:
                async with aiohttp.ClientSession(
                    timeout=self.timeout,
                    headers=self.headers
                ) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            original_size = len(content)
                            
                            # 获取内容类型
                            content_type = resp.headers.get('Content-Type', 'image/jpeg')
                            
                            # 压缩图片（在线程池中执行）
                            compressed, ext = await asyncio.to_thread(
                                self._compress_image, content, content_type
                            )
                            final_size = len(compressed)
                            
                            # 计算压缩后内容的 MD5
                            md5 = hashlib.md5(compressed).hexdigest()
                            
                            # 分片存储: images/md5_prefix_2/md5.jpg
                            sub_dir = self.save_dir / md5[:2]
                            sub_dir.mkdir(exist_ok=True)
                            file_path = sub_dir / f"{md5}{ext}"
                            
                            if not file_path.exists():
                                # 写入压缩后的图片
                                await asyncio.to_thread(file_path.write_bytes, compressed)
                                if original_size != final_size:
                                    saved = original_size - final_size
                                    logger.info(f"下载图片成功: {md5} ({final_size} bytes, 节省 {saved} bytes)")
                                else:
                                    logger.info(f"下载图片成功: {md5} ({final_size} bytes)")
                            else:
                                logger.debug(f"图片已存在，跳过下载: {md5}")
                            
                            return str(file_path), md5, final_size
                        else:
                            logger.warning(f"下载失败 {url}: HTTP {resp.status}")
            except asyncio.TimeoutError:
                logger.error(f"下载超时 {url}")
            except aiohttp.ClientError as e:
                logger.error(f"下载网络错误 {url}: {e}")
            except Exception as e:
                logger.error(f"下载异常 {url}: {e}")
        
        return None, None, None
    
    def _get_extension(self, content_type: str) -> str:
        """根据 Content-Type 获取文件扩展名"""
        type_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/bmp': '.bmp',
        }
        return type_map.get(content_type.split(';')[0], '.jpg')
    
    def _compress_image(self, content: bytes, content_type: str) -> Tuple[bytes, str]:
        """
        使用 OpenCV 压缩图片
        
        Args:
            content: 原始图片字节
            content_type: 图片类型
            
        Returns:
            Tuple[压缩后字节, 新扩展名]
        """
        if not OPENCV_AVAILABLE:
            ext = self._get_extension(content_type)
            return content, ext
        
        # GIF 不压缩（OpenCV 不支持动图）
        if 'gif' in content_type.lower():
            return content, '.gif'
        
        # 小于阈值不压缩
        if len(content) < self.COMPRESS_THRESHOLD:
            ext = self._get_extension(content_type)
            return content, ext
        
        try:
            original_size = len(content)
            
            # 将字节转为 numpy 数组，再解码为图片
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
            
            if img is None:
                ext = self._get_extension(content_type)
                return content, ext
            
            # 检查是否有透明通道
            has_alpha = img.shape[2] == 4 if len(img.shape) == 3 and img.shape[2] == 4 else False
            
            # 缩放大图
            height, width = img.shape[:2]
            if max(width, height) > self.MAX_IMAGE_SIZE:
                ratio = self.MAX_IMAGE_SIZE / max(width, height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            
            # 编码压缩
            if has_alpha:
                # 有透明通道，保存为 PNG
                encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 6]  # 0-9, 6 是平衡值
                success, encoded = cv2.imencode('.png', img, encode_params)
                ext = '.png'
            else:
                # 无透明通道，保存为 JPEG（压缩率更高）
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
                success, encoded = cv2.imencode('.jpg', img, encode_params)
                ext = '.jpg'
            
            if not success:
                ext = self._get_extension(content_type)
                return content, ext
            
            compressed = encoded.tobytes()
            new_size = len(compressed)
            
            # 如果压缩后反而更大，返回原图
            if new_size >= original_size:
                ext = self._get_extension(content_type)
                return content, ext
            
            saved_ratio = (1 - new_size / original_size) * 100
            logger.debug(f"图片压缩: {original_size} -> {new_size} bytes (节省 {saved_ratio:.1f}%)")
            
            return compressed, ext
            
        except Exception as e:
            logger.warning(f"图片压缩失败: {e}")
            ext = self._get_extension(content_type)
            return content, ext
    
    async def download_with_retry(self, url: str, file_id: str = None, 
                                   max_retries: int = 3) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """带重试的下载"""
        for attempt in range(max_retries):
            result = await self.download_image(url, file_id)
            if result[0] is not None:
                return result
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"重试下载 ({attempt + 1}/{max_retries})，等待 {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"下载最终失败: {url}")
        return None, None, None


class FileHasher:
    """文件哈希工具"""
    
    @staticmethod
    async def calculate_md5(file_path: str) -> Optional[str]:
        """异步计算文件MD5"""
        def _calc():
            try:
                with open(file_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            except Exception as e:
                logger.error(f"计算MD5失败: {e}")
                return None
        
        return await asyncio.to_thread(_calc)
    
    @staticmethod
    async def calculate_sha256(file_path: str) -> Optional[str]:
        """异步计算文件SHA256"""
        def _calc():
            try:
                with open(file_path, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            except Exception as e:
                logger.error(f"计算SHA256失败: {e}")
                return None
        
        return await asyncio.to_thread(_calc)


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_calls: int, period: float):
        """
        Args:
            max_calls: 周期内最大调用次数
            period: 周期时长（秒）
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """获取执行许可"""
        async with self.lock:
            now = time.time()
            
            # 清理过期的调用记录
            self.calls = [t for t in self.calls if now - t < self.period]
            
            if len(self.calls) >= self.max_calls:
                # 需要等待
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                self.calls = self.calls[1:]
            
            self.calls.append(time.time())
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


async def retry_async(func, *args, max_retries: int = 3, 
                      delay: float = 1.0, **kwargs):
    """
    通用异步重试装饰器
    
    Args:
        func: 异步函数
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"操作失败，重试 {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(delay * (attempt + 1))
    
    raise last_exception
