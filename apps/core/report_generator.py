"""
测试报告生成服务
"""
from ..core.models import TestReport, TestExecutionBatch, TestExecutionRecord


class TestReportGenerator:
    """测试报告生成器"""

    def generate(self, batch: TestExecutionBatch, user=None) -> TestReport:
        """为指定执行批次生成报告"""
        records = TestExecutionRecord.objects.filter(
            test_case__in=batch.test_cases.all()
        )

        summary = self._compute_summary(records)

        report_data = {
            'execution_summary': summary,
            'by_priority': self._compute_by_priority(records),
            'failed_details': self._collect_failed_details(records),
            'ai_analysis': {},
        }

        return TestReport.objects.create(
            title=f"{batch.name} - 测试报告",
            batch=batch,
            system=batch.system,
            report_data=report_data,
            summary=f"通过率 {summary['pass_rate']:.1f}%",
            generated_by=user,
        )

    def _compute_summary(self, records):
        total = records.count()
        passed = records.filter(status='passed').count()
        failed = records.filter(status='failed').count()
        skipped = records.filter(status='skipped').count()
        error = records.filter(status='error').count()
        total_duration = sum(r.duration or 0 for r in records)
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            'total': total, 'passed': passed, 'failed': failed,
            'skipped': skipped, 'error': error,
            'pass_rate': round(pass_rate, 2),
            'total_duration': round(total_duration, 2),
        }

    def _compute_by_priority(self, records):
        result = {}
        for rec in records:
            priority = rec.test_case.priority or 'p3'
            if priority not in result:
                result[priority] = {'total': 0, 'passed': 0, 'failed': 0}
            result[priority]['total'] += 1
            if rec.status == 'passed':
                result[priority]['passed'] += 1
            elif rec.status == 'failed':
                result[priority]['failed'] += 1
        return result

    def _collect_failed_details(self, records):
        details = []
        for rec in records.filter(status__in=['failed', 'error']):
            details.append({
                'case_id': rec.test_case.id,
                'title': rec.test_case.title,
                'priority': rec.test_case.priority,
                'error': rec.error_message or '',
                'suggestion': '',
            })
        return details
