from langchain_openai import ChatOpenAI
from typing import Any, Dict, Optional
import os
import logging


logger = logging.getLogger(__name__)

class QwenChatModel(ChatOpenAI):
    """通义千问聊天模型"""

    def __init__(
        self,
        api_key: Optional[str] = None,  # 工厂会传入API密钥
        base_url: Optional[str] = None,
        model: str = None,  # 工厂会传入模型名称
        extra_body: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # 所有参数都由工厂传入，不再有默认值逻辑
        logger.info(f"用于初始化QwenChatModel的参数: model={model}, base_url={base_url}, api_key={api_key}, extra_body={extra_body}, kwargs={kwargs}")


        # 直接传递所有参数：
        # - api_key: 由工厂传入
        # - model: 由工厂传入
        # - extra_body: 用于自定义参数（如阿里云特有参数）
        # - **kwargs: 用于标准OpenAI参数（如temperature, max_tokens等）
        super().__init__(
            model=model,
            base_url=base_url,
            api_key=api_key,
            extra_body=extra_body,
            **kwargs
        )