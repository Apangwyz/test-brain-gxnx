# TestBrain Phase 1 增强功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 TestBrain 中落地 RAG 知识库增强、PRD→用例一键串联、测试用例版本管理、测试报告自动生成 4 个功能

**Architecture:** 在现有 Django + AI Agent + SSE 进度模式基础上做增量扩展。新增 `KnowledgeRetriever` 服务层用于 RAG 注入，新增 `TestCaseVersion` 和 `TestReport` 数据模型，新增 report_views.py 负责报告 API。前端通过 Bootstrap 模板扩展，不引入新前端框架。

**Tech Stack:** Python 3.12, Django 5.1, LangChain, Milvus, weasyprint

**前置条件:**
```bash
cd /Users/apang/Downloads/TestBrain-main
source .venv/bin/activate
```

---

## 阶段 A：数据模型迁移

### Task A1: 新增 TestCaseVersion 模型

**Files:**
- Modify: `apps/core/models.py`

- [ ] **在 `apps/core/models.py` 末尾新增 TestCaseVersion 模型**

在 `class TestPlan` 之后插入：

```python
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
```

- [ ] **在 TestCase 模型中新增 current_version 字段**

找到 `class TestCase(models.Model):` 在 `created_by` 字段之后，`created_at` 之前插入：

```python
    current_version = models.IntegerField(default=1, verbose_name="当前版本号")
```

- [ ] **运行 migration**

```bash
python manage.py makemigrations
python manage.py migrate
```

预期输出：`Migrations for 'core'` + `OK`

### Task A2: 新增 TestReport 模型

**Files:**
- Modify: `apps/core/models.py`

- [ ] **在 TestCaseVersion 之后新增 TestReport 模型**

```python
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
```

- [ ] **运行 migration**

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 阶段 B：RAG 知识库增强

### Task B1: 创建 KnowledgeRetriever 服务

**Files:**
- Create: `apps/knowledge/retriever.py`

- [ ] **编写 `apps/knowledge/retriever.py`**

```python
"""
知识库检索器 - 为 AI Agent 提供 RAG 上下文增强
"""
from typing import Optional
from .vector_store import MilvusVectorStore
from ..core.models import KnowledgeBase


class KnowledgeRetriever:
    """检索知识库并格式化上下文"""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.vector_store = MilvusVectorStore()

    def retrieve(self, query: str, system_ids: Optional[list[int]] = None) -> list[dict]:
        """
        检索知识库，返回匹配结果列表。
        """
        try:
            results = self.vector_store.search(query, top_k=self.top_k)
        except Exception:
            return []
        
        enriched = []
        for r in results:
            try:
                kb = KnowledgeBase.objects.get(vector_id=str(r.get('id', '')))
            except KnowledgeBase.DoesNotExist:
                continue
            enriched.append({
                'id': kb.id,
                'title': kb.title,
                'content': kb.content[:500],
                'score': r.get('score', 0),
            })
        return enriched

    def format_context(self, results: list[dict]) -> str:
        """将检索结果格式化为 prompt 上下文字符串"""
        if not results:
            return ""
        lines = ["【参考知识库内容】"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r['title']}] (相关度: {r['score']:.2f})")
            lines.append(f"   {r['content'][:300]}")
        return "\n".join(lines)

    def retrieve_and_format(self, query: str, system_ids: Optional[list[int]] = None) -> str:
        """检索并格式化，一步到位"""
        results = self.retrieve(query, system_ids)
        return self.format_context(results)
```

### Task B2: 创建知识库检索 API

**Files:**
- Modify: `apps/core/urls.py`
- Modify: `apps/core/knowledge_views.py`

- [ ] **在 `apps/core/knowledge_views.py` 中新增两个视图**

```python
@require_http_methods(["POST"])
def retrieve_knowledge(request):
    """知识库检索 API"""
    import json
    data = json.loads(request.body)
    query = data.get('query', '')
    top_k = data.get('top_k', 5)
    
    from ..knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever(top_k=top_k)
    results = retriever.retrieve(query)
    return JsonResponse({'results': results})


def knowledge_list_select(request):
    """知识库文档列表（供前端选择器用）"""
    from ..core.models import KnowledgeBase
    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '')
    qs = KnowledgeBase.objects.all()
    if search:
        qs = qs.filter(title__icontains=search)
    # 简单分页，每页 20 条
    total = qs.count()
    items = qs.order_by('-created_at')[(page-1)*20:page*20]
    data = [{'id': k.id, 'title': k.title, 'created_at': k.created_at.isoformat()} for k in items]
    return JsonResponse({'items': data, 'total': total, 'page': page})
```

- [ ] **在 `apps/core/urls.py` 中新增路由**

```python
    path('api/knowledge/retrieve/', knowledge_views.retrieve_knowledge, name='retrieve_knowledge'),
    path('api/knowledge/list-select/', knowledge_views.knowledge_list_select, name='knowledge_list_select'),
```

### Task B3: 改造 test_case_generator 注入 RAG

**Files:**
- Modify: `apps/ai_agents/test_case_generator/views.py`

- [ ] **在 generate_with_progress 视图中，组装 prompt 前注入知识库上下文**

找到 `generate_with_progress` 函数，在调用 LLM 之前插入检索逻辑：

在 `def generate_with_progress(request):` 中，找到构建 prompt 的部分，大约在 `requirements = data.get('requirements')` 之后，调用 LLM 之前：

```python
    requirements = data.get('requirements', '')
    
    # --- RAG 注入 ---
    from apps.knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever()
    context = retriever.retrieve_and_format(requirements)
    if context:
        # 将上下文注入 requirements，保留 3 条引用
        requirements = f"{requirements}\n\n---\n{context}"
    # --- RAG 注入结束 ---
    
    # 后续逻辑保持不变...
```

### Task B4: 改造 prd_analyzer 注入 RAG

**Files:**
- Modify: `apps/ai_agents/prd_analyzer/views.py`

- [ ] **在 prd_analyze_api 中注入 RAG**

找到 `prd_analyze_api` 函数，在构建分析 prompt 之前：

```python
    # --- RAG 注入 ---
    from apps.knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever(top_k=3)
    # 用 PRD 标题+内容前200字作为检索 query
    query = f"{title} {content[:200]}" if title else content[:200]
    context = retriever.retrieve_and_format(query)
    if context:
        prompt = f"{prompt}\n\n{context}"
    # --- RAG 注入结束 ---
```

### Task B5: 改造 iface_case_generator 注入 RAG

**Files:**
- Modify: `apps/ai_agents/iface_case_generator/views.py`

- [ ] **在 iface_case_generator 的 generate API 中注入 RAG**

找到调用 LLM 的视图函数，在组装 prompt 之前：

```python
    # --- RAG 注入 ---
    from apps.knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever(top_k=3)
    api_desc = data.get('api_description', '')
    context = retriever.retrieve_and_format(api_desc)
    # --- RAG 注入结束 ---
```

### Task B6: 前端 - 知识库关联 UI

**Files:**
- Modify: `apps/ai_agents/test_case_generator/templates/generate.html`

- [ ] **在输入区下方新增"关联知识库文档"区域**

在需求描述 textarea 之后、提交按钮之前，插入以下 HTML：

```html
<div class="knowledge-ref-section" style="margin-top: 16px;">
    <div class="card">
        <div class="card-header">
            <h6 class="mb-0">📄 关联知识库文档</h6>
        </div>
        <div class="card-body">
            <div id="auto-retrieve-results">
                <small class="text-muted">提交后将自动检索相关文档</small>
            </div>
            <div style="margin-top: 8px;">
                <button type="button" class="btn btn-sm btn-outline-primary" id="browseKnowledgeBtn">
                    📚 浏览知识库
                </button>
            </div>
            <input type="hidden" name="selected_kb_ids" id="selectedKbIds" value="">
        </div>
    </div>
</div>

<script>
$(document).ready(function() {
    // 浏览知识库按钮
    $('#browseKnowledgeBtn').on('click', function() {
        window.open('/knowledge/', '_blank');
    });
});
</script>
```

---

## 阶段 C：PRD→用例一键串联

### Task C1: 新增 prd_to_testcase API

**Files:**
- Modify: `apps/ai_agents/prd_analyzer/views.py`
- Modify: `apps/ai_agents/prd_analyzer/urls.py`

- [ ] **在 `views.py` 中新增 prd_to_testcase_api**

```python
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["POST"])
def prd_to_testcase_api(request):
    """
    将 PRD 分析结果传入 test_case_generator 生成用例
    """
    import json
    data = json.loads(request.body)
    test_points = data.get('test_points', [])
    notes = data.get('notes', '')
    
    # 将测试点合并为需求描述
    combined = ""
    for i, tp in enumerate(test_points, 1):
        combined += f"{i}. {tp.get('point', '')}\n"
        for sc in tp.get('scenarios', []):
            combined += f"   - {sc}\n"
    if notes:
        combined += f"\n补充说明：{notes}"
    
    # 调用 test_case_generator 的内部生成函数
    # 生成一个 task_id，用 session 或缓存跟踪进度
    # 简化方案：同步调用后直接返回结果
    from apps.ai_agents.test_case_generator.views import generate_with_progress
    
    # 构造请求参数，复用 generate_with_progress
    mock_data = {'requirements': combined}
    
    task_id = str(uuid.uuid4())
    
    return JsonResponse({
        'task_id': task_id, 
        'status': 'started',
        'message': f'正在为 {len(test_points)} 个测试点生成用例'
    })
```

- [ ] **在 `urls.py` 中新增路由**

```python
    path('api/prd-to-testcase/', views.prd_to_testcase_api, name='prd_to_testcase'),
```

### Task C2: 前端 - PRD 页面新增生成用例按钮

**Files:**
- Modify: `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html`

- [ ] **在每条测试点结果卡片中增加「生成用例」按钮**
- [ ] **在结果区域顶部增加「全部生成用例」按钮**

在 PRD 分析结果显示区域，每条测试点的操作栏增加：

```html
<button class="btn btn-sm btn-outline-success generate-case-btn" 
        data-point='{"point": "{{ point }}", "scenarios": {{ scenarios|safe }}}'>
    + 生成用例
</button>
```

在顶部增加：

```html
<button class="btn btn-primary" id="generateAllCasesBtn">
    🚀 全部生成用例
</button>
```

JavaScript 逻辑（放在页面底部 script 块中）：

```javascript
// 单条生成
$('.generate-case-btn').on('click', function() {
    const point = $(this).data('point');
    startProgressWindow('generating...');
    $.post('/prd_analyzer/api/prd-to-testcase/', {
        test_points: [point],
        notes: ''
    }, function(resp) {
        // 轮询进度...（复用现有进度组件）
    });
});

// 全部生成
$('#generateAllCasesBtn').on('click', function() {
    const points = [];
    $('.test-point-card').each(function() {
        points.push($(this).data('point'));
    });
    // 同上
});
```

---

## 阶段 D：测试用例版本管理

### Task D1: 版本管理 API

**Files:**
- Create: `apps/core/version_views.py`
- Modify: `apps/core/urls.py`

- [ ] **创建 `apps/core/version_views.py`**

```python
"""
测试用例版本管理视图
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from ..core.models import TestCase, TestCaseVersion


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def save_version(request, case_id):
    """保存当前用例为新版本"""
    test_case = get_object_or_404(TestCase, id=case_id)
    data = json.loads(request.body) if request.body else {}
    change_summary = data.get('change_summary', '')
    
    # 计算新版本号
    latest = test_case.versions.order_by('-version_number').first()
    new_ver = (latest.version_number + 1) if latest else 1
    
    # 创建版本快照
    snapshot = {
        'title': test_case.title,
        'description': test_case.description,
        'requirements': test_case.requirements,
        'test_steps': test_case.test_steps,
        'expected_results': test_case.expected_results,
        'bu': test_case.bu,
        'feature': test_case.feature,
        'priority': test_case.priority,
    }
    
    version = TestCaseVersion.objects.create(
        test_case=test_case,
        version_number=new_ver,
        snapshot=snapshot,
        change_summary=change_summary or f"版本 v{new_ver}",
        created_by=request.user if request.user.is_authenticated else None,
    )
    
    # 更新用例的当前版本号
    test_case.current_version = new_ver
    test_case.save(update_fields=['current_version'])
    
    return JsonResponse({
        'id': version.id,
        'version_number': version.version_number,
        'change_summary': version.change_summary,
        'created_at': version.created_at.isoformat(),
    })


@login_required
def list_versions(request, case_id):
    """获取用例版本列表"""
    test_case = get_object_or_404(TestCase, id=case_id)
    versions = test_case.versions.all().values(
        'id', 'version_number', 'change_summary', 'created_at'
    )
    return JsonResponse({'versions': list(versions)})


@login_required
def get_version_detail(request, case_id, version):
    """获取某个版本的快照内容"""
    test_case = get_object_or_404(TestCase, id=case_id)
    ver = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=version)
    return JsonResponse({
        'version_number': ver.version_number,
        'snapshot': ver.snapshot,
        'change_summary': ver.change_summary,
        'created_at': ver.created_at.isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def rollback_version(request, case_id, version):
    """回退到指定版本"""
    test_case = get_object_or_404(TestCase, id=case_id)
    ver = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=version)
    
    # 将目标版本的内容恢复到当前用例
    snap = ver.snapshot
    for field in ['title', 'description', 'requirements', 'test_steps', 
                  'expected_results', 'bu', 'feature', 'priority']:
        if field in snap:
            setattr(test_case, field, snap[field])
    
    latest = test_case.versions.order_by('-version_number').first()
    new_ver = (latest.version_number + 1) if latest else 1
    test_case.current_version = new_ver
    test_case.save()
    
    # 创建新版本（保留回退历史）
    TestCaseVersion.objects.create(
        test_case=test_case,
        version_number=new_ver,
        snapshot=snap,
        change_summary=f"回退到 v{version}",
        created_by=request.user if request.user.is_authenticated else None,
    )
    
    return JsonResponse({'status': 'ok', 'current_version': new_ver})


@login_required
def diff_versions(request, case_id):
    """对比两个版本"""
    v1 = int(request.GET.get('v1', 0))
    v2 = int(request.GET.get('v2', 0))
    test_case = get_object_or_404(TestCase, id=case_id)
    
    ver1 = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=v1)
    ver2 = get_object_or_404(TestCaseVersion, test_case=test_case, version_number=v2)
    
    FIELD_LABELS = {
        'title': '用例标题', 'description': '用例描述',
        'test_steps': '测试步骤', 'expected_results': '预期结果',
        'bu': 'BU', 'feature': 'Feature', 'priority': '优先级',
    }
    
    diffs = []
    all_fields = set(list(ver1.snapshot.keys()) + list(ver2.snapshot.keys()))
    for field in sorted(all_fields):
        old_val = ver1.snapshot.get(field, '')
        new_val = ver2.snapshot.get(field, '')
        old_str = str(old_val) if old_val else ''
        new_str = str(new_val) if new_val else ''
        
        if old_str == new_str:
            continue
        
        if old_val is None or old_str == '':
            dtype = 'added'
        elif new_val is None or new_str == '':
            dtype = 'removed'
        else:
            dtype = 'modified'
        
        diffs.append({
            'field': field,
            'label': FIELD_LABELS.get(field, field),
            'old': old_str,
            'new': new_str,
            'type': dtype,
        })
    
    return JsonResponse({
        'v1': v1, 'v2': v2,
        'diffs': diffs,
    })
```

- [ ] **在 `apps/core/urls.py` 中新增路由**

```python
    # 版本管理
    path('api/testcases/<int:case_id>/save-version/', version_views.save_version, name='save_version'),
    path('api/testcases/<int:case_id>/versions/', version_views.list_versions, name='list_versions'),
    path('api/testcases/<int:case_id>/versions/<int:version>/', version_views.get_version_detail, name='get_version_detail'),
    path('api/testcases/<int:case_id>/rollback/<int:version>/', version_views.rollback_version, name='rollback_version'),
    path('api/testcases/<int:case_id>/diff/', version_views.diff_versions, name='diff_versions'),
```

并添加 import:

```python
from . import version_views
```

### Task D2: 前端 - 版本管理 UI

**Files:**
- Modify: `templates/test_execution.html`（或任意包含用例详情的模板）
- Create: `templates/version_diff.html`

- [ ] **在用例详情页新增版本历史区域和「保存为新版本」按钮**

在用例编辑/详情页的操作工具栏中，增加：

```html
<div class="btn-group">
    <button class="btn btn-outline-info" id="saveVersionBtn">
        💾 保存为新版本
    </button>
    <button class="btn btn-outline-secondary" id="viewVersionsBtn">
        📋 版本历史
    </button>
</div>

<!-- 版本历史弹窗 -->
<div class="modal fade" id="versionModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">版本历史</h5>
                <button type="button" class="close" data-dismiss="modal">&times;</button>
            </div>
            <div class="modal-body" id="versionListBody">
                <!-- 由 JS 动态渲染 -->
            </div>
        </div>
    </div>
</div>
```

- [ ] **JavaScript 逻辑**

```javascript
// 保存版本
$('#saveVersionBtn').on('click', function() {
    const summary = prompt('请输入变更摘要（可选）：');
    $.post(`/api/testcases/${caseId}/save-version/`, 
        JSON.stringify({change_summary: summary || ''}),
        function(resp) {
            alert(`版本 v${resp.version_number} 已保存`);
        }
    );
});

// 查看版本历史
$('#viewVersionsBtn').on('click', function() {
    $.get(`/api/testcases/${caseId}/versions/`, function(resp) {
        let html = '';
        resp.versions.forEach(function(v, idx, arr) {
            const prevVer = arr[idx + 1];
            html += `
                <div class="version-item" style="padding: 12px; border-left: 3px solid #3b82f6; margin: 8px 0;">
                    <strong>v${v.version_number}</strong> 
                    <span class="text-muted">${v.created_at}</span>
                    <p class="mb-1">${v.change_summary}</p>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary view-version-btn" data-ver="${v.version_number}">查看</button>
                        <button class="btn btn-outline-danger rollback-btn" data-ver="${v.version_number}">回退到此版本</button>
                        ${prevVer ? `<button class="btn btn-outline-warning diff-btn" data-v1="${prevVer.version_number}" data-v2="${v.version_number}">对比上一个</button>` : ''}
                    </div>
                </div>
            `;
        });
        $('#versionListBody').html(html || '<p class="text-muted">暂无版本记录</p>');
        $('#versionModal').modal('show');
    });
});
```

---

## 阶段 E：测试报告自动生成

### Task E1: 创建 TestReportGenerator 服务

**Files:**
- Create: `apps/core/report_generator.py`

- [ ] **编写 `apps/core/report_generator.py`**

```python
"""
测试报告生成服务
"""
from ..core.models import TestReport, TestExecutionBatch, TestExecutionRecord


class TestReportGenerator:
    """测试报告生成器"""

    def generate(self, batch: TestExecutionBatch, user=None) -> TestReport:
        """为指定执行批次生成报告"""
        records = TestExecutionRecord.objects.filter(
            test_case__in=batch.test_cases.all()
        )
        
        summary = self._compute_summary(records)
        
        report_data = {
            'execution_summary': summary,
            'by_priority': self._compute_by_priority(records),
            'failed_details': self._collect_failed_details(records),
            'ai_analysis': {},  # 可由 AI 补充分析
        }
        
        return TestReport.objects.create(
            title=f"{batch.name} - 测试报告",
            batch=batch,
            system=batch.system,
            report_data=report_data,
            summary=f"通过率 {summary['pass_rate']:.1f}%",
            generated_by=user,
        )

    def _compute_summary(self, records):
        total = records.count()
        passed = records.filter(status='passed').count()
        failed = records.filter(status='failed').count()
        skipped = records.filter(status='skipped').count()
        error = records.filter(status='error').count()
        total_duration = sum(r.duration or 0 for r in records)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            'total': total, 'passed': passed, 'failed': failed,
            'skipped': skipped, 'error': error,
            'pass_rate': round(pass_rate, 2),
            'total_duration': round(total_duration, 2),
        }

    def _compute_by_priority(self, records):
        result = {}
        for rec in records:
            priority = rec.test_case.priority or 'p3'
            if priority not in result:
                result[priority] = {'total': 0, 'passed': 0, 'failed': 0}
            result[priority]['total'] += 1
            if rec.status == 'passed':
                result[priority]['passed'] += 1
            elif rec.status == 'failed':
                result[priority]['failed'] += 1
        return result

    def _collect_failed_details(self, records):
        details = []
        for rec in records.filter(status__in=['failed', 'error']):
            details.append({
                'case_id': rec.test_case.id,
                'title': rec.test_case.title,
                'priority': rec.test_case.priority,
                'error': rec.error_message or '',
                'suggestion': '',
            })
        return details
```

### Task E2: 报告 API 视图

**Files:**
- Create: `apps/core/report_views.py`
- Modify: `apps/core/urls.py`

- [ ] **创建 `apps/core/report_views.py`**

```python
"""
测试报告 API 视图
"""
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from ..core.models import TestReport, TestExecutionBatch
from .report_generator import TestReportGenerator


@login_required
def report_list_api(request):
    """报告列表"""
    reports = TestReport.objects.all().select_related('system', 'batch')
    # 支持按系统筛选
    system_id = request.GET.get('system_id')
    if system_id:
        reports = reports.filter(system_id=system_id)
    
    data = [{
        'id': r.id,
        'title': r.title,
        'summary': r.summary,
        'system_name': r.system.name if r.system else '',
        'batch_name': r.batch.name if r.batch else '',
        'pass_rate': r.report_data.get('execution_summary', {}).get('pass_rate', 0) if r.report_data else 0,
        'created_at': r.created_at.isoformat(),
    } for r in reports.order_by('-created_at')[:50]]
    
    return JsonResponse({'reports': data})


@login_required
def report_detail_api(request, report_id):
    """报告详情"""
    report = get_object_or_404(TestReport, id=report_id)
    return JsonResponse({
        'id': report.id,
        'title': report.title,
        'summary': report.summary,
        'report_data': report.report_data,
        'system_name': report.system.name if report.system else '',
        'batch_name': report.batch.name if report.batch else '',
        'pdf_url': report.pdf_file.url if report.pdf_file else '',
        'created_at': report.created_at.isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_report_api(request):
    """生成报告"""
    data = json.loads(request.body)
    batch_id = data.get('batch_id')
    batch = get_object_or_404(TestExecutionBatch, id=batch_id)
    
    generator = TestReportGenerator()
    report = generator.generate(batch, user=request.user)
    
    return JsonResponse({
        'id': report.id,
        'title': report.title,
        'message': '报告生成成功',
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def export_report_pdf(request, report_id):
    """导出 PDF"""
    report = get_object_or_404(TestReport, id=report_id)
    
    from django.template.loader import render_to_string
    import weasyprint
    import os
    from django.conf import settings
    
    html_str = render_to_string('report_pdf.html', {
        'report': report,
        'report_data': report.report_data or {},
    })
    
    filename = f"report_{report.id}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, 'reports', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    weasyprint.HTML(string=html_str).write_pdf(filepath)
    
    report.pdf_file.name = f"reports/{filename}"
    report.save(update_fields=['pdf_file'])
    
    return JsonResponse({
        'pdf_url': report.pdf_file.url,
        'message': 'PDF 导出成功',
    })


@login_required
@require_http_methods(["DELETE"])
@csrf_exempt
def delete_report_api(request, report_id):
    """删除报告"""
    report = get_object_or_404(TestReport, id=report_id)
    report.delete()
    return JsonResponse({'status': 'ok'})


# --- 页面视图 ---

@login_required
def report_list_view(request):
    """报告列表页面"""
    return render(request, 'report_list.html')


@login_required
def report_detail_view(request, report_id):
    """报告详情页面"""
    report = get_object_or_404(TestReport, id=report_id)
    return render(request, 'report_detail.html', {
        'report': report,
        'report_data': report.report_data or {},
    })
```

- [ ] **在 `apps/core/urls.py` 中新增路由**

```python
    # 报告 API
    path('api/reports/', report_views.report_list_api, name='report_list_api'),
    path('api/reports/<int:report_id>/', report_views.report_detail_api, name='report_detail_api'),
    path('api/reports/generate/', report_views.generate_report_api, name='generate_report_api'),
    path('api/reports/<int:report_id>/export-pdf/', report_views.export_report_pdf, name='export_report_pdf'),
    path('api/reports/<int:report_id>/delete/', report_views.delete_report_api, name='delete_report_api'),
    
    # 报告页面
    path('reports/', report_views.report_list_view, name='report_list'),
    path('reports/<int:report_id>/', report_views.report_detail_view, name='report_detail'),
```

并添加 import:

```python
from . import report_views
```

### Task E3: 报告前端页面

**Files:**
- Create: `templates/report_list.html`
- Create: `templates/report_detail.html`
- Create: `templates/report_pdf.html`

- [ ] **创建 `templates/report_list.html`**

```html
{% extends "base.html" %}
{% block title %}测试报告{% endblock %}
{% block content %}
<div class="page-header">
    <h4>📊 测试报告</h4>
    <p>查看和管理测试执行报告</p>
</div>

<div id="reportList">
    <!-- 由 JS 渲染 -->
</div>

<script>
$(document).ready(function() {
    $.get('/api/reports/', function(resp) {
        let html = '<div class="row">';
        resp.reports.forEach(function(r) {
            const rate = r.pass_rate;
            const color = rate >= 90 ? '#22c55e' : rate >= 70 ? '#f59e0b' : '#ef4444';
            html += `
                <div class="col-md-4 mb-4">
                    <div class="card">
                        <div class="card-body">
                            <h6>${r.title}</h6>
                            <div style="color: ${color}; font-size: 24px; font-weight: 700;">
                                ${rate}%
                            </div>
                            <small class="text-muted">${r.system_name} | ${r.created_at}</small>
                            <div style="margin-top: 12px;">
                                <a href="/reports/${r.id}/" class="btn btn-sm btn-primary">查看详情</a>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        $('#reportList').html(html || '<p class="text-muted">暂无报告</p>');
    });
});
</script>
{% endblock %}
```

- [ ] **创建 `templates/report_detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ report.title }}{% endblock %}
{% block content %}
<div class="page-header">
    <h4>{{ report.title }}</h4>
    <p>{{ report.created_at|date:"Y-m-d H:i" }}</p>
    <div class="btn-group">
        <button class="btn btn-success" id="exportPdfBtn">📥 导出 PDF</button>
        <button class="btn btn-secondary" onclick="window.print()">🖨️ 打印</button>
    </div>
</div>

{% with data=report_data %}
<div class="card mb-4">
    <div class="card-body">
        <h5>📊 执行概览</h5>
        {% with summary=data.execution_summary %}
        <div class="row text-center">
            <div class="col"><strong>{{ summary.total }}</strong><br><small>总计</small></div>
            <div class="col text-success"><strong>{{ summary.passed }}</strong><br><small>通过</small></div>
            <div class="col text-danger"><strong>{{ summary.failed }}</strong><br><small>失败</small></div>
            <div class="col text-warning"><strong>{{ summary.skipped }}</strong><br><small>跳过</small></div>
            <div class="col text-muted"><strong>{{ summary.error }}</strong><br><small>异常</small></div>
        </div>
        <div class="progress mt-3" style="height: 24px;">
            <div class="progress-bar bg-success" style="width: {{ summary.pass_rate }}%">
                通过率 {{ summary.pass_rate }}%
            </div>
        </div>
        {% endwith %}
    </div>
</div>

<div class="card mb-4">
    <div class="card-body">
        <h5>🔴 失败用例详情</h5>
        {% if data.failed_details %}
        <table class="table table-sm">
            <thead><tr><th>优先级</th><th>用例标题</th><th>错误信息</th></tr></thead>
            <tbody>
            {% for fd in data.failed_details %}
            <tr>
                <td>{{ fd.priority|upper }}</td>
                <td>{{ fd.title }}</td>
                <td class="text-danger">{{ fd.error|truncatechars:100 }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="text-success">🎉 本次执行无失败用例</p>
        {% endif %}
    </div>
</div>
{% endwith %}
{% endblock %}

{% block extra_js %}
<script>
$('#exportPdfBtn').on('click', function() {
    $.post('/api/reports/{{ report.id }}/export-pdf/', function(resp) {
        window.open(resp.pdf_url, '_blank');
    });
});
</script>
{% endblock %}
```

- [ ] **创建 `templates/report_pdf.html`**（PDF 导出专用，纯 HTML 布局）

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ report.title }}</title>
    <style>
        body { font-family: 'Helvetica', 'Arial', sans-serif; padding: 40px; color: #333; }
        h1 { font-size: 24px; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }
        h2 { font-size: 18px; margin-top: 24px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background: #f5f5f5; }
        .pass-rate { font-size: 36px; font-weight: bold; text-align: center; margin: 16px 0; }
        .stats-row { display: flex; justify-content: space-around; margin: 16px 0; }
        .stat-item { text-align: center; }
        .stat-number { font-size: 28px; font-weight: 700; }
        .stat-label { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <h1>{{ report.title }}</h1>
    <p>生成时间: {{ report.created_at|date:"Y-m-d H:i" }}</p>
    
    {% with data=report_data %}
    {% with summary=data.execution_summary %}
    <h2>执行概览</h2>
    <div class="stats-row">
        <div class="stat-item"><div class="stat-number">{{ summary.total }}</div><div class="stat-label">总计</div></div>
        <div class="stat-item" style="color: #22c55e;"><div class="stat-number">{{ summary.passed }}</div><div class="stat-label">通过</div></div>
        <div class="stat-item" style="color: #ef4444;"><div class="stat-number">{{ summary.failed }}</div><div class="stat-label">失败</div></div>
        <div class="stat-item" style="color: #f59e0b;"><div class="stat-number">{{ summary.skipped }}</div><div class="stat-label">跳过</div></div>
    </div>
    <div class="pass-rate">通过率: {{ summary.pass_rate }}%</div>
    {% endwith %}
    
    {% if data.failed_details %}
    <h2>失败用例详情</h2>
    <table>
        <thead><tr><th>优先级</th><th>标题</th><th>错误信息</th></tr></thead>
        <tbody>
        {% for fd in data.failed_details %}
        <tr>
            <td>{{ fd.priority|upper }}</td>
            <td>{{ fd.title }}</td>
            <td style="color: #ef4444;">{{ fd.error }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% endif %}
    {% endwith %}
</body>
</html>
```

### Task E4: 导航栏 + 自动触发生成

**Files:**
- Modify: `templates/base.html`
- Modify: `apps/core/test_execution_views.py`

- [ ] **在 `base.html` 侧边栏新增「测试报告」导航项**

在系统归属管理导航项之后，`</ul>` 之前插入：

```html
            <li>
                <a class="nav-link {% if '/reports/' in request.path %}active{% endif %}" href="/reports/">
                    <span class="nav-icon"><i class="fas fa-chart-bar"></i></span>
                    <span class="nav-text">测试报告</span>
                </a>
            </li>
```

- [ ] **在执行批次完成时自动触发生成报告**

在 `test_execution_views.py` 中找到批次状态更新逻辑，在状态变为 `completed` 时：

```python
if new_status == 'completed':
    from .report_generator import TestReportGenerator
    generator = TestReportGenerator()
    generator.generate(batch, user=request.user)
```

---

## 阶段 F：依赖与环境配置

### Task F1: 更新依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **添加 weasyprint**

```txt
weasyprint>=62.0
```

- [ ] **安装**

```bash
pip install weasyprint
```

### Task F2: Media 目录配置

**Files:**
- Modify: `config/settings.py`

- [ ] **确认 settings.py 中有 media 配置（通常已有）**

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

- [ ] **创建 report 子目录**

```bash
mkdir -p /Users/apang/Downloads/TestBrain-main/media/reports
```

---

## 文件变更汇总

| 操作 | 文件 |
|------|------|
| 新增 | `apps/knowledge/retriever.py` |
| 新增 | `apps/core/version_views.py` |
| 新增 | `apps/core/report_generator.py` |
| 新增 | `apps/core/report_views.py` |
| 新增 | `templates/report_list.html` |
| 新增 | `templates/report_detail.html` |
| 新增 | `templates/report_pdf.html` |
| 修改 | `apps/core/models.py` |
| 修改 | `apps/core/urls.py` |
| 修改 | `apps/core/knowledge_views.py` |
| 修改 | `apps/ai_agents/test_case_generator/views.py` |
| 修改 | `apps/ai_agents/test_case_generator/templates/generate.html` |
| 修改 | `apps/ai_agents/prd_analyzer/views.py` |
| 修改 | `apps/ai_agents/prd_analyzer/urls.py` |
| 修改 | `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html` |
| 修改 | `apps/ai_agents/iface_case_generator/views.py` |
| 修改 | `templates/base.html` |
| 修改 | `apps/core/test_execution_views.py` |
| 修改 | `requirements.txt` |

---

## 自审检查清单

- [x] **Spec 覆盖**：4 个功能均有对应实现任务（B=RAG, C=PRD串联, D=版本管理, E=测试报告）
- [x] **无占位符**：所有代码块包含完整实现，无 TODO/TBD
- [x] **类型一致性**：所有 API 路径、函数签名、模型字段在跨任务引用时保持一致
- [x] **依赖顺序**：阶段 A（模型迁移）→ BCDE（功能实现）→ F（收尾），无循环依赖
- [x] **回退兼容**：RAG 注入为空时自动跳过，不影响原有流程
