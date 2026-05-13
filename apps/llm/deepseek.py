from langchain_openai import ChatOpenAI
from typing import Any, Dict, Optional
import os
import logging


logger = logging.getLogger(__name__)


class DeepSeekChatModel(ChatOpenAI):
    """DeepSeek聊天模型"""

    def __init__(
        self,
        api_key: Optional[str] = None,  # 工厂会传入API密钥
        base_url: Optional[str] = None,
        model: Optional[str] = None,  # 工厂会传入模型名称
        enable_thinking: Optional[bool] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # 处理 enable_thinking 参数（DeepSeek特有参数，需要放入extra_body）
        if enable_thinking is not None:
            if extra_body is None:
                extra_body = {}
            extra_body["enable_thinking"] = enable_thinking
        # 直接传递所有参数：
        # - api_key: 由工厂传入
        # - model: 由工厂传入
        # - extra_body: 用于自定义参数（如enable_thinking）
        # - **kwargs: 用于标准OpenAI参数（如temperature, max_tokens等）
        logger.info(f"用于初始化DeepSeekChatModel的参数: model={model}, base_url={base_url}, api_key={api_key}, extra_body={extra_body}, kwargs={kwargs}")
        super().__init__(
            model=model,
            base_url=base_url,
            api_key=api_key,
            extra_body=extra_body,
            **kwargs
        )