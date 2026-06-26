"""
API Key 认证装饰器

用于 JSON API 端点的外部调用认证。
客户端需要在请求头中携带 X-API-Key 字段。

兼容性：
- 如果用户已通过 Django session 登录（浏览器前端调用），通过 CSRF 保护
- 否则检查 X-API-Key 请求头，通过 API Key 认证后跳过 CSRF

认证策略（session_or_apikey_auth）：
1. 先检查用户是否已通过 Django session 登录 → 正常 CSRF 保护
2. 否则检查 X-API-Key 请求头 → 通过后跳过 CSRF
3. 都不通过 → 返回 401
"""
import asyncio
import inspect
from functools import wraps
from django.http import JsonResponse
from django.conf import settings


def _is_api_key_valid(request) -> bool:
    """检查请求是否携带有效的 API Key"""
    api_key = request.headers.get("X-API-Key", "")
    expected_key = getattr(settings, "API_KEY", "")
    return bool(expected_key and api_key and api_key == expected_key)


from asgiref.sync import sync_to_async


def _call_csrf_middleware(request):
    """同步调用 CSRF 中间件校验 (封装为单独函数供 sync_to_async 使用)"""
    from django.middleware.csrf import CsrfViewMiddleware
    return CsrfViewMiddleware(lambda r: None).process_view(request, None, (), {})


def _sync_or_async_wrap(view_func, handler):
    """
    根据 view_func 是同步还是异步，正确调度 handler，确保协程正确 await。

    handler 签名: handler(request, *args, **kwargs) -> HttpResponse
    如果是异步视图，返回包装后的 async 函数（自动 await handler 结果中的协程）；
    否则返回同步函数。
    """
    if inspect.iscoroutinefunction(view_func):
        @wraps(view_func)
        async def _async_wrapped(request, *args, **kwargs):
            # 对于 session 用户，在 async 上下文中需要用 sync_to_async 调用 CSRF 校验
            if request.user.is_authenticated:
                csrf_error = await sync_to_async(_call_csrf_middleware)(request)
                if csrf_error:
                    return csrf_error
                result = view_func(request, *args, **kwargs)
                if inspect.iscoroutine(result):
                    return await result
                return result
            # 非 session 用户：走 handler (API Key 校验)
            result = handler(request, *args, **kwargs)
            if inspect.iscoroutine(result):
                return await result
            return result
        return _async_wrapped
    else:
        @wraps(view_func)
        def _sync_wrapped(request, *args, **kwargs):
            return handler(request, *args, **kwargs)
        return _sync_wrapped


def api_key_required(view_func):
    """要求请求携带有效的 API Key（通过 X-API-Key 头），或用户已登录
    外层标记 csrf_exempt，session 用户由 handler 手动验证 CSRF。"""
    from django.middleware.csrf import CsrfViewMiddleware

    def _handler(request, *args, **kwargs):
        if request.user.is_authenticated:
            # session 已登录 → 手动验证 CSRF
            reason = CsrfViewMiddleware(lambda r: None).process_view(request, None, (), {})
            if reason:
                return JsonResponse(
                    {"success": False, "message": f"CSRF 验证失败: {reason}"},
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        if _is_api_key_valid(request):
            return view_func(request, *args, **kwargs)
        return JsonResponse(
            {"success": False, "message": "未授权访问，请提供有效的 API Key 或登录后操作"},
            status=401,
        )

    wrapped = _sync_or_async_wrap(view_func, _handler)
    wrapped.csrf_exempt = True
    return wrapped


def api_key_or_csrf_exempt(view_func):
    """
    已废弃：请使用 session_or_apikey_auth 代替。
    保留此函数仅用于向后兼容，将在后续版本移除。
    """
    from django.views.decorators.csrf import csrf_exempt
    return csrf_exempt(api_key_required(view_func))


def session_or_apikey_auth(view_func):
    """
    统一认证装饰器：session 登录用户走 CSRF 保护，API Key 用户跳过 CSRF。
    支持同步和异步视图函数。

    工作原理：
    - 外层包装始终标记 csrf_exempt = True（避免 CSRF 中间件拦截）
    - API Key 请求：通过认证后直接放行
    - Session 请求：通过认证后手动验证 CSRF Token

    适用于 JSON API 端点，兼顾浏览器前端和外部工具调用。
    """
    import logging
    from django.middleware.csrf import CsrfViewMiddleware, get_token

    def _check_csrf(request):
        """手动验证 CSRF Token，仅对 session 用户生效"""
        reason = CsrfViewMiddleware(lambda r: None).process_view(request, None, (), {})
        if reason:
            return JsonResponse(
                {"success": False, "message": f"CSRF 验证失败: {reason}"},
                status=403,
            )
        return None

    def _handler(request, *args, **kwargs):
        if request.user.is_authenticated:
            # session 已登录 → 手动验证 CSRF
            csrf_error = _check_csrf(request)
            if csrf_error:
                return csrf_error
            return view_func(request, *args, **kwargs)
        if _is_api_key_valid(request):
            # API Key 认证通过 → 跳过 CSRF
            return view_func(request, *args, **kwargs)
        return JsonResponse(
            {"success": False, "message": "未授权访问，请提供有效的 API Key 或登录后操作"},
            status=401,
        )

    wrapped = _sync_or_async_wrap(view_func, _handler)
    # 外层标记 csrf_exempt，由 handler 内部手动控制 CSRF
    wrapped.csrf_exempt = True
    return wrapped
