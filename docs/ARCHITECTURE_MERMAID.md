# TestBrain 系统架构 Mermaid 流程图

```mermaid
flowchart TD
    %% === 样式定义 ===
    classDef client fill:#e6f7ff,stroke:#1890ff,stroke-width:2
    classDef service fill:#fff7e6,stroke:#fa8c16,stroke-width:2
    classDef database fill:#fff1f0,stroke:#f5222d,stroke-width:2
    classDef external fill:#f0f5ff,stroke:#1890ff,stroke-width:2
    
    %% === 前端展示层 (Presentation Layer) ===
    subgraph PresentationLayer["前端展示层"]
        HomePage["首页"]
        TestCaseGenerator["测试用例生成器"]
        TestCaseReviewer["测试案例评审"]
        PRDAnalyzer["PRD分析器"]
        IfaceCaseGenerator["接口用例生成器"]
        JavaCodeAnalyzer["Java源码分析器"]
        KnowledgeManagement["知识库管理"]
        TestExecution["测试执行管理"]
        SystemManagement["系统归属管理"]
    end
    
    %% === 控制器层 (Controller Layer) ===
    subgraph ControllerLayer["控制器层"]
        URLRouter["URL路由"]
        ViewFunctions["视图函数"]
        Middleware["中间件"]
    end
    
    %% === 业务逻辑层 (Business Logic Layer) ===
    subgraph BusinessLayer["业务逻辑层"]
        subgraph AIAgents["AI Agent 服务"]
            TCGenAgent["测试用例生成Agent"]
            TCRevAgent["测试案例评审Agent"]
            PRDAgent["PRD分析Agent"]
            IfaceAgent["接口用例生成Agent"]
            JavaAgent["Java代码分析Agent"]
        end
        
        subgraph CoreServices["核心服务"]
            SysService["系统服务"]
            PlanService["测试计划服务"]
            ExecService["测试执行服务"]
            KnowService["知识库服务"]
        end
        
        LLMFactory["LLM服务工厂"]
    end
    
    %% === 数据访问层 (Data Access Layer) ===
    subgraph DataLayer["数据访问层"]
        DjangoORM["Django ORM"]
        Embedding["Embedding服务"]
        VectorSearch["向量检索"]
    end
    
    %% === 基础设施层 (Infrastructure Layer) ===
    subgraph Infrastructure["基础设施层"]
        MySQL[(MySQL数据库)]
        Milvus[(Milvus向量数据库)]
        Redis[(Redis缓存)]
    end
    
    %% === 外部依赖 ===
    subgraph External["外部依赖"]
        DeepSeekAPI["DeepSeek API"]
        QwenAPI["Qwen API"]
        HuggingFace["HuggingFace"]
    end
    
    %% === 连接关系 ===
    
    % 前端到控制器层
    HomePage --> URLRouter
    TestCaseGenerator --> URLRouter
    TestCaseReviewer --> URLRouter
    PRDAnalyzer --> URLRouter
    IfaceCaseGenerator --> URLRouter
    JavaCodeAnalyzer --> URLRouter
    KnowledgeManagement --> URLRouter
    TestExecution --> URLRouter
    SystemManagement --> URLRouter
    
    % 控制器层内部
    URLRouter --> ViewFunctions
    Middleware --> URLRouter
    
    % 控制器层到业务逻辑层
    ViewFunctions --> TCGenAgent
    ViewFunctions --> TCRevAgent
    ViewFunctions --> PRDAgent
    ViewFunctions --> IfaceAgent
    ViewFunctions --> JavaAgent
    ViewFunctions --> SysService
    ViewFunctions --> PlanService
    ViewFunctions --> ExecService
    ViewFunctions --> KnowService
    
    % AI Agent到LLM服务
    TCGenAgent --> LLMFactory
    TCRevAgent --> LLMFactory
    PRDAgent --> LLMFactory
    IfaceAgent --> LLMFactory
    JavaAgent --> LLMFactory
    
    % LLM工厂到外部API
    LLMFactory --> DeepSeekAPI
    LLMFactory --> QwenAPI
    
    % 知识库服务到数据层
    KnowService --> Embedding
    KnowService --> VectorSearch
    
    % 数据访问层到基础设施
    DjangoORM --> MySQL
    Embedding --> HuggingFace
    VectorSearch --> Milvus
    ExecService --> Redis
    
    % 业务服务到数据层
    SysService --> DjangoORM
    PlanService --> DjangoORM
    ExecService --> DjangoORM
    
    % 应用样式类
    class HomePage,TestCaseGenerator,TestCaseReviewer,PRDAnalyzer,IfaceCaseGenerator,JavaCodeAnalyzer,KnowledgeManagement,TestExecution,SystemManagement client
    class URLRouter,ViewFunctions,Middleware,TCGenAgent,TCRevAgent,PRDAgent,IfaceAgent,JavaAgent,SysService,PlanService,ExecService,KnowService,LLMFactory,DjangoORM,Embedding,VectorSearch service
    class MySQL,Milvus,Redis database
    class DeepSeekAPI,QwenAPI,HuggingFace external
```

---

## 流程图说明

### 架构分层说明

| 层级 | 颜色标识 | 说明 |
|-----|---------|-----|
| **前端展示层** | 蓝色边框 | 用户交互界面，包含9个核心页面 |
| **控制器层** | 橙色边框 | 请求处理和路由分发 |
| **业务逻辑层** | 橙色边框 | AI Agent服务和核心业务服务 |
| **数据访问层** | 橙色边框 | 数据持久化和检索 |
| **基础设施层** | 红色边框 | 底层数据库和缓存服务 |
| **外部依赖** | 浅蓝色边框 | LLM API和模型下载服务 |

### 核心组件说明

**客户端组件（蓝色）**：
- 首页、测试用例生成器、测试案例评审、PRD分析器
- 接口用例生成器、Java源码分析器、知识库管理
- 测试执行管理、系统归属管理

**服务组件（橙色）**：
- 控制器：URL路由、视图函数、中间件
- AI Agent：测试用例生成、案例评审、PRD分析、接口生成、Java分析
- 核心服务：系统服务、测试计划服务、测试执行服务、知识库服务
- LLM服务工厂、Django ORM、Embedding服务、向量检索

**数据库组件（红色）**：
- MySQL：关系型数据存储
- Milvus：向量数据存储和检索
- Redis：缓存和消息队列（预留扩展）

**外部依赖（浅蓝色）**：
- DeepSeek API、Qwen API、HuggingFace

### 数据流说明

```
用户请求 → 前端页面 → URL路由 → 视图函数 → 业务服务 → 数据访问层 → 数据库
                                                         ↓
                                                  LLM服务工厂 → 外部API
```

### 使用方式

将上述代码复制到支持Mermaid的环境中即可渲染：
- GitHub Markdown
- GitLab Markdown
- Mermaid Live Editor (https://mermaid.live)
- 支持Mermaid的IDE插件

---

**文档版本**：v1.0  
**生成时间**：2024年  
**项目名称**：TestBrain - 基于大语言模型的智能测试平台
