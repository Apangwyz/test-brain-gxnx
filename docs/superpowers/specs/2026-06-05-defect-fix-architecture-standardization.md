# TestBrain 缺陷修复与架构规范化

> 日期：2026-06-05
> 状态：已实施
> 版本：v1.0

---

## 1. 概述

### 1.1 背景

在 TestBrain 既有功能增强过程中，代码审查发现 **15 项问题**，涵盖阻断性 Bug、安全缺陷、架构不一致和功能残缺四大类。这些问题影响核心功能的可用性、系统的安全性和代码的可维护性。

### 1.2 修复范围

| 工作包 | 数量 | 类型 |
|--------|------|------|
| 工作包A — 阻断性Bug修复 | 4 | P0 阻断 |
| 工作包B — 安全与架构规范 | 4 | P1 安全/架构 |
| 工作包C — 功能补全与清理 | 6 | P2/P3 功能/清理 |

### 1.3 设计原则

- **最小侵入**：在现有代码基础上精确修复，不改动核心架构
- **渐进兼容**：旧接口标记废弃保留，新代码使用统一接口
- **安全优先**：CSRF 保护不可绕过，凭据不硬编码
- **测试可验证**：每项修复可通过独立测试脚本验证

---

## 2. 工作包A：阻断性Bug修复

### A1: PRD分析路径穿越检查反转

**问题：** `apps/ai_agents/prd_analyzer/views.py:246` 中的路径安全检查 `if '/' in file_path` 会导致所有合法文件路径被拒绝，因为服务端返回的 `file_path` 如 `prd/req_xxx.md` 必然包含斜杠。

**修复：** 改用白名单路径校验，将 `file_path` 解析为绝对路径后，检查是否在 `prd/` 或 `uploads/` 目录下：

```python
allowed_dirs = [os.path.abspath('prd'), os.path.abspath('uploads')]
resolved_path = os.path.abspath(file_path)
if not any(os.path.commonpath([resolved_path, d]) == d for d in allowed_dirs):
    return JsonResponse({'success': False, 'error': '非法文件路径'})
```

### A2: Java源码分析配置为空

**问题：** `PROJECT_ID_REPO_MAPPING = {}` 且 `GIT_CREDENTIALS` 硬编码为空字典，导致 Java 源码分析功能无法连接任何仓库。

**修复：** 
- `GIT_CREDENTIALS` 改为从环境变量 `GIT_TOKEN` / `GIT_USERNAME` + `GIT_PASSWORD` 读取
- `PROJECT_ID_REPO_MAPPING` 支持从 `JAVA_REPO_MAPPING_FILE` 环境变量指定的外部 JSON 文件加载
- `apps.py` 中已有空映射的优雅处理，启动时打印 INFO 日志而非崩溃

### A3: SECRET_KEY 缺失保护

**问题：** `SECRET_KEY = os.environ.get('SECRET_KEY')` 无校验，环境变量未设置时 Django 启动失败但无明确错误信息。

**修复：** 添加启动时校验：

```python
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY 环境变量未设置！请设置 SECRET_KEY 环境变量后再启动。')
```

### A4: Embedding 启动崩溃

**问题：** 当 `EMBEDDING_PROVIDER=aliyun` 但 `QWEN_API_KEY` 未设置时，`AliyunEmbedder.__init__` 抛出 `ValueError`，导致整个应用启动失败。

**修复：** 在 `create_embedder()` 中捕获 `ValueError`，自动降级到本地 BGE-M3 模型并打印 Warning 日志。

---

## 3. 工作包B：安全与架构规范

### B1: 统一认证策略重构

**问题：** `api_key_or_csrf_exempt` 装饰器对所有 POST 请求免除 CSRF 保护，浏览器用户也可绕过 API Key 校验。

**修复：** 新增 `session_or_apikey_auth` 装饰器，实现双层策略：

| 认证方式 | CSRF 保护 | 适用场景 |
|---------|-----------|---------|
| Django session 登录 | 启用（标准 CSRF Token） | 浏览器前端操作 |
| X-API-Key 请求头 | 跳过 | 外部工具/脚本调用 |
| 均不通过 | 返回 401 | 未授权访问 |

旧装饰器 `api_key_or_csrf_exempt` 保留为向后兼容的别名。

### B2: LLM 配置中心化

**问题：** 各 Agent 模块（prd_analyzer、iface_case_generator、java_code_analyzer 等）各自用不同方式读取 `LLM_PROVIDERS` 和 `AGENT_LLM_DEFAULTS`，配置修改需同步多处。

**修复：** 新增 `apps/llm/config_manager.py`，提供统一接口：

- `get_llm_config(agent_name)` → 返回 `(provider, providers_dict)`
- `get_provider_config(agent_name)` → 返回该 Agent 的完整配置字典
- `get_agent_llm_configs(agent_name)` → 兼容旧接口

所有 Agent 模块的 `llm_config = getattr(settings, ...)` 冗余代码已清理。

### B3: 统一进度管理

**问题：** 两套进度管理系统并存（旧 `TaskProgressManager` + 新 `StageProgressManager`）。

**修复：** 
- `TaskProgressManager` 添加废弃标记，新代码应直接使用 `apps.utils.progress_registry`
- `test_case_generator` 已使用新系统（`StageProgressManager`）
- `prd_analyzer` 和 `java_code_analyzer` 的迁移留待后续功能增强阶段

### B4: 双重 login_required

**问题：** `apps/core/knowledge_views.py` 中 `knowledge_view` 函数上堆叠了两个 `@login_required` 装饰器。

**修复：** 删除重复的装饰器行。

---

## 4. 工作包C：功能补全与清理

### C1: PRD → 用例联动补齐

**问题：** `prd_to_testcase_api` 仅生成一个 uuid 作为 task_id 返回，从未触发实际的测试用例生成流程。

**修复：** 接收 PRD 分析结果的测试点数据 → 合并为需求描述 → 通过 `submit_generation_task` 投递到 `test_case_generator` 线程池 → 返回真实 task_id 供前端轮询。

### C2: created_by 用户归属修复

**问题：** 保存测试用例时 `created_by=request.user` 被注释，导致所有用例的创建者为空。

**修复：** 取消注释，增加 `request.user.is_authenticated` guard：

```python
created_by=request.user if request.user.is_authenticated else None,
```

### C3: 系统列表分页

**问题：** `GET /api/systems/` 一次性返回全部系统数据，无分页，量大时响应超时。

**修复：** 参照 `test_execution_list` 的分页实现，增加 `page` / `page_size` 参数，返回 `total` 总数。

### C4: 空壳模块处理

**问题：** `change_analyzer/` 和 `defect_analyzer/` 目录仅有 static/templates/configs 空目录，无任何 Python 代码。

**修复：** 添加 `__init__.py` + `README.md`，注明"待开发"及计划用途。

### C5: 配置清理

**问题：** `settings.py` 中残留注释掉的 deepseek 官网 base_url、冗余的多行注释。

**修复：** 移除注释掉的旧配置，精简 Hugging Face 注释。

### C6: Embedding 降级逻辑

与 A4 合并实施。

---

## 5. 文件变更清单

| 操作 | 文件 |
|------|------|
| 修改 | `apps/ai_agents/prd_analyzer/views.py` |
| 修改 | `config/settings.py` |
| 修改 | `apps/knowledge/embedding.py` |
| 修改 | `apps/utils/auth_decorators.py` |
| 修改 | `apps/core/test_execution_views.py` |
| 修改 | `apps/core/knowledge_views.py` |
| 修改 | `apps/core/system_views.py` |
| 修改 | `apps/core/views.py` |
| 修改 | `apps/utils/progress_manager.py` |
| 修改 | `apps/ai_agents/iface_case_generator/views.py` |
| 修改 | `apps/ai_agents/test_case_generator/views.py` |
| 修改 | `apps/llm/utils.py` |
| 修改 | `apps/knowledge/apps.py` |
| 新增 | `apps/llm/config_manager.py` |
| 新增 | `apps/ai_agents/change_analyzer/__init__.py` |
| 新增 | `apps/ai_agents/change_analyzer/README.md` |
| 新增 | `apps/ai_agents/defect_analyzer/__init__.py` |
| 新增 | `apps/ai_agents/defect_analyzer/README.md` |

---

## 6. 验证测试

### 6.1 静态检查

```bash
SECRET_KEY=testkey123 python manage.py check
# 预期输出: System check identified no issues (0 silenced)
```

### 6.2 认证策略验证

| 场景 | 方法 | 预期 |
|------|------|------|
| 未登录 + 无 API Key → POST | POST /api/systems/ | 401 |
| 未登录 + 有效 API Key → POST | POST + Header X-API-Key | 200 |
| 已登录 + 有 CSRF → POST | 浏览器 session + csrftoken | 200 |
| 已登录 + 无 CSRF → POST | 浏览器 session 直接 POST | 403 |

### 6.3 PRD 分析流程

- 上传 .docx 文件 → 返回 file_path
- 调用 prd_analyze_api → 返回 task_id
- 调用 prd_to_testcase_api → 返回真实 task_id，触发 test_case_generator

### 6.4 SECRET_KEY 缺失

```bash
env -u SECRET_KEY python manage.py check
# 预期: RuntimeError: SECRET_KEY 环境变量未设置！
```

---

## 7. 回退与兼容性

- `api_key_or_csrf_exempt` 保留为别名，现有外部调用不受影响
- 旧 `TaskProgressManager` 保留但标记废弃，不破坏现有调用方
- `get_agent_llm_configs` 函数保留为 `config_manager` 的委托包装
- 所有修改均为增量，无数据迁移
