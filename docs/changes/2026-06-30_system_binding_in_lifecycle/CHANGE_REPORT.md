# 需求文档与测试用例全生命周期归属系统绑定 — 修改报告

> **日期**: 2026-06-30
> **对应测试报告**: `docs/test_reports/2026-06-30-system-lifecycle-binding-test-report.md`

---

## 一、修改背景

需求文档从分析到采纳，再到从需求文档生成测试用例，此前没有绑定归属系统。本次修改基于现有的系统归属模块（System 模型），将需求文档与测试用例与归属系统进行绑定。

**全生命周期关联**：上传 → 分析 → 采纳 → 生成测试用例，每个环节的数据都与系统绑定。

---

## 二、修改文件清单

### 2.1 后端 — 数据模型

| 文件 | 修改内容 |
|------|---------|
| `apps/core/models.py` | `RequirementAnalysis` 新增 `system = ForeignKey(System, null=True, on_delete=SET_NULL)` |

### 2.2 后端 — API 视图

| 文件 | 修改内容 |
|------|---------|
| `apps/ai_agents/requirement_analyzer/views.py` | `analyze_api` 从请求接收 `system_id`；`adopted_docs_api` 返回 `system_id`/`system_name`；`generate_from_analysis_api` 透传 `analysis.system_id` |
| `apps/ai_agents/requirement_analyzer/orchestrator.py` | `analyze()` 方法创建 `RequirementAnalysis` 时写入 `system_id`（**Bugfix**） |
| `apps/ai_agents/test_case_generator/views.py` | `save_test_case` 从请求接收 `system_id` 并写入 `TestCase.system`；`_generate_test_cases_async` 支持 `system_id` 透传 |
| `apps/ai_agents/test_case_generator/task_executor.py` | `submit_generation_task` 新增 `system_id` 参数 |

### 2.3 前端 — 模板

| 文件 | 修改内容 |
|------|---------|
| `apps/ai_agents/requirement_analyzer/templates/requirement_analysis.html` | 上传区新增"选择所属系统 *"下拉框 |
| `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html` | 上传区新增"选择所属系统 *"下拉框 |

### 2.4 前端 — JavaScript

| 文件 | 修改内容 |
|------|---------|
| `apps/ai_agents/requirement_analyzer/static/requirement_analysis.js` | `uploadAndAnalyze()` 传递 `system_id`；已采纳文档列表展示系统信息 |
| `apps/ai_agents/prd_analyzer/static/prd_analyzer.js` | `analyzePRD()` 传递 `system_id`；`loadPrdSystems()` 加载系统列表 |
| `apps/ai_agents/test_case_generator/static/generate.js` | 已采纳文档加载时展示 `system_name`；同系统文档自动选中系统下拉框 |

### 2.5 数据迁移

| 文件 | 说明 |
|------|------|
| `apps/core/migrations/0008_requirementanalysis_system.py` | 新增 `system` 字段，`null=True`，兼容存量数据 |

---

## 三、数据流图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      全生命周期系统绑定流程                            │
└─────────────────────────────────────────────────────────────────────┘

 1. 上传文档 + 选择系统
    ┌──────────────┐     POST /requirement_analysis/api/analyze/
    │  前端页面     │ ── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
    │ system_id=3  │                                                ▼
    └──────────────┘                               ┌──────────────────────┐
                                                   │  orchestrator.analyze │
 2. 分析结果存入                                    │  (system_id=3)        │
    ┌────────────────────┐                          └──────────────────────┘
    │ RequirementAnalysis │ ◄─────── 创建 ───────────────┘
    │ system_id = 3      │
    │ adopted = True     │
    └────────┬───────────┘
             │
 3. 采纳后     │  GET /requirement_analysis/api/adopted-docs/
             │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
             ▼                                  ▼
    ┌────────────────┐          ┌──────────────────────────┐
    │ adopted_docs   │          │ 返回 { system_id: 3,     │
    │ API            │          │       system_name: "用户 │
    └────────────────┘          │        管理系统", ... }  │
                                └──────────────────────────┘
             │
 4. 生成测试用例  │  POST /requirement_analysis/api/generate/
             │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
             ▼                                  ▼
    ┌────────────────────┐     ┌──────────────────────────────┐
    │ submit_generation_ │     │ _generate_test_cases_async   │
    │ task(system_id=3)  │ ──► │ (system_id=3)                │
    └────────────────────┘     └──────────┬───────────────────┘
                                          │
 5. 保存测试用例              ┌────────────▼────────────┐
                             │  TestCase.bulk_create(   │
                             │    system_id=3, ...)     │
                             └─────────────────────────┘
```

---

## 四、新增功能说明

### 4.1 模型字段

```python
# apps/core/models.py
class RequirementAnalysis(models.Model):
    # ... 已有字段 ...
    system = models.ForeignKey(
        System,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属系统",
        help_text="关联的系统归属",
    )
```

- `null=True`：存量数据兼容，已有分析记录 system 为 null
- `on_delete=SET_NULL`：系统被删除后分析记录不丢失，system 置空

### 4.2 API 变更

| API | 变更类型 | 说明 |
|-----|---------|------|
| `POST /api/systems/` | 已有 | 返回 `status='active'` 的系统列表 |
| `POST /requirement_analysis/api/analyze/` | 入参扩展 | 新增 `system_id`（integer, optional） |
| `GET /requirement_analysis/api/result/<id>/` | 出参扩展 | 新增 `system_id`、`system_name` |
| `GET /requirement_analysis/api/adopted-docs/` | 出参扩展 | 新增 `system_id`、`system_name` |
| `POST /test_case_generator/save-test-cases/` | 入参扩展 | 新增 `system_id`（integer, optional） |

### 4.3 前端交互变更

- **需求分析页**：上传文档前必须先选择系统（前端校验）
- **PRD 分析页**：开始分析前必须先选择系统
- **测试用例生成页**：从已采纳文档填充时，如果所选文档属于同一系统，自动选中系统下拉框

---

## 五、数据迁移说明

### 迁移文件

`apps/core/migrations/0008_requirementanalysis_system.py`

### 迁移命令

```bash
python manage.py migrate core
```

### 注意事项

- 迁移为 `nullable` 外键，**不会修改存量数据**
- 存量 5 条 RequirementAnalysis 记录的 `system_id` 为 null
- 选择器仅展示 `status='active'` 的系统（目前 5 个系统均为 active）
- `on_delete=SET_NULL`：系统删除后关联记录不断链

---

## 六、部署注意事项

1. **应用迁移**：部署后需执行 `python manage.py migrate` 使新字段生效
2. **缓存**：前端页面涉及 JS 更新，建议通知用户强制刷新（`Cmd+Shift+R`）
3. **API 兼容性**：前后端均为非破坏性扩展（新增可选字段），旧请求不受影响
4. **测试覆盖**：60 个存量测试全部通过，无回归风险
5. **已修复缺陷**：`orchestrator.analyze()` 接收 system_id 但未写入模型的 bug 已修复

---

## 七、回滚方案

如需回滚本次修改：

```bash
# 1. 回滚迁移
python manage.py migrate core 0007

# 2. 恢复代码修改（通过 git）
git checkout -- apps/core/models.py
git checkout -- apps/ai_agents/requirement_analyzer/
git checkout -- apps/ai_agents/test_case_generator/
git checkout -- apps/ai_agents/prd_analyzer/
```

> **注意**：回滚后已写入的 `system_id` 数据将丢失（迁移回滚会删除该列），建议回滚前备份数据。
