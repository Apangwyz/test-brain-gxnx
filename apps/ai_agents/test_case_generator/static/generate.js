// 测试用例生成页面专用脚本

document.addEventListener('DOMContentLoaded', function() {
    
    // 初始化表单提交功能
    initFormSubmit();
    
    // 初始化其他功能
    initOtherFeatures();
    
    // 加载已采纳需求文档
    loadAdoptedDocs();
});


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
            const systemSelectElement = document.getElementById('system-select');
            
            if (!requirementElement || !llmProviderElement) {
                console.error('缺失必要的页面元素');
                alert('页面元素缺失，无法保存数据');
                return;
            }
            
            const requestData = {
                test_cases: testCases,
                requirement: requirementElement.value,
                llm_provider: llmProviderElement.value,
                system_id: systemSelectElement ? systemSelectElement.value : null
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

// ===== 已采纳需求文档加载 =====

function loadAdoptedDocs() {
    window.__adoptedDocContents = {};
    const container = document.getElementById('adoptedDocsList');
    const hint = document.getElementById('noAdoptedHint');
    if (!container) return;

    fetch('/requirement_analysis/api/adopted-docs/')
    .then(r => r.json())
    .then(data => {
        if (data.success && data.data && data.data.length > 0) {
            hint.style.display = 'none';
            container.style.display = 'block';
            container.innerHTML = '';
            data.data.forEach(function(doc) {
                const score = doc.quality_score || 'N/A';
                const preview = (doc.content_preview || '').substring(0, 120);
                const item = document.createElement('div');
                item.className = 'adopted-doc-check-item';
                item.innerHTML = `
                    <input type="checkbox" class="adopted-doc-checkbox" value="${doc.id}" data-content="" data-doc-id="${doc.id}">
                    <div class="doc-info">
                        <div class="doc-name">📄 ${doc.document_name}</div>
                        <div class="doc-meta">${doc.word_count || 0} 字 | ${doc.total_sections || 0} 节 | ${preview}...</div>
                    </div>
                    <div class="doc-score">${score}分</div>
                `;
                container.appendChild(item);
                // 保存完整文档内容
                window.__adoptedDocContents[doc.id] = doc.content || "";
            });
            // 显示"确定选择"按钮并绑定事件
            const fillBtn = document.getElementById('fillSelectedBtn');
            fillBtn.style.display = 'inline-block';
            fillBtn.onclick = fillSelectedDocs;
            // 监听复选框变化
            container.addEventListener('change', function() {
                const checked = container.querySelectorAll('.adopted-doc-checkbox:checked');
                document.getElementById('selectedCount').textContent = checked.length;
                fillBtn.style.display = checked.length > 0 ? 'inline-block' : 'none';
            });
        } else {
            hint.style.display = 'block';
            container.style.display = 'none';
        }
    })
    .catch(function(err) {
        console.log('加载已采纳文档失败:', err);
    });
}

function fillSelectedDocs() {
    const checked = document.querySelectorAll('.adopted-doc-checkbox:checked');
    if (checked.length === 0) {
        showToast('请先选择至少一个已采纳的需求文档', 'warning');
        return;
    }
    const textarea = document.getElementById('input-text');
    if (!textarea) return;

    let combined = '';
    checked.forEach(function(cb) {
        const parent = cb.closest('.adopted-doc-check-item');
        const docName = parent?.querySelector('.doc-name')?.textContent?.trim() || '需求文档';
        const docId = cb.getAttribute('data-doc-id');
        const content = window.__adoptedDocContents && window.__adoptedDocContents[docId] ? window.__adoptedDocContents[docId] : '';
        combined += `=== ${docName} ===\n${content}\n\n`;
    });

    // 追加到现有内容后面
    const existing = textarea.value.trim();
    textarea.value = existing ? existing + '\n\n' + combined : combined;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));

    const count = checked.length;
    showToast(`已填入 ${count} 个已采纳需求文档的内容`, 'success');

    // 取消勾选
    checked.forEach(function(cb) { cb.checked = false; });
    document.getElementById('selectedCount').textContent = '0';
    document.getElementById('fillSelectedBtn').style.display = 'none';
}

// ===== Toast 通知 =====
function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = 'toast show ' + (type || 'success');
    toast.innerHTML = message;
    document.body.appendChild(toast);
    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
}
