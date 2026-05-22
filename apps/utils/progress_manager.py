"""
统一进度管理模块
提供文件上传和内容生成的进度管理功能
支持SSE实时进度推送
"""

import json
import time
import threading
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    ERROR = 'error'
    CANCELLED = 'cancelled'


class StageStatus(Enum):
    """阶段状态枚举"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    ERROR = 'error'


@dataclass
class StageInfo:
    """阶段信息"""
    stage: str
    title: str
    description: str
    status: StageStatus = StageStatus.PENDING
    details: Optional[str] = None
    progress: int = 0


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    message: str


@dataclass
class ProgressData:
    """进度数据"""
    task_id: str
    status: TaskStatus
    overall_progress: int = 0
    current_stage: Optional[StageInfo] = None
    stages: List[StageInfo] = field(default_factory=list)
    logs: List[LogEntry] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    estimated_time_remaining: Optional[str] = None


class GlobalProgressRegistry:
    """全局进度注册表"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._progress_map = {}
                    cls._listeners = {}
        return cls._instance
    
    def register_task(self, task_id: str, stages: List[StageInfo]) -> None:
        """注册任务"""
        with self._lock:
            self._progress_map[task_id] = ProgressData(
                task_id=task_id,
                status=TaskStatus.PENDING,
                stages=stages
            )
            self._listeners[task_id] = []
    
    def update_stage(self, task_id: str, stage_name: str, status: StageStatus, details: str = None) -> None:
        """更新阶段状态"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            for stage in progress_data.stages:
                if stage.stage == stage_name:
                    stage.status = status
                    if details:
                        stage.details = details
                    
                    # 更新当前阶段
                    if status == StageStatus.RUNNING:
                        progress_data.current_stage = stage
            
            # 更新总体进度
            self._update_overall_progress(task_id)
    
    def update_stage_progress(self, task_id: str, stage_name: str, progress: int) -> None:
        """更新阶段进度"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            for stage in progress_data.stages:
                if stage.stage == stage_name:
                    stage.progress = progress
            
            # 更新总体进度
            self._update_overall_progress(task_id)
    
    def _update_overall_progress(self, task_id: str) -> None:
        """计算总体进度"""
        progress_data = self._progress_map.get(task_id)
        if not progress_data or not progress_data.stages:
            return
        
        total_stages = len(progress_data.stages)
        completed_count = sum(1 for s in progress_data.stages if s.status == StageStatus.COMPLETED)
        running_stage = next((s for s in progress_data.stages if s.status == StageStatus.RUNNING), None)
        
        base_progress = (completed_count / total_stages) * 100
        
        if running_stage:
            stage_contribution = (running_stage.progress / 100) * (100 / total_stages)
            progress_data.overall_progress = min(99, int(base_progress + stage_contribution))
        else:
            progress_data.overall_progress = int(base_progress)
    
    def add_log(self, task_id: str, level: str, message: str) -> None:
        """添加日志"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            log_entry = LogEntry(
                timestamp=datetime.now().strftime('%H:%M:%S'),
                level=level,
                message=message
            )
            progress_data.logs.append(log_entry)
            
            # 限制日志数量
            if len(progress_data.logs) > 1000:
                progress_data.logs = progress_data.logs[-500:]
    
    def set_status(self, task_id: str, status: TaskStatus, message: str = None, result: Dict = None) -> None:
        """设置任务状态"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            progress_data.status = status
            progress_data.message = message
            
            if status == TaskStatus.COMPLETED:
                progress_data.overall_progress = 100
                progress_data.result = result
            elif status == TaskStatus.ERROR:
                progress_data.result = result
    
    def get_progress(self, task_id: str) -> Optional[ProgressData]:
        """获取进度数据"""
        with self._lock:
            return self._progress_map.get(task_id)
    
    def remove_task(self, task_id: str) -> None:
        """移除任务"""
        with self._lock:
            self._progress_map.pop(task_id, None)
            self._listeners.pop(task_id, None)
    
    def add_listener(self, task_id: str, callback: Callable) -> None:
        """添加监听器"""
        with self._lock:
            if task_id not in self._listeners:
                self._listeners[task_id] = []
            self._listeners[task_id].append(callback)
    
    def remove_listener(self, task_id: str, callback: Callable) -> None:
        """移除监听器"""
        with self._lock:
            if task_id in self._listeners:
                self._listeners[task_id].remove(callback)
    
    def notify_listeners(self, task_id: str) -> None:
        """通知所有监听器"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            listeners = self._listeners.get(task_id, [])
            for callback in listeners:
                try:
                    callback(progress_data)
                except Exception as e:
                    pass


def get_progress_registry() -> GlobalProgressRegistry:
    """获取进度注册表实例"""
    return GlobalProgressRegistry()


def generate_task_id(prefix: str = 'task') -> str:
    """生成唯一任务ID"""
    return f"{prefix}_{int(time.time() * 1000)}_{threading.current_thread().ident}"


class TaskProgressManager:
    """任务进度管理器"""
    
    def __init__(self, task_id: str, stages: List[Dict[str, str]]):
        self.task_id = task_id
        self.registry = get_progress_registry()
        
        # 将阶段字典转换为StageInfo对象
        stage_info_list = [
            StageInfo(
                stage=stage['stage'],
                title=stage.get('title', stage['stage']),
                description=stage.get('description', ''),
                status=StageStatus.PENDING
            )
            for stage in stages
        ]
        
        self.registry.register_task(task_id, stage_info_list)
    
    def start_stage(self, stage_name: str, details: str = None) -> None:
        """开始阶段"""
        self.registry.update_stage(self.task_id, stage_name, StageStatus.RUNNING, details)
        self.registry.set_status(self.task_id, TaskStatus.RUNNING)
        self.registry.add_log(self.task_id, 'info', f"开始阶段: {stage_name}")
    
    def complete_stage(self, stage_name: str, details: str = None) -> None:
        """完成阶段"""
        self.registry.update_stage(self.task_id, stage_name, StageStatus.COMPLETED, details)
        self.registry.add_log(self.task_id, 'info', f"完成阶段: {stage_name}")
    
    def error_stage(self, stage_name: str, error_message: str) -> None:
        """阶段出错"""
        self.registry.update_stage(self.task_id, stage_name, StageStatus.ERROR, error_message)
        self.registry.set_status(self.task_id, TaskStatus.ERROR, error_message)
        self.registry.add_log(self.task_id, 'error', f"阶段错误 [{stage_name}]: {error_message}")
    
    def update_progress(self, stage_name: str, progress: int) -> None:
        """更新阶段进度"""
        self.registry.update_stage_progress(self.task_id, stage_name, progress)
    
    def add_log(self, level: str, message: str) -> None:
        """添加日志"""
        self.registry.add_log(self.task_id, level, message)
    
    def set_completed(self, result: Dict = None, message: str = None) -> None:
        """设置任务完成"""
        self.registry.set_status(self.task_id, TaskStatus.COMPLETED, message, result)
        self.registry.add_log(self.task_id, 'info', message or '任务完成')
    
    def set_error(self, message: str, result: Dict = None) -> None:
        """设置任务错误"""
        self.registry.set_status(self.task_id, TaskStatus.ERROR, message, result)
        self.registry.add_log(self.task_id, 'error', message)
    
    def set_cancelled(self) -> None:
        """设置任务取消"""
        self.registry.set_status(self.task_id, TaskStatus.CANCELLED, '任务已取消')
        self.registry.add_log(self.task_id, 'info', '任务已取消')
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度数据（字典形式）"""
        progress_data = self.registry.get_progress(self.task_id)
        if not progress_data:
            return {}
        
        return {
            'task_id': progress_data.task_id,
            'status': progress_data.status.value,
            'overall_progress': progress_data.overall_progress,
            'current_stage': {
                'stage': progress_data.current_stage.stage,
                'title': progress_data.current_stage.title,
                'description': progress_data.current_stage.description
            } if progress_data.current_stage else None,
            'stages': [{
                'stage': s.stage,
                'title': s.title,
                'description': s.description,
                'status': s.status.value,
                'details': s.details,
                'progress': s.progress
            } for s in progress_data.stages],
            'logs': [{
                'timestamp': l.timestamp,
                'level': l.level,
                'message': l.message
            } for l in progress_data.logs],
            'result': progress_data.result,
            'message': progress_data.message,
            'estimated_time_remaining': progress_data.estimated_time_remaining
        }
    
    def cleanup(self) -> None:
        """清理任务"""
        self.registry.remove_task(self.task_id)


def create_progress_manager(task_id: str, stages: List[Dict[str, str]]) -> TaskProgressManager:
    """创建进度管理器"""
    return TaskProgressManager(task_id, stages)


def get_progress_manager(task_id: str) -> Optional[TaskProgressManager]:
    """获取进度管理器"""
    registry = get_progress_registry()
    progress_data = registry.get_progress(task_id)
    if not progress_data:
        return None
    
    # 重构阶段信息列表
    stages = [{
        'stage': s.stage,
        'title': s.title,
        'description': s.description
    } for s in progress_data.stages]
    
    manager = TaskProgressManager(task_id, stages)
    return manager


def remove_progress_manager(task_id: str) -> None:
    """移除进度管理器"""
    registry = get_progress_registry()
    registry.remove_task(task_id)


@csrf_exempt
@require_http_methods(["GET"])
def sse_progress_stream(request, task_id: str):
    """
    SSE端点：实时推送任务进度
    """
    def event_stream():
        registry = get_progress_registry()
        last_progress = None
        
        while True:
            progress_data = registry.get_progress(task_id)
            
            if not progress_data:
                yield f"data: {json.dumps({'status': 'not_found', 'message': '任务不存在'})}\n\n"
                break
            
            # 转换为可序列化的字典
            progress_dict = {
                'task_id': progress_data.task_id,
                'status': progress_data.status.value,
                'overall_progress': progress_data.overall_progress,
                'current_stage': {
                    'stage': progress_data.current_stage.stage,
                    'title': progress_data.current_stage.title,
                    'description': progress_data.current_stage.description
                } if progress_data.current_stage else None,
                'stages': [{
                    'stage': s.stage,
                    'title': s.title,
                    'description': s.description,
                    'status': s.status.value,
                    'details': s.details,
                    'progress': s.progress
                } for s in progress_data.stages],
                'logs': [{
                    'timestamp': l.timestamp,
                    'level': l.level,
                    'message': l.message
                } for l in progress_data.logs],
                'result': progress_data.result,
                'message': progress_data.message
            }
            
            # 只在进度变化时发送
            if progress_dict != last_progress:
                yield f"data: {json.dumps(progress_dict, ensure_ascii=False)}\n\n"
                last_progress = progress_dict
            
            # 任务完成或出错时结束
            if progress_data.status in [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.CANCELLED]:
                # 延迟清理任务数据
                def cleanup():
                    time.sleep(30)
                    remove_progress_manager(task_id)
                threading.Thread(target=cleanup, daemon=True).start()
                break
            
            time.sleep(0.5)
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@require_http_methods(["GET"])
def get_progress_api(request):
    """
    获取任务进度API
    """
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'success': False, 'message': '缺少task_id'})
    
    registry = get_progress_registry()
    progress_data = registry.get_progress(task_id)
    
    if not progress_data:
        return JsonResponse({'success': False, 'message': '任务不存在'})
    
    progress_dict = {
        'task_id': progress_data.task_id,
        'status': progress_data.status.value,
        'overall_progress': progress_data.overall_progress,
        'current_stage': {
            'stage': progress_data.current_stage.stage,
            'title': progress_data.current_stage.title,
            'description': progress_data.current_stage.description
        } if progress_data.current_stage else None,
        'stages': [{
            'stage': s.stage,
            'title': s.title,
            'description': s.description,
            'status': s.status.value,
            'details': s.details,
            'progress': s.progress
        } for s in progress_data.stages],
        'logs': [{
            'timestamp': l.timestamp,
            'level': l.level,
            'message': l.message
        } for l in progress_data.logs],
        'result': progress_data.result,
        'message': progress_data.message
    }
    
    return JsonResponse({'success': True, 'progress': progress_dict})


@csrf_exempt
@require_http_methods(["POST"])
def cancel_task_api(request):
    """
    取消任务API
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '无效的JSON数据'})
    
    if not task_id:
        return JsonResponse({'success': False, 'message': '缺少task_id'})
    
    manager = get_progress_manager(task_id)
    if not manager:
        return JsonResponse({'success': False, 'message': '任务不存在'})
    
    manager.set_cancelled()
    return JsonResponse({'success': True, 'message': '任务已取消'})


# 为了兼容旧代码，保留原有的导入接口
__all__ = [
    'TaskStatus',
    'StageStatus',
    'StageInfo',
    'ProgressData',
    'GlobalProgressRegistry',
    'TaskProgressManager',
    'get_progress_registry',
    'generate_task_id',
    'create_progress_manager',
    'get_progress_manager',
    'remove_progress_manager',
    'sse_progress_stream',
    'get_progress_api',
    'cancel_task_api'
]