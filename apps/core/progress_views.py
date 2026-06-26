"""
通用进度管理视图 — 供 common_progress.js 调用

提供三个端点：
  GET  /api/progress/<str:task_id>/  → SSE 流式进度推送
  GET  /api/progress/                → JSON 进度查询（?task_id=xxx）
  POST /api/cancel/<str:task_id>/    → 取消任务

同时检查 apps.utils.progress_registry（新系统）和
apps.utils.progress_manager（旧系统 GlobalProgressRegistry），确保兼容。
"""
import json
import time
import threading
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.utils.auth_decorators import session_or_apikey_auth, api_key_required
from apps.utils.progress_registry import get_progress as get_registry_progress
from apps.utils.progress_manager import (
    get_progress_registry,
    get_progress_manager,
    remove_progress_manager,
)


def _fetch_progress_data(task_id: str) -> dict:
    """
    从新旧两个系统中查找进度数据，统一输出格式。
    返回 None 表示任务不存在。
    """
    # 1) 先查旧系统 GlobalProgressRegistry（完整 stages 数据）
    registry = get_progress_registry()
    old_pd = registry.get_progress(task_id)
    if old_pd is not None:
        status_val = old_pd.status
        if hasattr(status_val, "value"):
            status_val = status_val.value
        return {
            "task_id": old_pd.task_id,
            "status": status_val,
            "overall_progress": old_pd.overall_progress,
            "current_stage": {
                "stage": old_pd.current_stage.stage,
                "title": old_pd.current_stage.title,
                "description": old_pd.current_stage.description,
            } if old_pd.current_stage else None,
            "stages": [
                {
                    "stage": s.stage, "title": s.title,
                    "description": s.description,
                    "status": s.status.value if hasattr(s.status, "value") else s.status,
                    "details": s.details, "progress": s.progress,
                }
                for s in (old_pd.stages or [])
            ],
            "logs": [
                {"timestamp": l.timestamp, "level": l.level, "message": l.message}
                for l in (old_pd.logs or [])
            ],
            "result": old_pd.result,
            "message": old_pd.message,
        }

    # 2) 新系统 progress_registry 作为后备（无 stage 明细）
    pd = get_registry_progress(task_id)
    if pd is not None:
        return {
            "task_id": task_id,
            "status": getattr(pd, "status", "unknown"),
            "overall_progress": getattr(pd, "percentage", 0),
            "current_stage": None,
            "stages": [],
            "logs": getattr(pd, "logs", []),
            "result": getattr(pd, "result", None),
            "message": getattr(pd, "message", ""),
        }

    return None

def sse_progress_stream(request, task_id):
    def event_stream():
        last = None
        while True:
            data = _fetch_progress_data(task_id)
            if data is None:
                yield f"data: {json.dumps({'status': 'not_found', 'message': '任务不存在'}, ensure_ascii=False)}\n\n"
                break
            if data != last:
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                last = data
            if data["status"] in ("completed", "error", "cancelled"):
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
    data = _fetch_progress_data(task_id)
    if data is None:
        return JsonResponse({"success": False, "message": "任务不存在"})
    return JsonResponse({"success": True, "progress": data})


@session_or_apikey_auth
@require_http_methods(["POST"])
def cancel_task_api(request, task_id=None):
    # 优先使用 URL 参数，兼容 POST body
    if not task_id:
        try:
            body = json.loads(request.body)
            task_id = body.get("task_id")
        except (json.JSONDecodeError, Exception):
            pass
    if not task_id:
        return JsonResponse({"success": False, "message": "缺少task_id"})
    manager = get_progress_manager(task_id)
    if not manager:
        # 尝试用 registry 直接标记
        from apps.utils.progress_registry import set_progress
        set_progress(task_id, {"status": "cancelled", "message": "任务已取消"})
        return JsonResponse({"success": True, "message": "任务已取消"})
    manager.set_cancelled()
    return JsonResponse({"success": True, "message": "任务已取消"})
