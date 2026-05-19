// 测试用例生成页面专用脚本

document.addEventListener('DOMContentLoaded', function() {
    // 初始化文件上传功能
    initFileUpload();
    
    // 初始化表单提交功能
    initFormSubmit();
    
    // 初始化其他功能
    initOtherFeatures();
});

// 文件上传相关变量
let uploadedFiles = [];
let isUploading = false;

// 初始化文件上传功能
function initFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const uploadedFilesContainer = document.getElementById('uploaded-files');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = uploadProgress?.querySelector('.progress-bar');
    const progressText = uploadProgress?.querySelector('.progress-text');
    
    // 支持的文件类型
    const allowedExtensions = ['.docx', '.md', '.txt', '.pdf'];
    
    // 拖拽上传 - 处理dragenter事件
    uploadArea?.addEventListener('dragenter', function(e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.add('dragover');
    });
    
    // 拖拽上传 - 处理dragover事件
    uploadArea?.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.add('dragover');
    });
    
    // 拖拽上传 - 处理dragleave事件
    uploadArea?.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const rect = uploadArea.getBoundingClientRect();
        if (e.clientX <= rect.left || e.clientX >= rect.right ||
            e.clientY <= rect.top || e.clientY >= rect.bottom) {
            uploadArea.classList.remove('dragover');
        }
    });
    
    // 拖拽上传 - 处理drop事件
    uploadArea?.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer?.files || []);
        handleFiles(files);
    });
    
    // 为document添加事件处理，防止拖拽事件影响其他元素
    document.addEventListener('dragenter', function(e) {
        e.preventDefault();
    });
    
    document.addEventListener('dragover', function(e) {
        e.preventDefault();
    });
    
    document.addEventListener('drop', function(e) {
        e.preventDefault();
    });
    
    // 文件选择变化 - 文件输入元素直接覆盖在上传区域上，无需额外点击事件
    fileInput?.addEventListener('change', function(e) {
        e.stopPropagation();
        const files = Array.from(e.target?.files || []);
        handleFiles(files);
    });
    
    // 处理文件
    function handleFiles(files) {
        if (!files || files.length === 0) return;
        if (isUploading) {
            showNotification('正在处理其他文件，请稍候...', 'warning');
            return;
        }
        
        // 筛选有效文件
        const validFiles = [];
        const maxFileSize = 50 * 1024 * 1024; // 50MB
        files.forEach(file => {
            const extension = file.name.split('.').pop().toLowerCase();
            if (!allowedExtensions.includes('.' + extension)) {
                showNotification(`不支持的文件类型: .${extension}，支持 .docx、.md、.txt、.pdf`, 'error');
                return;
            }
            
            if (file.size > maxFileSize) {
                const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
                showNotification(`文件 "${file.name}" 大小超过限制（${fileSizeMB}MB > 50MB）`, 'error');
                return;
            }
            
            validFiles.push(file);
        });
        
        if (validFiles.length === 0) {
            showNotification('没有有效的文件需要上传', 'warning');
            return;
        }
        
        // 显示进度条
        if (uploadProgress) {
            uploadProgress.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = `准备上传 ${validFiles.length} 个文件...`;
        }
        
        // 批量添加文件到列表并开始上传
        validFiles.forEach((file) => {
            const fileItem = createFileItem(file);
            uploadedFilesContainer?.appendChild(fileItem);
            uploadedFiles.push({
                file: file,
                element: fileItem,
                id: Date.now() + Math.random(),
                status: 'pending',
                uploadTime: null
            });
        });
        
        // 更新上传区域样式
        uploadArea?.classList.add('has-files');
        
        // 重置文件输入以便可以重复选择相同文件
        if (fileInput) {
            fileInput.value = '';
        }
        
        // 自动开始上传
        startUpload();
    }
    
    // 创建文件项元素
    function createFileItem(file) {
        const item = document.createElement('div');
        item.className = 'uploaded-file-item';
        item.dataset.id = Date.now() + Math.random();
        
        const fileExtension = file.name.split('.').pop().toLowerCase();
        const iconClass = getFileIconClass(fileExtension);
        const currentTime = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        
        item.innerHTML = `
            <div class="file-info">
                <span class="file-icon ${iconClass}"></span>
                <div class="file-details">
                    <span class="file-name">${file.name}</span>
                    <span class="file-meta">${formatFileSize(file.size)} · ${currentTime}</span>
                </div>
                <span class="file-status pending">
                    <span class="status-icon">
                        <i class="fas fa-spinner fa-spin"></i>
                    </span>
                    <span class="status-text">上传中...</span>
                </span>
            </div>
            <div class="file-actions">
                <button class="retry-btn" style="display: none;" onclick="retryUpload('${item.dataset.id}')">
                    <i class="fas fa-redo"></i>
                </button>
                <button class="remove-file-btn" onclick="removeFile('${item.dataset.id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        return item;
    }
    
    // 获取文件图标类名
    function getFileIconClass(extension) {
        switch (extension) {
            case 'docx':
                return 'fas fa-file-word text-blue';
            case 'md':
                return 'fas fa-file-code text-purple';
            case 'txt':
                return 'fas fa-file-text text-gray';
            case 'pdf':
                return 'fas fa-file-pdf text-red';
            default:
                return 'fas fa-file text-gray';
        }
    }
    
    // 格式化文件大小
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    
    // 开始上传
    function startUpload() {
        isUploading = true;
        const pendingFiles = uploadedFiles.filter(f => f.status === 'pending');
        
        if (pendingFiles.length === 0) {
            isUploading = false;
            return;
        }
        
        const totalFiles = pendingFiles.length;
        let processedFiles = 0;
        let combinedContent = '';
        
        // 更新进度文本
        if (progressText) {
            progressText.textContent = `正在上传 0/${totalFiles} 个文件...`;
        }
        
        // 逐个处理文件
        pendingFiles.forEach((uploadedFile, index) => {
            // 更新状态为上传中
            uploadedFile.status = 'uploading';
            
            const formData = new FormData();
            formData.append('file', uploadedFile.file);
            
            // 添加加载动画
            addLoadingAnimation(uploadedFile.element);
            
            fetch('/test_case_generator/upload-file/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                processedFiles++;
                
                // 移除加载动画
                removeLoadingAnimation(uploadedFile.element);
                
                // 更新文件状态
                const statusElement = uploadedFile.element.querySelector('.file-status');
                if (data.success) {
                    uploadedFile.status = 'success';
                    uploadedFile.uploadTime = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
                    
                    uploadedFile.element.classList.add('success');
                    uploadedFile.element.classList.remove('error');
                    statusElement.className = 'file-status success';
                    statusElement.innerHTML = '<span class="status-icon"><i class="fas fa-check-circle"></i></span><span class="status-text">上传成功</span>';
                    
                    // 隐藏重试按钮，显示成功动画
                    const retryBtn = uploadedFile.element.querySelector('.retry-btn');
                    if (retryBtn) retryBtn.style.display = 'none';
                    
                    addSuccessAnimation(uploadedFile.element);
                    
                    // 合并内容
                    combinedContent += (combinedContent ? '\n\n---\n\n' : '') + `## ${uploadedFile.file.name}\n\n` + data.content;
                    
                    showNotification(`文件 "${uploadedFile.file.name}" 上传成功`, 'success');
                } else {
                    uploadedFile.status = 'error';
                    uploadedFile.errorMessage = data.message;
                    
                    uploadedFile.element.classList.add('error');
                    uploadedFile.element.classList.remove('success');
                    statusElement.className = 'file-status error';
                    statusElement.innerHTML = '<span class="status-icon"><i class="fas fa-exclamation-circle"></i></span><span class="status-text">上传失败</span>';
                    
                    // 显示重试按钮
                    const retryBtn = uploadedFile.element.querySelector('.retry-btn');
                    if (retryBtn) retryBtn.style.display = 'inline-block';
                    
                    showNotification(`文件 "${uploadedFile.file.name}" 上传失败: ${data.message}`, 'error');
                }
                
                // 更新进度
                updateProgress(processedFiles, totalFiles);
                
                // 所有文件处理完成
                if (processedFiles === totalFiles) {
                    finishUpload(combinedContent, totalFiles);
                }
            })
            .catch(error => {
                processedFiles++;
                uploadedFile.status = 'error';
                uploadedFile.errorMessage = error.message || '网络错误';
                
                // 移除加载动画
                removeLoadingAnimation(uploadedFile.element);
                
                const statusElement = uploadedFile.element.querySelector('.file-status');
                uploadedFile.element.classList.add('error');
                uploadedFile.element.classList.remove('success');
                statusElement.className = 'file-status error';
                statusElement.innerHTML = '<span class="status-icon"><i class="fas fa-exclamation-circle"></i></span><span class="status-text">上传失败</span>';
                
                // 显示重试按钮
                const retryBtn = uploadedFile.element.querySelector('.retry-btn');
                if (retryBtn) retryBtn.style.display = 'inline-block';
                
                // 更新进度
                updateProgress(processedFiles, totalFiles);
                
                // 所有文件处理完成
                if (processedFiles === totalFiles) {
                    finishUpload(combinedContent, totalFiles);
                }
            });
        });
    }
    
    // 更新进度
    function updateProgress(processed, total) {
        const progress = Math.round((processed / total) * 100);
        if (progressBar) progressBar.style.width = progress + '%';
        if (progressText) progressText.textContent = `正在上传 ${processed}/${total} 个文件...`;
    }
    
    // 完成上传
    function finishUpload(combinedContent, totalFiles) {
        isUploading = false;
        
        // 隐藏进度条
        if (uploadProgress) {
            setTimeout(() => {
                uploadProgress.style.display = 'none';
            }, 500);
        }
        
        const successCount = uploadedFiles.filter(f => f.status === 'success').length;
        
        if (successCount > 0 && combinedContent) {
            // 将解析内容填充到文本框
            const inputText = document.getElementById('input-text');
            if (inputText) {
                // 如果已有内容，追加新内容
                if (inputText.value && inputText.value.trim()) {
                    inputText.value += '\n\n' + combinedContent;
                } else {
                    inputText.value = combinedContent;
                }
                // 滚动到文本框
                inputText.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            showNotification(`成功上传 ${successCount}/${totalFiles} 个文件，内容已填充到需求描述框`, 'success');
        } else if (successCount === 0) {
            showNotification('所有文件上传失败，请检查网络或重试', 'error');
        }
    }
    
    // 添加加载动画
    function addLoadingAnimation(element) {
        element.style.opacity = '0.7';
    }
    
    // 移除加载动画
    function removeLoadingAnimation(element) {
        element.style.opacity = '1';
    }
    
    // 添加成功动画
    function addSuccessAnimation(element) {
        element.style.animation = 'successPulse 0.5s ease-out';
        setTimeout(() => {
            element.style.animation = '';
        }, 500);
    }
    
    // 重试上传
    window.retryUpload = function(id) {
        const uploadedFile = uploadedFiles.find(f => f.element.dataset.id === id);
        if (!uploadedFile) return;
        
        // 更新状态为待上传
        uploadedFile.status = 'pending';
        
        // 重置UI状态
        const statusElement = uploadedFile.element.querySelector('.file-status');
        uploadedFile.element.classList.remove('success', 'error');
        statusElement.className = 'file-status pending';
        statusElement.innerHTML = '<span class="status-icon"><i class="fas fa-spinner fa-spin"></i></span><span class="status-text">重新上传...</span>';
        
        // 隐藏重试按钮
        const retryBtn = uploadedFile.element.querySelector('.retry-btn');
        if (retryBtn) retryBtn.style.display = 'none';
        
        // 重新开始上传
        startUpload();
    };
    
    // 移除文件
    window.removeFile = function(id) {
        const index = uploadedFiles.findIndex(f => f.element.dataset.id === id);
        if (index !== -1) {
            const file = uploadedFiles[index];
            // 添加移除动画
            file.element.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => {
                file.element.remove();
                uploadedFiles.splice(index, 1);
                
                // 更新上传区域样式
                if (uploadedFiles.length === 0) {
                    uploadArea?.classList.remove('has-files');
                }
            }, 300);
        }
    };
    
    // 清空所有文件
    window.clearAllFiles = function() {
        uploadedFiles.forEach(f => {
            f.element.style.animation = 'slideOut 0.3s ease-out';
        });
        setTimeout(() => {
            uploadedFiles.forEach(f => f.element.remove());
            uploadedFiles = [];
            uploadArea?.classList.remove('has-files');
        }, 300);
    };
}

// 初始化表单提交功能
function initFormSubmit() {
    const generateForm = document.getElementById('generate-form');
    const inputTextLabel = document.getElementById('input-text-label');
    const inputText = document.getElementById('input-text');
    const generateButton = document.getElementById('generate-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    // 表单提交时显示加载指示器
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取输入文本
            const inputTextValue = inputText?.value?.trim();
            
            // 获取选择框元素
            const designMethodsSelect = document.getElementById('case_design_methods');
            const caseCategoriesSelect = document.getElementById('case_categories');
            
            if (!designMethodsSelect || !caseCategoriesSelect) {
                console.error('找不到选择框元素');
                return;
            }
            
            // 获取选中的值
            const selectedDesignMethods = Array.from(designMethodsSelect.selectedOptions || []).map(option => option.textContent);
            const selectedCaseCategories = Array.from(caseCategoriesSelect.selectedOptions || []).map(option => option.textContent);
            
            if (!inputTextValue) {
                showNotification('请输入需求描述或上传需求文档', 'error');
                return;
            }
            
            // 禁用生成按钮
            if (generateButton) {
                generateButton.disabled = true;
            }
            
            // 清空结果容器
            const resultContainer = document.getElementById('result-container');
            if (resultContainer) {
                resultContainer.innerHTML = '';
            }
            
            // 构造请求数据
            const requestData = {
                requirements: inputTextValue,
                llm_provider: document.getElementById('llm-provider')?.value || 'deepseek',
                case_design_methods: selectedDesignMethods,
                case_categories: selectedCaseCategories,
                case_count: document.getElementById('case_count')?.value || '10'
            };
            
            console.log('发送的数据:', requestData);
            
            // 创建进度管理器
            const progressManager = new GenerationProgressManager();
            
            // 设置完成回调
            progressManager.onComplete(function(testCases) {
                // 启用生成按钮
                if (generateButton) {
                    generateButton.disabled = false;
                }
                
                // 显示测试用例
                displayTestCases(testCases);
                
                // 保存生成的测试用例到会话存储
                sessionStorage.setItem('generatedTestCases', JSON.stringify(testCases));
                sessionStorage.setItem('inputText', inputTextValue);
            });
            
            // 设置错误回调
            progressManager.onError(function(message) {
                // 启用生成按钮
                if (generateButton) {
                    generateButton.disabled = false;
                }
                
                showNotification('生成失败: ' + message, 'error');
            });
            
            // 发送请求启动任务
            fetch('/test_case_generator/generate-with-progress/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(requestData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.task_id) {
                    console.log('任务已启动:', data.task_id);
                    
                    // 显示进度模态框
                    progressManager.show();
                    
                    // 初始化步骤显示
                    const initialSteps = [
                        { stage: 'initializing', title: '初始化', description: '准备生成环境...', status: 'pending' },
                        { stage: 'analyzing', title: '分析需求', description: '正在理解您的需求描述...', status: 'pending' },
                        { stage: 'retrieving', title: '检索知识库', description: '从知识库中检索相关信息...', status: 'pending' },
                        { stage: 'generating', title: '生成测试用例', description: 'AI正在生成测试用例...', status: 'pending' },
                        { stage: 'validating', title: '验证结果', description: '验证生成的测试用例...', status: 'pending' },
                        { stage: 'completed', title: '完成', description: '测试用例生成完成！', status: 'pending' }
                    ];
                    progressManager.initializeSteps(initialSteps);
                    
                    // 开始监听进度
                    progressManager.startProgressStream(data.task_id);
                } else {
                    showNotification(data.message || '启动任务失败', 'error');
                    if (generateButton) {
                        generateButton.disabled = false;
                    }
                }
            })
            .catch(error => {
                console.error('请求发生错误:', error);
                showNotification('请求失败: ' + error.message, 'error');
                if (generateButton) {
                    generateButton.disabled = false;
                }
            });
        });
    }
}

// 初始化其他功能
function initOtherFeatures() {
    // 保存用户选择的大模型到本地存储
    const llmProviderSelect = document.getElementById('llm-provider');
    if (llmProviderSelect) {
        llmProviderSelect.addEventListener('change', function() {
            localStorage.setItem('preferred-llm-provider', this.value);
        });
        
        // 页面加载时恢复用户之前的选择
        if (!llmProviderSelect.options[llmProviderSelect.selectedIndex].hasAttribute('selected')) {
            const savedProvider = localStorage.getItem('preferred-llm-provider');
            if (savedProvider) {
                for (let i = 0; i < llmProviderSelect.options.length; i++) {
                    if (llmProviderSelect.options[i].value === savedProvider) {
                        llmProviderSelect.value = savedProvider;
                        break;
                    }
                }
            }
        }
    }
}

// 显示测试用例
function displayTestCases(testCases) {
    let resultContainer = document.getElementById('result-container');
    if (!resultContainer) {
        resultContainer = document.createElement('div');
        resultContainer.id = 'result-container';
        resultContainer.className = 'mt-4';
        const generateForm = document.getElementById('generate-form');
        if (generateForm) {
            generateForm.parentNode.insertBefore(resultContainer, generateForm.nextSibling);
        } else {
            document.body.appendChild(resultContainer);
        }
    }

    if (!testCases || !testCases.length) {
        resultContainer.innerHTML = '<div class="alert alert-info">没有生成测试用例</div>';
        return;
    }
    
    let html = `
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">生成的测试用例</h5>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered table-hover">
                        <thead class="thead-light">
                            <tr>
                                <th width="5%">编号</th>
                                <th width="25%">测试用例描述</th>
                                <th width="35%">测试步骤</th>
                                <th width="35%">预期结果</th>
                            </tr>
                        </thead>
                        <tbody>
    `;

    testCases.forEach((testCase, index) => {
        const testSteps = Array.isArray(testCase.test_steps) 
            ? testCase.test_steps 
            : testCase.test_steps.split('\n').filter(step => step.trim());
        
        const expectedResults = Array.isArray(testCase.expected_results)
            ? testCase.expected_results
            : testCase.expected_results.split('\n').filter(result => result.trim());

        html += `
            <tr>
                <td>${index + 1}</td>
                <td>${testCase.description || ''}</td>
                <td>
                    ${testSteps.map(step => `<div class="mb-2">${step}</div>`).join('')}
                </td>
                <td>
                    ${expectedResults.map(result => `<div class="mb-2">${result}</div>`).join('')}
                </td>
            </tr>
        `;
    });

    html += `
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="text-right mt-3">
            <button id="save-button" class="btn btn-success">保存测试用例</button>
        </div>
    `;

    resultContainer.innerHTML = html;

    // 重新绑定保存按钮事件
    const saveButton = document.getElementById('save-button');
    if (saveButton) {
        saveButton.disabled = false;
        
        saveButton.addEventListener('click', function() {
            console.log('保存按钮被点击');
            
            let testCases = null;
            try {
                testCases = JSON.parse(sessionStorage.getItem('generatedTestCases') || '[]');
            } catch (error) {
                console.error('解析测试用例数据失败:', error);
                alert('解析测试用例数据失败，请查看控制台获取详细信息');
                return;
            }
            
            if (!testCases || testCases.length === 0) {
                alert('没有可保存的测试用例');
                return;
            }
            
            const requirementElement = document.getElementById('input-text');
            const llmProviderElement = document.getElementById('llm-provider');
            
            if (!requirementElement || !llmProviderElement) {
                console.error('缺失必要的页面元素');
                alert('页面元素缺失，无法保存数据');
                return;
            }
            
            const requestData = {
                test_cases: testCases,
                requirement: requirementElement.value,
                llm_provider: llmProviderElement.value
            };
            
            saveButton.disabled = true;
            saveButton.textContent = '保存中...';
            
            fetch('/test_case_generator/save-test-case/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            })
            .then(response => response.json())
            .then(data => {
                saveButton.textContent = '保存测试用例';
                
                if (data.success) {
                    alert('测试用例保存成功！');
                    sessionStorage.removeItem('generatedTestCases');
                    sessionStorage.removeItem('inputText');
                } else {
                    saveButton.disabled = false;
                    alert('保存失败：' + (data.message || '未知错误'));
                }
            })
            .catch(error => {
                saveButton.disabled = false;
                saveButton.textContent = '保存测试用例';
                console.error('保存失败:', error);
                alert('保存失败，请查看控制台获取详细信息');
            });
        });
    }
}

// 获取CSRF Token的辅助函数
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 显示通知消息
function showNotification(message, type = 'success') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
        </span>
        <span class="toast-message">${message}</span>
    `;
    
    // 添加到页面
    document.body.appendChild(toast);
    
    // 显示toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // 3秒后自动消失
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}
