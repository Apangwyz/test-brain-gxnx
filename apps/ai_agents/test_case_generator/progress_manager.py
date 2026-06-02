"""
测试用例生成进度管理器 - 兼容层
用于管理生成过程中的实时进度反馈。

已集成到 apps.utils.progress_registry 中心注册表，所有进度数据统一通过 set_progress/get_progress 管理。
所有新代码应直接使用标准模型和 API。
"""
import json
import time
from typing import Dict, Any, Optional
from enum import Enum

from apps.utils.progress_schema import ProgressData, ProgressUpdate, TaskStatus as SchemaTaskStatus
from apps.utils.progress_registry import set_progress, get_progress


class GenerationStage(Enum):
    """生成阶段枚举"""
    INITIALIZING = "initializing"
    ANALYZING_REQUIREMENT = "analyzing"
    RETRIEVING_KNOWLEDGE = "retrieving"
    GENERATING_TESTCASES = "generating"
    VALIDATING_RESULTS = "validating"
    SAVING = "saving"
    COMPLETED = "completed"
    ERROR = "error"


class ProgressStep:
    """进度步骤"""
    def __init__(self, stage, title, description, status="pending", timestamp=None, details=None):
        self.stage = stage
        self.title = title
        self.description = description
        self.status = status
        self.timestamp = timestamp or time.time()
        self.details = details


class StageProgressManager:
    """进度管理器 - 委托到 apps.utils.progress_registry 中心注册表"""

    STAGES = {
        GenerationStage.INITIALIZING: {"weight": 5, "title": "初始化", "description": "准备生成环境..."},
        GenerationStage.ANALYZING_REQUIREMENT: {"weight": 15, "title": "分析需求", "description": "正在理解您的需求描述..."},
        GenerationStage.RETRIEVING_KNOWLEDGE: {"weight": 20, "title": "检索知识库", "description": "从知识库中检索相关信息..."},
        GenerationStage.GENERATING_TESTCASES: {"weight": 45, "title": "生成测试用例", "description": "AI正在生成测试用例..."},
        GenerationStage.VALIDATING_RESULTS: {"weight": 15, "title": "验证结果", "description": "验证生成的测试用例..."},
        GenerationStage.COMPLETED: {"weight": 0, "title": "完成", "description": "测试用例生成完成！"},
    }

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.steps = {}
        self.current_stage = None
        self.status = "running"
        self.message = ""
        self.result = None
        self._initialize_steps()
        set_progress(self.task_id, {"step": 0, "message": "任务已创建", "percentage": 0, "status": "running"})

    def _initialize_steps(self):
        for stage, config in self.STAGES.items():
            self.steps[stage] = ProgressStep(
                stage=stage.value, title=config["title"],
                description=config["description"], status="pending",
                timestamp=time.time(),
            )

    def _sync_to_registry(self):
        stage_index = self._get_current_stage_index()
        set_progress(self.task_id, {
            "step": stage_index,
            "message": self.message or (self.current_stage.value if self.current_stage else ""),
            "percentage": self._calculate_progress(),
            "status": self.status,
        })

    def _get_current_stage_index(self):
        if not self.current_stage:
            return 0
        stages_list = list(self.STAGES.keys())
        try:
            return stages_list.index(self.current_stage) + 1
        except ValueError:
            return 0

    def start_stage(self, stage, details=None):
        if self.current_stage and self.current_stage != stage:
            self.steps[self.current_stage].status = "completed"
        self.current_stage = stage
        self.steps[stage].status = "running"
        self.steps[stage].timestamp = time.time()
        self.message = details or self.STAGES.get(stage, {}).get("title", stage.value)
        if details:
            self.steps[stage].details = details
        self._sync_to_registry()

    def complete_stage(self, stage, details=None):
        self.steps[stage].status = "completed"
        if details:
            self.steps[stage].details = details
        self.message = details or self.STAGES.get(stage, {}).get("title", stage.value)
        self._sync_to_registry()

    def update_stage_details(self, stage, details):
        self.steps[stage].details = details
        self._sync_to_registry()

    def set_error(self, message):
        self.status = "error"
        self.message = message
        if self.current_stage:
            self.steps[self.current_stage].status = "error"
        self._sync_to_registry()

    def set_completed(self, result):
        self.status = "completed"
        self.result = result
        if self.current_stage:
            self.steps[self.current_stage].status = "completed"
        self.steps[GenerationStage.COMPLETED].status = "completed"
        self.message = "测试用例生成完成！"
        self._sync_to_registry()

    def _calculate_progress(self):
        if self.status == "completed":
            return 100
        if self.status == "error":
            return 0
        total_weight = sum(config["weight"] for config in self.STAGES.values())
        completed_weight = 0
        for stage, config in self.STAGES.items():
            step = self.steps[stage]
            if step.status == "completed":
                completed_weight += config["weight"]
            elif step.status == "running" and config["weight"] > 0:
                completed_weight += config["weight"] * 0.5
        return int((completed_weight / total_weight) * 100) if total_weight > 0 else 0

    def get_progress(self):
        return {
            "task_id": self.task_id,
            "overall_progress": self._calculate_progress(),
            "current_stage": self.current_stage.value if self.current_stage else None,
            "status": self.status,
            "message": self.message,
            "steps": [
                {"stage": step.stage, "title": step.title, "description": step.description,
                 "status": step.status, "details": step.details, "timestamp": step.timestamp}
                for step in self.steps.values()
            ],
            "result": self.result,
        }

    def to_json(self):
        return json.dumps(self.get_progress(), ensure_ascii=False)


ProgressManager = StageProgressManager

_progress_managers: Dict[str, StageProgressManager] = {}


def get_progress_manager(task_id: str) -> Optional[StageProgressManager]:
    return _progress_managers.get(task_id)


def create_progress_manager(task_id: Optional[str] = None) -> StageProgressManager:
    import uuid
    if task_id is None:
        task_id = str(uuid.uuid4())
    manager = StageProgressManager(task_id)
    _progress_managers[manager.task_id] = manager
    return manager


def remove_progress_manager(task_id: str) -> None:
    if task_id in _progress_managers:
        del _progress_managers[task_id]
    from apps.utils.progress_registry import clear_progress
    clear_progress(task_id)
