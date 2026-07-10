"""SRS 生成提示词管理"""
from pathlib import Path
import yaml
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate


class SRSGeneratorPrompt:
    """SRS 生成提示词管理器"""

    _config_cache = None

    def __init__(self):
        config_path = Path(__file__).parent / "configs" / "srs_prompt_config.yaml"
        self.config = self._load_config(config_path)

    @classmethod
    def _load_config(cls, config_path: Path):
        if cls._config_cache is None:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config_cache = yaml.safe_load(f)
        return cls._config_cache

    def get_srs_generation_prompt(self) -> ChatPromptTemplate:
        """获取完整 SRS 生成的提示词模板"""
        cfg = self.config["srs_generation"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])

    def get_srs_section_prompt(self) -> ChatPromptTemplate:
        """获取单章节重新生成的提示词模板"""
        cfg = self.config["srs_section_regeneration"]
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(cfg["system_template"]),
            HumanMessagePromptTemplate.from_template(cfg["human_template"]),
        ])
