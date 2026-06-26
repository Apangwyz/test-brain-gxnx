import hashlib
import threading
from typing import Dict, Any, Optional

from apps.llm.base import BaseLLMService
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
        cached = RequirementAnalysis.objects.filter(
            document_hash=document_hash
        ).first()
        # 验证缓存数据：如果质量评分中有 error 字段（之前失败的记录），跳过缓存
        if cached is not None:
            qs = cached.quality_score
            if isinstance(qs, dict) and 'error' in qs:
                # 缓存数据无效（先前分析失败），删除旧记录并返回 None 让系统重新分析
                cached.delete()
                return None
        return cached

    def analyze(self, document_name: str, markdown_content: str,
                progress_manager: Optional[TaskProgressManager] = None) -> RequirementAnalysis:
        """执行完整的分析管道"""

        document_hash = self.compute_document_hash(markdown_content)

        # 缓存命中检查
        cached = self.find_cached_analysis(document_hash)
        if cached:
            self.logger.info(f"缓存命中: {document_name} (hash={document_hash[:12]}...)")
            if progress_manager:
                progress_manager.complete_stage("scoring")
                progress_manager.complete_stage("deep_analysis")
                progress_manager.complete_stage("summarize")
                progress_manager.set_completed(
                    result={"id": cached.id, "cached": True},
                    message="使用缓存的分析结果"
                )
            return cached

        # Phase 1: 概要分析
        if progress_manager:
            progress_manager.start_stage("scoring", "质量评分与分类统计")

        quality_result = self._safe_analyze(self.quality_scorer.analyze, markdown_content, "quality_scorer")
        category_result = self._safe_analyze(self.category_statistician.analyze, markdown_content, "category_statistician")

        if progress_manager:
            progress_manager.complete_stage("scoring")

        # Phase 2: 深度分析（并行执行，最多2个并发避免 API 限速）
        if progress_manager:
            progress_manager.start_stage("deep_analysis", "深度分析（完整度/风险/冲突/可测试性）")

        phase2_results = {}
        phase2_lock = threading.Lock()

        def run_phase2_agent(name: str, analyze_func, content: str):
            result = self._safe_analyze(analyze_func, content, name)
            with phase2_lock:
                phase2_results[name] = result

        agents = [
            ("completeness", self.completeness_checker.analyze),
            ("risk", self.risk_identifier.analyze),
            ("consistency", self.consistency_checker.analyze),
            ("testability", self.testability_rater.analyze),
        ]
        # 每次并行2个
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

        # 检查是否所有 agent 均失败（API key 无效等全局性问题）
        if isinstance(quality_result, dict) and 'error' in quality_result:
            error_msg = str(quality_result.get('error', '未知错误'))
            # 检查是否为认证错误
            if '401' in error_msg or 'AuthenticationError' in error_msg or 'api_key' in error_msg.lower():
                raise RuntimeError(
                    f"LLM 服务认证失败，请检查 API Key 配置。详情: {error_msg[:200]}"
                )
            raise RuntimeError(f"质量评分失败: {error_msg[:200]}")

        strategy = self._compute_generation_strategy(
            quality_result, category_result, phase2_results
        )

        # 存入数据库
        analysis = RequirementAnalysis.objects.create(
            document_name=document_name,
            document_hash=document_hash,
            content_preview=markdown_content[:500],
            content=markdown_content,
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
            progress_manager.set_completed()

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

        # 基础场景权重
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

        # 高风险区域提取
        risk_data = phase2.get("risk", {}) if isinstance(phase2.get("risk"), dict) else {}
        risk_items = risk_data.get("risk_items", []) if isinstance(risk_data, dict) else []
        focus_areas = []
        for item in risk_items:
            if isinstance(item, dict) and item.get("severity") == "high":
                location = item.get("location", {})
                focus_areas.append({
                    "area": location.get("section", "未知") if isinstance(location, dict) else "未知",
                    "risk_level": "high",
                    "extra_cases": 3,
                })

        return {
            "case_count": 15,
            "scenario_weights": scenario_weights,
            "focus_areas": focus_areas,
            "quality_suggestions": [],
        }
