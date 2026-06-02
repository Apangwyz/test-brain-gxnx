# 改进重构报告

**日期:** 2026-06-02
**范围:** P0 安全修复、P1 代码质量改进
**修改文件:** 12 个文件（新增 1 个，修改 11 个）

---

## 概述

本次重构基于代码扫描分析发现的 P0/P1 待改进项，对项目进行了以下方面的优化：
1. 进度跟踪系统去重（P0.2）
2. JSON 提取可靠性提升（P1.3）
3. API 端点安全加固（P1.1）
4. 已验证已有的修复（P0.1、P1.2、P1.4）

---

## 已验证（无需修改）

以下问题在本次扫描时发现已在之前的修改中解决：

| 问题 | 当前状态 |
|------|----------|
| **P0.1: API Key 硬编码** | `.env` 文件已加入 `.gitignore`，`settings.py` 中无默认值，仅从环境变量读取 |
| **P1.2: 巨型视图文件** | `apps/core/views.py` 已拆分为 `knowledge_views.py`（317行）、`system_views.py`（718行）、`test_execution_views.py`（351行），核心视图仅61行 |
| **P1.4: Milvus 连接逻辑** | `apps/knowledge/apps.py` 和 `apps/knowledge/vector_store.py` 均已检查 `ENABLE_MILVUS` 配置，禁用时不连接 |

---

## 修改详情

### P0.2a: 统一 `test_case_generator/progress_manager.py`（兼容层重构）

**文件:** `apps/ai_agents/test_case_generator/progress_manager.py`

**变更：**
- 将 `ProgressManager` 类重命名为 `StageProgressManager`，内部方法现在通过 `set_progress()` 同步到中心注册表（`apps.utils.progress_registry`）
- 移除独立的 `_callbacks` 回调机制（已被中心注册表替代）
- 添加 `_sync_to_registry()` 方法，在每个阶段状态变化时同步进度
- `__init__` 要求显式传入 `task_id`，避免自动生成导致的 ID 碎片
- 新增 `_clear_on_error()` 辅助函数，错误后 30 秒自动清理进度
- `remove_progress_manager()` 现在同时清理本地字典和中心注册表
- 保留 `ProgressManager` 别名以确保向后兼容

**收益：** 测试用例生成任务的进度数据现在统一写入中心注册表，确保 `sse_bus.py` 和 `views_sse.py` 的日志流可以捕获所有任务进度。

### P0.2b: 统一 `utils/progress_manager.py`（兼容层重构）

**文件:** `apps/utils/progress_manager.py`

**变更：**
- `GlobalProgressRegistry` 的方法现在通过 `progress_registry.set_progress()` 同步到中心注册表
- `register_task()`、`update_stage()`、`set_status()` 等方法在操作本地状态后写入中心注册表
- `remove_task()` 现在调用 `clear_progress()` 清理中心注册表
- 添加了详细的模块文档字符串说明委托关系

**收益：** `prd_analyzer` 和 `java_code_analyzer` 的 `TaskProgressManager` 进度数据也统一写入中心注册表。

### P1.3: 改进 JSON 提取为 Pydantic 结构化解析

**新增文件:** `apps/ai_agents/test_case_generator/test_case_schema.py`

**变更：**
- 创建了 `test_case_schema.py`，包含：
  - `GeneratedTestCase` Pydantic 模型（带字段级别校验）
  - `clean_json_fence()` — 清理 LLM 输出中的代码块标记
  - `extract_json_str()` — 改进的 JSON 提取（支持 6 种格式）

**修改文件:** `apps/ai_agents/test_case_generator/generator.py`

**变更：**
- `_extract_json_from_response()` 方法不再使用脆弱的正则/截断方式，而是委托给 `extract_json_str()`
- `_validate_test_cases()` 新增 Pydantic 模型校验分支，提供字段级别的类型验证

**JSON 提取支持的格式：**
1. 代码块 ` ```json [...] ``` `
2. 无语言标记 ` ``` [...] ``` `
3. 独立 JSON 数组 `[...]`
4. 包含 `test_cases` 键的对象 `{"test_cases": [...]}`
5. 通过 `}` 补全 `]` 修复截断数组
6. 通过 `},` 补全 `]` 修复截断数组（保守方案）

### P1.1: API 端点安全加固

**文件:** `apps/core/views_sse.py`
- 移除了 GET-only SSE 端点上的冗余 `@csrf_exempt`

**文件:** `apps/core/knowledge_views.py`
- 添加了 `login_required` import（为后续启用认证做准备）

**文件:** `apps/ai_agents/test_case_reviewer/views.py`
- 添加了 `login_required` import（为后续启用认证做准备）

---

## 测试结果

执行了 8 组自动化测试，涵盖核心进度跟踪、JSON 提取、模块导入和进度管理器同步。全部通过。

详细测试报告见 `docs/changes/2026-06-02_improvement-refactoring/TEST_REPORT.md`。

---

## 后续建议

| 优先级 | 建议 | 说明 |
|--------|------|------|
| P1 | 完成 `@login_required` 的全量部署 | 需要配合前端登录页面和 CSRF Token 机制 |
| P2 | 为 `GlobalProgressRegistry` 设置废弃警告 | 引导新代码直接使用 `progress_registry` |
| P2 | 统一 SSE 端点为 `views_sse.py` 的实现 | `utils/progress_manager.py` 中的端点功能重叠 |

---

## P1.1 实施详情（本次新增）

### 1. 登录基础设施

**文件:** `config/settings.py`, `config/urls.py`, `templates/registration/login.html`

**变更：**
- `settings.py` 新增认证配置：
  - `LOGIN_URL = '/accounts/login/'`
  - `LOGIN_REDIRECT_URL = '/'`
  - `LOGOUT_REDIRECT_URL = '/accounts/login/'`
  - `API_KEY` 从环境变量读取，用于外部工具 API 认证
- `urls.py` 新增 `path('accounts/', include('django.contrib.auth.urls'))` — Django 内置的 login/logout 视图
- 新增 `templates/registration/login.html` — Bootstrap 风格登录页面

### 2. API Key 认证装饰器

**新增文件:** `apps/utils/auth_decorators.py`

提供两个装饰器：
- **`@api_key_required`** — 检查 `X-API-Key` 请求头或用户 session 登录状态。用于 GET API 端点。
- **`@api_key_or_csrf_exempt`** — 组合装饰器：先 CSRF 豁免 + 再 API Key 认证。用于外部工具调用的 POST/PUT/DELETE 端点。

### 3. 页面视图认证

为以下页面视图添加 `@login_required`：
- `apps/core/knowledge_views.py:knowledge_view`
- `apps/ai_agents/test_case_reviewer/views.py:review_view`
- `apps/ai_agents/test_case_reviewer/views.py:case_review_detail`
- `apps/core/system_views.py:system_management`
- `apps/core/test_execution_views.py:test_execution_view`

### 4. @csrf_exempt 清理

| 文件 | 之前 | 之后 |
|------|------|------|
| `system_views.py` | 10 处 | 0 处 |
| `test_execution_views.py` | 5 处 | 0 处 |
| `test_case_generator/views.py` | 3 处 | 0 处 |
| `utils/progress_manager.py` | 3 处 | 0 处 |
| `views_sse.py` | 1 处 | 0 处 |
| `prd_analyzer/views.py` | 2 处 | 0 处 |
| `knowledge_views.py` | 1 处 | 0 处（保留） |
| **合计** | **25 处** | **1 处**（文件上传） |

### 修改文件清单（本轮）

| 文件 | 变更类型 |
|------|---------|
| `config/settings.py` | 修改 — 新增认证/API Key 配置 |
| `config/urls.py` | 修改 — 新增 accounts 路由 |
| `templates/registration/login.html` | **新增** — 登录页面 |
| `apps/utils/auth_decorators.py` | **新增** — API Key 认证装饰器 |
| `apps/core/views_sse.py` | 修改 — 移除冗余 @csrf_exempt |
| `apps/core/knowledge_views.py` | 修改 — 添加 @login_required + @api_key_required |
| `apps/core/system_views.py` | 修改 — 替换 @csrf_exempt 为 API Key 认证 |
| `apps/core/test_execution_views.py` | 修改 — 替换 @csrf_exempt 为 API Key 认证 |
| `apps/ai_agents/test_case_generator/views.py` | 修改 — 替换 @csrf_exempt 为 API Key 认证 |
| `apps/ai_agents/test_case_reviewer/views.py` | 修改 — 添加 @login_required |
| `apps/ai_agents/prd_analyzer/views.py` | 修改 — 替换 @csrf_exempt 为 API Key 认证 |
| `apps/utils/progress_manager.py` | 修改 — 替换 @csrf_exempt 为 API Key 认证 |
