"""SRS 生成 Agent：根据 BRD 内容和分析结果，按 GB/T 9385 标准生成 SRS"""
import json
from typing import Dict, Any, Optional, List

from apps.llm.base import BaseLLMService
from apps.utils.logger_manager import get_logger
from .srs_prompts import SRSGeneratorPrompt


SRS_SECTION_TITLES: Dict[str, str] = {
    "introduction": "一、引言",
    "introduction.purpose": "1.1 目的",
    "introduction.scope": "1.2 范围",
    "introduction.definitions": "1.3 定义与缩略语",
    "introduction.references": "1.4 参考文献",
    "overall_description": "二、总体描述",
    "overall_description.product_overview": "2.1 产品概述",
    "overall_description.product_functions": "2.2 功能概要",
    "overall_description.user_characteristics": "2.3 用户特征",
    "overall_description.constraints": "2.4 约束",
    "overall_description.assumptions": "2.5 假设和依赖关系",
    "functional_requirements": "三、功能需求",
    "external_interfaces": "四、外部接口需求",
    "external_interfaces.user_interfaces": "4.1 用户接口",
    "external_interfaces.hardware_interfaces": "4.2 硬件接口",
    "external_interfaces.software_interfaces": "4.3 软件接口",
    "external_interfaces.communication_interfaces": "4.4 通信接口",
    "non_functional_requirements": "五、非功能需求",
    "non_functional_requirements.performance": "5.1 性能需求",
    "non_functional_requirements.security": "5.2 安全需求",
    "non_functional_requirements.usability": "5.3 可用性需求",
    "non_functional_requirements.reliability": "5.4 可靠性需求",
    "non_functional_requirements.maintainability": "5.5 可维护性需求",
    "data_requirements": "六、数据需求",
    "data_requirements.entities": "6.1 数据实体描述",
    "data_requirements.dictionary": "6.2 数据字典",
    "data_requirements.management": "6.3 数据管理要求",
    "appendix": "七、附录",
    "appendix.notes": "7.1 补充说明",
    "appendix.pending_items": "7.2 待确认事项",
}

SRS_ORDERED_KEYS: List[str] = [
    "introduction",
    "overall_description",
    "functional_requirements",
    "external_interfaces",
    "non_functional_requirements",
    "data_requirements",
    "appendix",
]


class SRSGenerator:
    """SRS 生成 Agent"""

    def __init__(self, llm_service: BaseLLMService):
        self.llm_service = llm_service
        self.prompt = SRSGeneratorPrompt()
        self.logger = get_logger(self.__class__.__name__)

    def generate(self, markdown_content: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据 BRD 内容和分析结果生成 SRS

        Args:
            markdown_content: BRD 文档的 Markdown 内容
            analysis_result: 需求分析结果字典，包含 quality_score, category_stats,
                           risk_identification, completeness 等

        Returns:
            结构化 SRS 字典
        """
        try:
            self.logger.info(f"开始生成 SRS，BRD 内容长度：{len(markdown_content)} 字符")

            # 整理分析摘要供 LLM 参考
            quality_score = analysis_result.get("quality_score", {})
            category_stats = analysis_result.get("category_stats", {})
            risk_data = analysis_result.get("risk_identification", {})
            completeness_data = analysis_result.get("completeness", {})

            # 构建分类摘要
            category_summary = self._format_category_summary(category_stats)
            # 构建风险摘要
            risk_summary = self._format_risk_summary(risk_data)
            # 构建完整度摘要
            completeness_summary = self._format_completeness_summary(completeness_data)

            # 获取提示词
            prompt = self.prompt.get_srs_generation_prompt()
            messages = prompt.format_messages(
                markdown_content=markdown_content,
                quality_score=quality_score.get("overall_score", "N/A"),
                category_summary=category_summary,
                risk_summary=risk_summary,
                completeness_summary=completeness_summary,
            )

            # 调用 LLM
            response = self.llm_service.invoke(messages)
            result = response.content
            self.logger.info(f"LLM SRS 生成完成，原始响应长度：{len(result)}")

            # 解析 JSON
            srs_data = self._parse_json_response(result)
            validated = self._validate_srs_structure(srs_data)
            self.logger.info("SRS 生成成功，章节完整")
            return validated

        except Exception as e:
            self.logger.error(f"SRS 生成失败: {str(e)}", exc_info=True)
            raise

    def regenerate_section(self, srs_context: Dict[str, Any], section_key: str,
                           current_content: str, user_feedback: str = "") -> str:
        """
        重新生成 SRS 的单个章节

        Args:
            srs_context: 完整 SRS 上下文
            section_key: 章节键路径
            current_content: 当前章节内容
            user_feedback: 用户修改要求

        Returns:
            重新生成后的章节内容（Markdown 字符串）
        """
        try:
            section_title = SRS_SECTION_TITLES.get(section_key, section_key)
            prompt = self.prompt.get_srs_section_prompt()
            messages = prompt.format_messages(
                srs_context=json.dumps(srs_context, ensure_ascii=False, indent=2),
                section_key=section_key,
                section_title=section_title,
                current_content=current_content,
                user_feedback=user_feedback or "请优化内容，使其更清晰、完整",
            )
            response = self.llm_service.invoke(messages)
            return response.content.strip()
        except Exception as e:
            self.logger.error(f"章节重新生成失败 [{section_key}]: {str(e)}", exc_info=True)
            raise

    def srs_to_markdown(self, srs_data: Dict[str, Any]) -> str:
        """
        将结构化 SRS 数据转换为 Markdown 文档

        Returns:
            Markdown 格式的完整 SRS 文档字符串
        """
        lines = []
        lines.append("# 软件需求规格说明书")
        lines.append("")
        lines.append("> 本文件由 TestBrain 系统根据业务需求文档（BRD）自动生成，遵循 GB/T 9385 标准。")
        lines.append("")

        # 遍历各章节
        for key in SRS_ORDERED_KEYS:
            section = srs_data.get(key)
            if section is None:
                continue

            section_title = SRS_SECTION_TITLES.get(key, key)
            lines.append(f"## {section_title}")
            lines.append("")

            if key == "functional_requirements":
                # 功能需求是列表，特殊处理
                if isinstance(section, list):
                    for fr in section:
                        if isinstance(fr, dict):
                            lines.append(f"### {fr.get('id', '')} {fr.get('name', '')}")
                            lines.append("")
                            lines.append(f"- **模块**: {fr.get('module', '')}")
                            lines.append(f"- **优先级**: {fr.get('priority', '')}")
                            lines.append(f"- **来源**: {fr.get('source', '')}")
                            lines.append("")
                            lines.append(f"{fr.get('description', '')}")
                            lines.append("")
            elif isinstance(section, dict):
                # 嵌套字典章节
                self._render_dict_section(lines, section, key)
            elif isinstance(section, str):
                lines.append(section)
                lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*报告由 TestBrain 系统自动生成*")
        return "\n".join(lines)

    def _render_dict_section(self, lines: list, section: Dict[str, Any], parent_key: str):
        """递归渲染字典类型的章节"""
        for sub_key, sub_val in section.items():
            full_key = f"{parent_key}.{sub_key}"
            sub_title = SRS_SECTION_TITLES.get(full_key, sub_key)

            if isinstance(sub_val, dict):
                lines.append(f"### {sub_title}")
                lines.append("")
                self._render_dict_section(lines, sub_val, full_key)
            elif isinstance(sub_val, str) and sub_val.strip():
                lines.append(f"### {sub_title}")
                lines.append("")
                lines.append(sub_val.strip())
                lines.append("")

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """从 LLM 响应中解析 JSON"""
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    def _validate_srs_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """验证并补充 SRS 结构"""
        required_keys = [
            "introduction", "overall_description", "functional_requirements",
            "external_interfaces", "non_functional_requirements",
            "data_requirements", "appendix",
        ]
        for key in required_keys:
            if key not in data:
                self.logger.warning(f"SRS 缺少章节: {key}，使用空占位")
                data[key] = {} if key != "functional_requirements" else []
        # 确保 functional_requirements 是列表
        if not isinstance(data.get("functional_requirements"), list):
            data["functional_requirements"] = []
        return data

    @staticmethod
    def _format_category_summary(category_stats: Dict[str, Any]) -> str:
        """格式化分类统计摘要"""
        cats = category_stats.get("categories", {})
        if isinstance(cats, dict):
            parts = []
            for k, v in cats.items():
                if isinstance(v, dict):
                    parts.append(f"{k}: {v.get('count', 0)}个({v.get('ratio', '0%')})")
                else:
                    parts.append(f"{k}: {v}")
            return "；".join(parts) if parts else "暂无分类数据"
        return str(cats)

    @staticmethod
    def _format_risk_summary(risk_data: Dict[str, Any]) -> str:
        """格式化风险摘要"""
        items = risk_data.get("risk_items", [])
        if not items:
            return "未识别到明显风险"
        high_risks = [r for r in items if isinstance(r, dict) and r.get("severity") == "high"]
        medium_risks = [r for r in items if isinstance(r, dict) and r.get("severity") == "medium"]
        parts = []
        if high_risks:
            parts.append(f"高风险 {len(high_risks)} 项")
        if medium_risks:
            parts.append(f"中风险 {len(medium_risks)} 项")
        parts.append(f"低风险 {len(items) - len(high_risks) - len(medium_risks)} 项")
        return "；".join(parts)

    @staticmethod
    def _format_completeness_summary(completeness_data: Dict[str, Any]) -> str:
        """格式化完整度摘要"""
        present = completeness_data.get("present_items", [])
        missing = completeness_data.get("missing_items", [])
        return f"已覆盖 {len(present)} 项，缺失 {len(missing)} 项"
