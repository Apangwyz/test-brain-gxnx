from django.urls import path
from . import views

app_name = 'test_case_generator'

urlpatterns = [
    # 页面路由
    path('', views.generate, name='generate'),

    # API 路由
    path('save-test-case/', views.save_test_case, name='save_test_case'),
    
    # 文件上传路由
    path('upload-file/', views.upload_file, name='upload_file'),
    
    # 带进度跟踪的生成API
    path('generate-with-progress/', views.generate_with_progress, name='generate_with_progress'),
    
    # SSE进度查询端点
    path('progress/<str:task_id>/', views.get_progress, name='get_progress'),


]