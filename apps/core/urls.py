from django.urls import path
from . import views
from .views_sse import stream_logs

urlpatterns = [
    # 页面路由
    path('', views.index, name='index'),

    path('knowledge/', views.knowledge_view, name='knowledge'),
    
    #知识库文件上传页面
    path('upload/', views.upload_single_file, name='upload_single_file'),

    path('api/add-knowledge/', views.add_knowledge, name='add_knowledge'),
    path('api/knowledge-list/', views.knowledge_list, name='knowledge_list'),
    path('api/search-knowledge/', views.search_knowledge, name='search_knowledge'),   
    path('api/stream-logs/', stream_logs, name='stream_logs'),
    
    # 系统管理API
    path('system/', views.system_management, name='system_management'),
    path('api/systems/', views.system_list, name='system_list'),
    path('api/systems/<int:system_id>/', views.system_detail, name='system_detail'),
    path('api/systems/search/', views.system_search, name='system_search'),
    path('api/systems/stats/', views.system_stats, name='system_stats'),
    path('api/systems/<int:system_id>/related/', views.get_system_related_data, name='system_related_data'),
    
    # 测试计划API
    path('api/test-plans/', views.test_plan_list, name='test_plan_list'),
    path('api/test-plans/<int:plan_id>/', views.test_plan_detail, name='test_plan_detail'),
    
    # 需求文档API
    path('api/requirements/', views.requirement_doc_list, name='requirement_doc_list'),
    path('api/requirements/<int:doc_id>/', views.requirement_doc_detail, name='requirement_doc_detail'),
    
    # 测试用例系统关联API
    path('api/testcases/<int:case_id>/system/', views.update_testcase_system, name='update_testcase_system'),
    
    # 测试执行API
    path('test-execution/', views.test_execution_view, name='test_execution'),
    path('api/test-execution/', views.test_execution_list, name='test_execution_list'),
    path('api/test-execution/<int:test_case_id>/execute/', views.execute_test_case, name='execute_test_case'),
    path('api/test-execution/batch/<int:batch_id>/execute/', views.execute_test_batch, name='execute_test_batch'),
    path('api/test-execution/stats/', views.test_execution_stats, name='test_execution_stats'),
    path('api/test-execution/export/', views.test_execution_export, name='test_execution_export'),
    ]