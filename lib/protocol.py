# -*- coding: utf-8 -*-
"""
OneBot V11 协议解析与构建模块
实现消息解析、事件分类和 API 调用构建
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("Protocol")


class PostType(Enum):
    """事件类型"""
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META_EVENT = "meta_event"


class MessageType(Enum):
    """消息类型"""
    PRIVATE = "private"
    GROUP = "group"


class NoticeType(Enum):
    """通知类型"""
    GROUP_UPLOAD = "group_upload"
    GROUP_ADMIN = "group_admin"
    GROUP_DECREASE = "group_decrease"
    GROUP_INCREASE = "group_increase"
    GROUP_BAN = "group_ban"
    FRIEND_ADD = "friend_add"
    GROUP_RECALL = "group_recall"
    FRIEND_RECALL = "friend_recall"
    NOTIFY = "notify"


@dataclass
class MessageSegment:
    """消息段"""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def text(cls, text: str) -> "MessageSegment":
        """文本消息"""
        return cls(type="text", data={"text": text})
    
    @classmethod
    def image(cls, file: str, url: str = None) -> "MessageSegment":
        """图片消息"""
        data = {"file": file}
        if url:
            data["url"] = url
        return cls(type="image", data=data)
    
    @classmethod
    def image_base64(cls, base64_data: str) -> "MessageSegment":
        """Base64 图片消息"""
        return cls(type="image", data={"file": f"base64://{base64_data}"})
    
    @classmethod
    def at(cls, qq: Union[int, str]) -> "MessageSegment":
        """@某人"""
        return cls(type="at", data={"qq": str(qq)})
    
    @classmethod
    def at_all(cls) -> "MessageSegment":
        """@全体成员"""
        return cls(type="at", data={"qq": "all"})
    
    @classmethod
    def face(cls, id: int) -> "MessageSegment":
        """QQ表情"""
        return cls(type="face", data={"id": str(id)})
    
    @classmethod
    def reply(cls, id: int) -> "MessageSegment":
        """回复消息"""
        return cls(type="reply", data={"id": str(id)})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {"type": self.type, "data": self.data}


@dataclass
class GroupMessage:
    """群消息事件"""
    message_id: int
    group_id: int
    user_id: int
    message: List[MessageSegment]
    raw_message: str
    time: int
    self_id: int
    sender: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroupMessage":
        """从字典创建"""
        message_segments = [
            MessageSegment(type=seg['type'], data=seg.get('data', {}))
            for seg in data.get('message', [])
        ]
        return cls(
            message_id=data.get('message_id', 0),
            group_id=data.get('group_id', 0),
            user_id=data.get('user_id', 0),
            message=message_segments,
            raw_message=data.get('raw_message', ''),
            time=data.get('time', int(time.time())),
            self_id=data.get('self_id', 0),
            sender=data.get('sender', {})
        )
    
    def get_plain_text(self) -> str:
        """获取纯文本内容"""
        texts = []
        for seg in self.message:
            if seg.type == 'text':
                texts.append(seg.data.get('text', ''))
        return ''.join(texts).strip()
    
    def get_images(self) -> List[Dict[str, str]]:
        """获取所有图片"""
        images = []
        for seg in self.message:
            if seg.type == 'image':
                images.append({
                    'file': seg.data.get('file', ''),
                    'url': seg.data.get('url', '')
                })
        return images
    
    def has_at(self, qq: int) -> bool:
        """检查是否@了某人"""
        for seg in self.message:
            if seg.type == 'at' and str(seg.data.get('qq')) == str(qq):
                return True
        return False


@dataclass
class FileUploadNotice:
    """群文件上传通知"""
    group_id: int
    user_id: int
    file: Dict[str, Any]
    time: int
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileUploadNotice":
        return cls(
            group_id=data.get('group_id', 0),
            user_id=data.get('user_id', 0),
            file=data.get('file', {}),
            time=data.get('time', int(time.time()))
        )


class OneBotProtocol:
    """OneBot V11 协议处理器"""
    
    def __init__(self):
        self._echo_counter = 0
    
    def _get_echo(self) -> str:
        """生成唯一的 echo 标识"""
        self._echo_counter += 1
        return f"echo_{self._echo_counter}_{int(time.time())}"
    
    def parse_event(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析 OneBot 事件
        
        Args:
            data: 原始 JSON 数据
            
        Returns:
            解析后的事件数据，包含 event_type 字段
        """
        post_type = data.get('post_type')
        
        if post_type == 'message':
            return self._parse_message_event(data)
        elif post_type == 'notice':
            return self._parse_notice_event(data)
        elif post_type == 'request':
            return self._parse_request_event(data)
        elif post_type == 'meta_event':
            return self._parse_meta_event(data)
        
        return None
    
    def _parse_message_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析消息事件"""
        msg_type = data.get('message_type')
        
        if msg_type == 'group':
            return {
                'event_type': 'group_message',
                'data': GroupMessage.from_dict(data)
            }
        elif msg_type == 'private':
            return {
                'event_type': 'private_message',
                'data': data
            }
        
        return {'event_type': 'unknown_message', 'data': data}
    
    def _parse_notice_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析通知事件"""
        notice_type = data.get('notice_type')
        
        if notice_type == 'group_upload':
            return {
                'event_type': 'group_upload',
                'data': FileUploadNotice.from_dict(data)
            }
        elif notice_type == 'group_recall':
            return {
                'event_type': 'group_recall',
                'data': data
            }
        elif notice_type == 'group_increase':
            return {
                'event_type': 'group_increase',
                'data': data
            }
        elif notice_type == 'group_decrease':
            return {
                'event_type': 'group_decrease',
                'data': data
            }
        
        return {'event_type': f'notice_{notice_type}', 'data': data}
    
    def _parse_request_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析请求事件"""
        return {'event_type': 'request', 'data': data}
    
    def _parse_meta_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析元事件"""
        meta_type = data.get('meta_event_type')
        
        if meta_type == 'heartbeat':
            return {'event_type': 'heartbeat', 'data': data}
        elif meta_type == 'lifecycle':
            return {'event_type': 'lifecycle', 'data': data}
        
        return {'event_type': f'meta_{meta_type}', 'data': data}
    
    # ==================== API 构建方法 ====================
    
    def build_send_group_msg(self, group_id: int, 
                             message: Union[str, List[MessageSegment]]) -> str:
        """
        构建发送群消息的 API 调用
        
        Args:
            group_id: 群号
            message: 消息内容，可以是字符串或消息段列表
        """
        if isinstance(message, str):
            msg_array = [MessageSegment.text(message).to_dict()]
        else:
            msg_array = [seg.to_dict() for seg in message]
        
        payload = {
            "action": "send_group_msg",
            "params": {
                "group_id": group_id,
                "message": msg_array
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload, ensure_ascii=False)
    
    def build_send_private_msg(self, user_id: int, 
                               message: Union[str, List[MessageSegment]]) -> str:
        """构建发送私聊消息的 API 调用"""
        if isinstance(message, str):
            msg_array = [MessageSegment.text(message).to_dict()]
        else:
            msg_array = [seg.to_dict() for seg in message]
        
        payload = {
            "action": "send_private_msg",
            "params": {
                "user_id": user_id,
                "message": msg_array
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload, ensure_ascii=False)
    
    def build_get_group_member_list(self, group_id: int) -> str:
        """构建获取群成员列表的 API 调用"""
        payload = {
            "action": "get_group_member_list",
            "params": {
                "group_id": group_id
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
    
    def build_get_group_info(self, group_id: int) -> str:
        """构建获取群信息的 API 调用"""
        payload = {
            "action": "get_group_info",
            "params": {
                "group_id": group_id
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
    
    def build_get_stranger_info(self, user_id: int) -> str:
        """构建获取陌生人信息的 API 调用"""
        payload = {
            "action": "get_stranger_info",
            "params": {
                "user_id": user_id
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
    
    def build_get_group_file_url(self, group_id: int, file_id: str, 
                                  bus_id: int) -> str:
        """构建获取群文件链接的 API 调用"""
        payload = {
            "action": "get_group_file_url",
            "params": {
                "group_id": group_id,
                "file_id": file_id,
                "bus_id": bus_id
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
    
    def build_delete_msg(self, message_id: int) -> str:
        """构建撤回消息的 API 调用"""
        payload = {
            "action": "delete_msg",
            "params": {
                "message_id": message_id
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
    
    def build_set_group_ban(self, group_id: int, user_id: int, 
                            duration: int = 60) -> str:
        """构建群组禁言的 API 调用"""
        payload = {
            "action": "set_group_ban",
            "params": {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration
            },
            "echo": self._get_echo()
        }
        return json.dumps(payload)
