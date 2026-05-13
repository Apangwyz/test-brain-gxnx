from typing import Dict, Any, List, Optional, Tuple
import json

from apps.llm.base import BaseLLMService
from apps.knowledge.service import KnowledgeService
from .prompts import PrdAnalyserPrompt
# from langchain_core.messages import SystemMessage, HumanMessage
from apps.utils.logger_manager import get_logger

class PrdAnalyserAgent:
    """PRD分析Agent，用于从PRD文档中提取测试点和测试场景"""
    
    def __init__(self, llm_service: BaseLLMService, knowledge_service: KnowledgeService = None):
        self.llm_service = llm_service
        self.knowledge_service = knowledge_service
        self.prompt = PrdAnalyserPrompt()
        self.logger = get_logger(self.__class__.__name__)
    
    def analyse(self, markdown_content: str) -> Dict[str, Any]:
        """
        分析PRD文档，提取测试点和测试场景
        
        Args:
            markdown_content: Markdown格式的PRD文档内容
            
        Returns:
            包含测试点和测试场景的字典，格式为：
            {
                "test_points": [...],
                "summary": {...}
            }
        """
        try:
            self.logger.info(f"开始分析PRD文档，文档长度：{len(markdown_content)} 字符")
            
            # 使用prompt模板格式化消息
            messages = self.prompt.format_messages(markdown_content=markdown_content)
            
            self.logger.info(f"构建后的PRD分析提示词: \n{'='*50}\n{messages}\n{'='*50}")
            
            # 调用LLM服务
            response = self.llm_service.invoke(messages)
            result = response.content
            self.logger.info(f"LLM服务返回原始结果: \n{'='*50}\n{result}\n{'='*50}")
            
            # 解析JSON结果
            try:
                if "```json" in result:
                    json_str = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    json_str = result.split("```")[1].split("```")[0].strip()
                else:
                    json_str = result
                    
                raw_result = json.loads(json_str)
                validated_result = self._validate_analysis_result(raw_result)
                self.logger.info(
                    "成功解析并清洗PRD分析结果，合法测试点数量：%s，合法测试场景数量：%s",
                    len(validated_result["test_points"]),
                    sum(len(point["scenarios"]) for point in validated_result["test_points"])
                )

                return validated_result
                
            except json.JSONDecodeError as e:
                self.logger.error(f"解析JSON结果失败: {str(e)}")
                self.logger.error(f"原始响应: {result}")
                raise ValueError(f"无法解析生成的分析结果: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"PRD分析过程出错: {str(e)}", exc_info=True)
            raise Exception(f"PRD分析失败: {str(e)}")
    
    def _validate_analysis_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """清洗LLM返回的结果合法性过滤掉不合法项，并计算汇总summary信息"""
        if not isinstance(result, dict):
            raise ValueError("分析结果格式错误，期望为JSON对象")

        raw_points = result.get("test_points")
        if not isinstance(raw_points, list):
            self.logger.warning("分析结果中的test_points不是列表，将使用空列表进行处理")
            raw_points = []

        required_point_fields = {"id", "title", "description", "priority", "scenarios"}
        required_scenario_fields = {"id", "title", "description", "test_type"}

        valid_points: List[Dict[str, Any]] = []
        dropped_points = 0
        dropped_scenarios = 0

        for point in raw_points:
            if not isinstance(point, dict):
                dropped_points += 1
                continue

            if not required_point_fields.issubset(point.keys()):
                dropped_points += 1
                continue

            scenarios = point.get("scenarios")
            if not isinstance(scenarios, list):
                dropped_points += 1
                continue

            valid_scenarios: List[Dict[str, Any]] = []
            for scenario in scenarios:
                if not isinstance(scenario, dict):
                    dropped_scenarios += 1
                    continue
                if not required_scenario_fields.issubset(scenario.keys()):
                    dropped_scenarios += 1
                    continue
                valid_scenarios.append(scenario)

            if not valid_scenarios:
                dropped_points += 1
                continue

            cleaned_point = dict(point)
            cleaned_point["scenarios"] = valid_scenarios
            valid_points.append(cleaned_point)

        summary = self._build_summary(valid_points)

        if dropped_points or dropped_scenarios:
            self.logger.warning(
                "PRD分析结果已清洗：丢弃无效测试点 %s 个，无效测试场景 %s 个",
                dropped_points,
                dropped_scenarios,
            )

        return {
            "test_points": valid_points,
            "summary": summary,
        }

    def _build_summary(self, test_points: List[Dict[str, Any]]) -> Dict[str, int]:
        """根据合法测试点计算summary信息"""
        total_test_points = len(test_points)
        total_test_scenarios = sum(len(point["scenarios"]) for point in test_points)

        priority_stats = {"high": 0, "medium": 0, "low": 0}
        for point in test_points:
            normalized_priority = self._normalize_priority(point.get("priority"))
            if normalized_priority in priority_stats:
                priority_stats[normalized_priority] += 1

        return {
            "total_test_points": total_test_points,
            "total_test_scenarios": total_test_scenarios,
            "high_priority_points": priority_stats["high"],
            "medium_priority_points": priority_stats["medium"],
            "low_priority_points": priority_stats["low"],
        }

    @staticmethod
    def _normalize_priority(raw_priority: Optional[str]) -> str:
        """将优先级转换为统一格式"""
        if raw_priority is None:
            return "low"

        value = str(raw_priority).strip().lower()
        if value in {"高", "high", "p0"}:
            return "high"
        if value in {"中", "medium", "p1"}:
            return "medium"
        if value in {"低", "low", "p2", "p3"}:
            return "low"
        return "low"

