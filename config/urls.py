"""
URL configuration for test_brain project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    # metersphere上接口测试用例生成路由
    path('iface_case_generator/', include('apps.ai_agents.iface_case_generator.urls')),
    path('java_code_analyzer/', include('apps.ai_agents.java_code_analyzer.urls')),
    path('prd_analyzer/', include('apps.ai_agents.prd_analyzer.urls')),
    path('test_case_generator/', include('apps.ai_agents.test_case_generator.urls')),
    path('test_case_reviewer/', include('apps.ai_agents.test_case_reviewer.urls')),

]

# 添加静态文件和媒体文件服务（开发环境）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 