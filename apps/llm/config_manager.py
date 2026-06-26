"""
LLM配置中心化管理器

统一管理各AI Agent的LLM提供商配置，消除各模块重复读取配置的问题。
所有Agent模块应从此管理器获取LLM配置，而非直接读取 settings.LLM_PROVIDERS。

新增 LLMProviderPriorityManager：支持通过 settings.py 和 .env 环境变量
配置 Provider 优先级列表，实现调用失败时按优先级自动降级。
"""

import os
from django.conf import settings
from apps.utils.logger_manager import get_logger

logger = get_logger(__name__)


def get_llm_config(agent_name: str = None):
    """
    获取LLM提供商配置。

    Args:
        agent_name: AI Agent名称，例如 "test_case_generator", "prd_analyzer" 等。
                    为 None 时返回全局默认配置。

    Returns:
        (provider, providers_dict) 元组：
            provider: 该Agent使用的默认提供商名称
            providers_dict: 所有可用提供商的配置字典 {provider_name: config}
    """
    llm_config = getattr(settings, "LLM_PROVIDERS", {})
    global_default_provider = llm_config.get("default_provider", "deepseek")
    providers = {k: v for k, v in llm_config.items() if k != "default_provider"}

    if agent_name is None:
        return global_default_provider, providers

    agent_defaults = getattr(settings, "AGENT_LLM_DEFAULTS", {})
    agent_cfg = agent_defaults.get(agent_name)

    if agent_cfg is None:
        logger.warning(
            f"Agent '{agent_name}' 未在 AGENT_LLM_DEFAULTS 中配置，"
            f"使用全局默认提供商 '{global_default_provider}'"
        )
        return global_default_provider, providers

    agent_provider = agent_cfg.get("provider", global_default_provider)
    if agent_provider not in providers:
        logger.warning(
            f"Agent '{agent_name}' 配置的提供商 '{agent_provider}' 不存在于 "
            f"LLM_PROVIDERS 中，使用全局默认提供商 '{global_default_provider}'"
        )
        agent_provider = global_default_provider

    return agent_provider, providers


def get_provider_config(agent_name: str = None):
    """
    获取指定Agent的完整提供商配置字典。

    Args:
        agent_name: AI Agent名称，为 None 时返回全局默认提供商的配置

    Returns:
        provider_config: 该提供商的具体配置字典（含 model, base_url, temperature 等）
    """
    provider, providers = get_llm_config(agent_name)
    return providers.get(provider, {})


def get_agent_llm_configs(agent_name: str):
    """
    兼容旧接口：包装 get_llm_config 以保持与现有代码的兼容性。
    """
    return get_llm_config(agent_name)



class LLMProviderPriorityManager:
    """Provider 优先级管理器

    从 settings.py 和 .env 环境变量读取 Provider 优先级列表。
    环境变量优先级高于 settings.py，支持按 Agent 粒度覆盖。

    解析顺序（优先级从高到低）：
      1. 环境变量 AGENT_PRIORITY__{agent_name}（按 Agent 覆盖）
      2. 环境变量 LLM_PROVIDER_PRIORITY（全局默认）
      3. settings.LLM_PROVIDER_PRIORITY["default"]
      4. 回退：只使用 AGENT_LLM_DEFAULTS 中配置的单一 Provider
    """

    @staticmethod
    def get_priority_list(agent_name: str = None, preferred: str = None) -> list:
        """获取按优先级排列的 (provider_name, config) 列表。

        Args:
            agent_name: AI Agent 名称，用于获取该 Agent 的优先级覆盖配置。
            preferred: 首选 Provider（前端手动选择），会提升到列表最前面。

        Returns:
            按优先级排列的 [(provider_name, config_dict), ...] 列表。
        """
        llm_config = getattr(settings, "LLM_PROVIDERS", {})
        provider_dict = {k: v for k, v in llm_config.items() if k != "default_provider"}

        # 1. 获取原始优先级名称列表
        raw_priority = LLMProviderPriorityManager._resolve_priority(agent_name)

        # 2. 确保 preferred 在最前面
        if preferred and preferred in provider_dict:
            raw_priority = [preferred] + [p for p in raw_priority if p != preferred]

        # 3. 去重 + 过滤不存在的 Provider
        seen = set()
        ordered = []
        for p in raw_priority:
            if p not in seen and p in provider_dict:
                seen.add(p)
                ordered.append((p, provider_dict[p]))

        if not ordered:
            logger.warning(f"Agent '{agent_name}' 无有效的 Provider 优先级配置，使用所有可用 Provider")
            ordered = list(provider_dict.items())

        logger.info(f"Agent '{agent_name}' Provider 优先级列表: {[p for p, _ in ordered]}")
        return ordered

    @staticmethod
    def _resolve_priority(agent_name: str = None) -> list:
        """按优先级链解析出 Provider 名称列表。"""
        llm_config = getattr(settings, "LLM_PROVIDERS", {})

        # 1. 按 Agent 的环境变量覆盖
        if agent_name:
            env_key = f"AGENT_PRIORITY__{agent_name}"
            env_val = os.getenv(env_key)
            if env_val:
                result = [x.strip() for x in env_val.split(",") if x.strip()]
                logger.info(f"从环境变量 {env_key} 读取优先级: {result}")
                return result

        # 2. 全局环境变量
        env_val = os.getenv("LLM_PROVIDER_PRIORITY")
        if env_val:
            result = [x.strip() for x in env_val.split(",") if x.strip()]
            logger.info(f"从环境变量 LLM_PROVIDER_PRIORITY 读取优先级: {result}")
            return result

        # 3. settings.py 中的优先级配置
        priority_config = getattr(settings, "LLM_PROVIDER_PRIORITY", {})

        if agent_name and agent_name in priority_config:
            logger.info(f"从 settings.LLM_PROVIDER_PRIORITY['{agent_name}'] 读取优先级: {priority_config[agent_name]}")
            return priority_config[agent_name]

        if "default" in priority_config:
            logger.info(f"从 settings.LLM_PROVIDER_PRIORITY['default'] 读取优先级: {priority_config['default']}")
            return priority_config["default"]

        # 4. 回退：从 AGENT_LLM_DEFAULTS 取单一 Provider
        agent_defaults = getattr(settings, "AGENT_LLM_DEFAULTS", {})
        provider = None
        if agent_name and agent_name in agent_defaults:
            provider = agent_defaults[agent_name].get("provider")

        if not provider:
            provider = llm_config.get("default_provider", "deepseek")

        logger.info(f"回退使用 AGENT_LLM_DEFAULTS 单一 Provider: {provider}")
        return [provider]
