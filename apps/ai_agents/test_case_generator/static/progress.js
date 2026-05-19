/**
 * 测试用例生成进度管理器
 * Progress Manager for Test Case Generation
 */

class GenerationProgressManager {
    constructor() {
        this.taskId = null;
        this.eventSource = null;
        this.isActive = false;
        this.onCompleteCallback = null;
        this.onErrorCallback = null;
        this.steps = [];
        this.currentProgress = 0;
        this.isBackgroundMode = false;  // 后台模式标志
        this.backgroundTasks = new Map();  // 存储后台任务
        this.floatButton = null;  // 悬浮按钮引用
    }

    /**
     * 日志记录（用于调试）
     */
    log(message) {
        console.log(`[ProgressManager] ${message}`);
    }

    /**
     * 显示进度模态框
     */
    show() {
        this.createModal();
        const modal = document.getElementById('generation-progress-modal');
        if (modal) {
            modal.classList.add('active');
            this.isActive = true;
        }
    }

    /**
     * 隐藏进度模态框
     */
    hide(allowBackground = true) {
        const modal = document.getElementById('generation-progress-modal');
        if (modal) {
            modal.classList.remove('active');
            
            // 移除键盘事件监听器
            if (modal._keydownHandler) {
                document.removeEventListener('keydown', modal._keydownHandler);
                console.log('键盘事件监听器已移除');
            }
            
            setTimeout(() => {
                modal.remove();
                this.isActive = false;
            }, 300);
        }
        
        // 如果允许后台运行且任务未完成，则保持SSE连接
        if (allowBackground && this.taskId && this.currentProgress < 100) {
            this.isBackgroundMode = true;
            this.backgroundTasks.set(this.taskId, {
                progress: this.currentProgress,
                startTime: Date.now()
            });
            console.log('任务进入后台运行模式:', this.taskId);
            showNotification('任务已在后台运行，完成后将通知您', 'info');
            
            // 创建并显示悬浮按钮
            this.createFloatButton();
            this.showFloatButton();
        } else {
            this.closeEventSource();
            // 如果任务已完成或不允许后台运行，隐藏悬浮按钮
            this.hideFloatButton();
        }
    }

    /**
     * 创建进度模态框 HTML
     */
    createModal() {
        // 如果已存在则移除
        const existingModal = document.getElementById('generation-progress-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modal = document.createElement('div');
        modal.id = 'generation-progress-modal';
        modal.className = 'progress-modal';
        modal.innerHTML = `
            <div class="progress-panel" id="progress-panel">
                <div class="progress-header">
                    <h3><i class="fas fa-magic"></i> AI 正在生成测试用例</h3>
                    <p>请稍候，正在为您分析需求并生成测试用例...</p>
                </div>
                
                <div class="overall-progress">
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" id="overall-progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="progress-percentage">
                        <span class="percentage" id="progress-percentage">0</span>% 完成
                    </div>
                </div>
                
                <div class="steps-container" id="steps-container">
                    <!-- 步骤将动态插入这里 -->
                </div>
                
                <div class="progress-footer">
                    <span class="progress-status-text" id="progress-status-text">
                        <span class="status-running"><i class="fas fa-circle-notch fa-spin"></i> 正在处理...</span>
                    </span>
                    <div class="progress-actions">
                        <button class="background-btn" id="background-btn" type="button" style="display: none;" title="后台运行">
                            <i class="fas fa-window-minimize"></i> 后台运行
                        </button>
                        <button class="close-progress-btn" id="close-progress-btn" type="button" disabled title="处理中，无法关闭">
                            <i class="fas fa-spinner fa-spin"></i> 处理中...
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // 使用事件委托确保按钮能正常响应点击
        modal.addEventListener('click', (event) => {
            const backgroundBtn = document.getElementById('background-btn');
            const closeBtn = document.getElementById('close-progress-btn');
            const panel = document.getElementById('progress-panel');
            
            // 检查点击的是否是后台运行按钮
            if (backgroundBtn && (event.target === backgroundBtn || backgroundBtn.contains(event.target))) {
                event.preventDefault();
                event.stopPropagation();
                console.log('点击后台运行按钮');
                this.hide(true);
                return;
            }
            
            // 检查点击的是否是关闭按钮
            if (closeBtn && (event.target === closeBtn || closeBtn.contains(event.target))) {
                event.preventDefault();
                event.stopPropagation();
                console.log('点击关闭按钮，disabled:', closeBtn.disabled);
                if (!closeBtn.disabled) {
                    this.hide(false);
                }
                return;
            }
            
            // 点击模态框遮罩层（非面板区域）时不做任何操作，保持模态框打开
            // 用户只能通过按钮关闭模态框
        });
        
        // 添加键盘快捷键支持 (ESC键关闭)
        const handleKeydown = (event) => {
            if (event.key === 'Escape') {
                const closeBtn = document.getElementById('close-progress-btn');
                if (closeBtn && !closeBtn.disabled) {
                    console.log('按ESC键关闭模态框');
                    this.hide(false);
                }
            }
        };
        document.addEventListener('keydown', handleKeydown);
        
        // 保存引用以便在hide时移除事件监听器
        modal._keydownHandler = handleKeydown;
        
        console.log('进度模态框创建完成，按钮已绑定，键盘快捷键已注册');
    }

    /**
     * 初始化步骤显示
     */
    initializeSteps(steps) {
        this.steps = steps;
        const container = document.getElementById('steps-container');
        if (!container) return;

        container.innerHTML = '';
        
        const stepOrder = [
            'initializing',
            'analyzing',
            'retrieving',
            'generating',
            'validating',
            'completed'
        ];

        stepOrder.forEach((stage, index) => {
            const step = steps.find(s => s.stage === stage);
            if (!step) return;

            const stepElement = document.createElement('div');
            stepElement.className = `progress-step ${step.status}`;
            stepElement.id = `step-${stage}`;
            stepElement.innerHTML = this.createStepHTML(step);
            container.appendChild(stepElement);
        });
    }

    /**
     * 创建步骤HTML
     */
    createStepHTML(step) {
        const icons = {
            initializing: 'fa-cog',
            analyzing: 'fa-search',
            retrieving: 'fa-database',
            generating: 'fa-brain',
            validating: 'fa-check-double',
            completed: 'fa-flag-checkered'
        };

        const statusLabels = {
            pending: '等待中',
            running: '进行中',
            completed: '已完成',
            error: '出错'
        };

        const icon = icons[step.stage] || 'fa-circle';
        const statusLabel = statusLabels[step.status] || step.status;

        let detailsHTML = '';
        if (step.details) {
            detailsHTML = `<div class="step-details">${this.escapeHtml(step.details)}</div>`;
        }

        return `
            <div class="step-icon">
                <i class="fas ${icon}"></i>
            </div>
            <div class="step-content">
                <div class="step-title">${this.escapeHtml(step.title)}</div>
                <div class="step-description">${this.escapeHtml(step.description)}</div>
                ${detailsHTML}
            </div>
            <div class="step-status">${statusLabel}</div>
        `;
    }

    /**
     * 更新进度
     */
    updateProgress(progressData) {
        // 更新总体进度
        this.currentProgress = progressData.overall_progress;
        
        // 如果在后台模式，更新悬浮按钮进度
        if (this.isBackgroundMode) {
            this.updateFloatButtonProgress(this.currentProgress);
        }
        
        const progressBar = document.getElementById('overall-progress-bar');
        const progressPercentage = document.getElementById('progress-percentage');
        
        if (progressBar) {
            progressBar.style.width = `${progressData.overall_progress}%`;
            
            // 根据状态更新进度条样式
            progressBar.classList.remove('completed', 'error');
            if (progressData.status === 'completed') {
                progressBar.classList.add('completed');
            } else if (progressData.status === 'error') {
                progressBar.classList.add('error');
            }
        }
        
        if (progressPercentage) {
            progressPercentage.textContent = progressData.overall_progress;
        }

        // 更新步骤状态
        if (progressData.steps) {
            progressData.steps.forEach(step => {
                this.updateStep(step);
            });
        }

        // 更新状态文本
        this.updateStatusText(progressData);

        // 检查是否完成
        if (progressData.status === 'completed') {
            this.onGenerationComplete(progressData.result);
        } else if (progressData.status === 'error') {
            this.onGenerationError(progressData.message);
        }
    }

    /**
     * 更新单个步骤
     */
    updateStep(step) {
        const stepElement = document.getElementById(`step-${step.stage}`);
        if (!stepElement) return;

        // 更新状态类
        stepElement.className = `progress-step ${step.status}`;
        
        // 更新内容
        stepElement.innerHTML = this.createStepHTML(step);

        // 如果是当前运行的步骤，滚动到可视区域
        if (step.status === 'running') {
            stepElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * 更新状态文本
     */
    updateStatusText(progressData) {
        const statusText = document.getElementById('progress-status-text');
        const closeBtn = document.getElementById('close-progress-btn');
        const backgroundBtn = document.getElementById('background-btn');
        
        if (!statusText) return;

        if (progressData.status === 'running') {
            statusText.innerHTML = '<span class="status-running"><i class="fas fa-circle-notch fa-spin"></i> 正在处理...</span>';
            if (closeBtn) {
                closeBtn.disabled = true;
                closeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';
                closeBtn.title = '处理中，无法关闭';
                this.log('更新按钮状态：禁用关闭按钮');
            }
            // 显示后台运行按钮
            if (backgroundBtn) {
                backgroundBtn.style.display = 'inline-block';
                this.log('更新按钮状态：显示后台运行按钮');
            }
        } else if (progressData.status === 'completed') {
            statusText.innerHTML = '<span class="status-completed"><i class="fas fa-check-circle"></i> 生成完成！</span>';
            if (closeBtn) {
                closeBtn.disabled = false;
                closeBtn.innerHTML = '<i class="fas fa-check"></i> 完成';
                closeBtn.title = '关闭窗口';
                this.log('更新按钮状态：启用关闭按钮');
            }
            // 隐藏后台运行按钮
            if (backgroundBtn) {
                backgroundBtn.style.display = 'none';
            }
            document.getElementById('progress-panel')?.classList.add('completed');
            
            // 如果在后台模式下完成，发送系统通知
            if (this.isBackgroundMode) {
                this.sendSystemNotification('测试用例生成完成', 'AI 已成功生成测试用例，请查看结果', 'success');
            }
        } else if (progressData.status === 'error') {
            statusText.innerHTML = `<span class="status-error"><i class="fas fa-exclamation-circle"></i> 生成失败</span>`;
            if (closeBtn) {
                closeBtn.disabled = false;
                closeBtn.innerHTML = '<i class="fas fa-times"></i> 关闭';
                closeBtn.title = '关闭错误提示';
                this.log('更新按钮状态：启用关闭按钮（错误状态）');
            }
            // 隐藏后台运行按钮
            if (backgroundBtn) {
                backgroundBtn.style.display = 'none';
            }
            
            // 如果在后台模式下出错，发送系统通知
            if (this.isBackgroundMode) {
                this.sendSystemNotification('测试用例生成失败', progressData.message || '生成过程中出现错误', 'error');
            }
        }
    }

    /**
     * 发送系统通知
     */
    sendSystemNotification(title, message, type = 'info') {
        // 检查浏览器通知权限
        if ('Notification' in window) {
            if (Notification.permission === 'granted') {
                new Notification(title, {
                    body: message,
                    icon: type === 'success' ? '/static/images/success.png' : '/static/images/error.png',
                    tag: this.taskId
                });
            } else if (Notification.permission !== 'denied') {
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        new Notification(title, {
                            body: message,
                            icon: type === 'success' ? '/static/images/success.png' : '/static/images/error.png',
                            tag: this.taskId
                        });
                    }
                });
            }
        }
        
        // 同时显示页面内通知
        showNotification(message, type);
    }

    /**
     * 生成完成回调
     */
    onGenerationComplete(result) {
        if (this.onCompleteCallback) {
            this.onCompleteCallback(result);
        }
    }

    /**
     * 生成错误回调
     */
    onGenerationError(message) {
        // 显示错误信息
        const panel = document.getElementById('progress-panel');
        if (panel) {
            // 移除已存在的错误消息
            const existingError = panel.querySelector('.error-message');
            if (existingError) {
                existingError.remove();
            }
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            
            // 如果错误消息很长，添加滚动支持
            const isLongMessage = message.length > 200;
            const escapedMessage = this.escapeHtml(message);
            
            let messageHtml = '';
            if (isLongMessage) {
                messageHtml = `
                    <div class="error-message-header">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h4>生成失败</h4>
                    </div>
                    <div class="error-message-body">
                        <div class="error-message-scroll">
                            <pre class="error-message-text">${escapedMessage}</pre>
                        </div>
                        <div class="error-message-actions">
                            <button class="copy-error-btn" onclick="this.parentElement.parentElement.querySelector('.error-message-text').select(); document.execCommand('copy'); this.innerHTML='已复制';">
                                <i class="fas fa-copy"></i> 复制错误信息
                            </button>
                        </div>
                    </div>
                `;
            } else {
                messageHtml = `
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>生成失败</h4>
                    <p>${escapedMessage}</p>
                `;
            }
            
            errorDiv.innerHTML = messageHtml;
            panel.insertBefore(errorDiv, panel.querySelector('.progress-footer'));
        }

        if (this.onErrorCallback) {
            this.onErrorCallback(message);
        }
    }

    /**
     * 开始监听进度（使用SSE）
     */
    startProgressStream(taskId) {
        this.taskId = taskId;
        
        // 使用EventSource连接SSE端点
        this.eventSource = new EventSource(`/test_case_generator/progress/${taskId}/`);
        
        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateProgress(data);
            } catch (e) {
                console.error('解析进度数据失败:', e);
            }
        };
        
        this.eventSource.onerror = (error) => {
            console.error('SSE连接错误:', error);
            this.closeEventSource();
        };
        
        this.eventSource.onopen = () => {
            console.log('SSE连接已建立');
        };
    }

    /**
     * 关闭EventSource连接
     */
    closeEventSource() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    /**
     * 设置完成回调
     */
    onComplete(callback) {
        this.onCompleteCallback = callback;
        return this;
    }

    /**
     * 设置错误回调
     */
    onError(callback) {
        this.onErrorCallback = callback;
        return this;
    }

    /**
     * HTML转义
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 创建悬浮按钮（用于后台任务唤醒）
     */
    createFloatButton() {
        // 如果已存在则移除
        const existingButton = document.getElementById('progress-float-button');
        if (existingButton) {
            existingButton.remove();
        }

        const button = document.createElement('div');
        button.id = 'progress-float-button';
        button.className = 'progress-float-button';
        button.innerHTML = `
            <div class="float-button-icon">
                <i class="fas fa-window-restore"></i>
            </div>
            <div class="float-button-badge">
                <span class="badge-progress">0%</span>
            </div>
            <div class="float-button-tooltip">
                <span>点击查看任务进度</span>
            </div>
        `;

        document.body.appendChild(button);
        this.floatButton = button;

        // 绑定点击事件
        button.addEventListener('click', () => {
            this.wakeFromBackground();
        });

        console.log('悬浮按钮创建完成');
    }

    /**
     * 显示悬浮按钮
     */
    showFloatButton() {
        if (!this.floatButton) {
            this.createFloatButton();
        }
        this.floatButton.classList.add('active');
        console.log('悬浮按钮已显示');
    }

    /**
     * 隐藏悬浮按钮
     */
    hideFloatButton() {
        if (this.floatButton) {
            this.floatButton.classList.remove('active');
            console.log('悬浮按钮已隐藏');
        }
    }

    /**
     * 更新悬浮按钮的进度显示
     */
    updateFloatButtonProgress(progress) {
        if (!this.floatButton) return;
        
        const badge = this.floatButton.querySelector('.badge-progress');
        if (badge) {
            badge.textContent = `${progress}%`;
        }

        // 根据进度更新样式
        if (progress >= 100) {
            this.floatButton.classList.add('completed');
        } else if (progress > 0) {
            this.floatButton.classList.remove('completed');
        }
    }

    /**
     * 从后台模式唤醒进度页面
     */
    wakeFromBackground() {
        console.log('从后台模式唤醒进度页面');
        
        // 重新显示进度模态框
        this.show();
        
        // 更新进度显示
        if (this.currentProgress >= 100) {
            // 任务已完成，显示完成状态
            const statusText = document.getElementById('progress-status-text');
            if (statusText) {
                statusText.innerHTML = '<span class="status-completed"><i class="fas fa-check-circle"></i> 生成完成！</span>';
            }
        }
        
        // 隐藏悬浮按钮
        this.hideFloatButton();
        
        // 发送通知提示用户
        showNotification('任务进度页面已打开', 'info');
    }

    /**
     * 更新后台任务进度（用于SSE更新）
     */
    updateBackgroundProgress(progressData) {
        if (!this.isBackgroundMode) return;
        
        this.currentProgress = progressData.overall_progress;
        
        // 更新悬浮按钮进度
        this.updateFloatButtonProgress(this.currentProgress);
        
        // 如果任务完成或出错，更新状态
        if (progressData.status === 'completed') {
            this.onGenerationComplete(progressData.result);
        } else if (progressData.status === 'error') {
            this.onGenerationError(progressData.message);
        }
    }
}

// 导出全局变量
window.GenerationProgressManager = GenerationProgressManager;
