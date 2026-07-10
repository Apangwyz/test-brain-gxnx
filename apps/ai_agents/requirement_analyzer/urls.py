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
    path("api/adopted-srs/", views.adopted_srs_api, name="adopted_srs"),
    path("api/my-docs/", views.my_docs_api, name="my_docs"),

    path("api/<int:analysis_id>/generate-srs/", views.generate_srs_api, name="generate_srs"),
    path("api/<int:analysis_id>/srs/", views.srs_detail_api, name="srs_detail"),
    path("api/<int:analysis_id>/srs/export/", views.export_srs_api, name="export_srs"),
    path("api/<int:analysis_id>/srs/adopt/", views.srs_adopt_api, name="srs_adopt"),
    path("api/<int:analysis_id>/srs/reject/", views.srs_reject_api, name="srs_reject"),
    path("api/<int:analysis_id>/export/", views.export_report_api, name="export_report"),
    path("api/<int:analysis_id>/delete/", views.delete_document_api, name="delete_document"),
    path("api/<int:analysis_id>/resubmit/", views.resubmit_document_api, name="resubmit_document"),
]
