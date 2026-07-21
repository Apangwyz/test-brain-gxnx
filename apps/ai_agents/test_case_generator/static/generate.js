// 测试用例生成页面专用脚本

document.addEventListener('DOMContentLoaded', function() {
    console.log('[generate.js] DOMContentLoaded fired');
    
    // 初始化表单提交功能
    initFormSubmit();
    
    // 初始化其他功能
    initOtherFeatures();
    
    // 加载已采纳需求文档
    loadAdoptedDocs();
    
    // 恢复已选知识库文档标签（页面刷新后从 hidden input 还原）
    restoreSelectedKbTags();
    
    console.log('[generate.js] All init functions called');
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
                case_count: document.getElementById('case_count')?.value || '10',
                selected_kb_ids: document.getElementById('selectedKbIds')?.value || ''
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
    
    // 浏览知识库按钮事件
    const browseBtn = document.getElementById('browseKnowledgeBtn');
    console.log('[generate.js] browseKnowledgeBtn element:', browseBtn);
    if (browseBtn) {
        browseBtn.addEventListener('click', function() {
            console.log('[generate.js] browseKnowledgeBtn clicked');
            openKnowledgeBrowser();
        });
    }
}

// ===== 知识库浏览模态框 =====
let kbBrowserModal = null;

function openKnowledgeBrowser() {
    console.log('[generate.js] openKnowledgeBrowser called');
    if (kbBrowserModal) {
        kbBrowserModal.modal('show');
        return;
    }

    const modalHtml = '\x0a' +
        '<div class="modal fade" id="knowledgeBrowserModal" tabindex="-1" role="dialog">\x0a' +
        '    <div class="modal-dialog modal-lg" role="document">\x0a' +
        '        <div class="modal-content">\x0a' +
        '            <div class="modal-header">\x0a' +
        '                <h5 class="modal-title">📚 浏览知识库</h5>\x0a' +
        '                <button type="button" class="close" data-dismiss="modal" aria-label="Close">\x0a' +
        '                    <span aria-hidden="true">&times;</span>\x0a' +
        '                </button>\x0a' +
        '            </div>\x0a' +
        '            <div class="modal-body">\x0a' +
        '                <div class="form-group">\x0a' +
        '                    <input type="text" class="form-control" id="kbSearchInput" placeholder="搜索知识库文档...">\x0a' +
        '                </div>\x0a' +
        '                <div id="kbListContainer">\x0a' +
        '                    <div class="text-center py-4">\x0a' +
        '                        <div class="spinner"></div>\x0a' +
        '                        <p class="mt-2 text-muted">加载知识库...</p>\x0a' +
        '                    </div>\x0a' +
        '                </div>\x0a' +
        '                <div id="kbPagination" class="d-flex justify-content-between align-items-center mt-2">\x0a' +
        '                    <small class="text-muted" id="kbTotalInfo">共 0 篇文档</small>\x0a' +
        '                    <div>\x0a' +
        '                        <button class="btn btn-sm btn-outline-secondary" id="kbPrevPage" disabled>上一页</button>\x0a' +
        '                        <span class="mx-2" id="kbPageInfo">第 1 页</span>\x0a' +
        '                        <button class="btn btn-sm btn-outline-secondary" id="kbNextPage" disabled>下一页</button>\x0a' +
        '                    </div>\x0a' +
        '                </div>\x0a' +
        '            </div>\x0a' +
        '            <div class="modal-footer">\x0a' +
        '                <span id="kbSelectedCount" class="text-muted mr-auto">已选择 0 篇</span>\x0a' +
        '                <button type="button" class="btn btn-secondary" data-dismiss="modal">取消</button>\x0a' +
        '                <button type="button" class="btn btn-primary" id="kbConfirmBtn">确定选择</button>\x0a' +
        '            </div>\x0a' +
        '        </div>\x0a' +
        '    </div>\x0a' +
        '</div>';

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    kbBrowserModal = $('#knowledgeBrowserModal');
    let currentPage = 1;

    function loadKnowledgeList(page, search) {
        const container = document.getElementById('kbListContainer');
        container.innerHTML = '<div class="text-center py-4"><div class="spinner"></div><p class="mt-2 text-muted">加载中...</p></div>';

        let url = '/api/knowledge/list-select/?page=' + page;
        if (search) {
            url += '&search=' + encodeURIComponent(search);
        }

        fetch(url)
            .then(function(res) { return res.json(); })
            .then(function(data) {
                var items = data.items || [];
                renderKnowledgeItems(items);
                updatePagination(data.total, data.page);
                currentPage = data.page || 1;
            })
            .catch(function(err) {
                container.innerHTML = '<div class="alert alert-danger">加载知识库失败: ' + err.message + '</div>';
            });
    }

    function renderKnowledgeItems(items) {
        var container = document.getElementById('kbListContainer');
        var currentSelected = (document.getElementById('selectedKbIds') ? document.getElementById('selectedKbIds').value : '').split(',').filter(Boolean);

        if (!items || items.length === 0) {
            container.innerHTML = '<div class=\"text-center py-4 text-muted\"><i class=\"fas fa-inbox\" style=\"font-size: 32px; display: block; margin-bottom: 8px;\"></i>暂无知识库文档</div>';
            return;
        }

        var html = '<div class=\"list-group\">';
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var checked = currentSelected.indexOf(String(item.id)) !== -1 ? 'checked' : '';
            html += '\x0a' +
                '                <div class=\"list-group-item d-flex align-items-center\">\x0a' +
                '                    <input type=\"checkbox\" class=\"kb-item-checkbox mr-3\" value=\"" + item.id + "\" ' + checked + '>\x0a' +
                '                    <div class=\"flex-grow-1\">\x0a' +
                '                        <div class=\"font-weight-bold\">' + escapeHtml(item.title) + '</div>\x0a' +
                '                        <small class=\"text-muted\">' + (item.created_at ? new Date(item.created_at).toLocaleDateString() : '') + '</small>\x0a' +
                '                    </div>\x0a' +
                '                </div>';
        }
        html += '</div>';
        container.innerHTML = html;
        updateSelectedCount();
    }

    function updatePagination(total, page) {
        document.getElementById('kbTotalInfo').textContent = '共 ' + total + ' 篇文档';
        document.getElementById('kbPageInfo').textContent = '第 ' + page + ' 页';
        var totalPages = Math.ceil(total / 20) || 1;
        document.getElementById('kbPrevPage').disabled = page <= 1;
        document.getElementById('kbNextPage').disabled = page >= totalPages;
    }

    function updateSelectedCount() {
        var checked = document.querySelectorAll('.kb-item-checkbox:checked').length;
        document.getElementById('kbSelectedCount').textContent = '已选择 ' + checked + ' 篇';
    }

    window.loadKnowledgeListForBrowser = function() {
        loadKnowledgeList(1, '');
    };

    // 搜索防抖
    var searchTimer = null;
    document.getElementById('kbSearchInput').addEventListener('input', function() {
        clearTimeout(searchTimer);
        var self = this;
        searchTimer = setTimeout(function() {
            loadKnowledgeList(1, self.value.trim());
        }, 300);
    });

    // 分页
    document.getElementById('kbPrevPage').addEventListener('click', function() {
        if (currentPage > 1) {
            var search = document.getElementById('kbSearchInput').value.trim();
            loadKnowledgeList(currentPage - 1, search);
        }
    });

    document.getElementById('kbNextPage').addEventListener('click', function() {
        var search = document.getElementById('kbSearchInput').value.trim();
        loadKnowledgeList(currentPage + 1, search);
    });

    // 复选框变更
    document.getElementById('kbListContainer').addEventListener('change', function(e) {
        if (e.target.classList.contains('kb-item-checkbox')) {
            updateSelectedCount();
        }
    });

    // 确认选择
    document.getElementById('kbConfirmBtn').addEventListener('click', function() {
        try {
            var checkedBoxes = document.querySelectorAll('.kb-item-checkbox:checked');
            var ids = [];
            var names = [];
            for (var i = 0; i < checkedBoxes.length; i++) {
                ids.push(checkedBoxes[i].value);
                var parentItem = checkedBoxes[i].closest('.list-group-item');
                var titleEl = parentItem ? parentItem.querySelector('.font-weight-bold') : null;
                names.push(titleEl ? titleEl.textContent.trim() : '文档 ' + checkedBoxes[i].value);
            }
            var idsStr = ids.join(',');
            document.getElementById('selectedKbIds').value = idsStr;
            window.__selectedKbDocs = [];
            for (var i = 0; i < ids.length; i++) {
                window.__selectedKbDocs.push({ id: ids[i], title: names[i] });
            }
            updateKnowledgeRefSection(idsStr);
            kbBrowserModal.modal('hide');
        } catch(e) {
            console.error('[generate.js] Confirm handler error:', e);
        }
    });

    kbBrowserModal.on('hidden.bs.modal', function() {
        // keep DOM for reuse
    });

    loadKnowledgeList(1, '');
    kbBrowserModal.modal('show');
}

function updateKnowledgeRefSection(idsStr) {
    var ids = idsStr.split(',').filter(Boolean);
    var container = document.getElementById('auto-retrieve-results');
    if (!container) return;
    if (ids.length === 0) {
        container.innerHTML = '<small class="text-muted">提交后将自动检索知识库中的相关文档，增强生成准确性</small>';
        window.__selectedKbDocs = [];
        return;
    }
    var docs = window.__selectedKbDocs || [];
    var titleHtml = '';
    docs.forEach(function(d) {
        titleHtml += '<span style="display:inline-block;background:#e8f4fd;border:1px solid #b3d7ff;border-radius:4px;padding:3px 10px;margin:3px 4px 3px 0;font-size:13px;">'
            + '📄 ' + escapeHtml(d.title)
            + ' <span style="cursor:pointer;margin-left:4px;font-weight:bold;color:#999;" onclick="removeSelectedKb(' + d.id + ')">&times;</span>'
            + '</span>';
    });
    container.innerHTML = '<div style="margin-bottom:6px;"><small class="text-success">✅ 已选择 <strong>' + ids.length + '</strong> 篇：</small></div>'
        + '<div style="display:flex;flex-wrap:wrap;">' + titleHtml + '</div>';
}

// 显示测试用例
// 渲染已选知识库文档的标签
function renderSelectedKbTags() {
    var idsStr = document.getElementById('selectedKbIds') ? document.getElementById('selectedKbIds').value : '';
    var ids = idsStr.split(',').filter(Boolean);
    var tagArea = document.getElementById('selectedKbTags');
    var container = document.getElementById('auto-retrieve-results');
    if (!container) return;

    // 清理旧标签区域
    if (tagArea) tagArea.remove();

    if (ids.length === 0) return;

    tagArea = document.createElement('div');
    tagArea.id = 'selectedKbTags';
    tagArea.className = 'd-flex flex-wrap';
    tagArea.style.cssText = 'margin-top: 8px; gap: 6px;';
    container.parentNode.insertBefore(tagArea, container.nextSibling);

    var docs = window.__selectedKbDocs || [];
    var tagHtml = '';
    docs.forEach(function(doc) {
        tagHtml += '<span class="badge badge-info" style="font-size: 13px; padding: 6px 12px; margin: 2px; display: inline-flex; align-items: center;">'
            + '📄 ' + escapeHtml(doc.title)
            + ' <span class="kb-remove-btn" data-id="' + doc.id + '" style="cursor:pointer;margin-left:6px;font-weight:bold;" onclick="removeSelectedKb(' + doc.id + ')">&times;</span>'
            + '</span>';
    });
    tagArea.innerHTML = tagHtml;
}

// 移除单个选中的知识库文档
function removeSelectedKb(id) {
    var hiddenInput = document.getElementById('selectedKbIds');
    if (!hiddenInput) return;
    var ids = hiddenInput.value.split(',').filter(Boolean);
    var newIds = ids.filter(function(v) { return v !== String(id); });
    hiddenInput.value = newIds.join(',');
    // 同步更新 __selectedKbDocs
    if (window.__selectedKbDocs) {
        window.__selectedKbDocs = window.__selectedKbDocs.filter(function(d) { return String(d.id) !== String(id); });
    }
    updateKnowledgeRefSection(newIds.join(','));
}

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
    if (!container || !hint) return;

    fetch('/requirement_analysis/api/adopted-docs/', { credentials: 'include' })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.data && data.data.length > 0) {
            console.log("[loadAdoptedDocs] success,", data.data.length, "docs");
            hint.style.display = 'none';
            container.style.display = 'block';
            container.innerHTML = '';
            data.data.forEach(function(doc) {
                const score = doc.quality_score || 'N/A';
                const preview = (doc.content_preview || '').substring(0, 120);
                const item = document.createElement('div');
                item.className = 'adopted-doc-check-item';
                // 判断 SRS 状态
                var srsStatus, srsClass;
                if (doc.has_srs) {
                    if (doc.srs_adoption_status === 'adopted') {
                        srsStatus = 'SRS 已采纳';
                        srsClass = 'low';
                    } else if (doc.srs_adoption_status === 'rejected') {
                        srsStatus = 'SRS 已拒绝';
                        srsClass = 'high';
                    } else {
                        srsStatus = 'SRS 待审核';
                        srsClass = 'medium';
                    }
                } else {
                    srsStatus = '未生成 SRS';
                    srsClass = 'medium';
                }

                item.innerHTML = `
                    <input type="checkbox" class="adopted-doc-checkbox" value="${doc.id}" data-content="" data-doc-id="${doc.id}" data-system-id="${doc.system_id || ''}" data-has-srs="${doc.has_srs || false}">
                    <div class="doc-info">
                        <div class="doc-name">📄 ${doc.document_name}</div>
                        <div class="doc-meta">
                            ${doc.word_count || 0} 字 | ${doc.total_sections || 0} 节${doc.system_name ? ' | 系统: ' + doc.system_name : ''}
                            <br><span class="issue-tag ${srsClass}">${srsStatus}</span>
                        </div>
                    </div>
                    <div class="doc-score">${score}分</div>
                `;
                // 保存完整文档内容
                window.__adoptedDocContents[doc.id] = doc.content || "";
                container.appendChild(item);
            });
            console.log("[loadAdoptedDocs] container has", container.children.length, "children");
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
            console.log('[loadAdoptedDocs] no data, success:', data.success, 'data:', data.data);
            hint.style.display = 'block';
            container.style.display = 'none';
        }
    })
    .catch(function(err) {
        console.error('[loadAdoptedDocs] fetch/catch error:', err);
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

// ===== HTML 转义 =====
// 页面加载时从 hidden input 还原已选知识库文档标签
function restoreSelectedKbTags() {
    var hiddenInput = document.getElementById('selectedKbIds');
    if (!hiddenInput || !hiddenInput.value) return;
    var ids = hiddenInput.value.split(',').filter(Boolean);
    if (ids.length === 0) return;
    // 先显示数量
    var container = document.getElementById('auto-retrieve-results');
    if (container) {
        container.innerHTML = '<small class="text-success">✅ 已选择 <strong>' + ids.length + '</strong> 篇知识库文档（加载标题中...）</small>';
    }
    // 异步加载标题
    window.__selectedKbDocs = [];
    fetch('/api/knowledge/list-select/?page=1')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var allItems = data.items || [];
            var found = [];
            allItems.forEach(function(item) {
                if (ids.indexOf(String(item.id)) !== -1) {
                    found.push({ id: item.id, title: item.title });
                }
            });
            window.__selectedKbDocs = found;
            updateKnowledgeRefSection(ids.join(','));
        })
        .catch(function() {
            // 降级：只显示数量
            if (container) {
                container.innerHTML = '<small class="text-success">✅ 已选择 <strong>' + ids.length + '</strong> 篇知识库文档</small>';
            }
        });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
