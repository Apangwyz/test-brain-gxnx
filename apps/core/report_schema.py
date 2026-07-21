from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ExecutionSummary:
    """执行概览"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    pass_rate: float = 0.0
    total_duration: float = 0.0

    def __post_init__(self):
        self.pass_rate = round(self.pass_rate, 2)
        self.total_duration = round(self.total_duration, 2)


@dataclass
class PriorityStats:
    """优先级统计"""
    total: int = 0
    passed: int = 0
    failed: int = 0


@dataclass
class FailedDetail:
    """失败用例详情"""
    case_id: int = 0
    title: str = ""
    priority: str = ""
    error: str = ""
    suggestion: str = ""


@dataclass
class AiAnalysis:
    """AI 分析结果"""
    failure_analysis: list[dict] = field(default_factory=list)
    risk_assessment: str = ""
    improvement_suggestions: str = ""


@dataclass
class ReportData:
    """完整报告数据结构"""
    execution_summary: ExecutionSummary = field(default_factory=ExecutionSummary)
    by_priority: dict[str, PriorityStats] = field(default_factory=dict)
    failed_details: list[FailedDetail] = field(default_factory=list)
    ai_analysis: AiAnalysis = field(default_factory=AiAnalysis)

    def to_dict(self) -> dict:
        """递归转为 JSON 可序列化的字典"""
        raw = asdict(self)
        return raw

    @classmethod
    def from_dict(cls, data: dict) -> ReportData:
        """从 dict 恢复（用于读取已有报告）"""
        es = ExecutionSummary(**data.get("execution_summary", {}))
        bp = {
            k: PriorityStats(**v) for k, v in data.get("by_priority", {}).items()
        }
        fd = [FailedDetail(**d) for d in data.get("failed_details", [])]
        aa_raw = data.get("ai_analysis", {})
        aa = AiAnalysis(**aa_raw) if isinstance(aa_raw, dict) else AiAnalysis()
        return cls(
            execution_summary=es,
            by_priority=bp,
            failed_details=fd,
            ai_analysis=aa,
        )
