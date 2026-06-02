"""
API Key 认证装饰器

用于 JSON API 端点的外部调用认证。
客户端需要在请求头中携带 X-API-Key 字段。

兼容性：
- 如果用户已通过 Django session 登录（浏览器前端调用），直接放行
- 否则检查 X-API-Key 请求头
"""
from functools import wraps
from django.http import JsonResponse
from django.conf import settings


def api_key_required(view_func):
    """要求请求携带有效的 API Key（通过 X-API-Key 头），或用户已登录"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 如果用户已登录（浏览器 session），直接放行
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        # 检查 API Key
        api_key = request.headers.get("X-API-Key", "")
        expected_key = getattr(settings, "API_KEY", "")
        if expected_key and api_key and api_key == expected_key:
            return view_func(request, *args, **kwargs)
        return JsonResponse(
            {"success": False, "message": "未授权访问，请提供有效的 API Key 或登录后操作"},
            status=401,
        )
    return _wrapped_view


def api_key_or_csrf_exempt(view_func):
    """
    组合装饰器：CSRF 豁免 + API Key 认证。
    适用于外部工具调用的 JSON API 端点。
    """
    from django.views.decorators.csrf import csrf_exempt
    return csrf_exempt(api_key_required(view_func))
