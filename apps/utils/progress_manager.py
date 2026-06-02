"""
统一进度管理模块 - 兼容层
提供文件上传和内容生成的进度管理功能，支持SSE实时进度推送。

本模块是 apps/utils/progress_schema.py 和 apps/utils/progress_registry.py 的兼容封装层。
所有新代码应直接使用 progress_schema / progress_registry 中的数据模型和存储 API。

**已重构：** GlobalProgressRegistry 内部存储委托给 progress_registry 中心注册表，
TaskProgressManager 同步进度到中心注册表，确保所有进度数据统一管理。
"""

import json
import time
import threading
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from apps.utils.auth_decorators import api_key_or_csrf_exempt, api_key_required

from .progress_schema import (
    TaskStatus as SchemaTaskStatus,
    ProgressData as SchemaProgressData,
    ProgressUpdate,
)
from .progress_registry import set_progress, get_progress, clear_progress, cleanup_expired


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class StageInfo:
    def __init__(self, stage, title, description, status=StageStatus.PENDING, details=None, progress=0):
        self.stage = stage
        self.title = title
        self.description = description
        self.status = status
        self.details = details
        self.progress = progress


class LogEntry:
    def __init__(self, timestamp, level, message):
        self.timestamp = timestamp
        self.level = level
        self.message = message


class ProgressData:
    def __init__(self, task_id, status=TaskStatus.PENDING, overall_progress=0,
                 current_stage=None, stages=None, logs=None, result=None,
                 message=None, estimated_time_remaining=None):
        self.task_id = task_id
        self.status = status
        self.overall_progress = overall_progress
        self.current_stage = current_stage
        self.stages = stages or []
        self.logs = logs or []
        self.result = result
        self.message = message
        self.estimated_time_remaining = estimated_time_remaining


class GlobalProgressRegistry:
    """
    全局进度注册表 - 兼容包装

    **注意：** 该类的内部存储已委托给 apps.utils.progress_registry 中的中心注册表，
    以避免数据分散在多处。新代码应直接使用 progress_registry.set_progress / get_progress。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._progress_map = {}
                    cls._instance._listeners = {}
                    cls._instance._local_lock = threading.Lock()
        return cls._instance

    def register_task(self, task_id, stages):
        with self._local_lock:
            self._progress_map[task_id] = ProgressData(task_id=task_id, status=TaskStatus.PENDING, stages=stages)
            self._listeners[task_id] = []
            # 同步到中心注册表
            set_progress(task_id, {"step": 0, "message": "任务已创建", "percentage": 0, "status": "pending"})

    def _sync(self, task_id):
        """将当前状态同步到中心注册表"""
        pd = self._progress_map.get(task_id)
        if not pd:
            return
        current_stage_name = pd.current_stage.stage if pd.current_stage else None
        set_progress(task_id, {
            "step": sum(1 for s in pd.stages if s.status == StageStatus.COMPLETED),
            "message": current_stage_name or pd.message or "",
            "percentage": pd.overall_progress,
            "status": pd.status.value,
        })

    def update_stage(self, task_id, stage_name, status, details=None):
        with self._local_lock:
            pd = self._progress_map.get(task_id)
            if not pd:
                return
            for stage in pd.stages:
                if stage.stage == stage_name:
                    stage.status = status
                    if details:
                        stage.details = details
                    if status == StageStatus.RUNNING:
                        pd.current_stage = stage
            self._update_overall_progress(task_id)
        self._sync(task_id)

    def update_stage_progress(self, task_id, stage_name, progress):
        with self._local_lock:
            pd = self._progress_map.get(task_id)
            if not pd:
                return
            for stage in pd.stages:
                if stage.stage == stage_name:
                    stage.progress = progress
            self._update_overall_progress(task_id)
        self._sync(task_id)

    def _update_overall_progress(self, task_id):
        pd = self._progress_map.get(task_id)
        if not pd or not pd.stages:
            return
        total = len(pd.stages)
        completed = sum(1 for s in pd.stages if s.status == StageStatus.COMPLETED)
        running = next((s for s in pd.stages if s.status == StageStatus.RUNNING), None)
        base = (completed / total) * 100 if total > 0 else 0
        if running:
            stage_contrib = (running.progress / 100) * (100 / total) if total > 0 else 0
            pd.overall_progress = min(99, int(base + stage_contrib))
        else:
            pd.overall_progress = int(base)

    def add_log(self, task_id, level, message):
        with self._local_lock:
            pd = self._progress_map.get(task_id)
            if not pd:
                return
            pd.logs.append(LogEntry(timestamp=datetime.now().strftime("%H:%M:%S"), level=level, message=message))
            if len(pd.logs) > 1000:
                pd.logs = pd.logs[-500:]

    def set_status(self, task_id, status, message=None, result=None):
        with self._local_lock:
            pd = self._progress_map.get(task_id)
            if not pd:
                return
            pd.status = status
            pd.message = message
            if status == TaskStatus.COMPLETED:
                pd.overall_progress = 100
                pd.result = result
            elif status == TaskStatus.ERROR:
                pd.result = result
        self._sync(task_id)

    def get_progress(self, task_id):
        with self._local_lock:
            return self._progress_map.get(task_id)

    def remove_task(self, task_id):
        with self._local_lock:
            self._progress_map.pop(task_id, None)
            self._listeners.pop(task_id, None)
        clear_progress(task_id)

    def add_listener(self, task_id, callback):
        with self._local_lock:
            if task_id not in self._listeners:
                self._listeners[task_id] = []
            self._listeners[task_id].append(callback)

    def remove_listener(self, task_id, callback):
        with self._local_lock:
            if task_id in self._listeners:
                self._listeners[task_id].remove(callback)

    def notify_listeners(self, task_id):
        with self._local_lock:
            pd = self._progress_map.get(task_id)
            if not pd:
                return
            for cb in self._listeners.get(task_id, []):
                try:
                    cb(pd)
                except Exception:
                    pass


def get_progress_registry():
    return GlobalProgressRegistry()


def generate_task_id(prefix="task"):
    return f"{prefix}_{int(time.time() * 1000)}_{threading.current_thread().ident}"


class TaskProgressManager:
    def __init__(self, task_id, stages):
        self.task_id = task_id
        self.registry = get_progress_registry()
        stage_info_list = [
            StageInfo(stage=s["stage"], title=s.get("title", s["stage"]),
                      description=s.get("description", ""), status=StageStatus.PENDING)
            for s in stages
        ]
        self.registry.register_task(task_id, stage_info_list)

    def start_stage(self, stage_name, details=None):
        self.registry.update_stage(self.task_id, stage_name, StageStatus.RUNNING, details)
        self.registry.set_status(self.task_id, TaskStatus.RUNNING)
        self.registry.add_log(self.task_id, "info", f"开始阶段: {stage_name}")

    def complete_stage(self, stage_name, details=None):
        self.registry.update_stage(self.task_id, stage_name, StageStatus.COMPLETED, details)
        self.registry.add_log(self.task_id, "info", f"完成阶段: {stage_name}")

    def error_stage(self, stage_name, error_message):
        self.registry.update_stage(self.task_id, stage_name, StageStatus.ERROR, error_message)
        self.registry.set_status(self.task_id, TaskStatus.ERROR, error_message)
        self.registry.add_log(self.task_id, "error", f"阶段错误 [{stage_name}]: {error_message}")

    def update_progress(self, stage_name, progress):
        self.registry.update_stage_progress(self.task_id, stage_name, progress)

    def add_log(self, level, message):
        self.registry.add_log(self.task_id, level, message)

    def set_completed(self, result=None, message=None):
        self.registry.set_status(self.task_id, TaskStatus.COMPLETED, message, result)
        self.registry.add_log(self.task_id, "info", message or "任务完成")

    def set_error(self, message, result=None):
        self.registry.set_status(self.task_id, TaskStatus.ERROR, message, result)
        self.registry.add_log(self.task_id, "error", message)

    def set_cancelled(self):
        self.registry.set_status(self.task_id, TaskStatus.CANCELLED, "任务已取消")
        self.registry.add_log(self.task_id, "info", "任务已取消")

    def get_progress(self):
        pd = self.registry.get_progress(self.task_id)
        if not pd:
            return {}
        return {
            "task_id": pd.task_id,
            "status": pd.status.value,
            "overall_progress": pd.overall_progress,
            "current_stage": {"stage": pd.current_stage.stage, "title": pd.current_stage.title,
                              "description": pd.current_stage.description} if pd.current_stage else None,
            "stages": [{"stage": s.stage, "title": s.title, "description": s.description,
                        "status": s.status.value, "details": s.details, "progress": s.progress}
                       for s in pd.stages],
            "logs": [{"timestamp": l.timestamp, "level": l.level, "message": l.message}
                     for l in pd.logs],
            "result": pd.result,
            "message": pd.message,
            "estimated_time_remaining": pd.estimated_time_remaining,
        }

    def cleanup(self):
        self.registry.remove_task(self.task_id)


def create_progress_manager(task_id, stages):
    return TaskProgressManager(task_id, stages)


def get_progress_manager(task_id):
    registry = get_progress_registry()
    pd = registry.get_progress(task_id)
    if not pd:
        return None
    stages = [{"stage": s.stage, "title": s.title, "description": s.description} for s in pd.stages]
    return TaskProgressManager(task_id, stages)


def remove_progress_manager(task_id):
    registry = get_progress_registry()
    registry.remove_task(task_id)


@api_key_required
@require_http_methods(["GET"])
def sse_progress_stream(request, task_id):
    def event_stream():
        registry = get_progress_registry()
        last = None
        while True:
            pd = registry.get_progress(task_id)
            if not pd:
                data = json.dumps({"status": "not_found", "message": "任务不存在"}, ensure_ascii=False)
                yield f"data: {data}\n\n"
                break
            d = {
                "task_id": pd.task_id,
                "status": pd.status.value,
                "overall_progress": pd.overall_progress,
                "current_stage": {"stage": pd.current_stage.stage, "title": pd.current_stage.title,
                                  "description": pd.current_stage.description} if pd.current_stage else None,
                "stages": [{"stage": s.stage, "title": s.title, "description": s.description,
                            "status": s.status.value, "details": s.details, "progress": s.progress}
                           for s in pd.stages],
                "logs": [{"timestamp": l.timestamp, "level": l.level, "message": l.message}
                         for l in pd.logs],
                "result": pd.result,
                "message": pd.message,
            }
            if d != last:
                yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
                last = d
            if pd.status in [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.CANCELLED]:
                def cleanup():
                    time.sleep(30)
                    remove_progress_manager(task_id)
                threading.Thread(target=cleanup, daemon=True).start()
                break
            time.sleep(0.5)
    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_key_required
@require_http_methods(["GET"])
def get_progress_api(request):
    task_id = request.GET.get("task_id")
    if not task_id:
        return JsonResponse({"success": False, "message": "缺少task_id"})
    registry = get_progress_registry()
    pd = registry.get_progress(task_id)
    if not pd:
        return JsonResponse({"success": False, "message": "任务不存在"})
    return JsonResponse({
        "success": True,
        "progress": {
            "task_id": pd.task_id,
            "status": pd.status.value,
            "overall_progress": pd.overall_progress,
            "current_stage": {"stage": pd.current_stage.stage, "title": pd.current_stage.title,
                              "description": pd.current_stage.description} if pd.current_stage else None,
            "stages": [{"stage": s.stage, "title": s.title, "description": s.description,
                        "status": s.status.value, "details": s.details, "progress": s.progress}
                       for s in pd.stages],
            "logs": [{"timestamp": l.timestamp, "level": l.level, "message": l.message}
                     for l in pd.logs],
            "result": pd.result,
            "message": pd.message,
        },
    })


@api_key_or_csrf_exempt
@require_http_methods(["POST"])
def cancel_task_api(request):
    try:
        data = json.loads(request.body)
        task_id = data.get("task_id")
    except (json.JSONDecodeError, Exception):
        return JsonResponse({"success": False, "message": "无效的JSON数据"})
    if not task_id:
        return JsonResponse({"success": False, "message": "缺少task_id"})
    manager = get_progress_manager(task_id)
    if not manager:
        return JsonResponse({"success": False, "message": "任务不存在"})
    manager.set_cancelled()
    return JsonResponse({"success": True, "message": "任务已取消"})


__all__ = [
    "TaskStatus", "StageStatus", "StageInfo", "ProgressData",
    "GlobalProgressRegistry", "TaskProgressManager",
    "get_progress_registry", "generate_task_id",
    "create_progress_manager", "get_progress_manager", "remove_progress_manager",
    "sse_progress_stream", "get_progress_api", "cancel_task_api",
]
