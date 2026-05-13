from langchain_core.callbacks import BaseCallbackHandler
from apps.utils.logger_manager import get_logger
import time
from typing import Any, Dict, Optional


class LoggingCallbackHandler(BaseCallbackHandler):
    """日志记录回调处理器"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self._llm_run_start_ts: Dict[str, float] = {}

    def _clip(self, value: Any, limit: int = 500) -> str:
        try:
            s = str(value)
        except Exception as e:
            s = f"<unprintable:{type(value).__name__}:{e}>"
        if len(s) > limit:
            return s[:limit] + f"...<truncated,len={len(s)}>"
        return s

    def _get_run_id(self, **kwargs) -> str:
        run_id = kwargs.get("run_id")
        return str(run_id) if run_id is not None else "<no_run_id>"

    def _get_model_name(self, serialized: Any, **kwargs) -> str:
        model = kwargs.get("model") or kwargs.get("model_name")
        if model:
            return str(model)
        try:
            if isinstance(serialized, dict):
                for k in ("name", "id", "model", "model_name"):
                    v = serialized.get(k)
                    if v:
                        return str(v)
        except Exception:
            pass
        return "<unknown_model>"
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM开始生成时的回调"""
        run_id = self._get_run_id(**kwargs)
        self._llm_run_start_ts[run_id] = time.time()

        model_name = self._get_model_name(serialized, **kwargs)
        prompt0 = prompts[0] if isinstance(prompts, list) and prompts else ""
        prompt_len = len(prompt0) if isinstance(prompt0, str) else None
        self.logger.info(
            "[LLM] start run_id=%s model=%s prompt_len=%s prompt_preview=%s",
            run_id,
            model_name,
            prompt_len,
            self._clip(prompt0, 300),
        )
    
    def on_llm_end(self, response, **kwargs):
        """LLM生成完成时的回调"""
        run_id = self._get_run_id(**kwargs)
        start_ts = self._llm_run_start_ts.pop(run_id, None)
        elapsed_ms = int((time.time() - start_ts) * 1000) if start_ts else None

        resp_str = self._clip(response, 800)
        self.logger.info(
            "[LLM] end run_id=%s elapsed_ms=%s response_preview=%s",
            run_id,
            elapsed_ms,
            resp_str,
        )
        self.logger.debug("[LLM] response_full=%s", self._clip(response, 8000))
    
    def on_llm_error(self, error, **kwargs):
        """LLM生成出错时的回调"""
        run_id = self._get_run_id(**kwargs)
        start_ts = self._llm_run_start_ts.pop(run_id, None)
        elapsed_ms = int((time.time() - start_ts) * 1000) if start_ts else None
        self.logger.error(
            "[LLM] error run_id=%s elapsed_ms=%s error=%s",
            run_id,
            elapsed_ms,
            self._clip(error, 800),
            exc_info=True,
        )
    
    def on_agent_action(self, action, **kwargs):
        """Agent执行行动时的回调"""
        self.logger.info(f"🤖 Agent行动: {action.tool}")
        self.logger.info(f"📝 行动输入: {action.tool_input}")
        self.logger.debug(f"完整行动: {action}")
    
    def on_agent_finish(self, finish, **kwargs):
        """Agent完成时的回调"""
        self.logger.info("✅ Agent执行完成")
        self.logger.info(f"📋 最终输出: {finish.return_values.get('output', '无输出')[:200]}...")
        self.logger.debug(f"完整结果: {finish}")
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        """工具开始执行时的回调"""
        tool_name = serialized.get('name', 'unknown_tool')
        self.logger.info(f"🔧 开始执行工具: {tool_name}")
        self.logger.debug(f"工具输入: {input_str}")
    
    def on_tool_end(self, output, **kwargs):
        """工具执行完成时的回调"""
        self.logger.info("🔧 工具执行完成")
        output_preview = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)
        self.logger.info(f"🔧 工具输出: {output_preview}")
        self.logger.debug(f"完整工具输出: {output}")
    
    def on_tool_error(self, error, **kwargs):
        """工具执行出错时的回调"""
        self.logger.error(f"🔧 工具执行出错: {str(error)}")
    
    def on_chain_start(self, serialized, inputs, **kwargs):
        """链开始执行时的回调"""
        chain_name = serialized.get('name', 'unknown_chain')
        self.logger.debug(f"🔗 链开始: {chain_name}, 输入: {inputs}")
    
    def on_chain_end(self, outputs, **kwargs):
        """链执行完成时的回调"""
        self.logger.debug(f"🔗 链完成，输出: {outputs}")
    
    def on_chain_error(self, error, **kwargs):
        """链执行出错时的回调"""
        self.logger.error(f"🔗 链出错: {str(error)}")