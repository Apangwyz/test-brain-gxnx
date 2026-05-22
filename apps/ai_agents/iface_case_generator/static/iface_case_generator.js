// 接口case生成页面专用脚本

document.addEventListener('DOMContentLoaded', function() {
    // 初始化统一进度管理器
    const progressManager = new CommonProgressManager({
        moduleName: 'iface_case_generator',
        progressUrl: '/api/progress/',
        cancelUrl: '/api/cancel/',
        uploadUrl: '/iface_case_generator/upload/'
    });

    // 全局变量
    window.uploadedFilePath = '';
    window.defaultRuleText = '';

    // 绑定事件
    bindGenerateButtonEvent();
    bindSelectAllFunctionality();
    setupRuleEditorValidation();
    enforceDigitOnlyForCountInput();

    // 添加完成回调
    progressManager.on('complete', function(result) {
        console.log('任务完成:', result);
        if (result.type === 'generation') {
            showGenerationResult(result);
        }
    });

    progressManager.on('error', function(message) {
        console.error('任务错误:', message);
        alert('生成失败: ' + message);
    });

    progressManager.on('progress', function(data) {
        console.log('进度更新:', data);
    });
});

// 显示上传模态框
function showUploadModal() {
    const progressManager = new CommonProgressManager({
        moduleName: 'iface_case_generator',
        uploadUrl: '/iface_case_generator/upload/'
    });

    progressManager.showUploadProgress({
        title: '上传API文件',
        hint: '支持从Metersphere导出的JSON格式API文件',
        accept: '.json'
    });

    // 设置上传完成回调
    progressManager.on('complete', function(result) {
        if (result.type === 'upload') {
            // 上传成功后处理API列表
            // 这里需要调用后端解析接口信息
            fetchUploadedFile();
        }
    });
}

// 获取上传的文件并解析
async function fetchUploadedFile() {
    // 这里需要根据实际上传逻辑调整
    // 假设文件已上传，现在获取解析后的API列表
    try {
        const response = await fetch('/iface_case_generator/api/get-uploaded-file/');
        const result = await response.json();
        
        if (result.success) {
            window.uploadedFilePath = result.file_path;
            handleFileUploadSuccess(result);
        }
    } catch (error) {
        console.error('获取上传文件失败:', error);
    }
}

// 处理表单提交
async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const fileInput = form.querySelector('input[type="file"]');
    
    if (!fileInput.files || !fileInput.files[0]) {
        showNotification('请先选择要上传的文件', 'error');
        return false;
    }

    const fileName = fileInput.files[0].name;
    if (!fileName.toLowerCase().endsWith('.json')) {
        showNotification('请选择JSON格式的文件', 'error');
        return false;
    }

    // 使用统一进度管理器显示上传进度
    const progressManager = new CommonProgressManager({
        moduleName: 'iface_case_generator',
        uploadUrl: '/iface_case_generator/upload/'
    });

    progressManager.showUploadProgress({
        title: '上传API文件',
        hint: '支持从Metersphere导出的JSON格式API文件',
        accept: '.json'
    });

    progressManager.on('complete', function(result) {
        if (result.type === 'upload') {
            handleFileUploadSuccess(result);
        }
    });
}

// 处理文件上传成功后的API列表显示
function handleFileUploadSuccess(response) {
    if (response.success && response.api_list) {
        // 隐藏上传区域，显示接口选择界面
        document.querySelector('.upload-container').style.display = 'none';
        document.getElementById('api-selection').style.display = 'block';
        
        // 生成接口表格行
        generateApiTableRows(response.api_list);
        
        // 保存文件路径
        window.uploadedFilePath = response.file_path;

        // 初始化规则编辑区
        fetch('/iface_case_generator/api/testcase-rule-template/')
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    window.defaultRuleText = data.rule_text || '';
                    const editor = document.getElementById('rule-editor');
                    if (editor) {
                        editor.value = window.defaultRuleText;
                        updateCharCount();
                    }
                }
            })
            .catch(() => {});
    }
}

// 更新字符计数显示
function updateCharCount() {
    const editor = document.getElementById('rule-editor');
    const charCount = document.getElementById('rule-char-count');
    if (editor && charCount) {
        const currentLength = editor.value.length;
        charCount.textContent = `${currentLength}/1000`;
        
        if (currentLength > 1000) {
            charCount.style.color = '#dc3545';
        } else if (currentLength > 800) {
            charCount.style.color = '#ffc107';
        } else {
            charCount.style.color = '#6c757d';
        }
    }
}

// 设置规则编辑器验证
function setupRuleEditorValidation() {
    const editor = document.getElementById('rule-editor');
    if (!editor) return;

    editor.addEventListener('input', function(e) {
        const value = e.target.value;
        const validValue = value.replace(/[^\u4e00-\u9fa5a-zA-Z0-9\s\n\r\t\u3000-\u303f\uff00-\uffef\u2000-\u206f\u0020-\u002f\u003a-\u0040\u005b-\u0060\u007b-\u007e]/g, '');
        
        if (value !== validValue) {
            e.target.value = validValue;
            showNotification('只允许输入中英文、数字和标点符号', 'error');
        }
        
        if (value.length > 1000) {
            e.target.value = value.substring(0, 1000);
            showNotification('字符数量不能超过1000个', 'error');
        }
        
        updateCharCount();
    });

    editor.addEventListener('paste', function(e) {
        setTimeout(() => {
            const value = e.target.value;
            const validValue = value.replace(/[^\u4e00-\u9fa5a-zA-Z0-9\s\n\r\t\u3000-\u303f\uff00-\uffef\u2000-\u206f\u0020-\u002f\u003a-\u0040\u005b-\u0060\u007b-\u007e]/g, '');
            
            if (value !== validValue) {
                e.target.value = validValue;
                showNotification('粘贴内容包含非法字符，已自动过滤', 'warning');
            }
            
            if (value.length > 1000) {
                e.target.value = value.substring(0, 1000);
                showNotification('粘贴内容超过1000字符限制，已截断', 'warning');
            }
            
            updateCharCount();
        }, 0);
    });
}

// 生成接口表格行
function generateApiTableRows(apiList) {
    const tbody = document.getElementById('api-table-body');
    tbody.innerHTML = '';
    
    apiList.forEach(api => {
        const row = document.createElement('tr');
        
        // 勾选框列
        const checkboxCell = document.createElement('td');
        checkboxCell.style.width = '80px';
        checkboxCell.style.textAlign = 'center';
        checkboxCell.style.padding = '8px';
        checkboxCell.style.border = '1px solid #dee2e6';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'api-checkbox';
        checkbox.value = api.path;
        checkbox.id = `api-${api.path.replace(/[^a-zA-Z0-9]/g, '-')}`;
        checkbox.style.margin = '0';
        checkbox.style.transform = 'scale(1.2)';
        
        checkboxCell.appendChild(checkbox);
        
        // API路径列
        const pathCell = document.createElement('td');
        pathCell.style.width = '40%';
        pathCell.style.padding = '8px';
        pathCell.style.border = '1px solid #dee2e6';
        pathCell.innerHTML = `<code>${api.method} ${api.path}</code>`;
        
        // API名称列
        const nameCell = document.createElement('td');
        nameCell.style.padding = '8px';
        nameCell.style.border = '1px solid #dee2e6';
        let nameContent = api.name;
        if (api.has_test_cases) {
            let cnt = null;
            if (api.test_case_count !== undefined && api.test_case_count !== null) {
                const n = Number(api.test_case_count);
                if (!Number.isNaN(n)) cnt = n;
            }
            nameContent += ` <span class="badge badge-info">已有（<span style="font-size: 2.0em; font-weight: bold; color: red;">${cnt}</span>）条测试用例</span>`;
        }
        nameCell.innerHTML = nameContent;
        
        row.appendChild(checkboxCell);
        row.appendChild(pathCell);
        row.appendChild(nameCell);
        
        tbody.appendChild(row);
    });
    
    bindSelectAllFunctionality();
}

// 绑定生成按钮事件
function bindGenerateButtonEvent() {
    const generateBtn = document.getElementById('generateBtn');
    if (!generateBtn) return;

    generateBtn.addEventListener('click', function() {
        const selectedApis = getSelectedApis();
        if (selectedApis.length === 0) {
            showNotification('请至少选择一个接口', 'warning');
            return;
        }
        
        const countInput = document.getElementById('count-per-api');
        let countPerApi = parseInt(countInput.value || '0', 10);
        if (isNaN(countPerApi) || countPerApi <= 0) {
            showNotification('每个接口生成数量必须为正整数', 'warning');
            countInput.focus();
            return;
        }
        
        const totalCount = selectedApis.length * countPerApi;
        if (totalCount < 1 || totalCount > 100) {
            showNotification('单次生成测试用例数量不能超过100条', 'warning');
            return;
        }
        
        const priority = document.getElementById('priority').value;
        const llmProvider = document.getElementById('llm-provider').value;
        
        // 显示进度界面
        const progressManager = new CommonProgressManager({
            moduleName: 'iface_case_generator',
            progressUrl: '/api/progress/',
            cancelUrl: '/api/cancel/'
        });

        progressManager.showProgress({
            title: 'AI 正在生成API测试用例'
        });

        // 初始化步骤
        progressManager.initializeSteps([
            { stage: 'initializing', title: '初始化', description: '准备生成环境...', status: 'pending' },
            { stage: 'analyzing', title: '分析接口', description: '分析选中的API接口...', status: 'pending' },
            { stage: 'generating', title: '生成用例', description: 'AI正在生成测试用例...', status: 'pending' },
            { stage: 'validating', title: '验证结果', description: '验证生成的测试用例...', status: 'pending' },
            { stage: 'completed', title: '完成', description: '生成完成', status: 'pending' }
        ]);

        // 发送生成请求
        generateTestCases(selectedApis, countPerApi, priority, llmProvider, progressManager);
    });
}

// 对“每个接口生成测试用例数量”的输入框仅允许数字
function enforceDigitOnlyForCountInput() {
    const countInput = document.getElementById('count-per-api');
    if (!countInput) return;

    try {
        countInput.setAttribute('inputmode', 'numeric');
        countInput.setAttribute('pattern', '\\d*');
    } catch (_) {}

    const sanitize = () => {
        const digits = (countInput.value || '').replace(/\D+/g, '');
        countInput.value = digits;
    };

    countInput.addEventListener('input', sanitize);
    countInput.addEventListener('paste', function() {
        setTimeout(sanitize, 0);
    });
    countInput.addEventListener('blur', function() {
        sanitize();
        if (countInput.value === '' || countInput.value === '0') {
            countInput.value = '1';
        }
    });
}

// 绑定全选功能
function bindSelectAllFunctionality() {
    const selectAllCheckbox = document.getElementById('select-all');
    const apiCheckboxes = document.querySelectorAll('.api-checkbox');
    
    if (!selectAllCheckbox) return;

    selectAllCheckbox.addEventListener('change', function() {
        const isChecked = this.checked;
        apiCheckboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });
    });
    
    apiCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectAllState();
        });
    });
}

// 更新全选复选框状态
function updateSelectAllState() {
    const selectAllCheckbox = document.getElementById('select-all');
    const apiCheckboxes = document.querySelectorAll('.api-checkbox');
    const checkedCount = document.querySelectorAll('.api-checkbox:checked').length;
    const totalCount = apiCheckboxes.length;
    
    if (checkedCount === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCount === totalCount) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    }
}

// 获取选中的接口
function getSelectedApis() {
    const checkboxes = document.querySelectorAll('#api-table-body input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// 生成测试用例
async function generateTestCases(selectedApis, countPerApi, priority, llmProvider, progressManager) {
    try {
        const formData = new FormData();
        formData.append('generate_test_cases', 'true');
        formData.append('file_path', window.uploadedFilePath);
        formData.append('selected_apis', JSON.stringify(selectedApis));
        formData.append('count_per_api', countPerApi);
        formData.append('priority', priority);
        formData.append('llm_provider', llmProvider);

        const editor = document.getElementById('rule-editor');
        if (editor) {
            const current = (editor.value || '').trim();
            const defaultText = (window.defaultRuleText || '').trim();
            if (current && current !== defaultText) {
                const isValidChars = /^[\u4e00-\u9fa5a-zA-Z0-9\s\n\r\t\u3000-\u303f\uff00-\uffef\u2000-\u206f\u0020-\u002f\u003a-\u0040\u005b-\u0060\u007b-\u007e]*$/.test(current);
                const isValidLength = current.length <= 1000;
                
                if (isValidChars && isValidLength) {
                    formData.append('rules_override', current);
                }
            }
        }
        
        const response = await fetch('/iface_case_generator/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });
        
        const result = await response.json();
        
        if (result.success && result.task_id) {
            // 开始监听进度
            progressManager.startProgressStream(result.task_id);
            window.currentTaskId = result.task_id;
        } else {
            showNotification('生成失败: ' + (result.error || '未知错误'), 'error');
            document.getElementById('api-selection').style.display = 'block';
        }
        
    } catch (error) {
        console.error('生成测试用例失败:', error);
        showNotification('生成失败: ' + error.message, 'error');
        document.getElementById('api-selection').style.display = 'block';
    }
}

// 显示生成结果
function showGenerationResult(result) {
    document.getElementById('api-selection').style.display = 'none';
    document.getElementById('generation-result').style.display = 'block';
    
    document.getElementById('result-message').textContent = result.message || 'API测试用例生成完成';
    if (result.file_path) {
        document.getElementById('download-link').href = `/iface_case_generator/download_file/?file_path=${encodeURIComponent(result.file_path)}`;
    }
}

// 显示通知
function showNotification(message, type = 'info') {
    // 检查是否已有通知容器
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'notification-container';
        document.body.appendChild(container);
    }

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    notification.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;

    container.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}