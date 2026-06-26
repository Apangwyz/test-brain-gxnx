"""
测试用例版本管理视图
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from ..core.models import TestCase, TestCaseVersion


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def save_version(request, case_id):
    """保存当前用例为新版本"""
    test_case = get_object_or_404(TestCase, id=case_id)
    data = json.loads(request.body) if request.body else {}
    change_summary = data.get('change_summary', '')

    latest = test_case.versions.order_by('-version_number').first()
    new_ver = (latest.version_number + 1) if latest else 1

    snapshot = {
        'title': test_case.title,
        'description': test_case.description,
        'requirements': test_case.requirements,
        'test_steps': test_case.test_steps,
        'expected_results': test_case.expected_results,
        'bu': test_case.bu,
        'feature': test_case.feature,
        'priority': test_case.priority,
    }

    version = TestCaseVersion.objects.create(
        test_case=test_case,
        version_number=new_ver,
        snapshot=snapshot,
        change_summary=change_summary or f"版本 v{new_ver}",
        created_by=request.user if request.user.is_authenticated else None,
    )

    test_case.current_version = new_ver
    test_case.save(update_fields=['current_version'])

    return JsonResponse({
        'id': version.id,
        'version_number': version.version_number,
        'change_summary': version.change_summary,
        'created_at': version.created_at.isoformat(),
    })


@login_required
def list_versions(request, case_id):
    """获取用例版本列表"""
    test_case = get_object_or_404(TestCase, id=case_id)
    versions = test_case.versions.all().values(
        'id', 'version_number', 'change_summary', 'created_at'
    )
    return JsonResponse({'versions': list(versions)})


@login_required
def get_version_detail(request, case_id, version):
    """获取某个版本的快照内容"""
    test_case = get_object_or_404(TestCase, id=case_id)
    ver = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=version)
    return JsonResponse({
        'version_number': ver.version_number,
        'snapshot': ver.snapshot,
        'change_summary': ver.change_summary,
        'created_at': ver.created_at.isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def rollback_version(request, case_id, version):
    """回退到指定版本"""
    test_case = get_object_or_404(TestCase, id=case_id)
    ver = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=version)

    snap = ver.snapshot
    for field in ['title', 'description', 'requirements', 'test_steps',
                  'expected_results', 'bu', 'feature', 'priority']:
        if field in snap:
            setattr(test_case, field, snap[field])

    latest = test_case.versions.order_by('-version_number').first()
    new_ver = (latest.version_number + 1) if latest else 1
    test_case.current_version = new_ver
    test_case.save()

    TestCaseVersion.objects.create(
        test_case=test_case,
        version_number=new_ver,
        snapshot=snap,
        change_summary=f"回退到 v{version}",
        created_by=request.user if request.user.is_authenticated else None,
    )

    return JsonResponse({'status': 'ok', 'current_version': new_ver})


@login_required
def diff_versions(request, case_id):
    """对比两个版本"""
    v1 = int(request.GET.get('v1', 0))
    v2 = int(request.GET.get('v2', 0))
    test_case = get_object_or_404(TestCase, id=case_id)

    ver1 = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=v1)
    ver2 = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=v2)

    FIELD_LABELS = {
        'title': '用例标题', 'description': '用例描述',
        'test_steps': '测试步骤', 'expected_results': '预期结果',
        'bu': 'BU', 'feature': 'Feature', 'priority': '优先级',
    }

    diffs = []
    all_fields = set(list(ver1.snapshot.keys()) + list(ver2.snapshot.keys()))
    for field in sorted(all_fields):
        old_val = ver1.snapshot.get(field, '')
        new_val = ver2.snapshot.get(field, '')
        old_str = str(old_val) if old_val else ''
        new_str = str(new_val) if new_val else ''

        if old_str == new_str:
            continue

        if old_val is None or old_str == '':
            dtype = 'added'
        elif new_val is None or new_str == '':
            dtype = 'removed'
        else:
            dtype = 'modified'

        diffs.append({
            'field': field,
            'label': FIELD_LABELS.get(field, field),
            'old': old_str,
            'new': new_str,
            'type': dtype,
        })

    return JsonResponse({
        'v1': v1, 'v2': v2,
        'diffs': diffs,
    })
