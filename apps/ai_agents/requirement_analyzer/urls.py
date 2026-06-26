from django.urls import path
from . import views

app_name = "requirement_analyzer"

urlpatterns = [
    path("", views.requirement_analysis_page, name="requirement_analysis"),
    path("upload/", views.upload_api, name="upload"),
    path("api/analyze/", views.analyze_api, name="analyze"),
    path("api/result/<int:analysis_id>/", views.analysis_result_api, name="analysis_result"),
    path("api/result/latest/", views.latest_result_api, name="analysis_result_latest"),
    path("api/generate/", views.generate_from_analysis_api, name="generate"),
    path("api/<int:analysis_id>/adopt/", views.adopt_document_api, name="adopt_document"),
    path("api/<int:analysis_id>/reject/", views.reject_document_api, name="reject_document"),
    path("api/adopted-docs/", views.adopted_docs_api, name="adopted_docs"),
    path("api/<int:analysis_id>/export/", views.export_report_api, name="export_report"),
]
