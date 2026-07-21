"""
测试报告生成服务
"""
from ..core.models import TestReport, TestExecutionBatch, TestExecutionRecord
from .report_schema import (
    ReportData, ExecutionSummary, PriorityStats, FailedDetail,
)
from .report_ai_analyzer import ReportAIAnalyzer
from apps.utils.logger_manager import get_logger

logger = get_logger("report_generator")


class TestReportGenerator:
    """测试报告生成器"""

    def generate(self, batch: TestExecutionBatch, user=None) -> TestReport:
        """为指定执行批次生成报告"""
        records = TestExecutionRecord.objects.filter(
            test_case__in=batch.test_cases.all()
        )

        # 1. 计算统计数据
        summary = self._compute_summary(records)
        by_priority = self._compute_by_priority(records)
        failed_details = self._collect_failed_details(records)

        # 2. 构建 schema 校验过的报告结构
        report_data_obj = ReportData(
            execution_summary=ExecutionSummary(**summary),
            by_priority={
                k: PriorityStats(**v) for k, v in by_priority.items()
            },
            failed_details=[
                FailedDetail(**d) for d in failed_details
            ],
        )

        # 3. 调用 AI 分析（仅在有失败用例时进行）
        if summary.get("failed", 0) > 0 or summary.get("error", 0) > 0:
            try:
                analyzer = ReportAIAnalyzer()
                ai_result = analyzer.analyze(
                    execution_summary=summary,
                    by_priority=by_priority,
                    failed_details=failed_details,
                )
                report_data_obj.ai_analysis.failure_analysis = \
                    ai_result.get("failure_analysis", [])
                report_data_obj.ai_analysis.risk_assessment = \
                    ai_result.get("risk_assessment", "")
                report_data_obj.ai_analysis.improvement_suggestions = \
                    ai_result.get("improvement_suggestions", "")
            except Exception as e:
                logger.error(f"AI 分析失败（不影响报告生成）: {e}", exc_info=True)

        report_data_dict = report_data_obj.to_dict()

        # 4. 检查是否已存在同批次报告（支持重新生成）
        existing = TestReport.objects.filter(batch=batch).first()
        if existing:
            existing.report_data = report_data_dict
            existing.summary = f"通过率 {summary['pass_rate']:.1f}%"
            existing.generated_by = user
            existing.save(update_fields=["report_data", "summary", "generated_by"])
            logger.info(f"报告已更新: {existing.title} (id={existing.id})")
            return existing

        report = TestReport.objects.create(
            title=f"{batch.name} - 测试报告",
            batch=batch,
            system=batch.system,
            report_data=report_data_dict,
            summary=f"通过率 {summary['pass_rate']:.1f}%",
            generated_by=user,
        )
        logger.info(f"报告已生成: {report.title} (id={report.id})")
        return report

    def _compute_summary(self, records):
        total = records.count()
        passed = records.filter(status="passed").count()
        failed = records.filter(status="failed").count()
        skipped = records.filter(status="skipped").count()
        error = records.filter(status="error").count()
        total_duration = sum(r.duration or 0 for r in records)
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error,
            "pass_rate": round(pass_rate, 2),
            "total_duration": round(total_duration, 2),
        }

    def _compute_by_priority(self, records):
        result = {}
        for rec in records:
            priority = rec.test_case.priority or "p3"
            if priority not in result:
                result[priority] = {"total": 0, "passed": 0, "failed": 0}
            result[priority]["total"] += 1
            if rec.status == "passed":
                result[priority]["passed"] += 1
            elif rec.status == "failed":
                result[priority]["failed"] += 1
        return result

    def _collect_failed_details(self, records):
        details = []
        for rec in records.filter(status__in=["failed", "error"]):
            details.append({
                "case_id": rec.test_case.id,
                "title": rec.test_case.title,
                "priority": rec.test_case.priority or "p3",
                "error": rec.error_message or "",
                "suggestion": "",
            })
        return details
