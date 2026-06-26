"""
LLM 工具函数

配置管理功能已迁移到 config_manager.py，此文件保留兼容性接口。
"""

from .config_manager import get_llm_config


def get_agent_llm_configs(agent_name: str):
    """
    获取AI Agent的LLM配置（兼容旧接口）

    内部委托给 config_manager.get_llm_config。
    """
    return get_llm_config(agent_name)
