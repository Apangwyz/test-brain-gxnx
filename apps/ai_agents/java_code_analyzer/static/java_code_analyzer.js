// Java源码分析页面的JavaScript功能
// 集成统一进度管理组件

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('javaCodeAnalysisForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    
    // 初始化统一进度管理器
    const progressManager = new CommonProgressManager({
        moduleName: 'java_code_analyzer',
        progressUrl: '/api/progress/',
        cancelUrl: '/api/cancel/'
    });

    // 添加完成回调
    progressManager.on('complete', function(result) {
        console.log('任务完成:', result);
        if (result.type === 'analysis') {
            showAnalysisResult(result);
        }
    });

    progressManager.on('error', function(message) {
        console.error('任务错误:', message);
        showNotification('分析失败: ' + message, 'error');
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = '开始分析';
    });

    progressManager.on('progress', function(data) {
        console.log('进度更新:', data);
    });

    // 表单提交事件处理
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        // 获取表单数据
        const targetService = document.getElementById('targetService').value;
        const baseCommit = document.getElementById('baseCommit').value;
        const newCommit = document.getElementById('newCommit').value;
        const llmProvider = document.getElementById('llmProvider').value;

        // 验证输入
        if (!targetService || !baseCommit || !newCommit) {
            showNotification('请填写所有必填字段', 'warning');
            return;
        }

        // 验证commit格式（简单验证）
        if (!/^[a-f0-9]{7,40}$/i.test(baseCommit)) {
            showNotification('Base Commit格式不正确，请输入有效的commit哈希值', 'warning');
            return;
        }

        if (!/^[a-f0-9]{7,40}$/i.test(newCommit)) {
            showNotification('New Commit格式不正确，请输入有效的commit哈希值', 'warning');
            return;
        }

        // 禁用按钮以防止重复提交
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = '分析中...';

        // 显示进度界面
        progressManager.showProgress({
            title: 'AI 正在分析Java源码变更'
        });

        // 初始化步骤
        progressManager.initializeSteps([
            { stage: 'initializing', title: '初始化', description: '准备分析环境...', status: 'pending' },
            { stage: 'fetching', title: '获取代码', description: '从版本库获取代码...', status: 'pending' },
            { stage: 'diffing', title: '代码对比', description: '对比两个commit的代码差异...', status: 'pending' },
            { stage: 'analyzing', title: '分析变更', description: 'AI分析代码变更内容...', status: 'pending' },
            { stage: 'reporting', title: '生成报告', description: '生成分析报告...', status: 'pending' },
            { stage: 'completed', title: '完成', description: '分析完成', status: 'pending' }
        ]);

        try {
            // 发送分析请求
            const response = await fetch('/java_code_analyzer/api/java-code-analyzer-service/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    project_id: targetService,
                    base_commit: baseCommit,
                    new_commit: newCommit,
                    llm_provider: llmProvider
                })
            });

            const data = await response.json();

            if (data.success && data.task_id) {
                // 开始监听进度
                progressManager.startProgressStream(data.task_id);
                window.currentTaskId = data.task_id;
            } else {
                progressManager.hide(false);
                showNotification(data.error || '分析失败', 'error');
                analyzeBtn.disabled = false;
                analyzeBtn.textContent = '开始分析';
            }
        } catch (error) {
            console.error('分析请求失败:', error);
            progressManager.hide(false);
            showNotification('网络错误或服务器不可用: ' + error.message, 'error');
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = '开始分析';
        }
    });

    // 目标服务选择变化事件处理
    document.getElementById('targetService').addEventListener('change', function() {
        const selectedValue = this.value;
        if (selectedValue === 'custom') {
            console.log('用户选择了自定义服务');
        }
    });
});

// 获取CSRF令牌的辅助函数
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

// 显示分析结果
function showAnalysisResult(result) {
    const analyzeBtn = document.getElementById('analyzeBtn');
    const resultContainer = document.getElementById('analysis-result');
    const resultMessage = document.getElementById('result-message');
    const downloadLink = document.getElementById('download-link');
    const resultContent = document.getElementById('result-content');

    // 隐藏进度模态框
    const progressManager = new CommonProgressManager({
        moduleName: 'java_code_analyzer'
    });
    progressManager.hide(false);

    // 显示结果区域
    resultContainer.style.display = 'block';

    if (result.message) {
        resultMessage.textContent = result.message;
    }

    if (result.report_download_url) {
        downloadLink.href = result.report_download_url;
        downloadLink.style.display = 'inline-block';
    } else {
        downloadLink.style.display = 'none';
    }

    if (result.content) {
        resultContent.textContent = result.content;
    }

    // 恢复按钮状态
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = '开始分析';

    showNotification('Java源码分析完成', 'success');
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