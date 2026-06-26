"""
主页仪表盘视图（拆分后保留的核心视图）
"""
import json
import os

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from ..core.models import TestCase
from apps.llm import LLMServiceFactory
from apps.utils.logger_manager import get_logger


logger = get_logger(__name__)


# 获取LLM配置（通过中心化管理器）
from apps.llm.config_manager import get_llm_config, get_provider_config
DEFAULT_PROVIDER, PROVIDERS = get_llm_config()
DEFAULT_LLM_CONFIG = get_provider_config()


llm_service = None


def get_llm_service():
    global llm_service
    if llm_service is None:
        llm_service = LLMServiceFactory.create_with_fallback(agent_name="core")
    return llm_service


from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    """页面-首页视图"""
    # 获取测试用例统计数据
    total_test_cases = TestCase.objects.count()
    pending_count = TestCase.objects.filter(status='pending').count()
    approved_count = TestCase.objects.filter(status='approved').count()
    rejected_count = TestCase.objects.filter(status='rejected').count()
    
    # 获取最近的测试用例
    recent_test_cases = TestCase.objects.order_by('-created_at')[:10]
    
    context = {
        'total_test_cases': total_test_cases,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'recent_test_cases': recent_test_cases,
    }
    
    return render(request, 'index.html', context)
