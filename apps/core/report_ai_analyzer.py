"""
报告 AI 分析模块
使用项目已有的 LLM 能力对测试执行结果进行智能分析
"""
import json
from typing import Any

from apps.utils.logger_manager import get_logger
from apps.llm.base import LLMServiceFactory

logger = get_logger("report_ai_analyzer")

SYSTEM_PROMPT = """你是一个资深的软件测试质量分析师。你会收到一份测试执行报告数据，请基于此数据进行专业分析。

你需要输出三部分内容，以 JSON 格式返回（不要包含额外说明文字）：

1. failure_analysis: 列表，对每个失败用例分析可能的根因。每项包含：
   - case_title: 用例标题
   - probable_cause: 推测的失败原因（1-2句话）
   - severity: 严重程度（high/medium/low）

2. risk_assessment: 字符串，整体质量风险评估（2-3句话）。
   包括：基于通过率的风险等级、建议优先修复的用例、对发布的影响。

3. improvement_suggestions: 字符串，基于失败模式给出团队改进建议（2-3句话）。
   包括：测试用例本身的质量、流程改进、自动化覆盖等方面。

请严格输出如下 JSON 格式（不要 markdown 代码块标记）：
{"failure_analysis": [{"case_title": "...", "probable_cause": "...", "severity": "high/medium/low"}], "risk_assessment": "...", "improvement_suggestions": "..."}"""


class ReportAIAnalyzer:
    """测试报告 AI 分析器"""

    def __init__(self):
        self.llm = LLMServiceFactory.create_with_fallback(
            agent_name="report_ai_analyzer"
        )

    def analyze(self, execution_summary: dict,
                by_priority: dict,
                failed_details: list[dict]) -> dict:
        """对测试执行结果进行 AI 分析"""
        if not failed_details:
            logger.info("无失败用例，跳过 AI 分析")
            return self._empty_result()

        context = self._build_context(execution_summary, by_priority, failed_details)
        logger.info(
            f"开始 AI 分析: 总计={execution_summary.get('total', 0)}, "
            f"失败={execution_summary.get('failed', 0)}, "
            f"通过率={execution_summary.get('pass_rate', 0)}%"
        )

        try:
            raw = self.llm.invoke([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ])
            content = raw.content if hasattr(raw, "content") else str(raw)
            result = self._parse_response(content)
            logger.info("AI 分析完成")
            return result
        except Exception as e:
            logger.error(f"AI 分析调用失败: {e}", exc_info=True)
            return self._empty_result()

    def _build_context(self, execution_summary: dict,
                       by_priority: dict,
                       failed_details: list[dict]) -> str:
        """构建 LLM 输入上下文"""
        lines = ["## 测试执行概览"]
        lines.append(json.dumps(execution_summary, ensure_ascii=False, indent=2))
        lines.append("\n## 按优先级统计")
        lines.append(json.dumps(by_priority, ensure_ascii=False, indent=2))
        lines.append("\n## 失败用例详情")
        for fd in failed_details:
            lines.append(
                f"- [{fd.get('priority', '').upper()}] {fd.get('title', '')}: "
                f"{fd.get('error', '')}"
            )
        return "\n".join(lines)

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 返回的 JSON"""
        content = content.strip()
        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if "```" in content:
                content = content.rsplit("```", 1)[0]
        content = content.strip()

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("AI 返回内容无法解析为 JSON，使用原始文本")
            return {
                "failure_analysis": [],
                "risk_assessment": content,
                "improvement_suggestions": "",
            }

        return {
            "failure_analysis": result.get("failure_analysis", []),
            "risk_assessment": result.get("risk_assessment", ""),
            "improvement_suggestions": result.get("improvement_suggestions", ""),
        }

    def _empty_result(self) -> dict:
        return {
            "failure_analysis": [],
            "risk_assessment": "",
            "improvement_suggestions": "",
        }
