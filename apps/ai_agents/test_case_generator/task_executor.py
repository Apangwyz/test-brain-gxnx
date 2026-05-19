"""
任务执行器 - 使用线程池执行异步生成任务
确保任务在请求完成后仍能继续执行
"""
import asyncio
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Any
from .progress_manager import get_progress_manager, GenerationStage
from apps.utils.logger_manager import get_logger

logger = get_logger(__name__)

# 全局线程池
_executor_pool: Optional[ThreadPoolExecutor] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None


def get_executor_pool(max_workers: int = 4) -> ThreadPoolExecutor:
    """获取线程池"""
    global _executor_pool
    if _executor_pool is None:
        _executor_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="testcase-gen")
    return _executor_pool


def get_event_loop() -> asyncio.AbstractEventLoop:
    """获取或创建事件循环"""
    global _event_loop, _loop_thread
    
    if _event_loop is None or _event_loop.is_closed():
        # 创建新的事件循环
        _event_loop = asyncio.new_event_loop()
        
        # 在独立线程中运行事件循环
        _loop_thread = threading.Thread(
            target=_run_event_loop,
            name="asyncio-event-loop",
            daemon=True
        )
        _loop_thread.start()
        
        # 等待事件循环启动
        import time
        time.sleep(0.1)
    
    return _event_loop


def _run_event_loop():
    """在独立线程中运行事件循环"""
    global _event_loop
    if _event_loop:
        asyncio.set_event_loop(_event_loop)
        _event_loop.run_forever()


def run_async_task(coro):
    """在线程池中运行异步任务"""
    loop = get_event_loop()
    
    def _run():
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception as e:
            logger.error(f"运行异步任务失败: {e}", exc_info=True)
    
    executor = get_executor_pool()
    executor.submit(_run)


def submit_generation_task(
    task_id: str,
    requirements: str,
    llm_provider: str,
    case_design_methods: list,
    case_categories: list,
    case_count: int,
    generator_func: Callable
):
    """
    提交生成任务到线程池
    
    Args:
        task_id: 任务ID
        requirements: 需求描述
        llm_provider: LLM提供商
        case_design_methods: 测试方法
        case_categories: 测试类型
        case_count: 用例数量
        generator_func: 生成函数
    """
    logger.info(f"提交任务 {task_id} 到线程池")
    
    async def _task_wrapper():
        try:
            logger.info(f"任务 {task_id} 开始执行")
            await generator_func(
                task_id=task_id,
                requirements=requirements,
                llm_provider=llm_provider,
                case_design_methods=case_design_methods,
                case_categories=case_categories,
                case_count=case_count
            )
            logger.info(f"任务 {task_id} 执行完成")
        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
            # 更新进度管理器为错误状态
            progress_manager = get_progress_manager(task_id)
            if progress_manager:
                progress_manager.set_error(str(e))
    
    run_async_task(_task_wrapper())


def shutdown_executor():
    """关闭线程池和事件循环"""
    global _executor_pool, _event_loop, _loop_thread
    
    if _executor_pool:
        _executor_pool.shutdown(wait=True)
        _executor_pool = None
    
    if _event_loop and not _event_loop.is_closed():
        _event_loop.call_soon_threadsafe(_event_loop.stop)
    
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=5)