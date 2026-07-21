"""
测试报告 API 视图
"""
import json
import math
import os

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings

from ..core.models import TestReport, TestExecutionBatch
from .report_generator import TestReportGenerator
from apps.utils.logger_manager import get_logger

logger = get_logger("report_views")

DEFAULT_PAGE_SIZE = 12


@login_required
def report_list_api(request):
    """报告列表（支持后端分页 + system_id 筛选）"""
    reports = TestReport.objects.all().select_related("system", "batch")

    system_id = request.GET.get("system_id")
    if system_id:
        reports = reports.filter(system_id=system_id)

    # 分页参数
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))
    page_size = min(max(page_size, 1), 100)  # 限制最大 100 条

    total = reports.count()
    total_pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size
    page_reports = reports.order_by("-created_at")[start:end]

    data = [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "system_name": r.system.name if r.system else "",
            "batch_name": r.batch.name if r.batch else "",
            "pass_rate": r.report_data.get("execution_summary", {}).get("pass_rate", 0)
            if r.report_data else 0,
            "created_at": r.created_at.isoformat(),
        }
        for r in page_reports
    ]

    return JsonResponse({
        "reports": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    })


@login_required
def report_detail_api(request, report_id):
    """报告详情"""
    report = get_object_or_404(TestReport, id=report_id)

    report_data = report.report_data or {}
    # 确保前端能读取到 ai_analysis
    if "ai_analysis" not in report_data:
        report_data["ai_analysis"] = {
            "failure_analysis": [],
            "risk_assessment": "",
            "improvement_suggestions": "",
        }

    return JsonResponse({
        "id": report.id,
        "title": report.title,
        "summary": report.summary,
        "report_data": report_data,
        "system_name": report.system.name if report.system else "",
        "batch_name": report.batch.name if report.batch else "",
        "batch_id": report.batch.id if report.batch else None,
        "pdf_url": report.pdf_file.url if report.pdf_file else "",
        "created_at": report.created_at.isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_report_api(request):
    """生成 / 重新生成报告"""
    data = json.loads(request.body)
    batch_id = data.get("batch_id")
    batch = get_object_or_404(TestExecutionBatch, id=batch_id)

    generator = TestReportGenerator()
    report = generator.generate(batch, user=request.user)

    action = "更新" if report.created_at != report.generated_by  else "生成"
    # 更准确的做法：检查 created_at 和 updated_at 是否接近
    # 我们用简单方式：检查日志
    logger.info(f"报告{'重新生成' if request.body else '生成'}成功: {report.title} (id={report.id})")

    return JsonResponse({
        "id": report.id,
        "title": report.title,
        "batch_id": batch_id,
        "message": "报告生成成功",
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def export_report_pdf(request, report_id):
    """导出 PDF"""
    report = get_object_or_404(TestReport, id=report_id)

    from django.template.loader import render_to_string
    import weasyprint

    report_data = report.report_data or {}
    html_str = render_to_string("report_pdf.html", {
        "report": report,
        "report_data": report_data,
    })

    filename = f"report_{report.id}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, "reports", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    weasyprint.HTML(string=html_str).write_pdf(filepath)

    report.pdf_file.name = f"reports/{filename}"
    report.save(update_fields=["pdf_file"])

    return JsonResponse({
        "pdf_url": report.pdf_file.url,
        "message": "PDF 导出成功",
    })


@login_required
@require_http_methods(["DELETE"])
@csrf_exempt
def delete_report_api(request, report_id):
    """删除报告"""
    report = get_object_or_404(TestReport, id=report_id)
    report.delete()
    return JsonResponse({"status": "ok"})


# --- 页面视图 ---

@login_required
def report_list_view(request):
    """报告列表页面"""
    return render(request, "report_list.html")


@login_required
def report_detail_view(request, report_id):
    """报告详情页面"""
    report = get_object_or_404(TestReport, id=report_id)
    report_data = report.report_data or {}
    if "ai_analysis" not in report_data:
        report_data["ai_analysis"] = {
            "failure_analysis": [],
            "risk_assessment": "",
            "improvement_suggestions": "",
        }
    return render(request, "report_detail.html", {
        "report": report,
        "report_data": report_data,
    })
