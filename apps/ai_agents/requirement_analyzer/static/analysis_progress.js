/**
 * 需求文档分析进度管理器
 * Analysis Progress Manager
 */

class RequirementAnalysisProgressManager {
    constructor() {
        this.taskId = null;
        this.eventSource = null;
        this.isActive = false;
        this.onCompleteCallback = null;
        this.onErrorCallback = null;
        this.steps = [];
        this.currentProgress = 0;
        this.isBackgroundMode = false;
        this.backgroundTasks = new Map();
        this.floatButton = null;
        this.currentStatus = 'running';
        this.errorMessage = '';
        
        this.restoreFromStorage();
    }

    log(message) {
        console.log(`[AnalysisProgress] ${message}`);
    }

    saveToStorage() {
        try {
            const state = {
                taskId: this.taskId,
                currentProgress: this.currentProgress,
                currentStatus: this.currentStatus,
                isBackgroundMode: this.isBackgroundMode,
                steps: this.steps,
                errorMessage: this.errorMessage,
                timestamp: Date.now()
            };
            localStorage.setItem('analysisProgress', JSON.stringify(state));
        } catch (e) {
            console.error('保存状态到本地存储失败:', e);
        }
    }

    restoreFromStorage() {
        try {
            const stored = localStorage.getItem('analysisProgress');
            if (stored) {
                const state = JSON.parse(stored);
                const now = Date.now();
                if (state.timestamp && (now - state.timestamp) < 300000) {
                    this.taskId = state.taskId;
                    this.currentProgress = state.currentProgress || 0;
                    this.currentStatus = state.currentStatus || 'running';
                    this.isBackgroundMode = state.isBackgroundMode || false;
                    this.steps = state.steps || [];
                    this.errorMessage = state.errorMessage || '';
                    
                    if (this.isBackgroundMode && this.currentProgress < 100 && this.taskId) {
                        this.createFloatButton();
                        this.showFloatButton();
                        this.updateFloatButtonProgress(this.currentProgress);
                        this.tryReconnectSSE();
                    }
                } else if (state.timestamp) {
                    localStorage.removeItem('analysisProgress');
                }
            }
        } catch (e) {
            console.error('从本地存储恢复状态失败:', e);
        }
    }

    clearStorage() {
        localStorage.removeItem('analysisProgress');
    }

    tryReconnectSSE() {
        if (this.taskId && !this.eventSource) {
            this.startProgressStream(this.taskId);
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

    show() {
        this.createModal();
        const modal = document.getElementById('analysis-progress-modal');
        if (modal) {
            modal.classList.add('active');
            this.isActive = true;
        }
    }

    hide(allowBackground = true) {
        const modal = document.getElementById('analysis-progress-modal');
        if (modal) {
            modal.classList.remove('active');
            if (modal._keydownHandler) {
                document.removeEventListener('keydown', modal._keydownHandler);
            }
            setTimeout(() => {
                modal.remove();
                this.isActive = false;
            }, 300);
        }
        
        if (allowBackground && this.taskId && this.currentProgress < 100) {
            this.isBackgroundMode = true;
            this.backgroundTasks.set(this.taskId, {
                progress: this.currentProgress,
                startTime: Date.now()
            });
            this.createFloatButton();
            this.showFloatButton();
            this.updateFloatButtonProgress(this.currentProgress);
            this.saveToStorage();
        } else {
            this.stopProgressStream();
            this.clearStorage();
        }
    }

    createModal() {
        // 移除已存在的模态框
        const existing = document.getElementById('analysis-progress-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.className = 'progress-modal';
        modal.id = 'analysis-progress-modal';
        modal.innerHTML = `
            <div class="progress-panel" id="analysis-progress-panel">
                <div class="progress-header">
                    <h3><i class="fas fa-microscope"></i> 需求文档分析中</h3>
                    <p>AI 正在分析您的需求文档，请稍候...</p>
                </div>
                
                <div class="overall-progress">
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" id="analysis-progress-bar" style="width: 0%;"></div>
                    </div>
                    <div class="progress-percentage">
                        总体进度: <span class="percentage" id="analysis-progress-percentage">0</span>%
                    </div>
                </div>
                
                <div class="steps-container" id="analysis-steps-container">
                    <!-- 步骤将动态插入这里 -->
                </div>
                
                <div class="progress-footer">
                    <span class="progress-status-text" id="analysis-progress-status-text">
                        <span class="status-running"><i class="fas fa-circle-notch fa-spin"></i> 正在处理...</span>
                    </span>
                    <div class="progress-actions">
                        <button class="background-btn" id="analysis-background-btn" type="button" style="display: none;" title="后台运行">
                            <i class="fas fa-window-minimize"></i> 后台运行
                        </button>
                        <button class="close-progress-btn" id="analysis-close-progress-btn" type="button" disabled title="处理中，无法关闭">
                            <i class="fas fa-spinner fa-spin"></i> 处理中...
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        modal.addEventListener('click', (event) => {
            const backgroundBtn = document.getElementById('analysis-background-btn');
            const closeBtn = document.getElementById('analysis-close-progress-btn');
            
            if (backgroundBtn && (event.target === backgroundBtn || backgroundBtn.contains(event.target))) {
                event.preventDefault();
                event.stopPropagation();
                this.hide(true);
                return;
            }
            
            if (closeBtn && (event.target === closeBtn || closeBtn.contains(event.target))) {
                event.preventDefault();
                event.stopPropagation();
                if (!closeBtn.disabled) {
                    this.hide(false);
                }
                return;
            }
        });
        
        const handleKeydown = (event) => {
            if (event.key === 'Escape') {
                const closeBtn = document.getElementById('analysis-close-progress-btn');
                if (closeBtn && !closeBtn.disabled) {
                    this.hide(false);
                }
            }
        };
        document.addEventListener('keydown', handleKeydown);
        modal._keydownHandler = handleKeydown;
    }

    initializeSteps(steps) {
        this.steps = steps;
        const container = document.getElementById('analysis-steps-container');
        if (!container) return;

        container.innerHTML = '';
        
        const stepOrder = [
            'extracting',
            'scoring',
            'deep_analysis',
            'summarize',
            'completed'
        ];

        stepOrder.forEach((stage) => {
            const step = steps.find(s => s.stage === stage);
            if (!step) return;

            const stepElement = document.createElement('div');
            stepElement.className = `progress-step ${step.status}`;
            stepElement.id = `analysis-step-${stage}`;
            stepElement.innerHTML = this.createStepHTML(step);
            container.appendChild(stepElement);
        });
    }

    createStepHTML(step) {
        const icons = {
            extracting: 'fa-file-alt',
            scoring: 'fa-star',
            deep_analysis: 'fa-search-plus',
            summarize: 'fa-chart-bar',
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
        const stepId = step.stage || `step-${Date.now()}`;
        
        let detailsHTML = '';
        if (step.details) {
            const escapedDetails = this.escapeHtml(step.details);
            if (step.status === 'error' && step.details.length > 5) {
                const truncatedDetails = escapedDetails.substring(0, 100);
                detailsHTML = `
                    <div class="step-details-container" id="analysis-step-details-${stepId}">
                        <div class="step-details-summary">
                            ${truncatedDetails}...
                            <button class="toggle-details-btn" id="analysis-toggle-btn-${stepId}">
                                <i class="fas fa-chevron-down"></i> 查看详情
                            </button>
                        </div>
                        <div class="step-details-scroll">
                            <pre class="step-details-full">${escapedDetails}</pre>
                        </div>
                    </div>
                `;
            } else {
                detailsHTML = `<div class="step-details">${escapedDetails}</div>`;
            }
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

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateProgress(progressData) {
        this.currentProgress = progressData.overall_progress;
        this.currentStatus = progressData.status || 'running';
        
        if (this.isBackgroundMode) {
            this.updateFloatButtonProgress(this.currentProgress);
        }
        
        const progressBar = document.getElementById('analysis-progress-bar');
        const progressPercentage = document.getElementById('analysis-progress-percentage');
        
        if (progressBar) {
            progressBar.style.width = `${progressData.overall_progress}%`;
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

        // 更新步骤
        if (progressData.stages) {
            progressData.stages.forEach(stepData => {
                const stepEl = document.getElementById(`analysis-step-${stepData.stage}`);
                if (!stepEl) return;
                
                stepEl.className = `progress-step ${stepData.status}`;
                
                const iconEl = stepEl.querySelector('.step-icon');
                if (iconEl) {
                    const icons = {
                        extracting: 'fa-file-alt',
                        scoring: 'fa-star',
                        deep_analysis: 'fa-search-plus',
                        summarize: 'fa-chart-bar',
                        completed: 'fa-flag-checkered'
                    };
                    iconEl.innerHTML = `<i class="fas ${icons[stepData.stage] || 'fa-circle'}"></i>`;
                }
                
                const statusEl = stepEl.querySelector('.step-status');
                if (statusEl) {
                    const statusLabels = { pending: '等待中', running: '进行中', completed: '已完成', error: '出错' };
                    statusEl.textContent = statusLabels[stepData.status] || stepData.status;
                }
                
                // 更新详情
                if (stepData.details) {
                    const contentEl = stepEl.querySelector('.step-content');
                    if (contentEl) {
                        let existingDetails = contentEl.querySelector('.step-details, .step-details-container');
                        if (existingDetails) existingDetails.remove();
                        
                        const escapedDetails = this.escapeHtml(stepData.details);
                        if (stepData.status === 'error') {
                            const truncated = escapedDetails.substring(0, 100);
                            const div = document.createElement('div');
                            div.className = 'step-details-container';
                            div.innerHTML = `
                                <div class="step-details-summary">
                                    ${truncated}...
                                    <button class="toggle-details-btn">
                                        <i class="fas fa-chevron-down"></i> 查看详情
                                    </button>
                                </div>
                                <div class="step-details-scroll">
                                    <pre class="step-details-full">${escapedDetails}</pre>
                                </div>
                            `;
                            contentEl.appendChild(div);
                        } else {
                            const div = document.createElement('div');
                            div.className = 'step-details';
                            div.textContent = stepData.details;
                            contentEl.appendChild(div);
                        }
                    }
                }
            });
        }

        // 更新状态文本和按钮
        const statusText = document.getElementById('analysis-progress-status-text');
        const closeBtn = document.getElementById('analysis-close-progress-btn');
        const backgroundBtn = document.getElementById('analysis-background-btn');
        
        if (statusText) {
            if (progressData.status === 'completed') {
                statusText.innerHTML = '<span class="status-completed"><i class="fas fa-check-circle"></i> 分析完成！</span>';
                if (closeBtn) {
                    closeBtn.disabled = false;
                    closeBtn.innerHTML = '<i class="fas fa-check"></i> 完成';
                }
            } else if (progressData.status === 'error') {
                statusText.innerHTML = '<span class="status-error"><i class="fas fa-exclamation-circle"></i> 分析失败</span>';
                if (closeBtn) {
                    closeBtn.disabled = false;
                    closeBtn.innerHTML = '<i class="fas fa-times"></i> 关闭';
                }
                if (this.errorMessage) {
                    this.onAnalysisError(this.errorMessage);
                }
            } else {
                statusText.innerHTML = '<span class="status-running"><i class="fas fa-circle-notch fa-spin"></i> 正在后台处理...</span>';
                if (closeBtn) {
                    closeBtn.disabled = true;
                    closeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';
                }
            }
        }
        
        if (backgroundBtn) {
            backgroundBtn.style.display = (this.currentStatus === 'running' && this.currentProgress < 100) ? 'inline-block' : 'none';
        }
    }

    startProgressStream(taskId) {
        this.taskId = taskId;
        this.eventSource = new EventSource(`/api/progress/${taskId}/`);
        
        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                // 初始化步骤
                if (data.stages && data.stages.length > 0 && !this.steps.length) {
                    this.initializeSteps(data.stages);
                }
                
                this.updateProgress(data);
                
                // 保存到本地存储
                if (this.isBackgroundMode) {
                    this.saveToStorage();
                }
                
                if (data.status === 'completed') {
                    this.stopProgressStream();
                    if (this.isBackgroundMode) {
                        this.sendSystemNotification('需求分析完成', 'AI 已完成需求文档分析，请查看结果', 'success');
                    }
                    if (this.onCompleteCallback) {
                        this.onCompleteCallback(data.result);
                    }
                } else if (data.status === 'error') {
                    this.stopProgressStream();
                    this.errorMessage = data.message || '分析过程中出现错误';
                    if (this.isBackgroundMode) {
                        this.sendSystemNotification('需求分析失败', this.errorMessage, 'error');
                    }
                    this.onAnalysisError(this.errorMessage);
                    if (this.onErrorCallback) {
                        this.onErrorCallback(this.errorMessage);
                    }
                }
            } catch (e) {
                console.error('解析进度数据失败:', e);
            }
        };
        
        this.eventSource.onerror = () => {
            console.error('SSE连接错误');
        };
    }

    stopProgressStream() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    onAnalysisError(message) {
        this.errorMessage = message;
        this.currentStatus = 'error';
        
        const panel = document.getElementById('analysis-progress-panel');
        if (panel) {
            const existingError = panel.querySelector('.error-message');
            if (existingError) existingError.remove();
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            
            const isLongMessage = message.length > 50;
            const escapedMessage = this.escapeHtml(message);
            const truncatedMessage = escapedMessage.substring(0, 150);
            
            if (isLongMessage) {
                errorDiv.innerHTML = `
                    <div class="error-message-header">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h4>分析失败</h4>
                    </div>
                    <div class="error-message-body">
                        <div class="error-message-summary">
                            <p>${truncatedMessage}...</p>
                            <button class="expand-error-btn" id="analysis-expand-error">
                                <i class="fas fa-chevron-down"></i> 查看完整错误信息
                            </button>
                        </div>
                        <div class="error-message-scroll-container">
                            <div class="error-message-scroll">
                                <pre class="error-message-text">${escapedMessage}</pre>
                            </div>
                            <div class="error-message-actions">
                                <button class="copy-error-btn" id="analysis-copy-error">
                                    <i class="fas fa-copy"></i> 复制错误信息
                                </button>
                                <button class="download-error-btn" id="analysis-download-error">
                                    <i class="fas fa-download"></i> 导出日志
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                errorDiv.innerHTML = `
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>分析失败</h4>
                    <p>${escapedMessage}</p>
                `;
            }
            
            panel.insertBefore(errorDiv, panel.querySelector('.progress-footer'));
            
            if (isLongMessage) {
                const expandBtn = errorDiv.querySelector('.expand-error-btn');
                if (expandBtn) {
                    expandBtn.addEventListener('click', () => {
                        errorDiv.classList.toggle('expanded');
                        expandBtn.innerHTML = errorDiv.classList.contains('expanded')
                            ? '<i class="fas fa-chevron-up"></i> 收起'
                            : '<i class="fas fa-chevron-down"></i> 查看完整错误信息';
                    });
                }
                
                const copyBtn = errorDiv.querySelector('.copy-error-btn');
                if (copyBtn) {
                    copyBtn.addEventListener('click', () => {
                        const text = errorDiv.querySelector('.error-message-text').textContent;
                        navigator.clipboard.writeText(text).then(() => {
                            copyBtn.innerHTML = '<i class="fas fa-check"></i> 已复制';
                        }).catch(() => {
                            copyBtn.innerHTML = '复制失败';
                        });
                    });
                }
                
                const downloadBtn = errorDiv.querySelector('.download-error-btn');
                if (downloadBtn) {
                    downloadBtn.addEventListener('click', () => {
                        const text = errorDiv.querySelector('.error-message-text').textContent;
                        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                        link.href = url;
                        link.download = `requirement_analysis_error_${timestamp}.txt`;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        URL.revokeObjectURL(url);
                    });
                }
            }
        }
        
        if (this.isBackgroundMode) {
            this.saveToStorage();
        }
    }

    sendSystemNotification(title, message, type) {
        if ('Notification' in window) {
            if (Notification.permission === 'granted') {
                new Notification(title, { body: message, tag: this.taskId });
            } else if (Notification.permission !== 'denied') {
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        new Notification(title, { body: message, tag: this.taskId });
                    }
                });
            }
        }
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        }
    }

    createFloatButton() {
        if (this.floatButton) return;
        
        const btn = document.createElement('div');
        btn.className = 'progress-float-button';
        btn.id = 'analysis-float-button';
        btn.innerHTML = `
            <div class="float-button-icon">
                <i class="fas fa-microscope"></i>
                <span class="float-button-badge">0%</span>
                <span class="float-button-tooltip">需求分析进度</span>
            </div>
        `;
        
        btn.addEventListener('click', () => {
            this.isBackgroundMode = false;
            this.hideFloatButton();
            this.show();
        });
        
        document.body.appendChild(btn);
        this.floatButton = btn;
    }

    showFloatButton() {
        if (this.floatButton) {
            setTimeout(() => {
                this.floatButton.classList.add('active');
            }, 300);
        }
    }

    hideFloatButton() {
        if (this.floatButton) {
            this.floatButton.classList.remove('active');
            setTimeout(() => {
                if (this.floatButton) {
                    this.floatButton.remove();
                    this.floatButton = null;
                }
            }, 300);
        }
    }

    updateFloatButtonProgress(progress) {
        if (this.floatButton) {
            const badge = this.floatButton.querySelector('.float-button-badge');
            if (badge) {
                badge.textContent = `${Math.round(progress)}%`;
            }
            if (progress >= 100) {
                this.floatButton.classList.add('completed');
                this.floatButton.classList.remove('active');
                setTimeout(() => {
                    this.hideFloatButton();
                }, 5000);
            }
        }
    }

    updateBackgroundProgress(progressData) {
        if (!this.isBackgroundMode) return;
        this.currentProgress = progressData.overall_progress;
        this.updateFloatButtonProgress(this.currentProgress);
        
        if (progressData.status === 'completed') {
            this.onCompleteCallback && this.onCompleteCallback(progressData.result);
        } else if (progressData.status === 'error') {
            this.onAnalysisError(progressData.message);
        }
    }
}

window.RequirementAnalysisProgressManager = RequirementAnalysisProgressManager;
