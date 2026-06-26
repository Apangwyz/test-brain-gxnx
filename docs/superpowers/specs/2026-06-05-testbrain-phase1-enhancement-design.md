# TestBrain Phase 1 功能增强设计方案

> 日期：2026-06-05
> 状态：已批准
> 版本：v1.0

---

## 1. 概述

### 1.1 目标

在 TestBrain 现有架构基础上，落地 4 个功能增强点，提升 AI 测试助手的实用性和管理闭环能力：

1. **RAG 知识库增强** — AI Agent 生成时自动引用知识库内容，提高输出准确性
2. **PRD→用例一键串联** — PRD 分析结果可直接生成测试用例，消除手动搬运
3. **测试用例版本管理** — 支持用例版本保存、历史查看、diff 对比和回退
4. **测试报告自动生成** — 执行完成后自动/手动生成结构化测试报告，支持 Web 查看和 PDF 导出

### 1.2 设计原则

- **增量扩展**：不改动现有核心模块架构，在现有代码基础上做加法
- **最小侵入**：对已有 Agent 的改造限制在 prompt 组装层，不影响 LLM 调用逻辑
- **复用现有组件**：SSE 进度管理、统一进度组件等直接复用

### 1.3 架构关系

```
┌──────────────────────────────────────────────┐
│                前端页面层                       │
│  index  generate  review  prd  iface  java   │
│  knowledge  execution  system  **report**     │
└──────────┬──────────────────────┬────────────┘
           │                      │
┌──────────▼──────────────────────▼────────────┐
│            Django View / API 层              │
│  core/views  knowledge_views  system_views   │
│  test_execution_views  **report_views**     │
│  prd_analyzer/views  test_case_generator/*  │
└──────────┬──────────────────────┬────────────┘
           │                      │
┌──────────▼──────────────────────▼────────────┐
│            AI Agent / Service 层              │
│  test_case_generator  test_case_reviewer      │
│  prd_analyzer  iface_case_generator           │
│  java_code_analyzer  **KnowledgeRetriever**  │
│  **TestReportGenerator**                     │
└──────────┬──────────────────────┬────────────┘
           │                      │
┌──────────▼──────────────────────▼────────────┐
│            数据 / 基础设施层                   │
│  TestCase  TestCaseVersion(新增)             │
│  TestReport(新增)  KnowledgeBase             │
│  Milvus + BGE-M3  SQLite/MySQL              │
└──────────────────────────────────────────────┘
```

---

## 2. 模块一：RAG 知识库增强

### 2.1 数据模型

无新增数据模型。完全基于现有 `KnowledgeBase` 模型和 Milvus 向量检索能力。

### 2.2 新增组件

**`apps/knowledge/retriever.py`** — `KnowledgeRetriever` 类：

```python
class KnowledgeRetriever:
    """
    知识库检索器，为 AI Agent 提供上下文增强。
    调用方只需传入 query 文本，返回格式化的上下文字符串。
    """
    
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.vector_store = MilvusVectorStore()  # 复用现有单例
    
    def retrieve(self, query: str, system_ids: list[int] = None) -> list[dict]:
        """
        检索知识库，返回匹配结果列表。
        每条结果: {id, title, content, score}
        """
        ...
    
    def format_context(self, results: list[dict]) -> str:
        """
        将检索结果格式化为 prompt 上下文字符串。
        格式:
        【参考知识库内容】
        1. [文档标题] (相关度: 0.95)
           文档内容摘要...
        """
        ...
    
    def retrieve_and_format(self, query: str, system_ids: list[int] = None) -> str:
        """检索并格式化，一步到位"""
        results = self.retrieve(query, system_ids)
        return self.format_context(results)
```

### 2.3 Agent 改造

每个 Agent 的 `views.py` 在组装 prompt 时增加检索步骤：

| Agent | 检索 Query | 注入位置 |
|-------|-----------|---------|
| `test_case_generator` | 用户输入的「需求描述」字段 | system prompt 末尾 |
| `prd_analyzer` | 上传的 PRD 文档标题 + 内容前 200 字 | analysis prompt 末尾 |
| `iface_case_generator` | 接口名称 + 接口描述 | system prompt 末尾 |

**改造模式示例**（伪代码）：

```python
# 改造前
prompt = self.build_prompt(user_input)
response = llm.invoke(prompt)

# 改造后
retriever = KnowledgeRetriever()
context = retriever.retrieve_and_format(user_input)
prompt = self.build_prompt(user_input, context=context)
response = llm.invoke(prompt)
# 返回时携带引用来源信息
```

### 2.4 前端变更

- **`test_case_generator/templates/generate.html`**：在输入区下方增加"关联知识库文档"区域
  - 自动检索结果列表（带复选框和匹配度）
  - 「浏览知识库」和「添加更多文档」按钮
  - 展示引用来源标注

### 2.5 API 接口

| 方法 | 接口 | 说明 |
|------|------|------|
| `POST` | `/api/knowledge/retrieve/` | 检索知识库，参数：`{query, top_k, system_ids}` |
| `GET` | `/api/knowledge/list-select/` | 知识库文档列表（供手动选择） |

---

## 3. 模块二：PRD→用例一键串联

### 3.1 数据模型

无新增数据模型。

### 3.2 后端变更

**`apps/ai_agents/prd_analyzer/views.py`** 新增 API：

| 方法 | 接口 | 说明 |
|------|------|------|
| `POST` | `/prd_analyzer/api/prd-to-testcase/` | 将 PRD 分析结果传入 test_case_generator 生成用例 |

**核心逻辑**：

```python
@csrf_exempt
@require_http_methods(["POST"])
def prd_to_testcase_api(request):
    """
    接收 PRD 分析出的测试点列表，调用 test_case_generator 生成完整用例。
    """
    data = json.loads(request.body)
    test_points = data.get('test_points', [])  # 来自 PRD 分析结果
    user_notes = data.get('notes', '')
    
    # 将测试点作为 test_case_generator 的输入
    # 复用 generate_with_progress 的逻辑或直接调用其内部方法
    task_id = str(uuid.uuid4())
    # 启动异步/同步生成任务
    ...
    return JsonResponse({"task_id": task_id, "status": "started"})
```

**`apps/ai_agents/prd_analyzer/urls.py`** 新增路由：

```python
path('api/prd-to-testcase/', views.prd_to_testcase_api, name='prd_to_testcase'),
```

### 3.3 前端变更

**`prd_analyzer/templates/prd_analyzer.html`**：

- 每条测试点右侧增加「生成用例」按钮（单条）
- 顶部增加「全部生成用例」按钮（批量）
- 点击后弹出 SSE 进度窗口（复用 `common_progress.js`）
- 完成后展示生成的用例列表，提供「查看详情」和「保存到用例库」操作

---

## 4. 模块三：测试用例版本管理

### 4.1 数据模型

**`apps/core/models.py`** 新增 `TestCaseVersion` 模型：

```python
class TestCaseVersion(models.Model):
    """测试用例版本快照"""
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE,
        related_name='versions', verbose_name="所属用例"
    )
    version_number = models.IntegerField(verbose_name="版本号")
    snapshot = models.JSONField(verbose_name="版本快照")
    # 存储 {title, description, requirements, code_snippet,
    #        test_steps, expected_results, bu, feature, priority}
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
```

**`TestCase` 模型新增字段**：

```python
current_version = models.IntegerField(default=1, verbose_name="当前版本号")
```

### 4.2 API 接口

| 方法 | 接口 | 说明 |
|------|------|------|
| `POST` | `/api/testcases/<id>/save-version/` | 保存当前内容为新版本 |
| `GET` | `/api/testcases/<id>/versions/` | 版本列表 |
| `GET` | `/api/testcases/<id>/versions/<v>/` | 某版本快照详情 |
| `POST` | `/api/testcases/<id>/rollback/<v>/` | 回退到指定版本 |
| `GET` | `/api/testcases/<id>/diff/?v1=a&v2=b` | 版本对比，返回字段级差异 |

**Diff 响应格式**：

```json
{
  "diffs": [
    {"field": "test_steps", "label": "测试步骤",
     "old": "步骤1...", "new": "步骤1(修改)...",
     "type": "modified"},
    {"field": "priority", "label": "优先级",
     "old": "P1", "new": "P0",
     "type": "modified"}
  ]
}
```

`type` 取值：`added`（新增）、`removed`（删除）、`modified`（修改）

### 4.3 前端变更

- **用例详情/编辑页**：新增版本管理区域
  - 版本历史列表（时间线样式）
  - 「保存为新版本」按钮
  - 版本对比弹窗或半屏视图
  - 颜色规则：绿色=新增，红色=删除，黄色=修改

---

## 5. 模块四：测试报告自动生成

### 5.1 数据模型

**`apps/core/models.py`** 新增 `TestReport` 模型：

```python
class TestReport(models.Model):
    """测试报告"""
    title = models.CharField(max_length=200, verbose_name="报告标题")
    batch = models.ForeignKey(
        TestExecutionBatch, on_delete=models.CASCADE,
        related_name='reports', verbose_name="关联执行批次",
        null=True, blank=True
    )
    system = models.ForeignKey(
        System, on_delete=models.SET_NULL,
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
```

**`report_data` 结构**：

```json
{
  "execution_summary": {
    "total": 120, "passed": 98, "failed": 12,
    "skipped": 8, "error": 2,
    "pass_rate": 81.67, "total_duration": 3600.5
  },
  "by_priority": {
    "p0": {"total": 20, "passed": 18, "failed": 2},
    "p1": {"total": 40, "passed": 35, "failed": 3}
  },
  "failed_details": [
    {"case_id": 1, "title": "...", "priority": "P0",
     "error": "...", "suggestion": "..."}
  ],
  "ai_analysis": {
    "risk_level": "medium",
    "risk_areas": [],
    "improvement_suggestions": []
  }
}
```

### 5.2 后端变更

**新增文件** `apps/core/report_views.py`（或并入 `apps/core/views.py`），提供：

| 方法 | 接口 | 说明 |
|------|------|------|
| `GET` | `/api/reports/` | 报告列表 |
| `GET` | `/api/reports/<id>/` | 报告详情 |
| `POST` | `/api/reports/generate/` | 生成报告，参数 `{batch_id}` |
| `POST` | `/api/reports/<id>/export-pdf/` | 导出 PDF |
| `DELETE` | `/api/reports/<id>/` | 删除报告 |

**生成核心逻辑**：

```python
class TestReportGenerator:
    """测试报告生成器"""
    
    def generate(self, batch: TestExecutionBatch) -> TestReport:
        # 1. 收集执行数据
        records = TestExecutionRecord.objects.filter(
            test_case__in=batch.test_cases.all()
        )
        # 2. 计算统计指标
        summary = self._compute_summary(records)
        # 3. 调用 LLM 生成 AI 分析
        ai_analysis = self._ai_analyze(summary, records)
        # 4. 组装 report_data
        report_data = {**summary, "ai_analysis": ai_analysis}
        # 5. 保存并返回
        return TestReport.objects.create(...)
```

**PDF 导出**：使用 `weasyprint`，将 Django HTML 模板渲染后导出。

### 5.3 前端变更

- **导航栏**：`base.html` 侧边栏新增「测试报告」入口
- **报告列表页** `/templates/report_list.html`：卡片式布局，显示报告标题、生成时间、关联系统
- **报告详情页** `/templates/report_detail.html`：
  - 执行概览进度条
  - 按优先级统计表格
  - 失败用例详情列表
  - AI 分析建议区块
  - 「导出 PDF」「打印」操作按钮

### 5.4 新增依赖

```txt
# requirements.txt
weasyprint>=62.0
```

---

## 6. 完整文件变更清单

| 操作 | 文件路径 |
|------|---------|
| 新增 | `apps/knowledge/retriever.py` |
| 新增 | `apps/core/report_views.py`（或 report_generator.py） |
| 新增 | `templates/report_list.html` |
| 新增 | `templates/report_detail.html` |
| 新增 | `templates/testcase_version_diff.html`（或组件） |
| 修改 | `apps/core/models.py` — 新增 TestCaseVersion、TestReport；TestCase 加 current_version |
| 修改 | `apps/core/urls.py` — 新增版本管理和报告路由 |
| 修改 | `apps/core/views.py` — 新增版本管理视图 |
| 修改 | `apps/ai_agents/prd_analyzer/views.py` — 新增 prd_to_testcase_api |
| 修改 | `apps/ai_agents/prd_analyzer/urls.py` — 新增路由 |
| 修改 | `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html` |
| 修改 | `apps/ai_agents/test_case_generator/templates/generate.html` — 增加知识库关联区 |
| 修改 | `apps/ai_agents/test_case_generator/views.py` — RAG 注入 |
| 修改 | `apps/ai_agents/test_case_reviewer/views.py` — RAG 注入 |
| 修改 | `apps/ai_agents/iface_case_generator/views.py` — RAG 注入 |
| 修改 | `templates/base.html` — 导航栏加「测试报告」 |
| 修改 | `requirements.txt` — 加 weasyprint |

---

## 7. 回退与兼容性

- 所有新增模型使用 Django migration 正向迁移，不破坏现有表结构
- 新增 API 路由使用独立 path，不影响既有接口
- RAG 增强为可选注入：当知识库为空时，自动跳过检索步骤，prompt 退化为原始内容
- PDF 导出使用独立依赖 weasyprint，不影响现有功能

---

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 知识库冷启动（无内容可检索） | 空结果时自动跳过 RAG 注入，不影响正常生成流程 |
| weasyprint 系统依赖问题 | 在 Docker 或 CI 环境提前安装系统库(libpango, libcairo) |
| 版本管理数据量增长 | 版本快照存储在 SQLite/MySQL 中，单条用例版本数建议上限 50 个 |
| PRD→用例串联中的 LLM 上下文超长 | 控制 RAG 注入的内容长度，超出 token 限制时截断或降级 |

---

## 9. 补充说明（自审修正）

### 9.1 PRD→用例串联：生成策略

- 每条测试点独立生成一个测试用例，而非合并成一个
- 「全部生成用例」批量提交所有测试点，并行/串行逐个生成
- 生成出的用例默认状态为 `pending`（待评审）

### 9.2 版本管理：保存与回退机制

- **保存版本**：用户点击「保存为新版本」时弹出对话框，输入变更摘要（可选），确认后创建新版本
- **回退**：回退到历史版本时，**不删除**当前版本，而是以目标版本内容创建**新版本**（版本号+1），保证历史链完整

### 9.3 RAG 知识库：检索范围

- 当 `system_ids` 为空时，检索全部知识库
- 当知识库中无匹配内容时（`results` 为空），`format_context` 返回空字符串，prompt 不注入任何上下文
- 前端展示「自动检索」和「手动追加」两个区域，互不冲突

### 9.4 测试报告：生成时机

- 执行批次完成时自动触发生成（通过信号或批次状态变更后检查）
- 同时支持用户在批次详情页手动点击「生成报告」
- 同一批次可生成多份报告（如在不同时间点做对比）

### 9.5 新增依赖

- `weasyprint>=62.0`：用于 PDF 导出
- 需在系统环境安装：`libpango-1.0-0`, `libharfbuzz0b`, `libcairo2`（Linux）或 `pango`, `cairo`（macOS via brew）
