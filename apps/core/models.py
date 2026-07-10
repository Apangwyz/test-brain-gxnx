from django.db import models
from django.contrib.auth.models import User

class TestCase(models.Model):
    """测试用例模型"""
    STATUS_CHOICES = [
        ('pending', '待评审'),
        ('approved', '评审通过'),
        ('rejected', '评审未通过'),
    ]

    BU_CHOICES = [
        ('education', '教育'),
        ('user_center', '用户中心'),
        ('collaboration', '协同'),
        ('im', 'IM'),
        ('workspace', '工作台'),
        ('recruitment', '招聘'),
        ('work_management', '工作管理'),
        ('ai_application', 'AI 应用'),
        ('operation_platform', '运营平台'),
    ]
    
    PRIORITY_CHOICES = [
        ('p0', 'P0'),
        ('p1', 'P1'),
        ('p2', 'P2'),
        ('p3', 'P3'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="测试用例标题")
    description = models.TextField(verbose_name="测试用例描述")
    requirements = models.TextField(verbose_name="需求描述", blank=True)
    code_snippet = models.TextField(verbose_name="代码片段", blank=True)
    test_steps = models.TextField(verbose_name="测试步骤")
    expected_results = models.TextField(verbose_name="预期结果")
    actual_results = models.TextField(verbose_name="实际结果", blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name="评审状态"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_testcases',
        verbose_name="创建者",
        null=True,
        blank=True
    )

    current_version = models.IntegerField(default=1, verbose_name="当前版本号")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    llm_provider = models.CharField(max_length=50, null=True, blank=True)
    bu = models.CharField(max_length=50, choices=BU_CHOICES, blank=True, verbose_name='BU')
    feature = models.CharField(max_length=100, blank=True, verbose_name='Feature')
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, blank=True, verbose_name='Priority')
    system = models.ForeignKey(
        'System', 
        on_delete=models.CASCADE, 
        related_name='test_cases',
        verbose_name="所属系统",
        null=True,
        blank=True
    )
    
    def __str__(self):
        return (
            f"用例描述：\n{self.description}\n\n"
            f"测试步骤：\n{self.test_steps}\n\n"
            f"预期结果：\n{self.expected_results}\n"
        )
    
    class Meta:
        verbose_name = "测试用例"
        verbose_name_plural = "测试用例"

class TestCaseReview(models.Model):
    """测试用例评审记录"""
    test_case = models.ForeignKey(
        TestCase, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name="测试用例"
    )
    reviewer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name="评审人"
    )
    review_comments = models.TextField(verbose_name="评审意见")
    review_date = models.DateTimeField(auto_now_add=True, verbose_name="评审时间")
    
    def __str__(self):
        return f"Review for {self.test_case.title}"
    
    class Meta:
        verbose_name = "测试用例评审"
        verbose_name_plural = "测试用例评审"

class KnowledgeBase(models.Model):
    """知识库条目"""
    title = models.CharField(max_length=200, verbose_name="知识条目标题")
    content = models.TextField(verbose_name="知识内容")
    vector_id = models.CharField(max_length=100, blank=True, verbose_name="向量ID")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "知识库"
        verbose_name_plural = "知识库" 


class System(models.Model):
    """系统模型 - 用于管理外围系统清单"""
    SYSTEM_STATUS_CHOICES = [
        ('active', '启用'),
        ('inactive', '停用'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name="系统名称")
    code = models.CharField(max_length=50, unique=True, verbose_name="系统编码")
    description = models.TextField(blank=True, verbose_name="系统描述")
    status = models.CharField(
        max_length=20, 
        choices=SYSTEM_STATUS_CHOICES, 
        default='active',
        verbose_name="状态"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='created_systems',
        verbose_name="创建人",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "系统"
        verbose_name_plural = "系统管理"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]


class TestPlan(models.Model):
    """测试计划模型"""
    PLAN_STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '执行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="测试计划标题")
    description = models.TextField(blank=True, verbose_name="测试计划描述")
    system = models.ForeignKey(
        System, 
        on_delete=models.CASCADE, 
        related_name='test_plans',
        verbose_name="所属系统",
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=PLAN_STATUS_CHOICES, 
        default='draft',
        verbose_name="状态"
    )
    test_cases = models.ManyToManyField(
        'TestCase', 
        related_name='test_plans',
        blank=True,
        verbose_name="关联测试用例"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='created_testplans',
        verbose_name="创建人",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "测试计划"
        verbose_name_plural = "测试计划"


class RequirementDoc(models.Model):
    """需求文档模型"""
    title = models.CharField(max_length=200, verbose_name="文档标题")
    content = models.TextField(verbose_name="文档内容")
    system = models.ForeignKey(
        System, 
        on_delete=models.CASCADE, 
        related_name='requirements',
        verbose_name="所属系统",
        null=True,
        blank=True
    )
    file_path = models.CharField(max_length=500, blank=True, verbose_name="文件路径")
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='uploaded_requirements',
        verbose_name="上传人",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "需求文档"
        verbose_name_plural = "需求文档"


class TestExecutionRecord(models.Model):
    """测试执行记录模型"""
    EXECUTION_STATUS_CHOICES = [
        ('running', '执行中'),
        ('passed', '通过'),
        ('failed', '失败'),
        ('skipped', '跳过'),
        ('error', '异常'),
    ]
    
    test_case = models.ForeignKey(
        TestCase, 
        on_delete=models.CASCADE, 
        related_name='execution_records',
        verbose_name="测试用例"
    )
    status = models.CharField(
        max_length=20, 
        choices=EXECUTION_STATUS_CHOICES, 
        default='running',
        verbose_name="执行状态"
    )
    executor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='executed_tests',
        verbose_name="执行人",
        null=True,
        blank=True
    )
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    duration = models.FloatField(null=True, blank=True, verbose_name="耗时(秒)")
    log = models.TextField(blank=True, verbose_name="执行日志")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    def __str__(self):
        return f"Execution for {self.test_case.title} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = "测试执行记录"
        verbose_name_plural = "测试执行记录"
        ordering = ['-created_at']


class TestExecutionBatch(models.Model):
    """测试执行批次模型"""
    BATCH_STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="批次名称")
    status = models.CharField(
        max_length=20, 
        choices=BATCH_STATUS_CHOICES, 
        default='pending',
        verbose_name="批次状态"
    )
    test_cases = models.ManyToManyField(
        TestCase, 
        related_name='execution_batches',
        blank=True,
        verbose_name="关联测试用例"
    )
    executor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='execution_batches',
        verbose_name="执行人",
        null=True,
        blank=True
    )
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "测试执行批次"
        verbose_name_plural = "测试执行批次"

class TestCaseVersion(models.Model):
    """测试用例版本快照"""
    test_case = models.ForeignKey(
        'TestCase', on_delete=models.CASCADE,
        related_name='versions', verbose_name="所属用例"
    )
    version_number = models.IntegerField(verbose_name="版本号")
    snapshot = models.JSONField(verbose_name="版本快照")
    change_summary = models.CharField(
        max_length=500, blank=True, verbose_name="变更摘要"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="创建人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "用例版本"
        verbose_name_plural = "用例版本"
        unique_together = ('test_case', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"v{self.version_number} - {self.test_case.title}"


class TestReport(models.Model):
    """测试报告"""
    title = models.CharField(max_length=200, verbose_name="报告标题")
    batch = models.ForeignKey(
        'TestExecutionBatch', on_delete=models.CASCADE,
        related_name='reports', verbose_name="关联执行批次",
        null=True, blank=True
    )
    system = models.ForeignKey(
        'System', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="所属系统"
    )
    report_data = models.JSONField(verbose_name="报告数据")
    summary = models.TextField(blank=True, verbose_name="报告摘要")
    pdf_file = models.FileField(
        upload_to='reports/', blank=True, verbose_name="PDF 文件"
    )
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="生成人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")

    class Meta:
        verbose_name = "测试报告"
        verbose_name_plural = "测试报告"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class RequirementAnalysis(models.Model):
    """需求文档分析记录"""
    document_name = models.CharField(max_length=200, verbose_name="文档名称")
    document_hash = models.CharField(max_length=64, verbose_name="文档内容Hash", db_index=True)
    content_preview = models.TextField(blank=True, verbose_name="内容预览")
    content = models.TextField(blank=True, verbose_name="完整文档内容")
    quality_score = models.JSONField(default=dict, verbose_name="质量评分")
    completeness = models.JSONField(default=dict, verbose_name="完整度检查")
    consistency = models.JSONField(default=dict, verbose_name="一致性/冲突检测")
    risk_identification = models.JSONField(default=dict, verbose_name="风险识别")
    category_stats = models.JSONField(default=dict, verbose_name="需求分类统计")
    testability = models.JSONField(default=dict, verbose_name="可测试性评级")
    generation_strategy = models.JSONField(default=dict, blank=True, verbose_name="生成策略")

    system = models.ForeignKey(
        "System",
        on_delete=models.CASCADE,
        related_name="requirement_analyses",
        verbose_name="所属系统",
        null=True,
        blank=True
    )

    total_sections = models.IntegerField(default=0, verbose_name="总章节数")
    word_count = models.IntegerField(default=0, verbose_name="总字数")
    analysis_version = models.CharField(max_length=20, default="1.0", verbose_name="分析版本")

    # 采纳状态
    ADOPTION_CHOICES = [
        ('pending', '待审核'),
        ('adopted', '已采纳'),
        ('rejected', '已拒绝'),
    ]
    adoption_status = models.CharField(
        max_length=20, choices=ADOPTION_CHOICES,
        default='pending', verbose_name="采纳状态"
    )
    adoption_reviewer = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="审核人"
    )
    adopted_at = models.DateTimeField(null=True, blank=True, verbose_name="采纳/拒绝时间")

    # SRS 生成
    srs_content = models.JSONField(default=dict, blank=True, verbose_name="SRS内容")
    srs_generated_at = models.DateTimeField(null=True, blank=True, verbose_name="SRS生成时间")

    # 文档类型标记
    brd_type = models.CharField(max_length=50, default="business_requirement", verbose_name="文档类型")

    # SRS 采纳状态
    SRS_ADOPTION_CHOICES = [
        ('pending', '待审核'),
        ('adopted', '已采纳'),
        ('rejected', '已拒绝'),
    ]
    srs_adoption_status = models.CharField(
        max_length=20, choices=SRS_ADOPTION_CHOICES,
        default='pending', verbose_name="SRS采纳状态"
    )
    srs_adopted_at = models.DateTimeField(null=True, blank=True, verbose_name="SRS采纳/拒绝时间")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="分析时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "需求分析记录"
        verbose_name_plural = "需求分析记录"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.document_name} ({self.quality_score.get('overall_score', 'N/A')}分)"
