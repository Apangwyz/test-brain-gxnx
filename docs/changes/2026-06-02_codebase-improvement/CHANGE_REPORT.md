# 代码库改进报告

**日期：** 2026-06-02  
**范围：** P0 安全修复 + P1 架构改进  
**验证状态：** Django system check 通过（0 silenced），所有模块导入成功

---

## 改进清单

### P0-1: 移除硬编码密钥（安全修复）

**问题：** `config/settings.py` 中包含：
- 阿里云 API Key 的明文默认值 `sk-7a0c2f...`
- `SECRET_KEY` 的不安全后备值
- `ALLOWED_HOSTS` 默认包含 `0.0.0.0`

**修复：**
- 移除 `ALIYUN_EMBEDDING_CONFIG['api_key']` 的硬编码默认值，仅从环境变量 `QWEN_API_KEY` 读取
- `SECRET_KEY` 不再有不安全后备值，必须通过环境变量配置
- `ALLOWED_HOSTS` 默认值收紧为 `['localhost', '127.0.0.1']`

### P0-2: 统一进度跟踪系统

**问题：** 存在三套并行的进度跟踪实现（dataclass 版、Pydantic 版、独立版），功能重复且数据格式不兼容。

**修复：**
- `apps/utils/progress_manager.py` → 重写为兼容层，底层委托给 `progress_schema.py` + `progress_registry.py`
- `apps/ai_agents/test_case_generator/progress_manager.py` → 重写为兼容层，底层委托给 `apps.utils.progress_schema`
- 规范化的核心模块（`progress_schema.py`、`progress_registry.py`、`sse_bus.py`）作为单一日志规范

### P1-1: 修复 Milvus 连接逻辑

**问题：** `settings.py` 中 `ENABLE_MILVUS = False`，但 `MilvusVectorStore.__init__` 始终连接 Milvus。

**修复：**
- `vector_store.py`：`__init__` 检查 `settings.ENABLE_MILVUS`，仅当为 `True` 时连接；新增 `is_available()` 方法；所有 public 方法添加 `_enabled` 卫语句
- `apps.py`：`KnowledgeConfig.ready()` 在创建 `MilvusVectorStore` 前检查 `ENABLE_MILVUS`

### P1-2: 拆分巨型视图文件

**问题：** `apps/core/views.py` 超过 1400 行。

**修复：** 拆分为 4 个模块：

| 模块 | 行数 | 功能 |
|------|------|------|
| `views.py` | 57 | 首页仪表盘 |
| `knowledge_views.py` | 313 | 知识库管理 + 文件上传 |
| `system_views.py` | 714 | 系统管理 + 测试计划 + 需求文档 |
| `test_execution_views.py` | 347 | 测试执行 + 统计 + 导出 |

### P1-3: 健壮的 JSON 提取

**问题：** `_extract_json_from_response` 只处理简单模式，遇到嵌套对象和代码块失败。

**修复：** 重写为支持：```json 代码块提取、嵌套括号匹配、尾随逗号和未加引号属性的 JSON 修复。

### P1-4: 恢复端点认证

**问题：** 所有页面视图的 `@login_required` 被注释，API 端点大量 `@csrf_exempt`。

**修复：** 为 8 个视图函数恢复 `@login_required`；settings.py 新增 `LOGIN_URL` 和 `LOGIN_REDIRECT_URL`。

---

## 验证结果

```
DJANGO_SETTINGS_MODULE=config.settings django-admin check
→ System check identified no issues (0 silenced).
```

### 关键配置验证

| 配置项 | 修改前 | 修改后 | 状态 |
|--------|--------|--------|------|
| `SECRET_KEY` 默认值 | 不安全后备值 | 无默认值，必须环境变量 | ✅ |
| `ALLOWED_HOSTS` | 含 `0.0.0.0` | 仅 `localhost`、`127.0.0.1` | ✅ |
| `ALIYUN_API_KEY` | 明文硬编码 | 仅从 `QWEN_API_KEY` 环境变量 | ✅ |
| `ENABLE_MILVUS` | False（但代码忽略） | False（代码实际检查） | ✅ |
| 首页路由 `/` | 1400 行单文件 | 57 行 + 3 个子模块 | ✅ |
| 进度跟踪 | 3 套重复实现 | 1 套规范 + 2 个兼容层 | ✅ |
| 页面认证 | `# @login_required` | 激活的 `@login_required` | ✅ |

---

## 后续建议（P2）

1. **单元测试覆盖** — 为核心 Agent 逻辑（generator、reviewer、analyser）编写 pytest 测试
2. **SSE 端点收敛** — 合并 `views_sse.py` 的 `stream_logs` 与 `progress_manager.py` 的 `sse_progress_stream`
3. **统一线程池** — 集中管理 `task_executor.py` 和 `iface_case_generator` 的线程池
4. **废弃代码清理** — 使用 `vulture` 清理全文注释掉的 import 和遗留代码
