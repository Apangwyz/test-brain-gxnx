from django.urls import path
from . import views
from . import knowledge_views
from . import system_views
from . import version_views
from . import report_views
from . import test_execution_views
from . import progress_views
from .views_sse import stream_logs

urlpatterns = [
    # 页面路由
    path('', views.index, name='index'),

    path('knowledge/', knowledge_views.knowledge_view, name='knowledge'),
    
    #知识库文件上传页面
    path('upload/', knowledge_views.upload_single_file, name='upload_single_file'),

    path('api/add-knowledge/', knowledge_views.add_knowledge, name='add_knowledge'),
    path('api/knowledge-list/', knowledge_views.knowledge_list, name='knowledge_list'),

    path('api/knowledge/retrieve/', knowledge_views.retrieve_knowledge, name='retrieve_knowledge'),
    path('api/knowledge/list-select/', knowledge_views.knowledge_list_select, name='knowledge_list_select'),
    path('api/search-knowledge/', knowledge_views.search_knowledge, name='search_knowledge'),   
    path('api/stream-logs/', stream_logs, name='stream_logs'),
    
    # 系统管理API
    path('system/', system_views.system_management, name='system_management'),
    path('api/systems/', system_views.system_list, name='system_list'),
    path('api/systems/<int:system_id>/', system_views.system_detail, name='system_detail'),
    path('api/systems/search/', system_views.system_search, name='system_search'),
    path('api/systems/stats/', system_views.system_stats, name='system_stats'),
    path('api/systems/<int:system_id>/related/', system_views.get_system_related_data, name='system_related_data'),
    
    # 测试计划API
    path('api/test-plans/', system_views.test_plan_list, name='test_plan_list'),
    path('api/test-plans/<int:plan_id>/', system_views.test_plan_detail, name='test_plan_detail'),
    
    # 需求文档API
    path('api/requirements/', system_views.requirement_doc_list, name='requirement_doc_list'),
    path('api/requirements/<int:doc_id>/', system_views.requirement_doc_detail, name='requirement_doc_detail'),
    
    # 测试用例系统关联API
    path('api/testcases/<int:case_id>/system/', system_views.update_testcase_system, name='update_testcase_system'),
    
    # 测试执行API
    path('test-execution/', test_execution_views.test_execution_view, name='test_execution'),
    path('api/test-execution/', test_execution_views.test_execution_list, name='test_execution_list'),
    path('api/test-execution/<int:test_case_id>/execute/', test_execution_views.execute_test_case, name='execute_test_case'),
    path('api/test-execution/batch/<int:batch_id>/execute/', test_execution_views.execute_test_batch, name='execute_test_batch'),
    path('api/test-execution/stats/', test_execution_views.test_execution_stats, name='test_execution_stats'),
    path('api/test-execution/export/', test_execution_views.test_execution_export, name='test_execution_export'),

    # 版本管理
    path('api/testcases/<int:case_id>/save-version/', version_views.save_version, name='save_version'),
    path('api/testcases/<int:case_id>/versions/', version_views.list_versions, name='list_versions'),
    path('api/testcases/<int:case_id>/versions/<int:version>/', version_views.get_version_detail, name='get_version_detail'),
    path('api/testcases/<int:case_id>/rollback/<int:version>/', version_views.rollback_version, name='rollback_version'),
    path('api/testcases/<int:case_id>/diff/', version_views.diff_versions, name='diff_versions'),
    
    # 报告 API
    path('api/reports/', report_views.report_list_api, name='report_list_api'),
    path('api/reports/<int:report_id>/', report_views.report_detail_api, name='report_detail_api'),
    path('api/reports/generate/', report_views.generate_report_api, name='generate_report_api'),
    path('api/reports/<int:report_id>/export-pdf/', report_views.export_report_pdf, name='export_report_pdf'),
    path('api/reports/<int:report_id>/delete/', report_views.delete_report_api, name='delete_report_api'),

    # 报告页面
    path('reports/', report_views.report_list_view, name='report_list'),
    path('reports/<int:report_id>/', report_views.report_detail_view, name='report_detail'),
    
    # 通用进度管理API (由 common_progress.js 调用)
    path('api/progress/', progress_views.get_progress_api, name='generic_progress_api'),
    path('api/progress/<str:task_id>/', progress_views.sse_progress_stream, name='generic_progress_stream'),
    path('api/cancel/<str:task_id>/', progress_views.cancel_task_api, name='generic_cancel_task'),
]