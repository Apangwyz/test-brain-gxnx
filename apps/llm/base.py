from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import time
from dotenv import load_dotenv
from apps.utils.logger_manager import get_logger
from django.conf import settings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from .callbacks import LoggingCallbackHandler
from .config_manager import LLMProviderPriorityManager
# from .deepseek import DeepSeekChatModel
# from .qwen import QwenChatModel


# 加载.env文件中的环境变量
load_dotenv()

class BaseLLMService(BaseChatModel):
    """基础LLM服务类"""
    
    def __init__(self):
        # 使用统一日志管理器获取日志记录器
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本响应"""
        pass
    
    @abstractmethod
    def generate_with_history(self, 
                             messages: List[Dict[str, str]], 
                             **kwargs) -> str:
        """基于对话历史生成响应"""
        pass
    
    def _log_request(self, method_name: str, prompt_or_messages, **kwargs):
        """记录请求日志"""
        if isinstance(prompt_or_messages, str):
            # 对于单个prompt，只记录前100个字符
            prompt_preview = prompt_or_messages[:100] + "..." if len(prompt_or_messages) > 100 else prompt_or_messages
            self.logger.info(f"开始调用 {method_name}: prompt='{prompt_preview}'")
        else:
            # 对于消息列表，记录消息数量和最后一条消息
            last_msg = prompt_or_messages[-1] if prompt_or_messages else {}
            last_content = last_msg.get('content', '')
            content_preview = last_content[:100] + "..." if len(last_content) > 100 else last_content
            self.logger.info(f"开始调用 {method_name}: 消息数量={len(prompt_or_messages)}, 最后消息='{content_preview}'")
        
        # 记录关键参数
        important_params = {k: v for k, v in kwargs.items() if k in ['model', 'temperature', 'max_tokens']}
        if important_params:
            self.logger.info(f"调用参数: {important_params}")
    
    def _log_response(self, method_name: str, response: str, elapsed_time: float):
        """记录响应日志"""
        response_preview = response[:100] + "..." if len(response) > 100 else response
        self.logger.info(f"调用成功 {method_name}: 耗时={elapsed_time:.2f}秒, 响应='{response_preview}'")
    
    def _log_error(self, method_name: str, error: Exception, elapsed_time: float):
        """记录错误日志"""
        self.logger.error(f"调用失败 {method_name}: 耗时={elapsed_time:.2f}秒, 错误={str(error)}", exc_info=True)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """实现 BaseChatModel 要求的方法"""
        raise NotImplementedError()
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return "base_llm_service"

class LLMServiceFactory:
    """大模型服务工厂"""
    
    @staticmethod
    def create(provider: str, **config) -> Any:
        """创建LLM服务实例"""
        logger = get_logger(__class__.__name__)
        logger.info(f"创建LLM服务: provider={provider}")
        
        # 获取LLM配置
        llm_config = getattr(settings, 'LLM_PROVIDERS', {})
        default_provider = llm_config.get('default_provider', 'deepseek')
        providers = {k: v for k, v in llm_config.items() if k != 'default_provider'}
        
        # 检查提供商是否存在
        if provider not in providers:
            logger.warning(f"不支持的LLM提供商: {provider}，使用默认提供商: {default_provider}")
            provider = default_provider
        
        # 获取提供商配置（来自settings.py）
        provider_config = providers.get(provider, {}).copy()
        
        # 获取API密钥
        # 优先使用运行时传入的 api_key，其次环境变量
        # DeepSeek 通过阿里云 DashScope 访问时需 QWEN_API_KEY
        api_key = config.get('api_key')
        if not api_key:
            api_key = os.getenv(f"{provider.upper()}_API_KEY")
        if not api_key:
            # 通用后备：检查 QWEN_API_KEY（阿里云 DashScope 统一密钥）
            api_key = os.getenv('QWEN_API_KEY')
        if api_key:
            provider_config['api_key'] = api_key
        
        # 创建回调处理器
        callbacks = [LoggingCallbackHandler()]
        
        # 合并配置：settings.py 配置为基础，运行时配置覆盖
        final_config = {
            **provider_config,  # 来自settings.py的默认配置
            **config,           # 运行时传入的配置（优先级更高）
            'callbacks': callbacks,
            'verbose': True
        }
        
        # 打印最终配置（调试用）
        logger.info(f"Final config for {provider}: {final_config}")
        
        # 根据提供商创建相应的服务实例
        if provider.lower() == "deepseek":
            from .deepseek import DeepSeekChatModel
            return DeepSeekChatModel(**final_config)
        elif provider.lower() == "qwen":
            from .qwen import QwenChatModel
            return QwenChatModel(**final_config)
        else:
            logger.error(f"未实现的LLM提供商: {provider}")
            raise NotImplementedError(f"LLM provider {provider} is not implemented")

    @staticmethod
    def create_with_fallback(agent_name: str = None, preferred_provider: str = None, max_fallback: int = None, **config) -> "FallbackLLMWrapper":
        """创建带优先级降级能力的 LLM 服务包装器。

        Args:
            agent_name: AI Agent 名称，用于获取该 Agent 的优先级配置。
            preferred_provider: 首选 Provider（前端手动选择）。
            max_fallback: 最大降级次数，None 表示不限制。
            **config: 传递给 LLM 的额外配置参数。

        Returns:
            FallbackLLMWrapper 实例，接口与 BaseChatModel 兼容（支持 invoke/ainvoke）。
        """
        logger = get_logger(__name__)
        logger.info(f"创建带降级的 LLM 服务: agent_name={agent_name}, preferred={preferred_provider}")

        priority_list = LLMProviderPriorityManager.get_priority_list(
            agent_name=agent_name,
            preferred=preferred_provider,
        )

        return FallbackLLMWrapper(priority_list, max_fallback=max_fallback, **config)


class FallbackLLMWrapper:
    """带优先级降级的 LLM 服务包装器。

    内部维护按优先级排序的 Provider 列表。
    调用 invoke 时使用优先级最高的 Provider；如果抛出降级触发异常，
    自动降级到下一个可用 Provider。

    用法::

        wrapper = LLMServiceFactory.create_with_fallback(
            agent_name="test_case_generator",
            preferred_provider="qwen",
        )
        response = wrapper.invoke(messages)  # 自动降级
    """

    # 触发降级的异常类型
    FALLBACK_TRIGGERS = (
        TimeoutError,
        ConnectionError,
    )

    def __init__(self, priority_list: list, max_fallback: int = None, **base_config):
        """
        Args:
            priority_list: 按优先级排列的 [(provider_name, config), ...] 列表。
            max_fallback: 最大降级次数，None 表示不限制。
            **base_config: 传递给底层 LLM 实例的额外配置。
        """
        self.logger = get_logger(self.__class__.__name__)
        self._priority_list = priority_list
        self._current_index = 0
        self._base_config = base_config
        self._max_fallback = max_fallback
        self._llm_cache = {}  # provider_name -> LLM instance
        self._fallback_count = 0
        self._current_provider = priority_list[0][0] if priority_list else None

    @property
    def current_provider(self) -> str:
        """当前正在使用的 Provider 名称。"""
        return self._current_provider

    def _get_or_create_llm(self, provider_name: str, provider_config: dict):
        """获取或创建指定 Provider 的 LLM 实例（缓存）。"""
        if provider_name not in self._llm_cache:
            merged_config = {
                **provider_config,
                **self._base_config,
            }
            self._llm_cache[provider_name] = LLMServiceFactory.create(provider_name, **merged_config)
        return self._llm_cache[provider_name]

    def invoke(self, messages, **kwargs):
        """调用 LLM，失败时按优先级自动降级。"""
        last_error = None
        start_index = self._current_index

        for i in range(start_index, len(self._priority_list)):
            provider_name, provider_config = self._priority_list[i]

            # 检查降级次数限制
            if self._max_fallback is not None and i > start_index:
                self._fallback_count += 1
                if self._fallback_count > self._max_fallback:
                    self.logger.error(
                        f"降级次数超过限制 ({self._max_fallback})，"
                        f"Provider '{provider_name}' 跳过"
                    )
                    continue

            try:
                llm = self._get_or_create_llm(provider_name, provider_config)
                self._current_provider = provider_name
                self._current_index = i

                self.logger.info(f"使用 Provider '{provider_name}' 调用 LLM (优先级位置 {i})")
                response = llm.invoke(messages, **kwargs)
                return response

            except self.FALLBACK_TRIGGERS as e:
                self.logger.warning(
                    f"Provider '{provider_name}' 调用失败（{type(e).__name__}），"
                    f"准备降级到下一个可用 Provider: {e}"
                )
                last_error = e
                # 缓存中删除失败的实例，避免下次复用
                self._llm_cache.pop(provider_name, None)
                continue

            except Exception as e:
                # 非降级触发异常，记录日志后继续尝试下一个 Provider
                self.logger.error(
                    f"Provider '{provider_name}' 调用出现非降级异常（{type(e).__name__}），"
                    f"仍尝试降级到下一个 Provider: {e}"
                )
                last_error = e
                self._llm_cache.pop(provider_name, None)
                continue

        # 所有 Provider 均失败
        available = [p for p, _ in self._priority_list]
        error_msg = (
            f"所有 Provider 均已失败: {available}。"
            f"最后错误: {last_error}"
        )
        self.logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    async def ainvoke(self, messages, **kwargs):
        """异步调用 LLM，失败时按优先级自动降级。"""
        last_error = None
        start_index = self._current_index

        for i in range(start_index, len(self._priority_list)):
            provider_name, provider_config = self._priority_list[i]

            if self._max_fallback is not None and i > start_index:
                self._fallback_count += 1
                if self._fallback_count > self._max_fallback:
                    self.logger.error(
                        f"降级次数超过限制 ({self._max_fallback})，"
                        f"Provider '{provider_name}' 跳过"
                    )
                    continue

            try:
                llm = self._get_or_create_llm(provider_name, provider_config)
                self._current_provider = provider_name
                self._current_index = i

                self.logger.info(f"使用 Provider '{provider_name}' 异步调用 LLM (优先级位置 {i})")
                response = await llm.ainvoke(messages, **kwargs)
                return response

            except self.FALLBACK_TRIGGERS as e:
                self.logger.warning(
                    f"Provider '{provider_name}' 异步调用失败（{type(e).__name__}），"
                    f"准备降级到下一个可用 Provider: {e}"
                )
                last_error = e
                self._llm_cache.pop(provider_name, None)
                continue

            except Exception as e:
                self.logger.error(
                    f"Provider '{provider_name}' 异步调用出现非降级异常（{type(e).__name__}），"
                    f"仍尝试降级到下一个 Provider: {e}"
                )
                last_error = e
                self._llm_cache.pop(provider_name, None)
                continue

        available = [p for p, _ in self._priority_list]
        error_msg = (
            f"所有 Provider 均已失败: {available}。"
            f"最后错误: {last_error}"
        )
        self.logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error
