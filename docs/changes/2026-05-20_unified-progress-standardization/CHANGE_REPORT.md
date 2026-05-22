# 统一进度管理规范化改造变更报告

## 变更基本信息

- **变更日期**: 2026-05-20
- **变更类型**: 架构重构与标准化
- **变更负责人**: 开发团队
- **关联 Issue**: 文件上传及内容生成业务场景规范化改造

---

## 变更概述

本次变更针对项目中所有涉及文件上传及内容生成的业务场景进行统一规范化改造，建立统一的进度管理标准和交互体验。

**改造范围**:
1. **统一进度管理组件**: 创建 `CommonProgressManager` 前端组件，支持文件上传和内容生成进度展示
2. **统一后端进度API**: 实现 `GlobalProgressRegistry` 和 `TaskProgressManager`，支持 SSE 实时进度推送
3. **模块改造**: 对 `iface_case_generator`、`java_code_analyzer`、`prd_analyzer` 三个模块进行规范化改造
4. **响应式设计**: 确保进度组件在不同设备上均有良好的显示效果

---

## 问题描述

### 问题 1: 文件上传功能缺乏统一标准

**现象**:
- 各模块上传组件状态标记不统一
- 上传失败时错误提示信息不清晰
- 缺乏重试机制
- 没有上传进度可视化展示
- 不支持大文件分片上传

**影响范围**:
- iface_case_generator、java_code_analyzer、prd_analyzer 模块

### 问题 2: 内容生成进度展示不一致

**现象**:
- 各模块生成进度页面样式和交互不一致
- 缺乏总体进度百分比、当前处理阶段说明、预计剩余时间等关键信息
- 部分模块不支持取消操作
- 生成完成后缺乏统一的结果预览和导出功能

**影响范围**:
- 所有涉及内容生成的模块

### 问题 3: 缺乏统一的交互标准

**现象**:
- 用户操作体验不一致
- 操作结果反馈机制不统一
- 状态变更未同步更新到业务数据记录

**影响范围**:
- 所有涉及文件上传和内容生成的业务场景

---

## 解决方案

### 1. 统一前端进度管理组件

**文件**: `apps/utils/static/common_progress.js`

**核心实现**:

```javascript
class CommonProgressManager {
    constructor(options = {}) {
        // 配置项
        this.config = {
            progressUrl: '/api/progress/',
            cancelUrl: '/api/cancel/',
            moduleName: 'default',
            allowBackground: true,
            showFloatButton: true,
            ...options
        };
        // 状态管理
        this.taskId = null;
        this.eventSource = null;
        this.isActive = false;
        this.currentProgress = 0;
        this.startTime = null;
        this.estimatedRemainingTime = 0;
        // 步骤定义
        this.steps = [];
    }
    
    // 显示上传进度
    showUploadProgress(options = {}) {
        this.createUploadModal(options);
        // ...
    }
    
    // 显示生成进度
    showProgress(options = {}) {
        this.createProgressModal(options);
        this.startTime = Date.now();
        // ...
    }
    
    // 开始监听进度（SSE）
    startProgressStream(taskId) {
        this.taskId = taskId;
        this.eventSource = new EventSource(`${this.config.progressUrl}${taskId}/`);
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateProgress(data);
            // 更新悬浮按钮进度
            if (this.isBackgroundMode) {
                this.updateFloatButtonProgress(this.currentProgress);
            }
        };
    }
}
```

**关键特性**:
- ✅ 统一的上传状态标记（上传中、上传成功、上传失败）
- ✅ 上传失败重试机制
- ✅ 上传进度可视化展示
- ✅ 支持大文件分片上传
- ✅ 实时进度百分比显示
- ✅ 当前处理阶段说明
- ✅ 预计剩余时间计算
- ✅ 取消操作支持
- ✅ 结果预览和导出功能
- ✅ 悬浮按钮唤醒入口
- ✅ 响应式设计

### 2. 统一后端进度管理API

**文件**: `apps/utils/progress_manager.py`

**核心实现**:

```python
class GlobalProgressRegistry:
    """全局进度注册表（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._progress_map = {}
                    cls._listeners = {}
        return cls._instance
    
    def register_task(self, task_id: str, stages: List[StageInfo]) -> None:
        """注册任务"""
        with self._lock:
            self._progress_map[task_id] = ProgressData(
                task_id=task_id,
                status=TaskStatus.PENDING,
                stages=stages
            )
            self._listeners[task_id] = []
    
    def update_stage(self, task_id: str, stage_name: str, 
                    status: StageStatus, details: str = None) -> None:
        """更新阶段状态"""
        with self._lock:
            progress_data = self._progress_map.get(task_id)
            if not progress_data:
                return
            
            for stage in progress_data.stages:
                if stage.stage == stage_name:
                    stage.status = status
                    if details:
                        stage.details = details
            
            # 更新总体进度
            self._update_overall_progress(task_id)
```

**关键特性**:
- ✅ 线程安全的单例模式
- ✅ 任务注册与进度管理
- ✅ 阶段状态更新
- ✅ SSE实时推送支持
- ✅ 数据一致性保证
- ✅ 操作原子性

### 3. 模块规范化改造

#### 3.1 iface_case_generator 模块

**修改文件**:
- `apps/ai_agents/iface_case_generator/templates/iface_case_generator.html`
- `apps/ai_agents/iface_case_generator/static/iface_case_generator.js`

**改造内容**:
- 集成 CommonProgressManager 组件
- 添加文件上传状态标记
- 实现进度页面展示
- 添加取消操作功能

#### 3.2 java_code_analyzer 模块

**修改文件**:
- `apps/ai_agents/java_code_analyzer/templates/java_code_analyzer.html`
- `apps/ai_agents/java_code_analyzer/static/java_code_analyzer.js`
- `apps/ai_agents/java_code_analyzer/views.py`

**改造内容**:
- 集成 CommonProgressManager 组件
- 添加进度页面展示
- 实现实时进度更新
- 添加取消操作功能
- 后端添加进度管理支持

#### 3.3 prd_analyzer 模块

**修改文件**:
- `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html`
- `apps/ai_agents/prd_analyzer/static/prd_analyzer.js`
- `apps/ai_agents/prd_analyzer/views.py`
- `apps/ai_agents/prd_analyzer/urls.py`

**改造内容**:
- 集成 CommonProgressManager 组件
- 添加 PDF 文件上传支持
- 实现进度页面展示
- 添加取消操作功能
- 后端实现 PDF 文本提取和进度管理

### 4. 统一样式与响应式设计

**文件**: `apps/utils/static/common_progress.css`

**关键样式特性**:
- ✅ 响应式布局（支持桌面端、平板、移动端）
- ✅ 弹性进度条设计
- ✅ 模态框自适应尺寸
- ✅ 悬浮按钮固定定位
- ✅ 平滑动画效果

---

## 修改文件清单

| 文件路径 | 修改类型 | 修改内容 | 说明 |
|---------|---------|---------|------|
| `apps/utils/static/common_progress.js` | 新增 | 统一前端进度管理组件 | 核心组件 |
| `apps/utils/static/common_progress.css` | 新增 | 统一进度管理样式 | 响应式设计 |
| `apps/utils/progress_manager.py` | 新增 | 后端进度管理API | SSE支持 |
| `apps/utils/progress_registry.py` | 新增 | 进度注册表实现 | 单例模式 |
| `apps/utils/progress_schema.py` | 新增 | 进度数据模型定义 | Pydantic模型 |
| `apps/utils/sse_bus.py` | 新增 | SSE消息总线 | 实时推送 |
| `apps/ai_agents/iface_case_generator/templates/iface_case_generator.html` | 修改 | 集成统一进度组件 | 前端模板 |
| `apps/ai_agents/iface_case_generator/static/iface_case_generator.js` | 修改 | 使用CommonProgressManager | 前端逻辑 |
| `apps/ai_agents/java_code_analyzer/templates/java_code_analyzer.html` | 修改 | 集成统一进度组件 | 前端模板 |
| `apps/ai_agents/java_code_analyzer/static/java_code_analyzer.js` | 修改 | 使用CommonProgressManager | 前端逻辑 |
| `apps/ai_agents/java_code_analyzer/views.py` | 修改 | 添加进度管理支持 | 后端视图 |
| `apps/ai_agents/prd_analyzer/templates/prd_analyzer.html` | 修改 | 集成统一进度组件 | 前端模板 |
| `apps/ai_agents/prd_analyzer/static/prd_analyzer.js` | 修改 | 使用CommonProgressManager | 前端逻辑 |
| `apps/ai_agents/prd_analyzer/views.py` | 修改 | 添加PDF支持和进度管理 | 后端视图 |
| `apps/ai_agents/prd_analyzer/urls.py` | 修改 | 添加文件上传和分析API路由 | URL配置 |

---

## 测试验证

### 1. 文件上传功能测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| 上传小文件 | 显示"上传中"状态，完成后显示"上传成功" | ✅ 通过 |
| 上传大文件 (>10MB) | 自动分片上传，显示进度百分比 | ✅ 通过 |
| 上传失败 | 显示"上传失败"状态和错误信息 | ✅ 通过 |
| 点击重试按钮 | 重新上传文件 | ✅ 通过 |
| 上传状态实时更新 | 进度条实时更新 | ✅ 通过 |

### 2. 内容生成功能测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| 开始生成 | 显示进度页面，包含总体进度百分比 | ✅ 通过 |
| 阶段切换 | 显示当前处理阶段说明 | ✅ 通过 |
| 预计剩余时间 | 动态计算并显示 | ✅ 通过 |
| 点击取消按钮 | 取消任务并返回上一页 | ✅ 通过 |
| 生成完成 | 显示结果预览 | ✅ 通过 |
| 点击导出按钮 | 下载生成结果 | ✅ 通过 |

### 3. 响应式设计测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| 桌面端显示 | 完整布局，所有功能正常 | ✅ 通过 |
| 平板端显示 | 自适应布局，功能正常 | ✅ 通过 |
| 移动端显示 | 紧凑布局，触控友好 | ✅ 通过 |

### 4. 后端API测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| SSE连接建立 | 成功建立实时连接 | ✅ 通过 |
| 进度更新推送 | 实时接收进度数据 | ✅ 通过 |
| 并发请求处理 | 正确处理多个并发任务 | ✅ 通过 |
| 任务取消 | 成功取消指定任务 | ✅ 通过 |

---

## 使用示例

### 1. 前端集成示例

```javascript
// 创建进度管理器实例
const progressManager = new CommonProgressManager({
    moduleName: 'iface_case_generator',
    showFloatButton: true
});

// 显示上传进度
progressManager.showUploadProgress({
    title: '上传接口文档',
    onComplete: (result) => {
        console.log('上传完成:', result);
    },
    onError: (error) => {
        console.error('上传失败:', error);
    }
});

// 显示生成进度
progressManager.showProgress({
    title: '生成测试用例',
    steps: [
        { name: '解析文档', weight: 20 },
        { name: '分析接口', weight: 30 },
        { name: '生成用例', weight: 40 },
        { name: '导出结果', weight: 10 }
    ],
    onCancel: () => {
        console.log('任务已取消');
    }
});

// 启动进度监听
progressManager.startProgressStream(taskId);
```

### 2. 后端进度更新示例

```python
from apps.utils.progress_manager import GlobalProgressRegistry

# 获取进度注册表实例
registry = GlobalProgressRegistry()

# 注册任务
registry.register_task(
    task_id=task_id,
    stages=[
        StageInfo(stage='解析文档', status=StageStatus.PENDING),
        StageInfo(stage='分析接口', status=StageStatus.PENDING),
        StageInfo(stage='生成用例', status=StageStatus.PENDING),
        StageInfo(stage='导出结果', status=StageStatus.PENDING)
    ]
)

# 更新阶段状态
registry.update_stage(
    task_id=task_id,
    stage_name='解析文档',
    status=StageStatus.RUNNING,
    details='正在解析接口文档...'
)

# 完成阶段
registry.update_stage(
    task_id=task_id,
    stage_name='解析文档',
    status=StageStatus.COMPLETED,
    details='文档解析完成'
)
```

---

## 验证清单

- [x] 统一前端进度管理组件创建完成
- [x] 统一后端进度管理API创建完成
- [x] SSE实时进度推送实现完成
- [x] iface_case_generator模块改造完成
- [x] java_code_analyzer模块改造完成
- [x] prd_analyzer模块改造完成
- [x] 文件上传状态标记实现完成
- [x] 上传失败重试机制实现完成
- [x] 上传进度可视化实现完成
- [x] 大文件分片上传支持完成
- [x] 进度页面展示实现完成
- [x] 总体进度百分比显示完成
- [x] 当前处理阶段说明实现完成
- [x] 预计剩余时间计算完成
- [x] 取消操作功能实现完成
- [x] 结果预览和导出功能完成
- [x] 响应式设计实现完成
- [x] 悬浮按钮唤醒入口完成
- [x] 统一交互标准实现完成
- [x] 测试验证通过

---

## 后续优化建议

### 短期优化
1. 添加任务队列管理功能
2. 支持任务暂停/继续操作
3. 添加任务历史记录查询
4. 实现文件断点续传功能

### 长期优化
1. 支持多任务并行处理
2. 添加任务优先级管理
3. 实现分布式任务调度
4. 添加任务超时自动处理
5. 实现智能重试策略

---

## 变更记录

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-05-20 | 创建 | 统一进度管理组件设计 |
| 2026-05-20 | 实现 | 前端CommonProgressManager组件开发 |
| 2026-05-20 | 实现 | 后端进度管理API开发 |
| 2026-05-20 | 改造 | iface_case_generator模块改造 |
| 2026-05-20 | 改造 | java_code_analyzer模块改造 |
| 2026-05-20 | 改造 | prd_analyzer模块改造 |
| 2026-05-20 | 测试 | 功能测试验证 |
| 2026-05-20 | 归档 | 变更文档整理归档 |

---

## 相关文档

- [功能增强报告](../2026-05-19_feature-enhancements/CHANGE_REPORT.md)
- [进度按钮修复报告](../2026-05-19_progress-button-fix/CHANGE_REPORT.md)
- [日志长度修复报告](../2026-05-19_log-length-fix/CHANGE_REPORT.md)
- [测试用例生成器修复报告](../2026-05-19_test-case-generator-fix/CHANGE_REPORT.md)
- [项目初始化报告](../2024-12-00_project-initialization/CHANGE_REPORT.md)