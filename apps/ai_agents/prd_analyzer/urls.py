from django.urls import path
from . import views

app_name = 'prd_analyzer'

urlpatterns = [
    # 页面路由
    path('', views.prd_analyzer, name='prd_analyzer'),
    path('prd_analyzer/', views.prd_analyzer, name='prd_analyzer'),

    # API 路由
    path('upload/', views.prd_upload_api, name='prd_upload'),
    path('api/analyze/', views.prd_analyze_api, name='prd_analyze_api'),
    path('api/prd-to-testcase/', views.prd_to_testcase_api, name='prd_to_testcase'),
]