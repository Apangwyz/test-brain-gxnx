
"""
测试报告 API 视图
"""
import json
import os
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings

from ..core.models import TestReport, TestExecutionBatch
from .report_generator import TestReportGenerator


@login_required
def report_list_api(request):
    """报告列表"""
    reports = TestReport.objects.all().select_related('system', 'batch')
    system_id = request.GET.get('system_id')
    if system_id:
        reports = reports.filter(system_id=system_id)

    data = [{
        'id': r.id,
        'title': r.title,
        'summary': r.summary,
        'system_name': r.system.name if r.system else '',
        'batch_name': r.batch.name if r.batch else '',
        'pass_rate': r.report_data.get('execution_summary', {}).get('pass_rate', 0) if r.report_data else 0,
        'created_at': r.created_at.isoformat(),
    } for r in reports.order_by('-created_at')[:50]]

    return JsonResponse({'reports': data})


@login_required
def report_detail_api(request, report_id):
    """报告详情"""
    report = get_object_or_404(TestReport, id=report_id)
    return JsonResponse({
        'id': report.id,
        'title': report.title,
        'summary': report.summary,
        'report_data': report.report_data,
        'system_name': report.system.name if report.system else '',
        'batch_name': report.batch.name if report.batch else '',
        'pdf_url': report.pdf_file.url if report.pdf_file else '',
        'created_at': report.created_at.isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_report_api(request):
    """生成报告"""
    data = json.loads(request.body)
    batch_id = data.get('batch_id')
    batch = get_object_or_404(TestExecutionBatch, id=batch_id)

    generator = TestReportGenerator()
    report = generator.generate(batch, user=request.user)

    return JsonResponse({
        'id': report.id,
        'title': report.title,
        'message': '报告生成成功',
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def export_report_pdf(request, report_id):
    """导出 PDF"""
    report = get_object_or_404(TestReport, id=report_id)

    from django.template.loader import render_to_string
    import weasyprint

    html_str = render_to_string('report_pdf.html', {
        'report': report,
        'report_data': report.report_data or {},
    })

    filename = f"report_{report.id}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, 'reports', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    weasyprint.HTML(string=html_str).write_pdf(filepath)

    report.pdf_file.name = f"reports/{filename}"
    report.save(update_fields=['pdf_file'])

    return JsonResponse({
        'pdf_url': report.pdf_file.url,
        'message': 'PDF 导出成功',
    })


@login_required
@require_http_methods(["DELETE"])
@csrf_exempt
def delete_report_api(request, report_id):
    """删除报告"""
    report = get_object_or_404(TestReport, id=report_id)
    report.delete()
    return JsonResponse({'status': 'ok'})


# --- 页面视图 ---

@login_required
def report_list_view(request):
    """报告列表页面"""
    return render(request, 'report_list.html')


@login_required
def report_detail_view(request, report_id):
    """报告详情页面"""
    report = get_object_or_404(TestReport, id=report_id)
    return render(request, 'report_detail.html', {
        'report': report,
        'report_data': report.report_data or {},
    })
