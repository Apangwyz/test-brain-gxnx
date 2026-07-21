"""
测试报告导入/解析引擎
支持 JUnit XML 和自定义 JSON 两种格式
"""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Tuple

from django.db import transaction

from ..core.models import TestReport
from .report_schema import (
    ReportData, ExecutionSummary, PriorityStats, FailedDetail,
)
from .report_ai_analyzer import ReportAIAnalyzer
from apps.utils.logger_manager import get_logger

logger = get_logger("report_importer")


class ReportImporter:
    """报告导入器"""

    SUPPORTED_EXTENSIONS = {".xml", ".json"}

    def __init__(self):
        self.ai_analyzer = ReportAIAnalyzer()

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    def import_report(self, file, user=None) -> TestReport:
        """完整导入流程：解析 → 分析 → 保存"""
        raw_content = file.read()
        filename = file.name
        logger.info(f"开始导入报告文件: {filename} (大小={len(raw_content)} bytes)")

        # 1. 解析
        report_data_obj, title = self.parse(raw_content, filename)

        # 2. AI 分析（仅在存在失败用例时）
        summary_dict = {
            "total": report_data_obj.execution_summary.total,
            "passed": report_data_obj.execution_summary.passed,
            "failed": report_data_obj.execution_summary.failed,
            "skipped": report_data_obj.execution_summary.skipped,
            "error": report_data_obj.execution_summary.error,
            "pass_rate": report_data_obj.execution_summary.pass_rate,
            "total_duration": report_data_obj.execution_summary.total_duration,
        }
        by_priority_dict = {
            k: {"total": v.total, "passed": v.passed, "failed": v.failed}
            for k, v in report_data_obj.by_priority.items()
        }
        failed_dicts = [
            {
                "case_id": d.case_id,
                "title": d.title,
                "priority": d.priority,
                "error": d.error,
                "suggestion": d.suggestion,
            }
            for d in report_data_obj.failed_details
        ]

        if summary_dict.get("failed", 0) > 0 or summary_dict.get("error", 0) > 0:
            try:
                ai_result = self.ai_analyzer.analyze(
                    execution_summary=summary_dict,
                    by_priority=by_priority_dict,
                    failed_details=failed_dicts,
                )
                report_data_obj.ai_analysis.failure_analysis = \
                    ai_result.get("failure_analysis", [])
                report_data_obj.ai_analysis.risk_assessment = \
                    ai_result.get("risk_assessment", "")
                report_data_obj.ai_analysis.improvement_suggestions = \
                    ai_result.get("improvement_suggestions", "")
                logger.info("导入报告的 AI 分析完成")
            except Exception as e:
                logger.error(f"导入报告 AI 分析失败: {e}", exc_info=True)

        # 3. 保存
        report = self._save_report(title, report_data_obj, filename, user)
        logger.info(f"报告导入完成: {report.title} (id={report.id})")
        return report

    # ------------------------------------------------------------------
    # 格式检测与解析
    # ------------------------------------------------------------------

    def detect_format(self, raw_content: bytes) -> str:
        """检测文件格式：xml / json / unknown"""
        stripped = raw_content.strip()
        if stripped.startswith(b"<"):
            return "xml"
        if stripped.startswith(b"{") or stripped.startswith(b"["):
            return "json"
        return "unknown"

    def parse(self, raw_content: bytes, filename: str = "") \
            -> Tuple[ReportData, str]:
        """将文件内容解析为 ReportData + 标题"""
        fmt = self.detect_format(raw_content)
        if fmt == "xml":
            return self._parse_junit_xml(raw_content, filename)
        elif fmt == "json":
            return self._parse_json(raw_content, filename)
        else:
            raise ValueError(
                f"无法识别文件格式: {filename}。"
                f"支持 .xml (JUnit) 和 .json 格式"
            )

    # ------------------------------------------------------------------
    # JUnit XML 解析
    # ------------------------------------------------------------------

    def _parse_junit_xml(self, raw: bytes, filename: str = "") -> Tuple[ReportData, str]:
        root = ET.fromstring(raw)
        suite = root if root.tag == "testsuite" else root.find(".//testsuite")
        if suite is None:
            # 兼容 <testsuites> 下有多个 <testsuite>
            suites = root.findall(".//testsuite")
            if suites:
                suite = suites[0]
        if suite is None:
            raise ValueError("JUnit XML 中未找到 <testsuite> 元素")

        total = int(suite.get("tests", 0))
        failed = int(suite.get("failures", 0))
        error = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        passed = total - failed - error - skipped
        suite_time = float(suite.get("time", 0))

        summary = ExecutionSummary(
            total=max(total, 0),
            passed=max(passed, 0),
            failed=max(failed, 0),
            skipped=max(skipped, 0),
            error=max(error, 0),
            pass_rate=(passed / total * 100) if total > 0 else 0.0,
            total_duration=suite_time,
        )

        failed_details = []
        idx = 0
        for tc in suite.findall("testcase"):
            classname = tc.get("classname", "")
            tc_name = tc.get("name", "")
            title = f"{classname}.{tc_name}" if classname else tc_name

            failure_el = tc.find("failure")
            if failure_el is not None:
                failed_details.append(FailedDetail(
                    case_id=idx,
                    title=title,
                    priority="p3",
                    error=(failure_el.text or failure_el.get("message", ""))[:500],
                    suggestion="",
                ))
                idx += 1

            error_el = tc.find("error")
            if error_el is not None:
                failed_details.append(FailedDetail(
                    case_id=idx,
                    title=title,
                    priority="p3",
                    error=(error_el.text or error_el.get("message", ""))[:500],
                    suggestion="",
                ))
                idx += 1

        # by_priority — JUnit 没有优先级，全部归入 p3
        by_priority = {
            "p3": PriorityStats(total=total, passed=passed, failed=failed + error),
        }

        suite_name = suite.get("name", filename)

        report_data = ReportData(
            execution_summary=summary,
            by_priority=by_priority,
            failed_details=failed_details,
        )

        return report_data, suite_name

    # ------------------------------------------------------------------
    # JSON 解析
    # ------------------------------------------------------------------

    def _parse_json(self, raw: bytes, filename: str = "") -> Tuple[ReportData, str]:
        data = json.loads(raw)

        # 尝试完整格式 → ReportData schema
        if "execution_summary" in data:
            return self._parse_full_json(data, filename)

        # 否则走简单格式
        return self._parse_simple_json(data)

    def _parse_full_json(self, data: dict, filename: str = "") -> Tuple[ReportData, str]:
        """完整格式：直接映射 ReportData schema"""
        return ReportData.from_dict(data), data.get("title", filename)

    def _parse_simple_json(self, data: dict) -> Tuple[ReportData, str]:
        """简单格式：{ total, passed, failed, skipped, error, duration, cases: [...] }"""
        total = int(data.get("total", 0))
        passed = int(data.get("passed", 0))
        failed = int(data.get("failed", 0))
        error = int(data.get("error", 0))
        skipped = int(data.get("skipped", 0))
        # 如果 total 为 0 但失败数量有值，尝试自动计算
        if total == 0 and (passed or failed):
            total = passed + failed + error + skipped

        summary = ExecutionSummary(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            error=error,
            pass_rate=(passed / total * 100) if total > 0 else 0.0,
            total_duration=float(data.get("duration", data.get("total_duration", 0))),
        )

        # 优先级统计（如果没有则从 cases 推算）
        by_priority_raw = data.get("by_priority", {})
        by_priority = {}
        for k, v in by_priority_raw.items():
            by_priority[k] = PriorityStats(**v)
        if not by_priority:
            by_priority["p3"] = PriorityStats(
                total=total, passed=passed, failed=failed + error,
            )

        # 失败用例
        cases = data.get("cases", data.get("failed_details", []))
        failed_details = []
        for i, c in enumerate(cases):
            status = c.get("status", "")
            if status in ("failed", "error") or not status:
                failed_details.append(FailedDetail(
                    case_id=int(c.get("id", i)),
                    title=c.get("title", c.get("name", f"用例 {i+1}")),
                    priority=c.get("priority", "p3"),
                    error=c.get("error", c.get("error_message", ""))[:500],
                    suggestion=c.get("suggestion", ""),
                ))

        report_data = ReportData(
            execution_summary=summary,
            by_priority=by_priority,
            failed_details=failed_details,
        )

        title = data.get("title", data.get("name", "导入报告"))
        return report_data, title

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _save_report(self, title: str, report_data_obj: ReportData,
                     filename: str, user) -> TestReport:
        report_data_dict = report_data_obj.to_dict()
        summary_text = \
            f"通过率 {report_data_obj.execution_summary.pass_rate:.1f}% " \
            f"(导入: {filename})"

        report = TestReport.objects.create(
            title=title,
            report_data=report_data_dict,
            summary=summary_text,
            generated_by=user,
        )
        return report
