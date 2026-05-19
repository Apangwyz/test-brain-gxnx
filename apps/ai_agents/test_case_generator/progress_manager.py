"""
测试用例生成进度管理器
用于管理生成过程中的实时进度反馈
"""
import json
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid


class GenerationStage(Enum):
    """生成阶段枚举"""
    INITIALIZING = "initializing"           # 初始化
    ANALYZING_REQUIREMENT = "analyzing"     # 分析需求
    RETRIEVING_KNOWLEDGE = "retrieving"     # 检索知识库
    GENERATING_TESTCASES = "generating"     # 生成测试用例
    VALIDATING_RESULTS = "validating"       # 验证结果
    COMPLETED = "completed"                 # 完成
    ERROR = "error"                         # 错误


@dataclass
class ProgressStep:
    """进度步骤"""
    stage: str
    title: str
    description: str
    status: str  # pending, running, completed, error
    timestamp: float
    details: Optional[str] = None


@dataclass
class GenerationProgress:
    """生成进度数据"""
    task_id: str
    overall_progress: int  # 0-100
    current_stage: str
    status: str  # running, completed, error
    steps: list
    message: Optional[str] = None
    result: Optional[Any] = None


class ProgressManager:
    """进度管理器"""
    
    # 阶段定义及其权重
    STAGES = {
        GenerationStage.INITIALIZING: {
            'weight': 5,
            'title': '初始化',
            'description': '准备生成环境...'
        },
        GenerationStage.ANALYZING_REQUIREMENT: {
            'weight': 15,
            'title': '分析需求',
            'description': '正在理解您的需求描述...'
        },
        GenerationStage.RETRIEVING_KNOWLEDGE: {
            'weight': 20,
            'title': '检索知识库',
            'description': '从知识库中检索相关信息...'
        },
        GenerationStage.GENERATING_TESTCASES: {
            'weight': 45,
            'title': '生成测试用例',
            'description': 'AI正在生成测试用例...'
        },
        GenerationStage.VALIDATING_RESULTS: {
            'weight': 15,
            'title': '验证结果',
            'description': '验证生成的测试用例...'
        },
        GenerationStage.COMPLETED: {
            'weight': 0,
            'title': '完成',
            'description': '测试用例生成完成！'
        }
    }
    
    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or str(uuid.uuid4())
        self.steps: Dict[GenerationStage, ProgressStep] = {}
        self.current_stage: Optional[GenerationStage] = None
        self.status = "running"
        self.message = ""
        self.result = None
        self._callbacks: list = []
        self._initialize_steps()
    
    def _initialize_steps(self):
        """初始化所有步骤"""
        import time
        for stage, config in self.STAGES.items():
            self.steps[stage] = ProgressStep(
                stage=stage.value,
                title=config['title'],
                description=config['description'],
                status='pending',
                timestamp=time.time()
            )
    
    def register_callback(self, callback: Callable):
        """注册进度更新回调"""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self):
        """通知所有回调"""
        progress_data = self.get_progress()
        for callback in self._callbacks:
            try:
                callback(progress_data)
            except Exception as e:
                print(f"回调执行失败: {e}")
    
    def start_stage(self, stage: GenerationStage, details: Optional[str] = None):
        """开始一个阶段"""
        import time
        
        # 将之前运行的阶段标记为完成
        if self.current_stage and self.current_stage != stage:
            self.steps[self.current_stage].status = 'completed'
        
        # 更新当前阶段
        self.current_stage = stage
        self.steps[stage].status = 'running'
        self.steps[stage].timestamp = time.time()
        if details:
            self.steps[stage].details = details
        
        self._notify_callbacks()
    
    def complete_stage(self, stage: GenerationStage, details: Optional[str] = None):
        """完成一个阶段"""
        self.steps[stage].status = 'completed'
        if details:
            self.steps[stage].details = details
        self._notify_callbacks()
    
    def update_stage_details(self, stage: GenerationStage, details: str):
        """更新阶段详情"""
        self.steps[stage].details = details
        self._notify_callbacks()
    
    def set_error(self, message: str):
        """设置错误状态"""
        self.status = 'error'
        self.message = message
        if self.current_stage:
            self.steps[self.current_stage].status = 'error'
        self._notify_callbacks()
    
    def set_completed(self, result: Any):
        """设置完成状态"""
        self.status = 'completed'
        self.result = result
        if self.current_stage:
            self.steps[self.current_stage].status = 'completed'
        self.steps[GenerationStage.COMPLETED].status = 'completed'
        self._notify_callbacks()
    
    def _calculate_progress(self) -> int:
        """计算总体进度"""
        if self.status == 'completed':
            return 100
        if self.status == 'error':
            return 0
        
        total_weight = sum(config['weight'] for config in self.STAGES.values())
        completed_weight = 0
        
        for stage, config in self.STAGES.items():
            step = self.steps[stage]
            if step.status == 'completed':
                completed_weight += config['weight']
            elif step.status == 'running' and config['weight'] > 0:
                # 当前运行中的阶段给予50%权重
                completed_weight += config['weight'] * 0.5
        
        return int((completed_weight / total_weight) * 100) if total_weight > 0 else 0
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度数据"""
        return {
            'task_id': self.task_id,
            'overall_progress': self._calculate_progress(),
            'current_stage': self.current_stage.value if self.current_stage else None,
            'status': self.status,
            'message': self.message,
            'steps': [
                {
                    'stage': step.stage,
                    'title': step.title,
                    'description': step.description,
                    'status': step.status,
                    'details': step.details,
                    'timestamp': step.timestamp
                }
                for step in self.steps.values()
            ],
            'result': self.result
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.get_progress(), ensure_ascii=False)


# 全局进度管理器存储
_progress_managers: Dict[str, ProgressManager] = {}


def get_progress_manager(task_id: str) -> Optional[ProgressManager]:
    """获取进度管理器"""
    return _progress_managers.get(task_id)


def create_progress_manager(task_id: Optional[str] = None) -> ProgressManager:
    """创建进度管理器"""
    manager = ProgressManager(task_id)
    _progress_managers[manager.task_id] = manager
    return manager


def remove_progress_manager(task_id: str):
    """移除进度管理器"""
    if task_id in _progress_managers:
        del _progress_managers[task_id]
