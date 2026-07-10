// PRD分析页面的JavaScript功能
// 集成统一进度管理组件，支持PDF和DOCX文件上传

document.addEventListener('DOMContentLoaded', function() {
    // 全局变量
    window.uploadedFilePath = '';
    window.uploadedFileName = '';
    
    // 加载系统列表
    loadPrdSystems();
    
    // 初始化统一进度管理器
    const progressManager = new CommonProgressManager({
        moduleName: 'prd_analyzer',
        progressUrl: '/api/progress/',
        cancelUrl: '/api/cancel/',
        uploadUrl: '/prd_analyzer/upload/'
    });

    // 添加完成回调
    progressManager.on('complete', function(result) {
        console.log('任务完成:', result);
        if (result.type === 'upload') {
            handleUploadComplete(result);
        } else if (result.type === 'analysis') {
            showAnalysisResult(result);
        }
    });

    progressManager.on('error', function(message) {
        console.error('任务错误:', message);
        showNotification('操作失败: ' + message, 'error');
        resetUI();
    });

    // 绑定解析按钮事件
    bindAnalyzeButtonEvent();
});

// 加载系统列表
function loadPrdSystems() {
    fetch('/api/systems/?status=active')
    .then(r => r.json())
    .then(data => {
        const select = document.getElementById('prd-system-select');
        if (!select) return;
        if (data.success && data.systems) {
            select.innerHTML = '<option value="">-- 请选择系统 --</option>';
            data.systems.forEach(function(s) {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name + ' (' + s.code + ')';
                select.appendChild(opt);
            });
        }
    })
    .catch(err => console.error('[prd_analyzer] 加载系统列表失败:', err));
}

// 显示上传模态框
function showUploadModal() {
    const progressManager = new CommonProgressManager({
        moduleName: 'prd_analyzer',
        uploadUrl: '/prd_analyzer/upload/'
    });

    progressManager.showUploadProgress({
        title: '上传PRD文件',
        hint: '支持 .docx 和 .pdf 格式的PRD文件',
        accept: '.docx,.pdf'
    });

    // 设置上传完成回调
    progressManager.on('complete', function(result) {
        if (result.type === 'upload') {
            handleUploadComplete(result);
        }
    });

    progressManager.on('error', function(message) {
        showNotification('上传失败: ' + message, 'error');
    });
}

// 处理上传完成
function handleUploadComplete(result) {
    if (result.file_path && result.file_name) {
        window.uploadedFilePath = result.file_path;
        window.uploadedFileName = result.file_name;
        
        // 显示选中文件信息
        const fileInfoDiv = document.getElementById('selected-file-info');
        const fileNameDiv = document.getElementById('selected-file-name');
        const statusDiv = document.getElementById('upload-status');
        
        fileInfoDiv.style.display = 'block';
        fileNameDiv.textContent = '已选择文件: ' + result.file_name;
        statusDiv.textContent = '文件上传成功';
        statusDiv.style.color = '#28a745';
        
        // 显示解析按钮
        document.getElementById('analyze-container').style.display = 'block';
        
        showNotification('文件上传成功', 'success');
    }
}

// 绑定解析按钮事件
function bindAnalyzeButtonEvent() {
    const submitBtn = document.getElementById('submitBtn');
    if (!submitBtn) return;

    submitBtn.addEventListener('click', function() {
        if (!window.uploadedFilePath) {
            showNotification('请先上传文件', 'warning');
            return;
        }
        
        const systemId = document.getElementById('prd-system-select')?.value;
        if (!systemId) {
            showNotification('请先选择所属系统', 'warning');
            document.getElementById('prd-system-select')?.focus();
            return;
        }
        window.prdSystemId = parseInt(systemId);

        // 显示进度界面
        const progressManager = new CommonProgressManager({
            moduleName: 'prd_analyzer',
            progressUrl: '/api/progress/',
            cancelUrl: '/api/cancel/'
        });

        progressManager.showProgress({
            title: 'AI 正在解析PRD文档'
        });

        // 初始化步骤
        progressManager.initializeSteps([
            { stage: 'initializing', title: '初始化', description: '准备解析环境...', status: 'pending' },
            { stage: 'extracting', title: '提取内容', description: '从文件中提取文本内容...', status: 'pending' },
            { stage: 'analyzing', title: '分析文档', description: 'AI分析PRD文档内容...', status: 'pending' },
            { stage: 'extracting_points', title: '提取测试点', description: '提取测试点和测试场景...', status: 'pending' },
            { stage: 'validating', title: '验证结果', description: '验证提取结果...', status: 'pending' },
            { stage: 'completed', title: '完成', description: '解析完成', status: 'pending' }
        ]);

        // 发送解析请求
        analyzePrdDocument(progressManager);
    });
}

// 分析PRD文档
async function analyzePrdDocument(progressManager) {
    try {
        const response = await fetch('/prd_analyzer/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({
                file_path: window.uploadedFilePath,
                file_name: window.uploadedFileName,
                system_id: window.prdSystemId || null
            })
        });

        const result = await response.json();

        if (result.success && result.task_id) {
            // 开始监听进度
            progressManager.startProgressStream(result.task_id);
            window.currentTaskId = result.task_id;
        } else {
            progressManager.hide(false);
            showNotification(result.error || '解析失败', 'error');
            resetUI();
        }
    } catch (error) {
        console.error('解析请求失败:', error);
        progressManager.hide(false);
        showNotification('网络错误或服务器不可用: ' + error.message, 'error');
        resetUI();
    }
}

// 显示分析结果
function showAnalysisResult(result) {
    const progressManager = new CommonProgressManager({
        moduleName: 'prd_analyzer'
    });
    progressManager.hide(false);

    // 显示结果区域
    const resultTable = document.getElementById('resultTable');
    resultTable.style.display = 'block';

    // 隐藏上传区域和解析按钮
    document.getElementById('analyze-container').style.display = 'none';

    // 显示统计信息
    if (result.summary) {
        displaySummary(result.summary);
    }

    // 显示测试点和场景数据
    if (result.test_points) {
        displayTestPoints(result.test_points);
    }

    showNotification('PRD文档解析完成', 'success');
}

// 显示统计信息
function displaySummary(summary) {
    const summaryDiv = document.getElementById('summary');
    summaryDiv.innerHTML = `
        <div class="col-md-4">
            <p><strong>总测试点数：</strong>${summary.total_test_points}</p>
            <p><strong>总测试场景数：</strong>${summary.total_test_scenarios}</p>
        </div>
        <div class="col-md-8">
            <p><strong>高优先级测试点：</strong>${summary.high_priority_points}</p>
            <p><strong>中优先级测试点：</strong>${summary.medium_priority_points}</p>
            <p><strong>低优先级测试点：</strong>${summary.low_priority_points}</p>
        </div>
    `;
}

// 显示测试点和场景数据
function displayTestPoints(testPoints) {
    const resultTableBody = document.getElementById('resultTableBody');
    resultTableBody.innerHTML = '';

    testPoints.forEach(point => {
        const scenariosCount = point.scenarios.length;
        
        point.scenarios.forEach((scenario, index) => {
            const row = document.createElement('tr');
            
            const formattedDescription = scenario.description.split('\n').map(line => {
                if (line.trim().startsWith('预期结果：')) {
                    return `<div class="text-success mt-2"><strong>${line.trim()}</strong></div>`;
                } else if (line.trim().match(/^\d+\./)) {
                    return `<div class="mt-1">${line.trim()}</div>`;
                }
                return line;
            }).join('');
            
            if (index === 0) {
                row.innerHTML = `
                    <td rowspan="${scenariosCount}">${escapeHtml(point.title)}</td>
                    <td rowspan="${scenariosCount}">${escapeHtml(point.description)}</td>
                    <td rowspan="${scenariosCount}" class="priority-${point.priority.toLowerCase()}">${point.priority}</td>
                    <td>${formattedDescription}</td>
                    <td>${scenario.test_type}</td>
                `;
            } else {
                row.innerHTML = `
                    <td>${formattedDescription}</td>
                    <td>${scenario.test_type}</td>
                `;
            }
            
            resultTableBody.appendChild(row);
        });
    });
}

// 重置UI状态
function resetUI() {
    window.uploadedFilePath = '';
    window.uploadedFileName = '';
    
    document.getElementById('selected-file-info').style.display = 'none';
    document.getElementById('analyze-container').style.display = 'none';
    document.getElementById('resultTable').style.display = 'none';
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 显示通知
function showNotification(message, type = 'info') {
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