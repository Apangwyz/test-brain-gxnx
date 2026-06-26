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
