# 项目初始化变更报告

## 变更基本信息

- **变更日期**: 2024-12-00
- **变更类型**: 项目初始化
- **变更负责人**: 开发团队
- **关联 Issue**: N/A

---

## 变更概述

完成 TestBrain 项目的初始化搭建，建立基于大语言模型的智能测试平台基础架构，为后续功能开发奠定基础。

---

## 变更详情

### 1. 项目架构搭建

#### 1.1 Django 项目结构
- 创建 Django 5.1.6 项目框架
- 配置 `config/settings.py` 核心设置
- 建立模块化应用目录结构 `apps/`

#### 1.2 核心应用模块
- **apps/core**: 公共视图、模型、页面模板
- **apps/ai_agents**: 多智能体系统实现
- **apps/knowledge**: 知识库向量检索服务
- **apps/llm**: 大语言模型工厂与 Provider 管理

### 2. AI Agent 系统

#### 2.1 测试用例生成器 (test_case_generator)
- **功能**: 根据需求描述自动生成测试用例
- **实现文件**:
  - `apps/ai_agents/test_case_generator/generator.py`
  - `apps/ai_agents/test_case_generator/prompts.py`
- **特性**:
  - 支持同步/异步调用 LLM
  - 可自定义设计方法、测试类型、生成条数
  - 结果保存到数据库

#### 2.2 测试用例评审器 (test_case_reviewer)
- **功能**: 对生成的测试用例进行评审与打分
- **实现文件**:
  - `apps/ai_agents/test_case_reviewer/reviewer.py`
  - `apps/ai_agents/test_case_reviewer/prompts.py`
- **特性**:
  - 输出风险评估
  - 提供改进建议
  - 支持多维度评分

#### 2.3 PRD 分析器 (prd_analyzer)
- **功能**: 解析产品需求文档，提炼测试点和测试场景
- **实现文件**:
  - `apps/ai_agents/prd_analyzer/analyser.py`
  - `apps/ai_agents/prd_analyzer/prompts.py`
- **特性**:
  - 内置 JSON 修复逻辑
  - 自动识别测试场景
  - 结构化输出测试点

#### 2.4 接口用例生成器 (iface_case_generator)
- **功能**: 基于接口描述生成测试用例
- **实现文件**:
  - `apps/ai_agents/iface_case_generator/iface_case_generator.py`
  - `apps/ai_agents/iface_case_generator/prompts.py`
- **特性**:
  - 支持多种接口协议
  - 自动生成边界测试
  - 模型可切换

#### 2.5 Java 代码分析器 (java_code_analyzer)
- **功能**: 静态分析 Java 源码，识别潜在测试点
- **实现文件**:
  - `apps/ai_agents/java_code_analyzer/java_code_analyzer_agent.py`
  - `apps/ai_agents/java_code_analyzer/tools.py`
- **特性**:
  - 代码结构分析
  - 潜在缺陷识别
  - 测试关注点建议

### 3. LLM 集成系统

#### 3.1 多 Provider 支持
- **DeepSeek**: 深度求索大语言模型
- **Qwen**: 通义千问大语言模型
- **扩展性**: 支持快速接入新模型供应商

#### 3.2 LLM 工厂模式
- **文件**: `apps/llm/base.py`
- **功能**:
  - 动态创建模型客户端
  - 统一接口封装
  - 支持同步/异步调用

#### 3.3 配置管理
- **Agent 默认模型**: `AGENT_LLM_DEFAULTS` 配置
- **Provider 列表**: `LLM_PROVIDERS` 配置
- **环境变量**: `.env` 文件管理 API Keys

### 4. 知识库系统

#### 4.1 向量数据库集成
- **Milvus 2.4.x**: 高性能向量数据库
- **集合管理**: 自动创建/验证集合
- **CRUD 操作**: 完整的向量增删改查

#### 4.2 Embedding 模型
- **模型**: `BAAI/bge-m3`
- **库**: `sentence-transformers`
- **单例模式**: `KnowledgeConfig.ready()` 预热

#### 4.3 知识服务
- **文件**: `apps/knowledge/service.py`
- **功能**:
  - 文档解析（Markdown、TXT 等）
  - 批量嵌入
  - 相似度检索
  - 上下文增强

### 5. 前端界面

#### 5.1 基础模板
- **文件**: `templates/base.html`
- **特性**:
  - 响应式布局
  - Bootstrap 样式
  - 统一导航栏

#### 5.2 功能页面
- **首页**: 项目概览与功能入口
- **知识库管理**: 文档上传与检索
- **用例生成**: 测试用例生成界面
- **用例评审**: 用例评审界面
- **PRD 分析**: 需求分析界面

#### 5.3 静态资源
- **CSS**: `static/css/main.css`
- **JS**: `static/js/main.js`, `static/js/knowledge.js`
- **第三方库**: jQuery, Bootstrap, Select2

### 6. 数据库设计

#### 6.1 测试用例模型 (TestCase)
```python
class TestCase(models.Model):
    requirement = models.TextField()  # 需求描述
    test_cases = models.JSONField()   # 测试用例 JSON
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### 6.2 迁移文件
- `apps/core/migrations/0001_initial.py`
- 支持自动表结构创建

### 7. 配置文件

#### 7.1 环境变量 (.env)
```dotenv
# LLM Keys
DEEPSEEK_API_KEY=your_key
QWEN_API_KEY=your_key

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

#### 7.2 Django 配置
- **config/settings.py**: 核心配置
- **config/urls.py**: URL 路由
- **config/asgi.py**: ASGI 入口
- **config/wsgi.py**: WSGI 入口

### 8. 依赖管理

#### 8.1 Python 依赖
- **文件**: `requirements.txt`
- **核心包**:
  - Django 5.1.6
  - LangChain
  - sentence-transformers
  - pymilvus
  - mysqlclient

#### 8.2 系统依赖
- Python 3.12+
- MySQL 8.x
- Milvus 2.4.x

### 9. 脚本工具

#### 9.1 管理脚本
- `scripts/deploy.py`: 部署脚本
- `scripts/backup.py`: 备份脚本
- `scripts/status.py`: 状态检查
- `scripts/restart.py`: 重启服务
- `scripts/stop.py`: 停止服务

#### 9.2 数据库迁移
- `migrate_all.sh`: 批量迁移脚本
- `manage.py migrate`: Django 迁移

---

## 变更影响

### 正面影响
1. ✅ 建立完整的项目架构
2. ✅ 实现多 Agent 协同能力
3. ✅ 支持多 LLM 供应商
4. ✅ 集成知识库向量检索
5. ✅ 提供友好的 Web 界面

### 风险评估
- ⚠️ Milvus 服务依赖需要单独部署
- ⚠️ Embedding 模型首次加载较慢
- ⚠️ 多进程模式可能导致单例初始化多次

---

## 测试验证

### 功能测试
- [x] 测试用例生成功能
- [x] 测试用例评审功能
- [x] PRD 分析功能
- [x] 知识库文档上传
- [x] 模型切换功能

### 集成测试
- [x] LLM Provider 切换
- [x] Milvus 向量检索
- [x] 数据库读写
- [x] 文件上传解析

---

## 文档清单

| 文档名称 | 文件路径 | 说明 |
|---------|---------|------|
| README.md | `/README.md` | 项目说明文档 |
| 需求文档 | `/uploads/req_02_银行内部管理系统.md` | 示例需求文档 |
| 演示视频 | `/videos/` | 功能演示视频 |
| 环境配置 | `/.env.example` | 环境变量模板 |

---

## 后续计划

### 短期计划
1. 完善错误处理机制
2. 优化日志记录格式
3. 增强前端交互体验
4. 添加更多测试场景

### 长期计划
1. 接入更多 LLM 供应商
2. 实现 Celery 异步任务
3. 添加用户权限管理
4. 提供 RESTful API

---

## 变更记录

| 日期 | 操作 | 说明 |
|------|------|------|
| 2024-12-00 | 创建 | 项目初始化完成 |
| 2025-01-19 | 归档 | 变更文档整理归档 |

---

## 附录

### A. 项目结构树
```
TestBrain/
├── apps/
│   ├── ai_agents/            # 各类智能体实现
│   ├── core/                 # 公共视图、模型、页面
│   ├── knowledge/            # Milvus & Embedding 服务
│   └── llm/                  # LLM 工厂、Provider 定义
├── config/                   # Django 配置
├── templates/                # 页面模板
├── static/                   # 静态资源
├── videos/                   # 功能演示视频
├── requirements.txt          # 依赖列表
└── manage.py
```

### B. 快速启动命令
```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python manage.py migrate

# 启动服务
python manage.py runserver 0.0.0.0:8000
```

### C. 相关链接
- 项目仓库：[TestBrain](file:///Users/apang/Downloads/TestBrain-main)
- 演示视频：`/videos/`
- 知识库文档：`/uploads/`
