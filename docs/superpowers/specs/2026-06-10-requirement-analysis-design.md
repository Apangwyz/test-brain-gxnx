# 需求文档深度分析功能设计

> **日期**: 2026-06-10
> **状态**: Draft
> **关联模块**: `prd_analyzer`、`test_case_generator`、`knowledge`

---

## 1. 概述

当前 TestBrain 的 `prd_analyzer` 仅支持从需求文档中提取测试点和测试场景，缺少对需求文档**本身质量**的分析。本功能在现有基础上构建一套完整的**需求文档深度分析管道**，产出 6 个维度的分析报告，并将分析结果联动到测试用例生成环节，实现"分析指导生成"的闭环。

### 目标用户

- **测试人员**: 了解需求的完整度、可测试性、风险点，从而更精准地设计测试用例
- **产品经理**: 获取需求文档质量反馈（完整性、一致性、清晰度），持续改进文档质量

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                    需求文档上传                            │
│            (复用已有上传逻辑，支持 .docx/.pdf)               │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│                  分析管道编排器 (Orchestrator)              │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │ Phase 1    │  │ Phase 2    │  │ Phase 3           │  │
│  │ 概要先跑    │→ │ 并行分析    │→ │ 汇总报告 + 联动    │  │
│  │ (质量评分、 │  │ (完整度、   │  │ (输出结构化报告，  │  │
│  │  分类统计)  │  │  风险识别、 │  │  注入生成策略)    │  │
│  │            │  │  冲突检测、 │  │                   │  │
│  │            │  │  可测试性)  │  │                   │  │
│  └────────────┘  └────────────┘  └───────────────────┘  │
└────────────────────┬─────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ 分析报告页面  │ │ 知识库    │ │ test_case    │
│ (新独立页面)  │ │ (存分析   │ │ _generator   │
│              │ │  结果供   │ │ (接收分析     │
│              │ │  后续查询)│ │  元数据)     │
└──────────────┘ └──────────┘ └──────────────┘
```

### 2.1 三阶段管道

| 阶段 | 包含维度 | 执行方式 | 说明 |
|------|---------|---------|------|
| **Phase 1: 概要** | 质量评分、需求分类统计 | 串行（先出概览） | 快速给出文档的总体健康度概览 |
| **Phase 2: 深度分析** | 完整度检查、风险识别、冲突检测、可测试性评级 | 并行执行 | 四个独立 Agent 并行分析，互不依赖 |
| **Phase 3: 汇总联动** | 报告聚合、生成策略注入 | 串行 | 汇总所有分析结果，计算出注入到 test_case_generator 的策略参数 |

### 2.2 SSE 进度推送

使用当前系统已有的 `apps/utils/sse_bus.py` 机制，每个阶段完成时推送到前端，前端按"概览 → 质量评分 → 完整度 → 风险 → 冲突 → 分类统计 → 可测试性"顺序流式展示。

---

## 3. 六个分析维度详细设计

### 3.1 质量评分

- **分析内容**: 从完整性、清晰度、一致性、可测试性、结构化程度五个子维度对文档打分（0-100 分）
- **输出格式**:
  ```json
  {
    "overall_score": 85,
    "dimensions": {
      "completeness": 90,
      "clarity": 80,
      "consistency": 85,
      "testability": 75,
      "structure": 92
    },
    "summary": "文档整体质量良好，但在可测试性方面有所欠缺，部分需求描述过于模糊。"
  }
  ```

### 3.2 完整度检查

- **分析内容**: 逐项检查文档是否包含核心要素：前置条件、后置条件、正常流程、异常流程、验收标准、输入输出定义、业务规则、界面原型/描述
- **输出格式**:
  ```json
  {
    "total_items": ["前置条件", "正常流程", "异常流程", "验收标准", "业务规则", "输入/输出定义", "界面描述"],
    "present_items": ["前置条件", "正常流程", "业务规则", "界面描述"],
    "missing_items": ["异常流程", "验收标准", "输入/输出定义"],
    "suggestions": [
      {"item": "异常流程", "severity": "high", "suggestion": "建议补充各功能点的异常处理流程"},
      {"item": "验收标准", "severity": "medium", "suggestion": "建议为每个需求点明确验收标准"}
    ]
  }
  ```

### 3.3 一致性与冲突检测

- **分析内容**: 扫描全文识别矛盾表述、重复定义、前后不一致的术语或数据
- **输出格式**:
  ```json
  {
    "conflicts": [
      {
        "type": "contradiction",
        "severity": "high",
        "location_a": {"section": "3.2", "text": "系统响应时间不超过2秒"},
        "location_b": {"section": "5.1", "text": "系统响应时间应在5秒以内"},
        "description": "不同章节对响应时间的要求不一致"
      }
    ],
    "duplications": [
      {"location_a": {"section": "2.1"}, "location_b": {"section": "4.3"}, "description": "用户登录功能在两个章节重复描述"}
    ]
  }
  ```

### 3.4 风险识别

- **分析内容**: 识别模糊表述（"等等"、"相关"、"相应"）、技术实现风险、过宽需求、外部依赖未明确等
- **输出格式**:
  ```json
  {
    "risk_items": [
      {
        "type": "vague_description",
        "severity": "high",
        "location": {"section": "3.4", "text": "系统应在相应时间内返回结果"},
        "risk": "使用了模糊词'相应时间'，无法确定具体性能指标"
      },
      {
        "type": "missing_dependency",
        "severity": "medium",
        "location": {"section": "7.2", "text": "对接第三方支付平台"},
        "risk": "未指定第三方支付平台名称和对接方式"
      }
    ]
  }
  ```

### 3.5 需求分类统计

- **分析内容**: 将需求自动归类并按类别统计数量、占比、优先级分布
- **输出格式**:
  ```json
  {
    "categories": {
      "functional": {"count": 15, "ratio": "60%"},
      "non_functional": {"count": 3, "ratio": "12%"},
      "business_rule": {"count": 5, "ratio": "20%"},
      "ui_ux": {"count": 2, "ratio": "8%"}
    },
    "priority_distribution": {
      "high": 8,
      "medium": 12,
      "low": 5
    }
  }
  ```

### 3.6 可测试性评级

- **分析内容**: 逐条判断每个需求能否被测试验证，输出可测试性等级
- **输出格式**:
  ```json
  {
    "testability_overall": "medium",
    "items": [
      {"section": "3.2.1", "text": "用户点击登录按钮后进入首页", "level": "high", "reason": "操作步骤明确，预期结果清晰"},
      {"section": "3.2.2", "text": "系统性能应良好", "level": "low", "reason": "未定义'良好'的量化标准"}
    ],
    "untestable_count": 2,
    "recommendation": "有2条需求无法直接测试验证，建议补充量化标准"
  }
  ```

---

## 4. 分析与测试用例生成的联动

### 4.1 生成策略参数

分析报告结束后，编排器计算出一组**策略参数**，通过 API 传递给 `test_case_generator`：

```json
{
  "generation_strategy": {
    "case_count": 15,
    "scenario_weights": {
      "normal": 0.4,
      "abnormal": 0.35,
      "boundary": 0.15,
      "performance": 0.10
    },
    "focus_areas": [
      {"area": "用户登录", "risk_level": "high", "extra_cases": 3},
      {"area": "支付流程", "risk_level": "high", "extra_cases": 5}
    ],
    "quality_suggestions": ["补充异常流程覆盖", "关注含糊需求的澄清验证"]
  }
}
```

### 4.2 联动触发方式

- 分析报告页面底部提供 **"以分析结果生成测试用例"** 按钮
- 点击后调用现有 `prd_to_testcase_api` 的增强版本，附加上 strategy 参数
- `test_case_generator` 接收新的 strategy 参数后，调整用例生成的 prompt 和计数分配

### 4.3 与现有 `prd_to_testcase_api` 的兼容

- 保持现有接口签名不变（向后兼容）
- 新增可选字段 `analysis_strategy`，不存在时使用默认生成行为
- 前端根据是否经过了分析流程来决定是否传入此字段

---

## 5. 数据库模型扩展

在 `apps/core/models.py` 中新增模型：

```python
class RequirementAnalysis(models.Model):
    """需求文档分析记录"""
    document_name = models.CharField(max_length=200, verbose_name="文档名称")
    document_hash = models.CharField(max_length=64, verbose_name="文档内容Hash", db_index=True)
    content_preview = models.TextField(blank=True, verbose_name="内容预览")
    
    # 六个维度结果（全部存为 JSON）
    quality_score = models.JSONField(default=dict, verbose_name="质量评分")
    completeness = models.JSONField(default=dict, verbose_name="完整度检查")
    consistency = models.JSONField(default=dict, verbose_name="一致性/冲突检测")
    risk_identification = models.JSONField(default=dict, verbose_name="风险识别")
    category_stats = models.JSONField(default=dict, verbose_name="需求分类统计")
    testability = models.JSONField(default=dict, verbose_name="可测试性评级")
    
    # 生成的生成策略（联动用）
    generation_strategy = models.JSONField(default=dict, blank=True, verbose_name="生成策略")
    
    # 元信息
    total_sections = models.IntegerField(default=0, verbose_name="总章节数")
    word_count = models.IntegerField(default=0, verbose_name="总字数")
    analysis_version = models.CharField(max_length=20, default="1.0", verbose_name="分析版本")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="分析时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "需求分析记录"
        verbose_name_plural = "需求分析记录"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.document_name} ({self.quality_score.get('overall_score', 'N/A')}分)"
```

---

## 6. 新页面与前端设计

### 6.1 页面路径

- **入口**: 导航栏新增"需求分析"菜单项
- **页面**: `/requirement_analysis/`
- **模板**: `templates/requirement_analysis.html`
- **JS**: `static/js/requirement_analysis.js`

### 6.2 页面布局

```
┌──────────────────────────────────────────────────────┐
│  [文件上传区]  选择 .docx / .pdf 文件                  │
│  已选: xxx.docx  [开始分析]                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  分析进度条 ████████░░ 70%                            │
│  当前: 风险识别分析中...                                │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────── 概览仪表盘 ──────────┐                   │
│  │  综合评分: 85/100              │                   │
│  │  ┌─────── 雷达图 ────────┐    │                   │
│  │  │  完整度 ████████ 90   │    │                   │
│  │  │  清晰度 ███████  80   │    │                   │
│  │  │  一致性 ████████ 85   │    │                   │
│  │  │  可测试 ███████  75   │    │                   │
│  │  │  结构化 █████████ 92  │    │                   │
│  │  └──────────────────────┘    │                   │
│  │  [以分析结果生成测试用例]      │                   │
│  └──────────────────────────────┘                   │
│                                                      │
│  ┌── 完整度检查 ─────────────────────────────────┐  │
│  │  ✅ 已覆盖: 前置条件 正常流程 业务规则 界面描述  │  │
│  │  ⚠️ 缺失: 异常流程(高) 验收标准(中) 输入输出(中) │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌── 冲突检测 ─────────────────────────────────┐    │
│  │  🔴 响应时间要求不一致 (3.2 vs 5.1)         │    │
│  │  🟡 登录功能重复描述 (2.1 vs 4.3)           │    │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌── 风险识别 ─────────────────────────────────┐    │
│  │  🔴 模糊表述: "相应时间" (3.4)              │    │
│  │  🟡 外部依赖未明确: 第三方支付平台 (7.2)     │    │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌── 需求分类 ──────────── 可测试性 ────────────┐    │
│  │  功能需求: 60%           可测试: 85%         │    │
│  │  业务规则: 20%          不可测: 2条          │    │
│  │  非功能性: 12%                               │    │
│  │  UI/UX: 8%                                   │    │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────────┐ │
│  │  [以分析结果生成测试用例]  [导出分析报告]          │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 7. 文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `apps/ai_agents/requirement_analyzer/` | **新建目录** | 新 Agent 模块，包含 6 个分析 Agent + 编排器 |
| `apps/ai_agents/requirement_analyzer/analyser.py` | 新建 | 编排器 Orchestrator，管理三阶段管道 |
| `apps/ai_agents/requirement_analyzer/agents/` | 新建 | 6 个分析 Agent（共用一个 prompts.py） |
| `apps/ai_agents/requirement_analyzer/views.py` | 新建 | 上传 + 分析 API + 页面路由 |
| `apps/ai_agents/requirement_analyzer/urls.py` | 新建 | URL 配置 |
| `apps/ai_agents/requirement_analyzer/prompts.py` | 新建 | YAML prompt 配置 |
| `apps/ai_agents/requirement_analyzer/configs/prompt_config.yaml` | 新建 | 各分析维度的 LLM prompt |
| `apps/ai_agents/requirement_analyzer/static/` | 新建 | JS 文件 |
| `apps/ai_agents/requirement_analyzer/templates/` | 新建 | HTML 模板 |
| `apps/core/models.py` | 修改 | 新增 `RequirementAnalysis` 模型 |
| `apps/core/urls.py` | 修改 | 注册 `requirement_analysis` URL |
| `config/settings.py` | 修改 | 注册新 App，新增 Agent 默认 LLM 配置 |
| `apps/ai_agents/test_case_generator/generator.py` | 修改 | 接收 `analysis_strategy` 参数，调整生成策略 |
| `apps/ai_agents/test_case_generator/views.py` | 修改 | 联动 API 增强 |
| `templates/base.html` | 修改 | 导航栏新增"需求分析"入口 |

---

## 8. 测试场景

| 场景 | 预期结果 |
|------|---------|
| 上传一份高质量完整的需求文档 | 质量评分 > 80，6 个维度报告完整，可一键生成用例 |
| 上传一份低质量模糊的需求文档 | 质量评分 < 60，风险识别提示多处模糊表述，生成策略中异常场景权重提高 |
| 上传包含矛盾表述的文档 | 冲突检测正确识别矛盾位置并高亮 |
| 上传同一文档两次（内容未变） | 根据 document_hash 命中缓存，直接返回历史分析结果 |
| 上传同一文档两次（内容已变） | 触发变更分析，对比报告高亮变化部分 |
| 分析完成后点击"生成测试用例" | 传入 strategy 参数，用例生成覆盖偏向高风险区域 |

---

## 9. 假设与决策记录

| 假设/决策 | 说明 |
|-----------|------|
| 分析结果缓存策略 | 按文档内容 SHA256 hash 缓存，同一文档不重复分析 |
| 变更分析触发条件 | 只有 document_hash 不同才触发变更分析，且缓存旧版本结果用于对比 |
| 并行度限制 | Phase 2 的 4 个 Agent 最多并行 2 个，避免 API 限速 |
| 评分标准校准 | 初期使用 LLM 直接评分，后续可基于用户反馈做校准 |
| 向后兼容 | `prd_to_testcase_api` 新增可选字段，不传则行为不变 |
