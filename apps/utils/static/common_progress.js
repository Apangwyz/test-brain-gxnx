/**
 * 统一进度管理组件 - CommonProgressManager
 * 适用于所有涉及文件上传和内容生成的业务场景
 * 
 * 功能特性：
 * 1. 文件上传状态标记（上传中、上传成功、上传失败）
 * 2. 上传失败重试机制
 * 3. 上传进度可视化
 * 4. 内容生成进度页面（总体进度、当前阶段、预计剩余时间）
 * 5. 取消操作选项
 * 6. 结果预览和导出功能
 * 7. 悬浮按钮后台任务唤醒
 * 8. SSE实时进度更新
 */

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
        this.isBackgroundMode = false;
        this.currentProgress = 0;
        this.startTime = null;
        this.estimatedRemainingTime = 0;

        // 回调函数
        this.onCompleteCallback = null;
        this.onErrorCallback = null;
        this.onCancelCallback = null;
        this.onProgressCallback = null;

        // DOM引用
        this.modal = null;
        this.floatButton = null;
        this.uploadProgress = null;

        // 步骤定义
        this.steps = [];
    }

    /**
     * 日志记录
     */
    log(message) {
        console.log(`[${this.config.moduleName} ProgressManager] ${message}`);
    }

    /**
     * 显示上传进度
     * @param {Object} options - 上传选项
     */
    showUploadProgress(options = {}) {
        this.createUploadModal(options);
        this.modal = document.getElementById('common-upload-modal');
        if (this.modal) {
            this.modal.classList.add('active');
            this.isActive = true;
        }
    }

    /**
     * 显示生成进度
     * @param {Object} options - 进度选项
     */
    showProgress(options = {}) {
        this.createProgressModal(options);
        this.modal = document.getElementById('common-progress-modal');
        if (this.modal) {
            this.modal.classList.add('active');
            this.isActive = true;
            this.startTime = Date.now();
        }
    }

    /**
     * 隐藏模态框
     */
    hide(allowBackground = false) {
        if (!this.modal) return;

        this.modal.classList.remove('active');

        // 移除键盘事件监听器
        if (this.modal._keydownHandler) {
            document.removeEventListener('keydown', this.modal._keydownHandler);
        }

        setTimeout(() => {
            this.modal.remove();
            this.modal = null;
            this.isActive = false;
        }, 300);

        // 如果允许后台运行且任务未完成
        if (allowBackground && this.taskId && this.currentProgress < 100 && this.config.showFloatButton) {
            this.isBackgroundMode = true;
            this.createFloatButton();
            this.showFloatButton();
            this.showNotification('任务已在后台运行，完成后将通知您', 'info');
        } else {
            this.closeEventSource();
            this.hideFloatButton();
        }
    }

    /**
     * 创建上传模态框
     */
    createUploadModal(options) {
        const existingModal = document.getElementById('common-upload-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'common-upload-modal';
        modal.className = 'common-modal upload-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3><i class="fas fa-upload"></i> ${options.title || '文件上传'}</h3>
                    <button class="modal-close" onclick="commonProgressManager.hide()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="upload-area" id="upload-area">
                        <div class="upload-icon">
                            <i class="fas fa-cloud-upload-alt"></i>
                        </div>
                        <p class="upload-text">点击或拖拽文件到此处上传</p>
                        <p class="upload-hint">${options.hint || '支持多种文件格式'}</p>
                        <input type="file" id="upload-file-input" multiple accept="${options.accept || '*'}" class="upload-file-input">
                    </div>
                    <div class="upload-files-list" id="upload-files-list"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="commonProgressManager.hide()">取消</button>
                    <button class="btn btn-primary" id="upload-submit-btn" disabled>开始上传</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // 绑定事件
        this.bindUploadEvents();
    }

    /**
     * 绑定上传事件
     */
    bindUploadEvents() {
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('upload-file-input');
        const submitBtn = document.getElementById('upload-submit-btn');
        const filesList = document.getElementById('upload-files-list');

        // 拖拽事件
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        uploadArea.addEventListener('dragenter', () => uploadArea.classList.add('drag-over'));
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
        uploadArea.addEventListener('dragover', () => uploadArea.classList.add('drag-over'));

        uploadArea.addEventListener('drop', (e) => {
            uploadArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                this.renderFilesList(files);
                submitBtn.disabled = false;
            }
        });

        // 点击上传
        uploadArea.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            this.renderFilesList(files);
            submitBtn.disabled = false;
        });

        // 上传按钮
        submitBtn.addEventListener('click', () => {
            this.uploadFiles(fileInput.files);
        });
    }

    /**
     * 渲染文件列表
     */
    renderFilesList(files) {
        const container = document.getElementById('upload-files-list');
        container.innerHTML = '';

        Array.from(files).forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'upload-file-item';
            fileItem.id = `upload-file-${index}`;
            fileItem.innerHTML = `
                <div class="file-icon">
                    <i class="fas ${this.getFileIcon(file.name)}"></i>
                </div>
                <div class="file-info">
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${this.formatFileSize(file.size)}</span>
                </div>
                <div class="file-status" id="file-status-${index}">
                    <span class="status-pending">等待上传</span>
                </div>
                <div class="file-progress" id="file-progress-${index}" style="display: none;">
                    <div class="progress-bar-fill"></div>
                </div>
                <button class="file-remove" onclick="this.parentElement.remove(); commonProgressManager.checkSubmitButton()">
                    <i class="fas fa-times"></i>
                </button>
            `;
            container.appendChild(fileItem);
        });
    }

    /**
     * 获取文件图标
     */
    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            docx: 'fa-file-word text-blue',
            doc: 'fa-file-word text-blue',
            pdf: 'fa-file-pdf text-red',
            md: 'fa-file-code text-purple',
            txt: 'fa-file-text text-gray',
            json: 'fa-file-code text-yellow',
            xlsx: 'fa-file-excel text-green',
            csv: 'fa-file-csv text-green'
        };
        return icons[ext] || 'fa-file text-gray';
    }

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 检查提交按钮状态
     */
    checkSubmitButton() {
        const container = document.getElementById('upload-files-list');
        const submitBtn = document.getElementById('upload-submit-btn');
        submitBtn.disabled = !container || container.children.length === 0;
    }

    /**
     * 上传文件
     */
    async uploadFiles(files) {
        const submitBtn = document.getElementById('upload-submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';

        const totalFiles = files.length;
        let uploadedCount = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const statusElement = document.getElementById(`file-status-${i}`);
            const progressElement = document.getElementById(`file-progress-${i}`);

            try {
                statusElement.innerHTML = '<span class="status-uploading"><i class="fas fa-spinner fa-spin"></i> 上传中...</span>';
                progressElement.style.display = 'block';

                const formData = new FormData();
                formData.append('file', file);
                formData.append('module', this.config.moduleName);

                const response = await fetch(this.config.uploadUrl || '/api/upload/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });

                const result = await response.json();

                if (result.success) {
                    statusElement.innerHTML = '<span class="status-success"><i class="fas fa-check"></i> 上传成功</span>';
                    progressElement.querySelector('.progress-bar-fill').style.width = '100%';
                    uploadedCount++;

                    if (this.onProgressCallback) {
                        this.onProgressCallback({
                            type: 'upload',
                            progress: Math.round((uploadedCount / totalFiles) * 100),
                            currentFile: file.name,
                            totalFiles,
                            uploadedCount
                        });
                    }
                } else {
                    throw new Error(result.message || '上传失败');
                }
            } catch (error) {
                statusElement.innerHTML = `
                    <span class="status-error">
                        <i class="fas fa-exclamation-circle"></i> 上传失败
                    </span>
                    <button class="retry-btn" onclick="commonProgressManager.retryUpload(${i}, this)">重试</button>
                `;
                progressElement.querySelector('.progress-bar-fill').style.width = '0%';

                this.showNotification(`文件 "${file.name}" 上传失败: ${error.message}`, 'error');
            }
        }

        if (uploadedCount === totalFiles) {
            submitBtn.innerHTML = '<i class="fas fa-check"></i> 全部上传完成';
            this.showNotification(`成功上传 ${totalFiles} 个文件`, 'success');

            if (this.onCompleteCallback) {
                this.onCompleteCallback({ type: 'upload', totalFiles });
            }
        } else {
            submitBtn.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${uploadedCount}/${totalFiles} 上传成功`;
        }
    }

    /**
     * 重试上传
     */
    async retryUpload(index, retryBtn) {
        const fileInput = document.getElementById('upload-file-input');
        const file = fileInput.files[index];
        const statusElement = document.getElementById(`file-status-${index}`);
        const progressElement = document.getElementById(`file-progress-${index}`);

        retryBtn.style.display = 'none';
        statusElement.innerHTML = '<span class="status-uploading"><i class="fas fa-spinner fa-spin"></i> 重新上传...</span>';
        progressElement.style.display = 'block';

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('module', this.config.moduleName);

            const response = await fetch(this.config.uploadUrl || '/api/upload/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            const result = await response.json();

            if (result.success) {
                statusElement.innerHTML = '<span class="status-success"><i class="fas fa-check"></i> 上传成功</span>';
                progressElement.querySelector('.progress-bar-fill').style.width = '100%';
                this.showNotification(`文件 "${file.name}" 重新上传成功`, 'success');
            } else {
                throw new Error(result.message || '重试失败');
            }
        } catch (error) {
            statusElement.innerHTML = `
                <span class="status-error">
                    <i class="fas fa-exclamation-circle"></i> 上传失败
                </span>
                <button class="retry-btn" onclick="commonProgressManager.retryUpload(${index}, this)">重试</button>
            `;
            this.showNotification(`文件 "${file.name}" 重试失败: ${error.message}`, 'error');
        }
    }

    /**
     * 创建进度模态框
     */
    createProgressModal(options) {
        const existingModal = document.getElementById('common-progress-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'common-progress-modal';
        modal.className = 'common-modal progress-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content progress-content">
                <div class="modal-header">
                    <h3><i class="fas fa-magic"></i> ${options.title || 'AI 正在处理'}</h3>
                    <button class="modal-close" onclick="commonProgressManager.hide(false)" disabled>
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <!-- 总体进度 -->
                    <div class="overall-progress-section">
                        <div class="progress-info">
                            <span class="progress-label">总体进度</span>
                            <span class="progress-percentage" id="overall-percentage">0%</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill" id="overall-progress-bar" style="width: 0%"></div>
                        </div>
                        <div class="progress-meta">
                            <span class="current-stage" id="current-stage">初始化...</span>
                            <span class="remaining-time" id="remaining-time">预计剩余时间: 计算中...</span>
                        </div>
                    </div>

                    <!-- 步骤详情 -->
                    <div class="steps-section">
                        <h4><i class="fas fa-list-check"></i> 处理步骤</h4>
                        <div class="steps-container" id="progress-steps-container"></div>
                    </div>

                    <!-- 实时日志 -->
                    <div class="logs-section">
                        <h4><i class="fas fa-scroll"></i> 操作日志</h4>
                        <div class="logs-container" id="progress-logs-container"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-danger" id="cancel-btn" disabled>
                        <i class="fas fa-times-circle"></i> 取消任务
                    </button>
                    <button class="btn btn-primary" id="complete-btn" style="display: none;">
                        <i class="fas fa-check"></i> 完成
                    </button>
                    <button class="btn btn-secondary" id="background-btn" style="display: none;">
                        <i class="fas fa-window-minimize"></i> 后台运行
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // 绑定事件
        this.bindProgressEvents();
    }

    /**
     * 绑定进度事件
     */
    bindProgressEvents() {
        const cancelBtn = document.getElementById('cancel-btn');
        const completeBtn = document.getElementById('complete-btn');
        const backgroundBtn = document.getElementById('background-btn');

        cancelBtn.addEventListener('click', () => this.cancelTask());
        completeBtn.addEventListener('click', () => this.hide(false));
        backgroundBtn.addEventListener('click', () => this.hide(true));

        // ESC键关闭
        const handleKeydown = (event) => {
            if (event.key === 'Escape') {
                const btn = document.getElementById('complete-btn').style.display === 'block' 
                    ? document.getElementById('complete-btn') 
                    : document.getElementById('cancel-btn');
                if (btn && !btn.disabled) {
                    if (btn === completeBtn) {
                        this.hide(false);
                    }
                }
            }
        };
        document.addEventListener('keydown', handleKeydown);
        this.modal._keydownHandler = handleKeydown;
    }

    /**
     * 初始化步骤显示
     */
    initializeSteps(steps) {
        this.steps = steps;
        const container = document.getElementById('progress-steps-container');
        if (!container) return;

        container.innerHTML = '';

        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = `progress-step ${step.status}`;
            stepElement.id = `step-${step.stage}`;
            stepElement.innerHTML = this.createStepHTML(step, index);
            container.appendChild(stepElement);
        });
    }

    /**
     * 创建步骤HTML
     */
    createStepHTML(step, index) {
        const icons = {
            initializing: 'fa-cog',
            analyzing: 'fa-search',
            retrieving: 'fa-database',
            generating: 'fa-brain',
            validating: 'fa-check-double',
            exporting: 'fa-download',
            completed: 'fa-flag-checkered',
            processing: 'fa-spinner'
        };

        const statusLabels = {
            pending: '等待中',
            running: '进行中',
            completed: '已完成',
            error: '出错'
        };

        const icon = icons[step.stage] || 'fa-circle';
        const statusLabel = statusLabels[step.status] || step.status;

        return `
            <div class="step-icon">
                <span class="step-number">${index + 1}</span>
                <i class="fas ${icon}"></i>
            </div>
            <div class="step-content">
                <div class="step-title">${this.escapeHtml(step.title)}</div>
                <div class="step-description">${this.escapeHtml(step.description)}</div>
                ${step.details ? `<div class="step-details">${this.escapeHtml(step.details)}</div>` : ''}
            </div>
            <div class="step-status">
                <span class="${step.status}">${statusLabel}</span>
            </div>
        `;
    }

    /**
     * 更新进度
     */
    updateProgress(progressData) {
        this.currentProgress = progressData.overall_progress || 0;

        // 更新总体进度
        const progressBar = document.getElementById('overall-progress-bar');
        const percentage = document.getElementById('overall-percentage');
        const currentStage = document.getElementById('current-stage');
        const remainingTime = document.getElementById('remaining-time');

        if (progressBar) {
            progressBar.style.width = `${this.currentProgress}%`;
            progressBar.classList.remove('completed', 'error');
            if (progressData.status === 'completed') {
                progressBar.classList.add('completed');
            } else if (progressData.status === 'error') {
                progressBar.classList.add('error');
            }
        }

        if (percentage) {
            percentage.textContent = `${this.currentProgress}%`;
        }

        // 更新阶段信息
        if (progressData.current_stage) {
            const stageInfo = progressData.current_stage;
            if (currentStage) {
                currentStage.textContent = stageInfo.title || '处理中...';
            }
            if (stageInfo.description && this.onProgressCallback) {
                this.onProgressCallback({
                    type: 'stage',
                    stage: stageInfo.title,
                    description: stageInfo.description
                });
            }
        }

        // 计算预计剩余时间
        if (this.startTime && this.currentProgress > 0 && this.currentProgress < 100) {
            const elapsedTime = (Date.now() - this.startTime) / 1000; // 秒
            const estimatedTotalTime = (elapsedTime / this.currentProgress) * 100;
            this.estimatedRemainingTime = Math.max(0, estimatedTotalTime - elapsedTime);
            
            if (remainingTime) {
                remainingTime.textContent = `预计剩余时间: ${this.formatTime(this.estimatedRemainingTime)}`;
            }
        }

        // 更新步骤状态
        if (progressData.steps) {
            progressData.steps.forEach(step => {
                this.updateStep(step);
            });
        }

        // 更新日志
        if (progressData.logs && Array.isArray(progressData.logs)) {
            this.updateLogs(progressData.logs);
        }

        // 更新按钮状态
        this.updateButtonStates(progressData.status);

        // 回调处理
        if (progressData.status === 'completed') {
            this.onComplete(progressData.result);
        } else if (progressData.status === 'error') {
            this.onError(progressData.message);
        }
    }

    /**
     * 格式化时间
     */
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        if (mins > 0) {
            return `${mins}分${secs}秒`;
        }
        return `${secs}秒`;
    }

    /**
     * 更新单个步骤
     */
    updateStep(step) {
        const stepElement = document.getElementById(`step-${step.stage}`);
        if (!stepElement) return;

        stepElement.className = `progress-step ${step.status}`;
        stepElement.innerHTML = this.createStepHTML(step, this.steps.findIndex(s => s.stage === step.stage));

        if (step.status === 'running') {
            stepElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * 更新日志显示
     */
    updateLogs(logs) {
        const container = document.getElementById('progress-logs-container');
        if (!container) return;

        logs.forEach(log => {
            const logElement = document.createElement('div');
            logElement.className = `log-item ${log.level || 'info'}`;
            logElement.innerHTML = `
                <span class="log-time">${log.timestamp || new Date().toLocaleTimeString()}</span>
                <span class="log-level">${this.getLogLevelLabel(log.level)}</span>
                <span class="log-message">${this.escapeHtml(log.message)}</span>
            `;
            container.appendChild(logElement);
        });

        container.scrollTop = container.scrollHeight;
    }

    /**
     * 获取日志级别标签
     */
    getLogLevelLabel(level) {
        const labels = {
            debug: 'DEBUG',
            info: 'INFO',
            warning: 'WARN',
            error: 'ERROR'
        };
        return labels[level] || 'INFO';
    }

    /**
     * 更新按钮状态
     */
    updateButtonStates(status) {
        const cancelBtn = document.getElementById('cancel-btn');
        const completeBtn = document.getElementById('complete-btn');
        const backgroundBtn = document.getElementById('background-btn');
        const closeBtn = document.querySelector('.modal-close');

        switch (status) {
            case 'running':
                cancelBtn.disabled = false;
                completeBtn.style.display = 'none';
                backgroundBtn.style.display = 'inline-block';
                closeBtn.disabled = true;
                break;
            case 'completed':
                cancelBtn.disabled = true;
                cancelBtn.style.display = 'none';
                completeBtn.style.display = 'inline-block';
                backgroundBtn.style.display = 'none';
                closeBtn.disabled = false;
                break;
            case 'error':
                cancelBtn.disabled = true;
                cancelBtn.style.display = 'none';
                completeBtn.style.display = 'inline-block';
                backgroundBtn.style.display = 'none';
                closeBtn.disabled = false;
                break;
            case 'cancelled':
                cancelBtn.disabled = true;
                completeBtn.style.display = 'inline-block';
                backgroundBtn.style.display = 'none';
                closeBtn.disabled = false;
                break;
        }
    }

    /**
     * 开始监听进度（SSE）
     */
    startProgressStream(taskId) {
        this.taskId = taskId;

        this.eventSource = new EventSource(`${this.config.progressUrl}${taskId}/`);

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateProgress(data);

                // 如果在后台模式，更新悬浮按钮
                if (this.isBackgroundMode) {
                    this.updateFloatButtonProgress(this.currentProgress);
                }
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
     * 取消任务
     */
    async cancelTask() {
        const cancelBtn = document.getElementById('cancel-btn');
        cancelBtn.disabled = true;
        cancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 取消中...';

        try {
            const response = await fetch(`${this.config.cancelUrl}${this.taskId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ task_id: this.taskId })
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('任务已取消', 'info');
                this.closeEventSource();
                this.hide(false);

                if (this.onCancelCallback) {
                    this.onCancelCallback();
                }
            } else {
                throw new Error(result.message || '取消失败');
            }
        } catch (error) {
            this.showNotification(`取消任务失败: ${error.message}`, 'error');
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = '<i class="fas fa-times-circle"></i> 取消任务';
        }
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
     * 完成回调
     */
    onComplete(result) {
        if (this.onCompleteCallback) {
            this.onCompleteCallback(result);
        }

        // 如果在后台模式，发送通知
        if (this.isBackgroundMode) {
            this.sendSystemNotification('任务完成', 'AI 处理已完成，请查看结果', 'success');
        }
    }

    /**
     * 错误回调
     */
    onError(message) {
        if (this.onErrorCallback) {
            this.onErrorCallback(message);
        }

        if (this.isBackgroundMode) {
            this.sendSystemNotification('任务失败', message, 'error');
        }
    }

    /**
     * 创建悬浮按钮
     */
    createFloatButton() {
        const existingButton = document.getElementById('common-float-button');
        if (existingButton) existingButton.remove();

        const button = document.createElement('div');
        button.id = 'common-float-button';
        button.className = 'common-float-button';
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

        button.addEventListener('click', () => this.wakeFromBackground());
    }

    /**
     * 显示悬浮按钮
     */
    showFloatButton() {
        if (!this.floatButton) {
            this.createFloatButton();
        }
        this.floatButton.classList.add('active');
    }

    /**
     * 隐藏悬浮按钮
     */
    hideFloatButton() {
        if (this.floatButton) {
            this.floatButton.classList.remove('active');
        }
    }

    /**
     * 更新悬浮按钮进度
     */
    updateFloatButtonProgress(progress) {
        if (!this.floatButton) return;

        const badge = this.floatButton.querySelector('.badge-progress');
        if (badge) {
            badge.textContent = `${progress}%`;
        }

        if (progress >= 100) {
            this.floatButton.classList.add('completed');
        } else {
            this.floatButton.classList.remove('completed');
        }
    }

    /**
     * 从后台模式唤醒
     */
    wakeFromBackground() {
        this.showProgress({ title: '任务进度' });
        this.hideFloatButton();
        this.isBackgroundMode = false;
        this.showNotification('任务进度页面已打开', 'info');
    }

    /**
     * 发送系统通知
     */
    sendSystemNotification(title, message, type = 'info') {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body: message,
                tag: this.taskId
            });
        }
        this.showNotification(message, type);
    }

    /**
     * 显示页面通知
     */
    showNotification(message, type = 'info') {
        const notificationContainer = document.getElementById('notification-container') || this.createNotificationContainer();
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fas ${this.getNotificationIcon(type)}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        notificationContainer.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    /**
     * 创建通知容器
     */
    createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'notification-container';
        document.body.appendChild(container);
        return container;
    }

    /**
     * 获取通知图标
     */
    getNotificationIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    /**
     * 设置回调函数
     */
    on(event, callback) {
        switch (event) {
            case 'complete':
                this.onCompleteCallback = callback;
                break;
            case 'error':
                this.onErrorCallback = callback;
                break;
            case 'cancel':
                this.onCancelCallback = callback;
                break;
            case 'progress':
                this.onProgressCallback = callback;
                break;
        }
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
}

// 导出全局实例
window.CommonProgressManager = CommonProgressManager;
window.commonProgressManager = new CommonProgressManager();