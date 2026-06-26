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
