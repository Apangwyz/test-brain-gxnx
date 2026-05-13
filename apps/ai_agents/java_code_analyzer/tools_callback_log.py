'''
定义触发工具的函数以及工具函数的回调日志记录
'''
import json
import time
from typing import Any, Dict, Optional


def to_log_str(value: Any, *, limit: int = 8000) -> str:
    """将任意对象转为可打印日志字符串，并做长度保护。

    - dict/list/tuple: json.dumps(ensure_ascii=False)
    - 其他类型: str(...)
    - 超过 limit: 截断并附带原始长度
    """
    try:
        if value is None:
            s = "null"
        elif isinstance(value, (dict, list, tuple)):
            s = json.dumps(value, ensure_ascii=False)
        else:
            s = str(value)
    except Exception as e:
        s = f"<unprintable:{type(value).__name__}:{e}>"

    if len(s) > limit:
        return s[:limit] + f"...<truncated,len={len(s)}>"
    return s


def invoke_tool(logger, tool, args: Dict[str, Any], *, label: str, limit: int = 8000) -> Any:
    """统一封装工具调用并记录可核对日志。

    记录内容：label、tool 名称、入参、出参、耗时、异常堆栈。

    注意：这里的 tool 是 LangChain Tool（BaseTool），并非 LLM。
    """
    tool_name = getattr(tool, "name", str(tool))
    t0 = time.time()
    logger.info(
        "[JavaCodeAnalyzer][ToolCall] start label=%s tool=%s args=%s",
        label,
        tool_name,
        to_log_str(args, limit=limit),
    )
    try:
        result = tool.invoke(args)
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[JavaCodeAnalyzer][ToolCall] end label=%s tool=%s elapsed_ms=%s result=%s",
            label,
            tool_name,
            elapsed_ms,
            to_log_str(result, limit=limit),
        )
        return result
    except Exception:
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.exception(
            "[JavaCodeAnalyzer][ToolCall] error label=%s tool=%s elapsed_ms=%s args=%s",
            label,
            tool_name,
            elapsed_ms,
            to_log_str(args, limit=limit),
        )
        raise


def log_node_start(logger, name: str, state: Dict[str, Any], *, project_id: Optional[str] = None) -> float:
    """记录 LangGraph 节点开始日志，并返回计时起点。"""
    start = time.time()
    try:
        logger.info(
            "[JavaCodeAnalyzer][LangGraph] node_start=%s base=%s new=%s project_id=%s",
            name,
            (state.get("base_commit") or "")[:8],
            (state.get("new_commit") or "")[:8],
            project_id,
        )
    except Exception:
        pass
    return start


def log_node_end(logger, name: str, start: float, **extra) -> None:
    """记录 LangGraph 节点结束日志（含耗时与可选摘要字段）。"""
    elapsed_ms = int((time.time() - start) * 1000)
    try:
        if extra:
            logger.info(
                "[JavaCodeAnalyzer][LangGraph] node_end=%s elapsed_ms=%s extra=%s",
                name,
                elapsed_ms,
                extra,
            )
        else:
            logger.info(
                "[JavaCodeAnalyzer][LangGraph] node_end=%s elapsed_ms=%s",
                name,
                elapsed_ms,
            )
    except Exception:
        pass
