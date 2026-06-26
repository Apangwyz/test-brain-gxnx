# 需求文档深度分析功能 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 TestBrain 中新建"需求文档深度分析"功能，支持 6 维度自动分析，并将分析结果联动到测试用例生成

**Architecture:** 新建 `requirement_analyzer` Agent 模块，内部分为三阶段管道（概要→并行深度分析→汇总联动），6 个分析维度各自封装为独立 Agent，编排器 Orchestrator 管理执行流程。分析结果存入新增的 `RequirementAnalysis` 模型，并通过增强版 API 注入 `test_case_generator` 的生成策略。

**Tech Stack:** Django 5.1, LangChain, SSE 推送, 已有 LLM 工厂(`apps/llm/`), 已有知识库(`apps/knowledge/`)

---

### Task 1: 新增 RequirementAnalysis 模型

**Files:**
- Modify: `apps/core/models.py`（末尾新增模型）
- Create: `apps/core/migrations/0005_requirementanalysis.py`

- [ ] **Step 1: 在 models.py 末尾新增 RequirementAnalysis 模型**

追加到 `apps/core/models.py` 文件末尾：

```python
class RequirementAnalysis(models.Model):
    """需求文档分析记录"""
    document_name = models.CharField(max_length=200, verbose_name="文档名称")
    document_hash = models.CharField(max_length=64, verbose_name="文档内容Hash", db_index=True)
    content_preview = models.TextField(blank=True, verbose_name="内容预览")

    quality_score = models.JSONField(default=dict, verbose_name="质量评分")
    completeness = models.JSONField(default=dict, verbose_name="完整度检查")
    consistency = models.JSONField(default=dict, verbose_name="一致性/冲突检测")
    risk_identification = models.JSONField(default=dict, verbose_name="风险识别")
    category_stats = models.JSONField(default=dict, verbose_name="需求分类统计")
    testability = models.JSONField(default=dict, verbose_name="可测试性评级")
    generation_strategy = models.JSONField(default=dict, blank=True, verbose_name="生成策略")

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

- [ ] **Step 2: 生成迁移文件并执行迁移**

Run:
```bash
python manage.py makemigrations
python manage.py migrate
```

Expected: 生成 `apps/core/migrations/0005_requirementanalysis.py` 并成功写入 `db.sqlite3`

---

### Task 2: 创建 requirement_analyzer Agent 模块骨架

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/__init__.py`（空文件）
- Create: `apps/ai_agents/requirement_analyzer/apps.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/__init__.py`（空文件）
- Create: `apps/ai_agents/requirement_analyzer/configs/__init__.py`（空文件）
- Modify: `config/settings.py`（注册新 App）

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p apps/ai_agents/requirement_analyzer/{agents,configs,templates,static}
touch apps/ai_agents/requirement_analyzer/__init__.py
touch apps/ai_agents/requirement_analyzer/agents/__init__.py
touch apps/ai_agents/requirement_analyzer/configs/__init__.py
```

- [ ] **Step 2: 创建 apps.py**

写 `apps/ai_agents/requirement_analyzer/apps.py`：

```python
from django.apps import AppConfig


class RequirementAnalyzerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_agents.requirement_analyzer"
    verbose_name = "需求文档分析"
```

- [ ] **Step 3: 在 settings.py 中注册新 App**

在 `config/settings.py` 的 `INSTALLED_APPS` 中追加：

```python
"apps.ai_agents.requirement_analyzer",
```

同时在 `AGENT_LLM_DEFAULTS` 字典中新增：

```python
"requirement_analyzer": {"provider": "deepseek"},
```

---

### Task 3: Prompt 配置 — 6 个分析维度的 LLM prompt

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/prompts.py`
- Create: `apps/ai_agents/requirement_analyzer/configs/prompt_config.yaml`

- [ ] **Step 1: 创建 prompt_config.yaml**

写 `apps/ai_agents/requirement_analyzer/configs/prompt_config.yaml`：

```yaml
# ═══════════════════════════════════════════════
# Phase 1: 概要分析
# ═══════════════════════════════════════════════

quality_scoring:
  system_template: |
    你是一位需求文档质量分析专家。请从完整性、清晰度、一致性、可测试性、结构化程度五个维度对以下需求文档进行评分（0-100分），并给出综合评分和简短总结。
    每个维度的评分标准：
    - 完整性：文档是否覆盖了功能描述、业务流程、边界条件、异常处理
    - 清晰度：表述是否明确无歧义，术语是否统一
    - 一致性：前后章节是否存在矛盾或重复
    - 可测试性：需求是否能被验证和测试
    - 结构化程度：文档是否有清晰的层次结构，是否使用标题/列表等组织内容
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "overall_score": 整数,
      "dimensions": {{
        "completeness": 整数,
        "clarity": 整数,
        "consistency": 整数,
        "testability": 整数,
        "structure": 整数
      }},
      "summary": "一句话总结"
    }}

category_stats:
  system_template: |
    你是需求分类专家。请将以下需求文档中的内容按功能需求、非功能性需求、业务规则、UI/UX 四大类进行归类，统计各类别的数量和占比，并按优先级分布进行统计。
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "categories": {{
        "functional": {{"count": 整数, "ratio": "百分比"}},
        "non_functional": {{"count": 整数, "ratio": "百分比"}},
        "business_rule": {{"count": 整数, "ratio": "百分比"}},
        "ui_ux": {{"count": 整数, "ratio": "百分比"}}
      }},
      "priority_distribution": {{
        "high": 整数,
        "medium": 整数,
        "low": 整数
      }}
    }}

# ═══════════════════════════════════════════════
# Phase 2: 深度分析（4个 Agent 并行执行）
# ═══════════════════════════════════════════════

completeness_check:
  system_template: |
    你是需求文档完整度检查专家。请检查以下需求文档是否包含以下核心要素：前置条件、正常流程、异常流程、验收标准、输入/输出定义、业务规则、界面描述。
    对于每个缺失项，给出严重程度（high/medium/low）和改进建议。
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "total_items": ["前置条件", "正常流程", "异常流程", "验收标准", "业务规则", "输入/输出定义", "界面描述"],
      "present_items": ["已有的要素"],
      "missing_items": ["缺失的要素"],
      "suggestions": [
        {{"item": "要素名称", "severity": "high/medium/low", "suggestion": "改进建议"}}
      ]
    }}

risk_identification:
  system_template: |
    你是需求文档风险识别专家。请扫描以下需求文档，识别以下类型的风险：
    - 模糊表述：使用了"等等"、"相关"、"相应"、"等"等不明确的词语
    - 技术风险：涉及技术实现高难度的需求
    - 依赖风险：外部依赖、第三方系统未明确指定
    - 范围过大：需求范围过于宽泛难以实现
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "risk_items": [
        {{
          "type": "vague_description / technical_risk / dependency_risk / overscoped",
          "severity": "high/medium/low",
          "location": {{"section": "章节", "text": "原文片段"}},
          "risk": "风险描述",
          "suggestion": "改进建议"
        }}
      ]
    }}

consistency_check:
  system_template: |
    你是需求文档一致性检查专家。请仔细阅读以下需求文档，检查：
    - 矛盾：不同章节对同一事物描述不一致
    - 重复：同一功能在多处重复描述
    - 术语不一致：同一概念使用了不同的术语
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "conflicts": [
        {{
          "type": "contradiction / duplication / terminology",
          "severity": "high/medium/low",
          "location_a": {{"section": "章节A", "text": "原文A"}},
          "location_b": {{"section": "章节B", "text": "原文B"}},
          "description": "问题描述"
        }}
      ]
    }}

testability_rating:
  system_template: |
    你是需求可测试性评估专家。请分析以下需求文档中的每个需求点，判断其是否能被测试验证。
    - high：操作步骤明确，预期结果清晰可验证
    - medium：需要补充少量细节才能测试
    - low：表述模糊，无法直接设计测试用例
   human_template: |
    请分析以下需求文档：

    ```
    {markdown_content}
    ```

    请严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记）：
    {{
      "testability_overall": "high/medium/low",
      "items": [
        {{
          "section": "章节位置",
          "text": "原文片段",
          "level": "high/medium/low",
          "reason": "判断依据"
        }}
      ],
      "untestable_count": 整数,
      "recommendation": "改进建议"
    }}
```

- [ ] **Step 2: 创建 prompts.py**（复用现有 PrdAnalyserPrompt 的模式）

写 `apps/ai_agents/requirement_analyzer/prompts.py`：

```python
from pathlib import Path
import yaml
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate


class RequirementAnalyzerPrompt:
    """需求文档分析提示词管理器"""

    _config_cache = None  # 类级别缓存，避免重复加载 YAML

    def __init__(self):
        config_path = Path(__file__).parent / "configs" / "prompt_config.yaml"
        self.config = self._load_config(config_path)

    @classmethod
    def _load_config(cls, config_path: Path):
        if cls._config_cache is None:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config_cache = yaml.safe_load(f)
        return cls._config_cache

    def get_quality_scoring_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["quality_scoring"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_category_stats_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["category_stats"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_completeness_check_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["completeness_check"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_risk_identification_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["risk_identification"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_consistency_check_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["consistency_check"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_testability_rating_prompt(self) -> ChatPromptTemplate:
        cfg = self.config["testability_rating"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])
```

---

### Task 4: 6 个分析 Agent 实现

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/agents/quality_scorer.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/category_statistician.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/completeness_checker.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/risk_identifier.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/consistency_checker.py`
- Create: `apps/ai_agents/requirement_analyzer/agents/testability_rater.py`

每个 Agent 遵循相同模式：接收 `BaseLLMService` + 文档内容，返回对应的 JSON dict。

- [ ] **Step 1: 实现 quality_scorer.py**

```python
import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class QualityScorer:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_quality_scoring_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

- [ ] **Step 2: 实现 category_statistician.py**

```python
import json
from typing import Dict, Any
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class CategoryStatistician:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_category_stats_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

- [ ] **Step 3: 实现 completeness_checker.py**

```python
import json
from typing import Dict, Any
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class CompletenessChecker:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_completeness_check_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

- [ ] **Step 4: 实现 risk_identifier.py**

```python
import json
from typing import Dict, Any
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class RiskIdentifier:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_risk_identification_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

- [ ] **Step 5: 实现 consistency_checker.py**

```python
import json
from typing import Dict, Any
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class ConsistencyChecker:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_consistency_check_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

- [ ] **Step 6: 实现 testability_rater.py**

```python
import json
from typing import Dict, Any
from apps.llm.base import BaseLLMService
from apps.ai_agents.requirement_analyzer.prompts import RequirementAnalyzerPrompt
from apps.utils.logger_manager import get_logger


class TestabilityRater:
    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = RequirementAnalyzerPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def analyze(self, markdown_content: str) -> Dict[str, Any]:
        messages = self.prompt.get_testability_rating_prompt().format_messages(
            markdown_content=markdown_content
        )
        response = self.llm_service.invoke(messages)
        return json.loads(response.content.strip().removeprefix("```json").removesuffix("```").strip())
```

---

### Task 5: 编排器 Orchestrator

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/orchestrator.py`

编排器职责：管理三阶段管道执行，计算 hash 缓存，计算联动策略

- [ ] **Step 1: 实现 orchestrator.py**

```python
import hashlib
import threading
import json
from typing import Dict, Any, Optional
from django.utils import timezone

from apps.llm.base import BaseLLMService
from apps.llm import LLMServiceFactory
from apps.utils.logger_manager import get_logger
from apps.utils.progress_manager import TaskProgressManager
from apps.core.models import RequirementAnalysis

from .agents.quality_scorer import QualityScorer
from .agents.category_statistician import CategoryStatistician
from .agents.completeness_checker import CompletenessChecker
from .agents.risk_identifier import RiskIdentifier
from .agents.consistency_checker import ConsistencyChecker
from .agents.testability_rater import TestabilityRater


class AnalysisOrchestrator:
    """
    需求文档分析编排器
    
    三阶段管道：
    Phase 1 (串行): 质量评分 + 需求分类统计 → 快速给出概览
    Phase 2 (并行): 完整度检查 + 风险识别 + 冲突检测 + 可测试性评级
    Phase 3 (串行): 汇总报告 → 计算生成策略
    """

    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.quality_scorer = QualityScorer(llm_service)
        self.category_statistician = CategoryStatistician(llm_service)
        self.completeness_checker = CompletenessChecker(llm_service)
        self.risk_identifier = RiskIdentifier(llm_service)
        self.consistency_checker = ConsistencyChecker(llm_service)
        self.testability_rater = TestabilityRater(llm_service)
        self.logger = get_logger(self.__class__.__name__)

    @staticmethod
    def compute_document_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def find_cached_analysis(document_hash: str) -> Optional[RequirementAnalysis]:
        return RequirementAnalysis.objects.filter(
            document_hash=document_hash
        ).first()

    def analyze(self, document_name: str, markdown_content: str,
                progress_manager: Optional[TaskProgressManager] = None) -> RequirementAnalysis:
        """执行完整的分析管道"""

        document_hash = self.compute_document_hash(markdown_content)

        # 缓存命中检查
        cached = self.find_cached_analysis(document_hash)
        if cached:
            self.logger.info(f"缓存命中: {document_name} (hash={document_hash[:12]}...)")
            if progress_manager:
                progress_manager.update_progress(100, "使用缓存的分析结果")
            return cached

        # Phase 1: 概要分析
        if progress_manager:
            progress_manager.start_stage("scoring", "质量评分与分类统计")

        quality_result = self._safe_analyze(self.quality_scorer.analyze, markdown_content, "quality_scorer")
        category_result = self._safe_analyze(self.category_statistician.analyze, markdown_content, "category_statistician")

        if progress_manager:
            progress_manager.complete_stage("scoring")

        # Phase 2: 深度分析（并行执行）
        if progress_manager:
            progress_manager.start_stage("deep_analysis", "深度分析（完整度/风险/冲突/可测试性）")

        phase2_results = {}
        phase2_lock = threading.Lock()

        def run_phase2_agent(name: str, analyze_func, content: str):
            result = self._safe_analyze(analyze_func, content, name)
            with phase2_lock:
                phase2_results[name] = result

        threads = []
        agents = [
            ("completeness", self.completeness_checker.analyze),
            ("risk", self.risk_identifier.analyze),
            ("consistency", self.consistency_checker.analyze),
            ("testability", self.testability_rater.analyze),
        ]
        # 最多并行2个，避免 API 限速
        for i in range(0, len(agents), 2):
            batch = agents[i:i+2]
            threads = []
            for name, func in batch:
                t = threading.Thread(target=run_phase2_agent, args=(name, func, markdown_content))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()

        if progress_manager:
            progress_manager.complete_stage("deep_analysis")

        # Phase 3: 汇总 + 计算生成策略
        if progress_manager:
            progress_manager.start_stage("summarize", "汇总分析结果与生成策略")

        strategy = self._compute_generation_strategy(
            quality_result, category_result, phase2_results
        )

        # 存入数据库
        analysis = RequirementAnalysis.objects.create(
            document_name=document_name,
            document_hash=document_hash,
            content_preview=markdown_content[:500],
            quality_score=quality_result,
            category_stats=category_result,
            completeness=phase2_results.get("completeness", {}),
            risk_identification=phase2_results.get("risk", {}),
            consistency=phase2_results.get("consistency", {}),
            testability=phase2_results.get("testability", {}),
            generation_strategy=strategy,
            total_sections=markdown_content.count("\n## "),
            word_count=len(markdown_content),
        )

        if progress_manager:
            progress_manager.complete_stage("summarize")
            progress_manager.complete()

        self.logger.info(f"分析完成: {document_name}, 评分={quality_result.get('overall_score', 'N/A')}")
        return analysis

    def _safe_analyze(self, analyze_func, content: str, name: str) -> Dict[str, Any]:
        """安全执行分析，失败时返回空字典"""
        try:
            return analyze_func(content)
        except Exception as e:
            self.logger.error(f"{name} 分析失败: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _compute_generation_strategy(self, quality: Dict[str, Any],
                                      category: Dict[str, Any],
                                      phase2: Dict[str, Any]) -> Dict[str, Any]:
        """根据分析结果计算测试用例生成策略"""
        quality_score = quality.get("overall_score", 70) if isinstance(quality, dict) else 70

        # 基础权重
        scenario_weights = {
            "normal": 0.50,
            "abnormal": 0.25,
            "boundary": 0.15,
            "performance": 0.10,
        }

        # 低质量文档 → 增加异常场景权重
        if quality_score < 60:
            scenario_weights["normal"] = 0.30
            scenario_weights["abnormal"] = 0.40
            scenario_weights["boundary"] = 0.20
            scenario_weights["performance"] = 0.10

        # 中等质量文档 → 适度增加异常场景
        elif quality_score < 80:
            scenario_weights["normal"] = 0.40
            scenario_weights["abnormal"] = 0.30
            scenario_weights["boundary"] = 0.20
            scenario_weights["performance"] = 0.10

        # 高风险区域
        risk_items = phase2.get("risk", {}).get("risk_items", []) if isinstance(phase2.get("risk"), dict) else []
        focus_areas = []
        for item in risk_items:
            if isinstance(item, dict) and item.get("severity") == "high":
                focus_areas.append({
                    "area": item.get("location", {}).get("section", "未知"),
                    "risk_level": "high",
                    "extra_cases": 3,
                })

        return {
            "case_count": 15,
            "scenario_weights": scenario_weights,
            "focus_areas": focus_areas,
            "quality_suggestions": [],
        }
```

---

### Task 6: 视图（Views）、URL 路由、模板和 JS

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/views.py`
- Create: `apps/ai_agents/requirement_analyzer/urls.py`
- Create: `apps/ai_agents/requirement_analyzer/templates/requirement_analysis.html`
- Create: `apps/ai_agents/requirement_analyzer/static/requirement_analysis.js`
- Modify: `config/urls.py`（注册路由）

- [ ] **Step 1: 实现 views.py**

```python
import os
import json
import threading
import hashlib

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from apps.llm import LLMServiceFactory
from apps.llm.utils import get_agent_llm_configs
from apps.utils.logger_manager import get_logger
from apps.utils.file_transfer import word_to_markdown
from apps.utils.file_parser import extract_text_from_pdf
from apps.utils.progress_manager import TaskProgressManager, generate_task_id
from apps.utils.auth_decorators import session_or_apikey_auth
from apps.core.models import RequirementAnalysis

from .orchestrator import AnalysisOrchestrator


logger = get_logger(__name__)

DEFAULT_PROVIDER, PROVIDERS = get_agent_llm_configs("requirement_analyzer")
DEFAULT_LLM_CONFIG = PROVIDERS.get(DEFAULT_PROVIDER, {})


@login_required
def requirement_analysis_page(request):
    return render(request, "requirement_analysis.html")


def _get_sse_bus():
    from apps.utils.sse_bus import SSEManager
    return SSEManager


@session_or_apikey_auth
@require_http_methods(["POST"])
def upload_api(request):
    """文件上传 API（复用 prd_analyzer 的上传逻辑）"""
    try:
        if "file" not in request.FILES:
            return JsonResponse({"success": False, "error": "未接收到文件"})

        uploaded_file = request.FILES["file"]
        file_name = uploaded_file.name
        file_type = os.path.splitext(file_name)[1].lower()

        if file_type not in [".docx", ".pdf"]:
            return JsonResponse({"success": False, "error": "仅支持 .docx 和 .pdf 格式"})

        max_size = 10 * 1024 * 1024
        if uploaded_file.size > max_size:
            return JsonResponse({"success": False, "error": "文件大小超过限制（最大10MB）"})

        save_dir = "requirement_analysis/"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file_name)

        counter = 1
        while os.path.exists(file_path):
            base, ext = os.path.splitext(file_name)
            file_path = os.path.join(save_dir, f"{base}_{counter}{ext}")
            counter += 1

        with open(file_path, "wb+") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        return JsonResponse({
            "success": True,
            "file_path": file_path,
            "file_name": file_name,
            "file_type": file_type,
        })
    except Exception as e:
        logger.error(f"上传失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": f"上传失败: {str(e)}"})


def _extract_content(file_path: str, file_type: str) -> str:
    """从文件中提取文本内容"""
    if file_type == ".docx":
        md_path = file_path.replace(".docx", ".md")
        word_to_markdown(file_path, md_path)
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    elif file_type == ".pdf":
        return extract_text_from_pdf(file_path)
    return ""


def _run_analysis_async(task_id: str, file_path: str, file_name: str, file_type: str):
    """异步执行分析"""
    stages = [
        {"stage": "extracting", "title": "提取内容", "description": "从文件中提取文本..."},
        {"stage": "scoring", "title": "质量评分", "description": "评估文档质量..."},
        {"stage": "deep_analysis", "title": "深度分析", "description": "完整度/风险/冲突/可测试性分析..."},
        {"stage": "summarize", "title": "汇总报告", "description": "生成分析报告与测试策略..."},
        {"stage": "completed", "title": "完成", "description": "分析完成"},
    ]
    progress_manager = TaskProgressManager(task_id, stages)

    try:
        progress_manager.start_stage("extracting")
        content = _extract_content(file_path, file_type)
        if not content:
            progress_manager.error_stage("extracting", "无法提取文件内容")
            return
        progress_manager.complete_stage("extracting")

        llm_service = LLMServiceFactory.create(provider=DEFAULT_PROVIDER)
        orchestrator = AnalysisOrchestrator(llm_service)
        analysis = orchestrator.analyze(file_name, content, progress_manager)

        # 推送完成事件
        sse_bus = _get_sse_bus()
        sse_bus.send_event(task_id, "completed", {"message": "分析完成", "analysis_id": analysis.id})

    except Exception as e:
        logger.error(f"分析过程出错: {str(e)}", exc_info=True)
        progress_manager.error_stage("completed", f"分析失败: {str(e)}")


@session_or_apikey_auth
@require_http_methods(["POST"])
def analyze_api(request):
    """开始分析 API"""
    try:
        data = json.loads(request.body)
        file_path = data.get("file_path")
        file_name = data.get("file_name")
        file_type = data.get("file_type", os.path.splitext(file_name)[1].lower())

        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"success": False, "error": "文件不存在"})

        task_id = generate_task_id("req_analysis")
        thread = threading.Thread(
            target=_run_analysis_async,
            args=(task_id, file_path, file_name, file_type),
            daemon=True,
        )
        thread.start()

        return JsonResponse({"success": True, "task_id": task_id})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "无效的JSON数据"})
    except Exception as e:
        logger.error(f"分析请求处理失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def analysis_result_api(request, analysis_id: int):
    """获取分析结果 API"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        return JsonResponse({
            "success": True,
            "data": {
                "id": analysis.id,
                "document_name": analysis.document_name,
                "quality_score": analysis.quality_score,
                "completeness": analysis.completeness,
                "consistency": analysis.consistency,
                "risk_identification": analysis.risk_identification,
                "category_stats": analysis.category_stats,
                "testability": analysis.testability,
                "generation_strategy": analysis.generation_strategy,
                "total_sections": analysis.total_sections,
                "word_count": analysis.word_count,
                "created_at": analysis.created_at.isoformat(),
            }
        })
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"获取分析结果失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def latest_result_api(request):
    """获取最近一次分析结果 API（供前端 fallback 使用）"""
    try:
        analysis = RequirementAnalysis.objects.order_by("-created_at").first()
        if not analysis:
            return JsonResponse({"success": False, "error": "暂无分析记录"})
        return JsonResponse({
            "success": True,
            "data": {
                "id": analysis.id,
                "document_name": analysis.document_name,
                "quality_score": analysis.quality_score,
                "completeness": analysis.completeness,
                "consistency": analysis.consistency,
                "risk_identification": analysis.risk_identification,
                "category_stats": analysis.category_stats,
                "testability": analysis.testability,
                "generation_strategy": analysis.generation_strategy,
                "total_sections": analysis.total_sections,
                "word_count": analysis.word_count,
                "created_at": analysis.created_at.isoformat(),
            }
        })
    except Exception as e:
        logger.error(f"获取最近分析结果失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def generate_from_analysis_api(request):
    """
    基于分析结果生成测试用例（增强版 prd_to_testcase）
    接收 analysis_id，获取分析记录中的 strategy 参数传入 test_case_generator
    """
    try:
        data = json.loads(request.body)
        analysis_id = data.get("analysis_id")

        if not analysis_id:
            return JsonResponse({"success": False, "error": "缺少 analysis_id"})

        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        strategy = analysis.generation_strategy

        # 组装需求描述（用原文或分类统计中的内容）
        combined = analysis.content_preview or ""

        if not combined.strip():
            return JsonResponse({"success": False, "error": "分析记录内容为空"})

        from apps.ai_agents.test_case_generator.progress_manager import create_progress_manager
        from apps.ai_agents.test_case_generator.task_executor import submit_generation_task
        from apps.ai_agents.test_case_generator.views import _generate_test_cases_async

        progress_manager = create_progress_manager()
        task_id = progress_manager.task_id

        case_count = strategy.get("case_count", 15) if isinstance(strategy, dict) else 15

        submit_generation_task(
            task_id=task_id,
            requirements=combined,
            llm_provider=DEFAULT_PROVIDER,
            case_design_methods=[],
            case_categories=[],
            case_count=case_count,
            generator_func=_generate_test_cases_async,
        )

        return JsonResponse({
            "success": True,
            "task_id": task_id,
            "message": f"基于分析结果生成 {case_count} 条测试用例（策略：高风险区域优先覆盖）",
        })

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"生成用例失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})
```

- [ ] **Step 2: 实现 urls.py**

```python
from django.urls import path
from . import views

app_name = "requirement_analyzer"

urlpatterns = [
    path("", views.requirement_analysis_page, name="requirement_analysis"),
    path("upload/", views.upload_api, name="upload"),
    path("api/analyze/", views.analyze_api, name="analyze"),
    path("api/result/<int:analysis_id>/", views.analysis_result_api, name="analysis_result"),
    path("api/result/latest/", views.latest_result_api, name="analysis_result_latest"),
    path("api/generate/", views.generate_from_analysis_api, name="generate"),
]
```

- [ ] **Step 3: 在 config/urls.py 中注册路由**

在 `config/urls.py` 的 `urlpatterns` 中追加：

```python
path('requirement_analysis/', include('apps.ai_agents.requirement_analyzer.urls')),
```

- [ ] **Step 4: 实现 requirement_analysis.html 模板**

```html
{% extends "base.html" %}
{% load static %}

{% block title %}TestBrain - 需求文档分析{% endblock %}

{% block extra_css %}
<style>
:root {
    --progress-height: 8px;
}

.upload-zone {
    border: 2px dashed var(--border-color);
    border-radius: var(--radius-md);
    padding: 48px 24px;
    text-align: center;
    transition: all 0.3s ease;
    cursor: pointer;
}
.upload-zone:hover {
    border-color: var(--primary);
    background: var(--bg-tertiary);
}
.upload-zone.dragover {
    border-color: var(--primary);
    background: rgba(var(--primary-rgb), 0.08);
}
.upload-icon {
    font-size: 48px;
    color: var(--text-tertiary);
    margin-bottom: 16px;
}

.progress-container {
    margin-top: 24px;
    display: none;
}
.progress-bar-container {
    height: var(--progress-height);
    background: var(--bg-tertiary);
    border-radius: calc(var(--progress-height) / 2);
    overflow: hidden;
    margin-bottom: 8px;
}
.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--info));
    border-radius: calc(var(--progress-height) / 2);
    transition: width 0.5s ease;
    width: 0%;
}
.progress-status {
    font-size: 14px;
    color: var(--text-secondary);
}

.report-container {
    display: none;
    margin-top: 24px;
}

.score-ring {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
    font-size: 36px;
    font-weight: 700;
}
.score-ring.high {
    background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
    color: #2e7d32;
}
.score-ring.medium {
    background: linear-gradient(135deg, #fff3e0, #ffe0b2);
    color: #e65100;
}
.score-ring.low {
    background: linear-gradient(135deg, #fce4ec, #f8bbd0);
    color: #c62828;
}

.radar-container {
    max-width: 400px;
    margin: 0 auto;
}

.section-card {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 16px 20px;
    margin-bottom: 16px;
}
.section-card h6 {
    font-weight: 600;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.issue-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}
.issue-tag.high { background: #fce4ec; color: #c62828; }
.issue-tag.medium { background: #fff3e0; color: #e65100; }
.issue-tag.low { background: #e8f5e9; color: #2e7d32; }

.action-bar {
    margin-top: 24px;
    padding: 16px 0;
    border-top: 1px solid var(--border-color);
    text-align: center;
}
</style>
{% endblock %}

{% block content %}
<div class="page-header">
    <h4>需求文档分析</h4>
    <p>上传需求文档，自动进行质量评分、完整度检查、风险识别、冲突检测、需求分类与可测试性评估</p>
</div>

<!-- 上传区 -->
<div class="card">
    <div class="card-body">
        <div class="upload-zone" id="uploadZone">
            <div class="upload-icon">
                <i class="fas fa-cloud-upload-alt"></i>
            </div>
            <h5>点击选择或拖拽文件到此处</h5>
            <p style="color: var(--text-secondary); font-size: 14px; margin-top: 8px;">
                支持 .docx 和 .pdf 格式，最大 10MB
            </p>
            <input type="file" id="fileInput" accept=".docx,.pdf" style="display: none;">
        </div>
        <div id="selectedFileInfo" style="display: none; margin-top: 20px; text-align: center;">
            <p style="color: var(--success); font-weight: 500;" id="fileNameDisplay"></p>
            <button class="btn btn-primary btn-lg" id="startAnalysisBtn">
                <i class="fas fa-microscope"></i> 开始分析
            </button>
        </div>
    </div>
</div>

<!-- 进度条 -->
<div class="progress-container" id="progressContainer">
    <div class="progress-bar-container">
        <div class="progress-bar-fill" id="progressFill"></div>
    </div>
    <div class="progress-status" id="progressStatus">准备中...</div>
</div>

<!-- 分析报告 -->
<div class="report-container" id="reportContainer">

    <!-- 概览仪表盘 -->
    <div class="card">
        <div class="card-header"><h5 style="margin:0;">📊 分析概览</h5></div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-4 text-center">
                    <div class="score-ring" id="scoreRing">-</div>
                    <p style="font-size: 18px; font-weight: 500;">综合评分</p>
                </div>
                <div class="col-md-8">
                    <div class="row" id="dimensionScores"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- 完整度检查 -->
    <div class="section-card" id="completenessSection">
        <h6>📋 完整度检查</h6>
        <div id="completenessContent">分析中...</div>
    </div>

    <!-- 冲突检测 -->
    <div class="section-card" id="conflictSection">
        <h6>⚠️ 一致性与冲突检测</h6>
        <div id="conflictContent">分析中...</div>
    </div>

    <!-- 风险识别 -->
    <div class="section-card" id="riskSection">
        <h6>🚨 风险识别</h6>
        <div id="riskContent">分析中...</div>
    </div>

    <!-- 需求分类 -->
    <div class="section-card" id="categorySection">
        <h6>📂 需求分类统计</h6>
        <div id="categoryContent">分析中...</div>
    </div>

    <!-- 可测试性 -->
    <div class="section-card" id="testabilitySection">
        <h6>✅ 可测试性评级</h6>
        <div id="testabilityContent">分析中...</div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
        <button class="btn btn-success btn-lg" id="generateCasesBtn" style="display: none;">
            <i class="fas fa-flask"></i> 基于分析结果生成测试用例
        </button>
        <button class="btn btn-outline-secondary btn-lg" id="exportReportBtn" style="display: none; margin-left: 12px;">
            <i class="fas fa-download"></i> 导出分析报告
        </button>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'requirement_analysis.js' %}"></script>
{% endblock %}
```

- [ ] **Step 5: 实现 requirement_analysis.js**

```javascript
let currentAnalysisId = null;
let currentFilePath = null;
let currentFileName = null;
let currentFileType = null;

document.addEventListener('DOMContentLoaded', function() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    uploadZone.addEventListener('click', function() {
        fileInput.click();
    });

    uploadZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', function() {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFileSelect(this.files[0]);
        }
    });

    document.getElementById('startAnalysisBtn').addEventListener('click', uploadAndAnalyze);
    document.getElementById('generateCasesBtn').addEventListener('click', generateFromAnalysis);
    document.getElementById('exportReportBtn').addEventListener('click', exportReport);
});

function handleFileSelect(file) {
    const validTypes = ['.docx', '.pdf'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!validTypes.includes(ext)) {
        alert('仅支持 .docx 和 .pdf 格式');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        alert('文件大小超过限制（最大10MB）');
        return;
    }

    currentFileName = file.name;
    document.getElementById('fileNameDisplay').textContent = '已选择: ' + file.name;
    document.getElementById('uploadZone').style.display = 'none';
    document.getElementById('selectedFileInfo').style.display = 'block';

    // 保存文件到变量供上传使用
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    document.getElementById('fileInput').files = dataTransfer.files;
}

function uploadAndAnalyze() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    document.getElementById('selectedFileInfo').style.display = 'none';
    document.getElementById('progressContainer').style.display = 'block';

    // Step 1: 上传
    setProgressStatus('正在上传文件...');
    fetch('/requirement_analysis/upload/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() },
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) { alert(data.error); return; }
        currentFilePath = data.file_path;
        currentFileType = data.file_type;

        // Step 2: 开始分析
        setProgressStatus('正在分析文档...');
        return fetch('/requirement_analysis/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                file_path: currentFilePath,
                file_name: currentFileName,
                file_type: currentFileType
            })
        });
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) { alert(data.error); return; }
        pollProgress(data.task_id);
    })
    .catch(err => { alert('请求失败: ' + err.message); });
}

function pollProgress(taskId) {
    // 使用 SSE 监听进度（复用系统已有的 SSE 机制）
    const eventSource = new EventSource('/progress/stream/' + taskId + '/');

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        const percent = data.percentage || 0;
        document.getElementById('progressFill').style.width = percent + '%';

        if (data.status === 'completed') {
            eventSource.close();
            setProgressStatus('分析完成!');
            document.getElementById('progressContainer').style.display = 'none';
            const analysisId = data.analysis_id || null;
            fetchAnalysisResult(taskId, analysisId);
        } else if (data.status === 'error') {
            eventSource.close();
            setProgressStatus('分析失败: ' + (data.message || '未知错误'));
        } else {
            setProgressStatus(data.message || '分析中...');
        }
    };
}

function fetchAnalysisResult(taskId, analysisId) {
    if (analysisId) {
        // 使用 SSE 事件中携带的 analysis_id 直接获取
        fetch('/requirement_analysis/api/result/' + analysisId + '/')
        .then(r => r.json())
        .then(data => {
            if (data.success) renderReport(data.data);
        });
        return;
    }
    // fallback: 轮询最近的分析记录
    pollLatestAnalysis().then(data => {
        if (data && data.success) {
            renderReport(data.data);
        }
    });
}

function pollLatestAnalysis(retries = 10) {
    return new Promise((resolve) => {
        function tryFetch(n) {
            if (n <= 0) { resolve(null); return; }
            setTimeout(() => {
                // 获取最近一次分析记录
                fetch('/requirement_analysis/api/result/latest/')
                .then(r => r.json())
                .then(data => {
                    if (data.success && data.data) resolve(data);
                    else tryFetch(n - 1);
                })
                .catch(() => tryFetch(n - 1));
            }, 2000);
        }
        tryFetch(retries);
    });
}

function renderReport(data) {
    currentAnalysisId = data.id;
    document.getElementById('reportContainer').style.display = 'block';

    // 评分
    const score = data.quality_score?.overall_score || 0;
    const ring = document.getElementById('scoreRing');
    ring.textContent = score;
    ring.className = 'score-ring ' + (score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low');

    // 各维度评分
    const dims = data.quality_score?.dimensions || {};
    const dimLabels = {
        completeness: '完整性', clarity: '清晰度', consistency: '一致性',
        testability: '可测试性', structure: '结构化'
    };
    const dimContainer = document.getElementById('dimensionScores');
    dimContainer.innerHTML = '';
    Object.entries(dims).forEach(([key, val]) => {
        dimContainer.innerHTML += `
            <div class="col-6 col-md-4 mb-3">
                <div style="font-size: 13px; color: var(--text-secondary);">${dimLabels[key] || key}</div>
                <div style="font-size: 24px; font-weight: 700; color: ${val >= 80 ? '#2e7d32' : val >= 60 ? '#e65100' : '#c62828'};">${val}</div>
            </div>
        `;
    });

    // 完整度
    const comp = data.completeness || {};
    document.getElementById('completenessContent').innerHTML = renderCompleteness(comp);

    // 冲突检测
    const cons = data.consistency || {};
    document.getElementById('conflictContent').innerHTML = renderConflicts(cons);

    // 风险识别
    const risk = data.risk_identification || {};
    document.getElementById('riskContent').innerHTML = renderRisks(risk);

    // 分类统计
    const cat = data.category_stats || {};
    document.getElementById('categoryContent').innerHTML = renderCategories(cat);

    // 可测试性
    const test = data.testability || {};
    document.getElementById('testabilityContent').innerHTML = renderTestability(test);

    // 显示按钮
    document.getElementById('generateCasesBtn').style.display = 'inline-block';
    document.getElementById('exportReportBtn').style.display = 'inline-block';

    // 滚动到报告区域
    document.getElementById('reportContainer').scrollIntoView({ behavior: 'smooth' });
}

function renderCompleteness(data) {
    const present = data.present_items || [];
    const missing = data.missing_items || [];
    const suggestions = data.suggestions || [];
    let html = '<div class="row">';
    html += '<div class="col-md-6"><strong>✅ 已覆盖</strong><ul>';
    present.forEach(item => { html += '<li>' + item + '</li>'; });
    html += '</ul></div><div class="col-md-6"><strong>❌ 缺失</strong><ul>';
    missing.forEach(item => { html += '<li>' + item + '</li>'; });
    html += '</ul></div></div>';
    if (suggestions.length) {
        html += '<div style="margin-top: 12px;"><strong>💡 改进建议</strong><ul>';
        suggestions.forEach(s => {
            html += '<li><span class="issue-tag ' + s.severity + '">' + s.severity + '</span> ' + s.suggestion + '</li>';
        });
        html += '</ul></div>';
    }
    return html;
}

function renderConflicts(data) {
    const conflicts = data.conflicts || [];
    if (!conflicts.length) return '<p style="color: var(--success);">✅ 未检测到明显的冲突或矛盾</p>';
    let html = '';
    conflicts.forEach(c => {
        html += '<div style="margin-bottom: 12px; padding: 8px; background: var(--bg-tertiary); border-radius: 4px;">';
        html += '<span class="issue-tag ' + c.severity + '">' + c.severity + '</span> ';
        html += '<strong>' + c.type + '</strong>: ' + c.description;
        html += '<div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">';
        html += '📍 ' + (c.location_a?.section || '?') + ' ↔ ' + (c.location_b?.section || '?');
        html += '</div></div>';
    });
    return html;
}

function renderRisks(data) {
    const items = data.risk_items || [];
    if (!items.length) return '<p style="color: var(--success);">✅ 未识别到高风险项</p>';
    let html = '';
    items.forEach(item => {
        html += '<div style="margin-bottom: 12px; padding: 8px; background: var(--bg-tertiary); border-radius: 4px;">';
        html += '<span class="issue-tag ' + item.severity + '">' + item.severity + '</span> ';
        html += '<strong>' + (item.type || '未知') + '</strong>';
        html += '<div style="font-size: 13px; margin-top: 4px;">' + item.risk + '</div>';
        if (item.suggestion) {
            html += '<div style="font-size: 13px; color: var(--info); margin-top: 2px;">💡 ' + item.suggestion + '</div>';
        }
        if (item.location?.section) {
            html += '<div style="font-size: 12px; color: var(--text-tertiary);">📍 ' + item.location.section + '</div>';
        }
        html += '</div>';
    });
    return html;
}

function renderCategories(data) {
    const cats = data.categories || {};
    const pri = data.priority_distribution || {};
    let html = '<div class="row">';
    html += '<div class="col-md-6"><strong>📂 需求分类</strong><ul>';
    Object.entries(cats).forEach(([key, val]) => {
        const label = { functional: '功能需求', non_functional: '非功能性', business_rule: '业务规则', ui_ux: 'UI/UX' }[key] || key;
        html += '<li>' + label + ': ' + (typeof val === 'object' ? (val.count + ' (' + (val.ratio || '') + ')') : val) + '</li>';
    });
    html += '</ul></div><div class="col-md-6"><strong>📊 优先级分布</strong><ul>';
    if (pri.high) html += '<li>🔴 高: ' + pri.high + '</li>';
    if (pri.medium) html += '<li>🟡 中: ' + pri.medium + '</li>';
    if (pri.low) html += '<li>🟢 低: ' + pri.low + '</li>';
    html += '</ul></div></div>';
    return html;
}

function renderTestability(data) {
    const items = data.items || [];
    const untestable = data.untestable_count || 0;
    const recommendation = data.recommendation || '';
    const overall = data.testability_overall || 'unknown';
    const overallLabel = { high: '🟢 高', medium: '🟡 中', low: '🔴 低' }[overall] || overall;

    let html = '<p><strong>整体可测试性: ' + overallLabel + '</strong>';
    if (untestable > 0) html += ' | 不可测试需求: ' + untestable + ' 条';
    html += '</p>';
    if (items.length) {
        html += '<ul>';
        items.forEach(item => {
            const levelLabel = { high: '🟢', medium: '🟡', low: '🔴' }[item.level] || '⚪';
            html += '<li>' + levelLabel + ' ' + (item.section || '') + ': ' + (item.reason || '') + '</li>';
        });
        html += '</ul>';
    }
    if (recommendation) {
        html += '<div style="background: var(--bg-tertiary); padding: 8px; border-radius: 4px; font-size: 13px;">💡 ' + recommendation + '</div>';
    }
    return html;
}

function generateFromAnalysis() {
    if (!currentAnalysisId) return;

    fetch('/requirement_analysis/api/generate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ analysis_id: currentAnalysisId })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message || '正在生成测试用例，请前往"测试用例生成"页面查看进度');
            window.location.href = '/test_case_generator/';
        } else {
            alert('生成失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(err => alert('请求失败: ' + err.message));
}

function exportReport() {
    if (!currentAnalysisId) return;
    // 跳转到导出页面（未来可以生成 PDF）
    window.open('/requirement_analysis/api/result/' + currentAnalysisId + '/?format=json', '_blank');
}

function setProgressStatus(msg) {
    document.getElementById('progressStatus').textContent = msg;
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}
```

---

### Task 7: SSE 进度集成

**Files:**
- Modify: `apps/utils/sse_bus.py`（确认已有 SSE 机制可用）

- [ ] **Step 1: 检查现有 SSE 机制是否支持进度流的直接广播**

查看 `apps/utils/sse_bus.py` 和 `apps/core/urls.py`，确认现有的 SSE 端点（如 `/progress/stream/<task_id>/`）可以直接被 `requirement_analyzer` 复用。

Run:
```bash
cat apps/utils/sse_bus.py
cat apps/core/urls.py
```

Expected: 确认 SSE 流接口可用，无需额外修改。

如果不可用，仿照现有模式在 `apps/core/urls.py` 注册 SSE 路径，在 `apps/core/views.py` 或 `apps/core/views_sse.py` 中实现 SSE 视图（参考现有实现）。

---

### Task 8: 导航栏入口

**Files:**
- Modify: `templates/base.html`（导航栏新增入口）

- [ ] **Step 1: 在导航栏新增"需求分析"菜单项**

在 `templates/base.html` 的导航栏中，在"测试点解析"或"PRD 分析"附近新增：

```html
<li class="nav-item">
    <a class="nav-link" href="{% url 'requirement_analyzer:requirement_analysis' %}">
        <i class="fas fa-file-alt"></i> 需求分析
    </a>
</li>
```

---

### Task 9: 将分析策略参数接入 test_case_generator

**Files:**
- Modify: `apps/ai_agents/test_case_generator/generator.py`（接收 strategy 参数）
- Modify: `apps/ai_agents/test_case_generator/views.py`（联动 API 增强）

- [ ] **Step 1: 在 generator.py 中支持 strategy 参数**

修改 `TestCaseGeneratorAgent.__init__` 方法，新增可选参数 `generation_strategy: Optional[Dict] = None`。当 strategy 存在时：

1. 使用 `strategy["case_count"]` 覆盖 `self.case_count`
2. 使用 `strategy["scenario_weights"]` 在 prompt 中调整场景分布提示
3. 将 `strategy["focus_areas"]` 注入 prompt，提示 LLM 对这些区域增加用例密度

```python
# 在 __init__ 方法末尾新增
self.generation_strategy = generation_strategy or {}

# 在 async_generate 方法中，构建 prompt 前，覆盖参数
if self.generation_strategy.get("case_count"):
    self.case_count = self.generation_strategy["case_count"]
```

- [ ] **Step 2: 在 views.py 的 submit API 中接收 strategy 参数**

修改 `apps/ai_agents/test_case_generator/views.py` 中的相关视图，在解析请求 body 时增加：

```python
strategy = data.get("generation_strategy", {})
```

并在创建 `TestCaseGeneratorAgent` 时传入。

---

### Task 10: 数据迁移与缓存预热

**Files:**
- Create: `apps/ai_agents/requirement_analyzer/migrations/__init__.py`（空）

- [ ] **Step 1: 执行最终迁移**

```bash
python manage.py makemigrations
python manage.py migrate
```

Expected: 所有 model 变更已同步到数据库

- [ ] **Step 2: 验证功能完整性**

```bash
python manage.py runserver 0.0.0.0:8000
```

手动测试流程：
1. 访问 `/requirement_analysis/` 确认页面加载正常
2. 上传一个 .docx 文件，观察进度条和报告展示
3. 点击"基于分析结果生成测试用例"，验证跳转到生成页面

---

### 范围检查确认

对照设计文档各章节：

| 规格章节 | 覆盖任务 | 说明 |
|---------|---------|------|
| 整体架构（三阶段管道） | Task 5 | Orchestrator 实现三阶段编排 |
| SSE 进度推送 | Task 7 | 复用现有 SSE 机制 |
| 质量评分 | Task 4 (QualityScorer) + Task 3 (prompt) | Phase 1 串行 |
| 完整度检查 | Task 4 (CompletenessChecker) | Phase 2 并行 |
| 冲突检测 | Task 4 (ConsistencyChecker) | Phase 2 并行 |
| 风险识别 | Task 4 (RiskIdentifier) | Phase 2 并行 |
| 需求分类统计 | Task 4 (CategoryStatistician) | Phase 1 串行 |
| 可测试性评级 | Task 4 (TestabilityRater) | Phase 2 并行 |
| 联动生成策略 | Task 5 (Orchestrator._compute_generation_strategy) | Phase 3 汇总 |
| RequirementAnalysis 模型 | Task 1 | Django Model |
| 新页面（上传+报告） | Task 6 | view + template + JS |
| test_case_generator 接入 | Task 9 | 接收 strategy 参数 |
| 导航栏入口 | Task 8 | base.html |
| 缓存去重（document_hash） | Task 5 (Orchestrator.find_cached_analysis) | SHA256 缓存 |
| 向后兼容 | Task 6 + Task 9 | 新增可选字段 |
