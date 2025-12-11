# -*- coding: utf-8 -*-
"""
命令系统模块
使用装饰器模式注册命令，支持别名和自动生成帮助
"""

import logging
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("Commands")


@dataclass
class CommandInfo:
    """命令信息"""
    name: str                          # 命令名
    handler: Callable                  # 处理函数
    aliases: List[str] = field(default_factory=list)  # 别名
    description: str = ""              # 描述
    usage: str = ""                    # 用法
    category: str = "通用"             # 分类
    admin_only: bool = False           # 仅管理员


class CommandRegistry:
    """命令注册中心"""
    
    def __init__(self, prefix: str = "/"):
        self.prefix = prefix
        self._commands: Dict[str, CommandInfo] = {}
        self._aliases: Dict[str, str] = {}  # 别名 -> 主命令名
    
    @property
    def commands(self) -> Dict[str, CommandInfo]:
        """返回所有已注册的命令"""
        return self._commands
    
    def command(
        self,
        name: str,
        aliases: List[str] = None,
        description: str = "",
        usage: str = "",
        category: str = "通用",
        admin_only: bool = False
    ):
        """
        命令装饰器
        
        @bot.commands.command("stat", aliases=["统计"], description="查看热词统计")
        async def cmd_stat(ctx):
            ...
        """
        aliases = aliases or []
        
        def decorator(func: Callable):
            cmd_info = CommandInfo(
                name=name,
                handler=func,
                aliases=aliases,
                description=description,
                usage=usage,
                category=category,
                admin_only=admin_only
            )
            
            # 注册主命令
            self._commands[name.lower()] = cmd_info
            
            # 注册别名
            for alias in aliases:
                self._aliases[alias.lower()] = name.lower()
            
            logger.debug(f"注册命令: {name} (别名: {aliases})")
            return func
        
        return decorator
    
    def register(self, cmd_info: CommandInfo):
        """直接注册命令信息对象"""
        # 注册主命令
        self._commands[cmd_info.name.lower()] = cmd_info
        
        # 注册别名
        for alias in (cmd_info.aliases or []):
            self._aliases[alias.lower()] = cmd_info.name.lower()
        
        logger.debug(f"注册命令: {cmd_info.name} (别名: {cmd_info.aliases})")
    
    def get(self, cmd_name: str) -> Optional[CommandInfo]:
        """获取命令信息 (get_command 的别名)"""
        return self.get_command(cmd_name)
    
    def get_command(self, cmd_name: str) -> Optional[CommandInfo]:
        """获取命令信息"""
        cmd_name = cmd_name.lower()
        """获取命令信息"""
        cmd_name = cmd_name.lower()
        
        # 先查主命令
        if cmd_name in self._commands:
            return self._commands[cmd_name]
        
        # 再查别名
        if cmd_name in self._aliases:
            main_cmd = self._aliases[cmd_name]
            return self._commands.get(main_cmd)
        
        return None
    
    def parse_command(self, text: str) -> Optional[tuple]:
        """
        解析命令文本
        返回: (CommandInfo, args) 或 None
        """
        if not text.startswith(self.prefix):
            return None
        
        # 去掉前缀，分割命令和参数
        content = text[len(self.prefix):].strip()
        if not content:
            return None
        
        parts = content.split(maxsplit=1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        cmd_info = self.get_command(cmd_name)
        if cmd_info:
            return (cmd_info, args)
        
        return None
    
    def get_all_commands(self) -> List[CommandInfo]:
        """获取所有命令"""
        return list(self._commands.values())
    
    def get_commands_by_category(self) -> Dict[str, List[CommandInfo]]:
        """按分类获取命令"""
        categories = {}
        for cmd in self._commands.values():
            if cmd.category not in categories:
                categories[cmd.category] = []
            categories[cmd.category].append(cmd)
        return categories
    
    def generate_help_text(self) -> str:
        """生成帮助文本"""
        lines = ["📖 QQ群聊统计机器人 - 命令帮助", "─" * 25, ""]
        
        categories = self.get_commands_by_category()
        
        for category, commands in categories.items():
            lines.append(f"【{category}】")
            for cmd in commands:
                # 主命令和别名
                cmd_str = f"{self.prefix}{cmd.name}"
                if cmd.aliases:
                    alias_str = ", ".join(f"{self.prefix}{a}" for a in cmd.aliases)
                    cmd_str = f"{cmd_str} ({alias_str})"
                
                # 描述
                desc = cmd.description or "暂无描述"
                lines.append(f"  {cmd_str}")
                lines.append(f"    └ {desc}")
                
                # 用法
                if cmd.usage:
                    lines.append(f"    └ 用法: {cmd.usage}")
            
            lines.append("")
        
        lines.append("─" * 25)
        lines.append("💡 发送命令即可使用对应功能")
        
        return "\n".join(lines)
    
    def generate_help(self, prefix: str = None) -> str:
        """生成帮助文本的别名方法"""
        if prefix:
            old_prefix = self.prefix
            self.prefix = prefix
            result = self.generate_help_text()
            self.prefix = old_prefix
            return result
        return self.generate_help_text()


@dataclass
class CommandContext:
    """命令上下文"""
    group_id: int
    user_id: int
    args: str = ""
    message: Any = None      # GroupMessage 原始消息对象
    bot: Any = None          # QQStatBot 实例
    message_id: int = 0
    raw_message: str = ""
    
    @property
    def args_list(self) -> List[str]:
        """参数列表"""
        return self.args.split() if self.args else []
    
    def get_arg(self, index: int, default: str = "") -> str:
        """获取指定位置的参数"""
        args = self.args_list
        return args[index] if index < len(args) else default
    
    def get_at_users(self) -> List[int]:
        """从参数中提取 @ 的用户"""
        # 这里简化处理，实际可能需要从原始消息中解析
        import re
        users = []
        # 匹配 QQ 号
        for match in re.finditer(r'\[CQ:at,qq=(\d+)\]|@(\d+)', self.args):
            qq = match.group(1) or match.group(2)
            if qq:
                users.append(int(qq))
        return users
