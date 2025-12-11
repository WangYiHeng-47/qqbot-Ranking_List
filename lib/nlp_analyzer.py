# -*- coding: utf-8 -*-
"""
NLP 分析模块
包含情感分析、TF-IDF 关键词提取、互动关系分析
"""

import json
import logging
import re
from typing import List, Dict, Tuple, Optional, Any
from collections import Counter, defaultdict
from dataclasses import dataclass

logger = logging.getLogger("NLPAnalyzer")

# 尝试导入依赖
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba 未安装")

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    logger.warning("snownlp 未安装，情感分析功能不可用")

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx 未安装，互动关系图功能不可用")


@dataclass
class SentimentResult:
    """情感分析结果"""
    positive_ratio: float      # 积极比例
    negative_ratio: float      # 消极比例
    neutral_ratio: float       # 中性比例
    average_score: float       # 平均情感分数 (0-1)
    mood: str                  # 整体氛围描述
    total_messages: int        # 分析的消息数


@dataclass
class UserInteraction:
    """用户互动数据"""
    from_user: int
    to_user: int
    count: int


class NLPAnalyzer:
    """NLP 分析器"""
    
    def __init__(self, stop_words: set = None):
        self.stop_words = stop_words or set()
        
        # 情感阈值
        self.POSITIVE_THRESHOLD = 0.6
        self.NEGATIVE_THRESHOLD = 0.4
    
    def extract_text_from_messages(self, messages: List[Dict]) -> List[str]:
        """从消息列表中提取纯文本"""
        texts = []
        for msg in messages:
            try:
                raw_content = msg.get('raw_content', '[]')
                if isinstance(raw_content, str):
                    segments = json.loads(raw_content)
                else:
                    segments = raw_content
                
                for seg in segments:
                    if seg.get('type') == 'text':
                        text = seg.get('data', {}).get('text', '').strip()
                        if text and len(text) > 1:
                            texts.append(text)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return texts
    
    def analyze_sentiment(self, texts: List[str]) -> Optional[SentimentResult]:
        """
        情感分析
        返回整体情感倾向
        """
        if not SNOWNLP_AVAILABLE:
            logger.warning("snownlp 不可用，跳过情感分析")
            return None
        
        if not texts:
            return None
        
        scores = []
        for text in texts:
            try:
                if len(text) < 2:
                    continue
                s = SnowNLP(text)
                scores.append(s.sentiments)
            except Exception:
                continue
        
        if not scores:
            return None
        
        # 统计情感分布
        positive = sum(1 for s in scores if s >= self.POSITIVE_THRESHOLD)
        negative = sum(1 for s in scores if s <= self.NEGATIVE_THRESHOLD)
        neutral = len(scores) - positive - negative
        
        total = len(scores)
        avg_score = sum(scores) / total
        
        # 判断整体氛围
        if avg_score >= 0.65:
            mood = "🌈 群聊氛围非常积极活跃！"
        elif avg_score >= 0.55:
            mood = "😊 群聊氛围比较轻松愉快"
        elif avg_score >= 0.45:
            mood = "😐 群聊氛围比较平淡中性"
        elif avg_score >= 0.35:
            mood = "😔 群聊氛围有些低落"
        else:
            mood = "😰 群聊氛围比较焦虑消极"
        
        return SentimentResult(
            positive_ratio=positive / total,
            negative_ratio=negative / total,
            neutral_ratio=neutral / total,
            average_score=avg_score,
            mood=mood,
            total_messages=total
        )
    
    def extract_keywords_tfidf(self, texts: List[str], top_n: int = 20) -> List[Tuple[str, float]]:
        """
        使用 TF-IDF 提取关键词
        返回: [(关键词, 权重), ...]
        """
        if not JIEBA_AVAILABLE:
            return []
        
        if not texts:
            return []
        
        # 合并所有文本
        full_text = " ".join(texts)
        
        # 使用 jieba 的 TF-IDF 算法
        keywords = jieba.analyse.extract_tags(
            full_text,
            topK=top_n,
            withWeight=True,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'an')  # 名词、动词、形容词
        )
        
        # 过滤停用词
        filtered = [
            (word, weight) for word, weight in keywords
            if word not in self.stop_words and len(word) > 1
        ]
        
        return filtered[:top_n]
    
    def extract_keywords_textrank(self, texts: List[str], top_n: int = 20) -> List[Tuple[str, float]]:
        """
        使用 TextRank 提取关键词
        """
        if not JIEBA_AVAILABLE:
            return []
        
        if not texts:
            return []
        
        full_text = " ".join(texts)
        
        keywords = jieba.analyse.textrank(
            full_text,
            topK=top_n,
            withWeight=True,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn')
        )
        
        filtered = [
            (word, weight) for word, weight in keywords
            if word not in self.stop_words and len(word) > 1
        ]
        
        return filtered[:top_n]
    
    def analyze_interactions(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        分析用户互动关系
        通过 @ 和回复消息来判断互动
        
        messages: [{'user_id': 123, 'raw_content': '...', 'reply_to': 456}, ...]
        """
        if not messages:
            return {'edges': [], 'nodes': [], 'stats': {}}
        
        # 统计互动次数
        interactions = defaultdict(int)  # (from_user, to_user) -> count
        user_msg_count = defaultdict(int)  # user_id -> 消息数
        
        for msg in messages:
            user_id = msg.get('user_id')
            if not user_id:
                continue
            
            user_msg_count[user_id] += 1
            
            # 解析 @ 的用户
            try:
                raw_content = msg.get('raw_content', '[]')
                if isinstance(raw_content, str):
                    segments = json.loads(raw_content)
                else:
                    segments = raw_content
                
                for seg in segments:
                    if seg.get('type') == 'at':
                        target_qq = seg.get('data', {}).get('qq')
                        if target_qq and target_qq != 'all':
                            try:
                                target_id = int(target_qq)
                                if target_id != user_id:  # 排除自己 @ 自己
                                    interactions[(user_id, target_id)] += 1
                            except ValueError:
                                pass
                    
                    # 解析回复消息
                    if seg.get('type') == 'reply':
                        # 回复消息需要从数据库查询被回复消息的发送者
                        # 这里简化处理，后续可扩展
                        pass
                        
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        
        # 构建边列表
        edges = [
            {'from': from_user, 'to': to_user, 'weight': count}
            for (from_user, to_user), count in interactions.items()
            if count > 0
        ]
        
        # 节点列表
        all_users = set(user_msg_count.keys())
        for edge in edges:
            all_users.add(edge['from'])
            all_users.add(edge['to'])
        
        nodes = [
            {'id': user_id, 'msg_count': user_msg_count.get(user_id, 0)}
            for user_id in all_users
        ]
        
        # 统计信息
        stats = {
            'total_interactions': sum(e['weight'] for e in edges),
            'unique_pairs': len(edges),
            'most_active_pair': max(edges, key=lambda x: x['weight']) if edges else None
        }
        
        return {
            'edges': edges,
            'nodes': nodes,
            'stats': stats
        }
    
    def detect_repeaters(self, messages, min_repeat: int = 3) -> List[Dict]:
        """
        检测复读机
        
        参数:
            messages: 可以是以下格式之一:
                - List[Tuple[str, int]]: [(文本, user_id), ...]
                - List[Dict]: [{'raw_content': ..., 'user_id': ...}, ...]
            min_repeat: 最小连续重复次数
        
        返回连续相同消息的统计
        """
        if not messages:
            return []
        
        # 提取纯文本内容
        msg_texts = []
        
        for msg in messages:
            # 处理简单元组格式 (text, user_id)
            if isinstance(msg, (tuple, list)) and len(msg) >= 2:
                text, user_id = msg[0], msg[1]
                if text and text.strip():
                    msg_texts.append({
                        'user_id': user_id,
                        'text': text.strip()
                    })
                continue
            
            # 处理 dict 格式
            if isinstance(msg, dict):
                try:
                    raw_content = msg.get('raw_content', '[]')
                    if isinstance(raw_content, str):
                        segments = json.loads(raw_content)
                    else:
                        segments = raw_content
                    
                    text_parts = []
                    for seg in segments:
                        if seg.get('type') == 'text':
                            text_parts.append(seg.get('data', {}).get('text', ''))
                    
                    full_text = ''.join(text_parts).strip()
                    if full_text:
                        msg_texts.append({
                            'user_id': msg.get('user_id'),
                            'text': full_text,
                            'time': msg.get('created_at', 0)
                        })
                except Exception:
                    continue
        
        if not msg_texts:
            return []
        
        # 检测连续复读
        repeats = []
        current_text = None
        current_users = []
        
        for item in msg_texts:
            if item['text'] == current_text:
                current_users.append(item['user_id'])
            else:
                if len(current_users) >= min_repeat:
                    repeats.append({
                        'text': current_text[:50] + ('...' if len(current_text) > 50 else ''),
                        'count': len(current_users),
                        'users': list(set(current_users))
                    })
                current_text = item['text']
                current_users = [item['user_id']]
        
        # 处理最后一组
        if len(current_users) >= min_repeat:
            repeats.append({
                'text': current_text[:50] + ('...' if len(current_text) > 50 else ''),
                'count': len(current_users),
                'users': list(set(current_users))
            })
        
        # 按复读次数排序
        repeats.sort(key=lambda x: x['count'], reverse=True)
        
        return repeats
    
    def get_user_word_cloud(self, texts_or_messages, user_id: int = None, top_n: int = 30) -> List[Tuple[str, int]]:
        """
        获取词云数据
        
        Args:
            texts_or_messages: 可以是文本列表 List[str] 或消息列表 List[Dict]
            user_id: 如果传消息列表，用于过滤用户（可选）
            top_n: 返回前 N 个词
        """
        if not JIEBA_AVAILABLE:
            return []
        
        user_texts = []
        
        # 判断输入类型
        if texts_or_messages and isinstance(texts_or_messages[0], str):
            # 直接是文本列表
            user_texts = texts_or_messages
        else:
            # 是消息列表，需要提取文本
            for msg in texts_or_messages:
                if user_id and msg.get('user_id') != user_id:
                    continue
                try:
                    raw_content = msg.get('raw_content', '[]')
                    if isinstance(raw_content, str):
                        segments = json.loads(raw_content)
                    else:
                        segments = raw_content
                    
                    for seg in segments:
                        if seg.get('type') == 'text':
                            text = seg.get('data', {}).get('text', '').strip()
                            if text:
                                user_texts.append(text)
                except Exception:
                    continue
        
        if not user_texts:
            return []
        
        # 分词统计
        words = []
        for text in user_texts:
            words.extend(jieba.lcut(text))
        
        # 过滤
        filtered = [
            w for w in words
            if len(w) > 1 and w not in self.stop_words
        ]
        
        # 统计
        counter = Counter(filtered)
        return counter.most_common(top_n)
    
    def analyze_user_active_hours(self, messages: List[Dict], user_id: int) -> Dict[int, int]:
        """
        分析用户活跃时段
        返回: {hour: count, ...}
        """
        import time
        
        hourly = {i: 0 for i in range(24)}
        
        for msg in messages:
            if msg.get('user_id') != user_id:
                continue
            
            created_at = msg.get('created_at', 0)
            if created_at:
                hour = time.localtime(created_at).tm_hour
                hourly[hour] += 1
        
        return hourly
    
    def get_user_type(self, hourly_stats: Dict[int, int]) -> str:
        """
        根据活跃时段判断用户类型
        """
        if not hourly_stats or sum(hourly_stats.values()) == 0:
            return "🫥 潜水员"
        
        # 计算各时段消息占比
        total = sum(hourly_stats.values())
        
        morning = sum(hourly_stats.get(h, 0) for h in range(6, 12)) / total  # 6-12点
        afternoon = sum(hourly_stats.get(h, 0) for h in range(12, 18)) / total  # 12-18点
        evening = sum(hourly_stats.get(h, 0) for h in range(18, 24)) / total  # 18-24点
        night = sum(hourly_stats.get(h, 0) for h in list(range(0, 6))) / total  # 0-6点
        
        # 判断类型
        if night > 0.3:
            return "🦉 夜猫子"
        elif morning > 0.4:
            return "🐦 早起鸟"
        elif evening > 0.5:
            return "🌙 夜间活跃"
        elif afternoon > 0.4:
            return "☀️ 午后达人"
        else:
            return "⚖️ 均衡型"
