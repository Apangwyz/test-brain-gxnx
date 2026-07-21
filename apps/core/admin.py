from django.contrib import admin
from .models import TestCase, TestCaseReview, KnowledgeBase, System, TestPlan, RequirementDoc, TestExecutionRecord, TestExecutionBatch, TestReport

@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(TestCaseReview)
class TestCaseReviewAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'reviewer', 'review_date')
    list_filter = ('review_date',)
    search_fields = ('test_case__title', 'review_comments')
    readonly_fields = ('review_date',)

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at') 

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(TestPlan)
class TestPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'system', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(RequirementDoc)
class RequirementDocAdmin(admin.ModelAdmin):
    list_display = ('title', 'system', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at') 

@admin.register(TestExecutionRecord)
class TestExecutionRecordAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'status', 'start_time', 'duration', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('test_case__title', 'log')
    readonly_fields = ('created_at',)

@admin.register(TestExecutionBatch)
class TestExecutionBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_time', 'end_time', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
@admin.register(TestReport)
class TestReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'system', 'batch', 'summary', 'generated_by', 'created_at')
    list_filter = ('created_at', 'system')
    search_fields = ('title', 'summary')
    readonly_fields = ('created_at',)
    raw_id_fields = ('batch', 'generated_by')
