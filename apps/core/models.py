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