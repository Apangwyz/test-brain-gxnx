"""
测试报告导入视图
"""
import os
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .report_importer import ReportImporter
from apps.utils.logger_manager import get_logger

logger = get_logger("report_import_views")

SUPPORTED_EXTENSIONS = {".xml", ".json"}


@login_required
def import_report_page(request):
    """报告导入页面"""
    return render(request, "report_import.html")


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def import_report_api(request):
    """导入报告 API"""
    # 校验文件
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "请上传文件"}, status=400)

    uploaded = request.FILES["file"]
    ext = os.path.splitext(uploaded.name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return JsonResponse({
            "success": False,
            "message": f"不支持的文件类型 '{ext}'，支持: {', '.join(SUPPORTED_EXTENSIONS)}",
        }, status=400)

    if uploaded.size == 0:
        return JsonResponse({
            "success": False, "message": "文件内容为空",
        }, status=400)

    # 限制文件大小（10MB）
    if uploaded.size > 10 * 1024 * 1024:
        return JsonResponse({
            "success": False, "message": "文件大小超过 10MB 限制",
        }, status=400)

    try:
        importer = ReportImporter()
        report = importer.import_report(uploaded, user=request.user)

        return JsonResponse({
            "success": True,
            "id": report.id,
            "title": report.title,
            "summary": report.summary,
            "message": "报告导入成功",
        })
    except ValueError as e:
        logger.warning(f"导入解析失败: {e}")
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception as e:
        logger.error(f"导入异常: {e}", exc_info=True)
        return JsonResponse({
            "success": False,
            "message": f"导入失败: {str(e)}",
        }, status=500)
