# TestBrain

> 基于大语言模型的智能测试平台，聚焦手工&接口测试用例生成、评审与知识复用、java源码分析，帮助测试团队打造高效、可扩展的“AI 测试助手”。

## 🧭 项目概览

TestBrain 通过 Django + LangChain + 多模型接入的方式，提供以下核心能力：

- **多 Agent 协同**：针对不同测试场景提供专用智能体（测试用例生成、评审、PRD 分析、接口用例生成、Java 代码分析等）。
- **多 LLM 供应商**：支持 DeepSeek、Qwen 等模型，并可按 Agent 维度配置默认模型/参数，前端也可手动切换。
- **Provider 降级容错**：支持按优先级配置 Provider 列表，当首选 Provider 调用失败时自动降级到下一个可用 Provider，提升系统可用性。
- **知识库加持**：集成 Milvus 向量数据库与 BGEM3 Embedding，支持文档解析、入库、向量检索与上下文增强。
- **可扩展架构**：模块化的 LLM 工厂、Agent 封装、知识库服务，便于新增模型、Agent 或自定义流程。

## 🛠️ 功能模块

| 模块 | 功能 | 关键实现 |
| --- | --- | --- |
| **AI Agents** | - `test_case_generator`：根据需求生成用例（支持同步/异步调用 LLM）<br>- `test_case_reviewer`：对生成的用例进行评审与打分<br>- `prd_analyzer`：解析 PRD，提炼测试点/场景（内置 JSON 修复兜底）<br>- `iface_case_generator`：基于接口描述生成测试用例<br>- `java_code_analyzer`：分析 Java 代码并梳理潜在测试点 | `apps/ai_agents/*`，配合统一的 Prompt 管理与服务调用 |
| **LLM 集成** | - `LLMServiceFactory` 动态创建模型客户端<br>- `get_agent_llm_configs()` 返回 Agent 默认模型与 Provider 列表<br>- 支持同步 `invoke` 与异步 `ainvoke`<br>- `FallbackLLMWrapper` 按优先级自动降级<br>- `LLMProviderPriorityManager` 配置驱动优先级 | `apps/llm/base.py` / `apps/llm/config_manager.py` |
| **知识库** | - `KnowledgeConfig.ready()` 预热 Milvus + BGEM3 单例<br>- `KnowledgeService` 封装向量入库、检索、相似度匹配<br>- 支持多格式文档解析、批量嵌入与检索 | `apps/knowledge/*` |
| **核心应用** | - Web 页面与 API（Django View）<br>- 用例管理（`TestCase` 模型）<br>- 配置管理、日志、权限预留 | `apps/core/*` |

## 🏗️ 技术栈 & 服务依赖

- **运行框架**：Python 3.12、Django 5.1.6、LangChain
- **向量数据库**：Milvus 2.4.x（需先启动 Milvus 服务）
- **Embedding 模型**：`BAAI/bge-m3`（通过 `sentence-transformers`，首启由 `KnowledgeConfig` 预热）
- **数据库**：MySQL 8.x（默认使用 `mysqlclient`）
- **其他依赖**：Celery、Redis（如需异步任务，可在后续扩展）


## 📁 项目结构

```
TestBrain/
├── apps/
│   ├── ai_agents/            # 各类智能体实现
│   │   ├── test_case_generator/
│   │   ├── test_case_reviewer/
│   │   ├── prd_analyzer/
│   │   ├── iface_case_generator/
│   │   └── java_code_analyzer/
│   ├── core/                 # 公共视图、模型、页面
│   ├── knowledge/            # Milvus & Embedding 服务
│   └── llm/                  # LLM 工厂、Provider 定义
├── config/                   # Django 配置（INSTALLED_APPS、数据库、LLM 设置等）
├── templates/                # 页面模板
├── static/                   # 静态资源
├── videos/                   # 功能演示视频
├── requirements.txt          # 依赖列表
└── manage.py
```

## ⚙️ 配置说明

### 1. 环境变量（`.env` 模板）

```dotenv
# LLM Keys
DEEPSEEK_API_KEY=your_key
QWEN_API_KEY=your_key

# LLM Provider 优先级（按优先级降级，逗号分隔）
# 当首选 Provider 调用失败时，自动按此列表顺序降级
# 可选：按 Agent 覆盖优先级（AGENT_PRIORITY__{agent_name}）
LLM_PROVIDER_PRIORITY=qwen,deepseek
# AGENT_PRIORITY__requirement_analyzer=deepseek,qwen

# 数据库
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=testbrain

# 向量数据库
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION=vv_knowledge_collection
```

### 2. LLM Provider 配置

`config/settings.py` 中维护：

```python
LLM_PROVIDERS = {
    "default_provider": "deepseek",
    "deepseek": {...},
    "qwen": {...}
}

AGENT_LLM_DEFAULTS = {
    "test_case_generator": {"provider": "deepseek"},
    "prd_analyzer": {"provider": "deepseek"},
    ...
}

# Provider 优先级配置（降级容错）
# 当首选 Provider 调用失败时，按此列表顺序自动降级
# 环境变量可覆盖此配置
LLM_PROVIDER_PRIORITY = {
    "default": ["qwen", "deepseek"],
    "requirement_analyzer": ["deepseek", "qwen"],
}
```

- 前端使用 `providers` 渲染下拉列表，可手动切换模型。
- 后端通过 `get_agent_llm_configs(agent_name)` 获取默认 Provider 及配置。
- **降级容错**：通过 `LLMServiceFactory.create_with_fallback()` 创建的 LLM 服务，在调用失败时会按 `LLM_PROVIDER_PRIORITY` 配置的优先级顺序自动降级到下一个可用 Provider。
- **优先级解析链**（高 → 低）：
  1. 环境变量 `AGENT_PRIORITY__{agent_name}`（按 Agent 覆盖）
  2. 环境变量 `LLM_PROVIDER_PRIORITY`（全局默认）
  3. `settings.LLM_PROVIDER_PRIORITY["default"]`
  4. 回退：仅使用 `AGENT_LLM_DEFAULTS` 中配置的单一 Provider

### 3. 知识库单例初始化

`apps/knowledge/apps.py` 中的 `KnowledgeConfig.ready()`：

```python
class KnowledgeConfig(AppConfig):
    name = "apps.knowledge"

    def ready(self):
        from .embedding import BGEM3Embedder
        from .vector_store import MilvusVectorStore

        if not hasattr(self, "embedder"):
            self.embedder = BGEM3Embedder()
        if not hasattr(self, "vector_store"):
            self.vector_store = MilvusVectorStore()
```

业务侧通过 `KnowledgeService()` 自动复用该单例。

## 🚀 本地运行

1. **准备依赖**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows 使用 .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **配置环境变量**
   - 复制 `.env` 示例并补全数据库、Milvus、LLM Key。

3. **初始化数据库**
   ```bash
   python manage.py migrate
   ```


3a. **创建管理员用户（可选）**
   > 默认凭据：admin / admin123
   >
   > 登录入口：http://127.0.0.1:8000/accounts/login/
   >
   > ⚠️ 首次登录后请及时修改密码。
   > 使用 @login_required 保护页面，未登录时会被重定向到登录页。
   > 外部工具调用 JSON API 需在请求头传入 `X-API-Key`（通过环境变量 `API_KEY` 配置）。

## 📼 演示视频

- 测试用例生成：`videos/测试用例生成.mp4`
- 测试用例评审：`videos/测试用例评审.mp4`
- 知识库文档上传：`videos/知识库文档上传.mp4`
