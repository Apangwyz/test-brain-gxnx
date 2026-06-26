let currentAnalysisId = null;
let currentFilePath = null;
let currentFileName = null;
let currentFileType = null;

document.addEventListener('DOMContentLoaded', function() {
    try {
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');

        if (!uploadZone) { console.error('[req_analysis] uploadZone not found'); return; }
        if (!fileInput) { console.error('[req_analysis] fileInput not found'); return; }

        uploadZone.addEventListener('click', function() {
            fileInput.click();
        });

        uploadZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', function() {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                handleFileSelect(this.files[0]);
            }
        });

        var exportBtn = document.getElementById('exportReportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', exportReport);
        } else {
            console.error('[req_analysis] exportReportBtn not found');
        }

        var startBtn = document.getElementById('startAnalysisBtn');
        if (startBtn) startBtn.addEventListener('click', uploadAndAnalyze);

        var generateBtn = document.getElementById('generateCasesBtn');
        if (generateBtn) generateBtn.addEventListener('click', generateFromAnalysis);
    } catch(e) {
        console.error('[req_analysis] DOMContentLoaded error:', e);
    }
});

function handleFileSelect(file) {
    const validTypes = ['.docx', '.pdf', '.md'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!validTypes.includes(ext)) {
        alert('仅支持 .docx、.pdf 和 .md 格式');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        alert('文件大小超过限制（最大10MB）');
        return;
    }

    currentFileName = file.name;
    document.getElementById('fileNameDisplay').textContent = '已选择: ' + file.name;
    document.getElementById('uploadZone').style.display = 'none';
    document.getElementById('selectedFileInfo').style.display = 'block';

    // 保存文件到 input 供上传使用
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    document.getElementById('fileInput').files = dataTransfer.files;
}

function uploadAndAnalyze() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    document.getElementById('selectedFileInfo').style.display = 'none';

    // 创建进度管理器
    const progressManager = new RequirementAnalysisProgressManager();

    // 设置完成回调
    progressManager.onComplete(function(result) {
        pollLatestAnalysis().then(function(resultData) {
            if (resultData && resultData.success) {
                renderReport(resultData.data);
                progressManager.hide(false);
            }
        });
    });

    // 设置错误回调
    progressManager.onError(function(message) {
        alert('分析失败: ' + message);
    });

    fetch('/requirement_analysis/upload/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() },
        body: formData
    })
    .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
    .then(data => {
        if (!data.success) { throw new Error(data.error); }
        currentFilePath = data.file_path;
        currentFileType = data.file_type;

        return fetch('/requirement_analysis/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                file_path: currentFilePath,
                file_name: currentFileName,
                file_type: currentFileType
            })
        });
    })
    .then(r => {
        if (!r.ok) { return r.text().then(t => { throw new Error('分析请求失败: ' + (t || r.statusText)); }); }
        return r.json();
    })
    .then(data => {
        if (!data.success) { throw new Error(data.error); }
        
        // 显示进度模态框
        progressManager.show();
        
        // 初始化步骤显示
        const initialSteps = [
            { stage: 'extracting', title: '提取内容', description: '从文件中提取文本...', status: 'pending' },
            { stage: 'scoring', title: '质量评分', description: '评估文档质量...', status: 'pending' },
            { stage: 'deep_analysis', title: '深度分析', description: '完整度/风险/冲突/可测试性分析...', status: 'pending' },
            { stage: 'summarize', title: '汇总报告', description: '生成分析报告与测试策略...', status: 'pending' },
            { stage: 'completed', title: '完成', description: '分析完成！', status: 'pending' }
        ];
        progressManager.initializeSteps(initialSteps);
        
        // 开始监听进度
        progressManager.startProgressStream(data.task_id);
    })
    .catch(err => { alert('请求失败: ' + err.message); });
}

function pollLatestAnalysis(retries = 10) {
    return new Promise((resolve) => {
        function tryFetch(n) {
            if (n <= 0) { resolve(null); return; }
            setTimeout(() => {
                fetch('/requirement_analysis/api/result/latest/')
                .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
                .then(data => {
                    if (data.success && data.data) resolve(data);
                    else tryFetch(n - 1);
                })
                .catch(() => tryFetch(n - 1));
            }, 2000);
        }
        tryFetch(retries);
    });
}

function renderReport(data) {
    currentAnalysisId = data.id;
    // 持久化 analysisId，防止刷新后丢失
    try { sessionStorage.setItem('req_analysis_current_id', currentAnalysisId); } catch(e) {}
    document.getElementById('reportContainer').style.display = 'block';

    // 评分
    const score = data.quality_score?.overall_score || 0;
    const ring = document.getElementById('scoreRing');
    ring.textContent = score;
    ring.className = 'score-ring ' + (score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low');

    // 各维度评分
    const dims = data.quality_score?.dimensions || {};
    const dimLabels = {
        completeness: '完整性', clarity: '清晰度', consistency: '一致性',
        testability: '可测试性', structure: '结构化'
    };
    const dimContainer = document.getElementById('dimensionScores');
    dimContainer.innerHTML = '';
    Object.entries(dims).forEach(([key, val]) => {
        dimContainer.innerHTML += `
            <div class="col-6 col-md-4 mb-3">
                <div style="font-size: 13px; color: var(--text-secondary);">${dimLabels[key] || key}</div>
                <div style="font-size: 24px; font-weight: 700; color: ${val >= 80 ? '#2e7d32' : val >= 60 ? '#e65100' : '#c62828'};">${val}</div>
            </div>
        `;
    });

    // 完整度
    const comp = data.completeness || {};
    document.getElementById('completenessContent').innerHTML = renderCompleteness(comp);

    // 冲突检测
    const cons = data.consistency || {};
    document.getElementById('conflictContent').innerHTML = renderConflicts(cons);

    // 风险识别
    const risk = data.risk_identification || {};
    document.getElementById('riskContent').innerHTML = renderRisks(risk);

    // 分类统计
    const cat = data.category_stats || {};
    document.getElementById('categoryContent').innerHTML = renderCategories(cat);

    // 可测试性
    const test = data.testability || {};
    document.getElementById('testabilityContent').innerHTML = renderTestability(test);

    // 显示采纳栏和导出按钮
    document.getElementById('adoptionBar').style.display = 'block';
    document.getElementById('exportReportBtn').style.display = 'inline-block';
    // 重置采纳状态显示
    document.getElementById('adoptionActions').style.display = 'block';
    document.getElementById('adoptionResult').style.display = 'none';
    document.getElementById('adoptionStatusBadge').textContent = '待审核';
    document.getElementById('adoptionStatusBadge').className = 'status-badge pending';

    // 滚动到报告区域
    document.getElementById('reportContainer').scrollIntoView({ behavior: 'smooth' });
}

// 优先级权重映射（用于排序）
const PRIORITY_WEIGHT = { high: 3, medium: 2, low: 1 };

// 优先级中文映射
const PRIORITY_CN = { high: '高', medium: '中', low: '低' };

// 英文标签 → 中文标签映射
const TYPE_CN = {
    vague_description: '描述模糊',
    incomplete_requirement: '需求不完整',
    missing_business_rule: '缺少业务规则',
    missing_error_handling: '缺少异常处理',
    missing_boundary: '缺少边界条件',
    contradiction: '相互矛盾',
    duplicate: '重复定义',
    duplication: '重复描述',
    terminology: '术语不一致',
    overscoped: '范围过大',
    dependency_risk: '依赖风险',
    security_risk: '安全风险',
    performance_risk: '性能风险',
    technical_risk: '技术风险',
    technical_debt: '技术债务',
    ambiguity: '表述歧义',
    data_risk: '数据风险',
    integration_risk: '集成风险',
    design_issue: '设计问题',
    requirement_gap: '需求遗漏',
};

function sortByPriority(items, key) {
    const w = PRIORITY_WEIGHT;
    return [...items].sort((a, b) => (w[a[key]] || 0) > (w[b[key]] || 0) ? -1 : 1);
}

function cnPriority(val) {
    return PRIORITY_CN[val] || val || '';
}

function cnType(val) {
    return TYPE_CN[val] || val || '其他';
}

function cnSeverity(val) {
    return PRIORITY_CN[val] || val || '';
}

function renderCompleteness(data) {
    const present = data.present_items || [];
    const missing = data.missing_items || [];
    const suggestions = sortByPriority(data.suggestions || [], 'severity');
    let html = '<div class="row">';
    html += '<div class="col-md-6"><strong>✅ 已覆盖</strong><ul>';
    present.forEach(item => { html += '<li>' + item + '</li>'; });
    html += '</ul></div><div class="col-md-6"><strong>❌ 缺失</strong><ul>';
    missing.forEach(item => { html += '<li>' + item + '</li>'; });
    html += '</ul></div></div>';
    if (suggestions.length) {
        html += '<div style="margin-top: 12px;"><strong>💡 改进建议</strong>';
        // 按优先级分组
        const groups = { high: [], medium: [], low: [] };
        suggestions.forEach(s => { const g = groups[s.severity]; if (g) g.push(s); });
        ['high','medium','low'].forEach(sev => {
            if (!groups[sev].length) return;
            html += '<div style="margin-top:8px;"><span class="issue-tag ' + sev + '">' + cnPriority(sev) + ' 优先级</span><ul>';
            groups[sev].forEach(s => { html += '<li>' + s.suggestion + '</li>'; });
            html += '</ul></div>';
        });
        html += '</div>';
    }
    return html;
}

function renderConflicts(data) {
    const conflicts = sortByPriority(data.conflicts || [], 'severity');
    if (!conflicts.length) return '<p style="color: var(--success);">✅ 未检测到明显的冲突或矛盾</p>';
    let html = '';
    conflicts.forEach(c => {
        html += '<div style="margin-bottom: 12px; padding: 8px; background: var(--bg-tertiary); border-radius: 4px;">';
        html += '<span class="issue-tag ' + c.severity + '">' + cnPriority(c.severity) + '</span> ';
        html += '<strong>' + cnType(c.type) + '</strong>: ' + (c.description || '');
        html += '<div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">';
        html += '📍 ' + ((c.location_a && c.location_a.section) || '?') + ' ↔ ' + ((c.location_b && c.location_b.section) || '?');
        html += '</div></div>';
    });
    return html;
}

function renderRisks(data) {
    const items = data.risk_items || [];
    if (!items.length) return '<p style="color: var(--success);">✅ 未识别到高风险项</p>';
    
    // 按 type 归类
    const groups = {};
    items.forEach(item => {
        const t = item.type || 'other';
        if (!groups[t]) groups[t] = [];
        groups[t].push(item);
    });
    
    // 每组内按优先级排序，组间按最高优先级排序
    const groupEntries = Object.entries(groups).map(([type, list]) => {
        const sorted = sortByPriority(list, 'severity');
        const maxPriority = Math.max(...sorted.map(it => PRIORITY_WEIGHT[it.severity] || 0));
        return { type, items: sorted, maxPriority };
    });
    groupEntries.sort((a, b) => a.maxPriority > b.maxPriority ? -1 : 1);
    
    let html = '';
    groupEntries.forEach(group => {
        html += '<div style="margin-bottom: 16px;">';
        html += '<h6 style="font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">📌 ' + cnType(group.type) + '</h6>';
        group.items.forEach(item => {
            html += '<div style="margin-bottom: 8px; padding: 8px; background: var(--bg-tertiary); border-radius: 4px; border-left: 3px solid ' + (item.severity === 'high' ? '#dc3545' : item.severity === 'medium' ? '#ffc107' : '#28a745') + ';">';
            html += '<span class="issue-tag ' + (item.severity || 'low') + '">' + cnPriority(item.severity) + '</span> ';
            html += '<div style="font-size: 13px; margin-top: 4px;">' + (item.risk || '') + '</div>';
            if (item.suggestion) {
                html += '<div style="font-size: 13px; color: var(--info); margin-top: 2px;">💡 ' + item.suggestion + '</div>';
            }
            if (item.location && item.location.section) {
                html += '<div style="font-size: 12px; color: var(--text-tertiary);">📍 ' + item.location.section + '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    });
    return html;
}

function renderCategories(data) {
    const cats = data.categories || {};
    const pri = data.priority_distribution || {};
    let html = '<div class="row">';
    html += '<div class="col-md-6"><strong>📂 需求分类</strong><ul>';
    const labels = { functional: '功能需求', non_functional: '非功能性', business_rule: '业务规则', ui_ux: 'UI/UX' };
    Object.entries(cats).forEach(([key, val]) => {
        const label = labels[key] || key;
        const count = typeof val === 'object' ? (val.count + ' (' + (val.ratio || '') + ')') : val;
        html += '<li>' + label + ': ' + count + '</li>';
    });
    html += '</ul></div><div class="col-md-6"><strong>📊 优先级分布</strong><ul>';
    if (pri.high) html += '<li>🔴 高: ' + pri.high + '</li>';
    if (pri.medium) html += '<li>🟡 中: ' + pri.medium + '</li>';
    if (pri.low) html += '<li>🟢 低: ' + pri.low + '</li>';
    html += '</ul></div></div>';
    return html;
}

function renderTestability(data) {
    const items = data.items || [];
    const untestable = data.untestable_count || 0;
    const recommendation = data.recommendation || '';
    const overall = data.testability_overall || 'unknown';
    const overallLabels = { high: '🟢 高', medium: '🟡 中', low: '🔴 低' };
    let html = '<p><strong>整体可测试性: ' + (overallLabels[overall] || overall) + '</strong>';
    if (untestable > 0) html += ' | 不可测试需求: ' + untestable + ' 条';
    html += '</p>';
    if (items.length) {
        html += '<ul>';
        items.forEach(item => {
            const levelLabel = { high: '🟢', medium: '🟡', low: '🔴' }[item.level] || '⚪';
            html += '<li>' + levelLabel + ' ' + (item.section || '') + ': ' + (item.reason || '') + '</li>';
        });
        html += '</ul>';
    }
    if (recommendation) {
        html += '<div style="background: var(--bg-tertiary); padding: 8px; border-radius: 4px; font-size: 13px;">💡 ' + recommendation + '</div>';
    }
    return html;
}

function generateFromAnalysis() {
    if (!currentAnalysisId) return;

    fetch('/requirement_analysis/api/generate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ analysis_id: currentAnalysisId })
    })
    .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
    .then(data => {
        if (data.success) {
            alert(data.message || '正在生成测试用例，请前往"测试用例生成"页面查看进度');
            window.location.href = '/test_case_generator/';
        } else {
            alert('生成失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(err => alert('请求失败: ' + err.message));
}

function exportReport() {
    // ===== 调试信息 =====
    var debugEl = document.getElementById('exportDebug');
    if (!debugEl) {
        debugEl = document.createElement('div');
        debugEl.id = 'exportDebug';
        debugEl.style.cssText = 'margin-top:12px;padding:10px;background:#f0f0f0;border-radius:4px;font-size:13px;color:#333;white-space:pre-wrap;word-break:break-all;';
        var container = document.getElementById('reportContainer');
        if (container) container.appendChild(debugEl);
    }
    function debug(msg) { debugEl.textContent = '[DEBUG] ' + new Date().toLocaleTimeString() + ' ' + msg; }
    // ===================

    debug('exportReport 被调用');
    var btn = document.getElementById('exportReportBtn');
    if (!btn) { debug('错误: 找不到 exportReportBtn 元素'); return; }
    debug('按钮存在, currentAnalysisId=' + currentAnalysisId);

    btn.textContent = '⏳ 正在导出...';
    btn.disabled = true;

    var id = currentAnalysisId;
    if (!id) {
        debug('currentAnalysisId 为空，尝试 sessionStorage...');
        try { id = sessionStorage.getItem('req_analysis_current_id'); debug('sessionStorage 获取到: ' + id); } catch(e) { debug('sessionStorage 失败: ' + e.message); }
    }
    if (!id) {
        var msg = '没有可导出的分析报告，请先完成需求分析';
        debug(msg);
        alert(msg);
        btn.textContent = '导出分析报告';
        btn.disabled = false;
        return;
    }

    var url = '/requirement_analysis/api/' + id + '/export/';
    debug('准备下载, URL=' + url);

    // 方法1: 直接用 location.href
    debug('执行 window.location.href = ' + url);
    window.location.href = url;
}


// ===== 采纳/拒绝功能 =====

document.getElementById('adoptBtn')?.addEventListener('click', function() {
    if (!currentAnalysisId) return;
    fetch('/requirement_analysis/api/' + currentAnalysisId + '/adopt/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
    .then(data => {
        if (data.success) {
            document.getElementById('adoptionActions').style.display = 'none';
            document.getElementById('adoptionResult').style.display = 'block';
            document.getElementById('adoptionResultText').innerHTML = '✅ ' + data.message;
            document.getElementById('adoptionStatusBadge').textContent = '已采纳';
            document.getElementById('adoptionStatusBadge').className = 'status-badge adopted';
            loadAdoptedDocs();
        } else {
            alert('采纳失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(err => alert('请求失败: ' + err.message));
});

document.getElementById('rejectBtn')?.addEventListener('click', function() {
    if (!currentAnalysisId) return;
    fetch('/requirement_analysis/api/' + currentAnalysisId + '/reject/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
    .then(data => {
        if (data.success) {
            document.getElementById('adoptionActions').style.display = 'none';
            document.getElementById('adoptionResult').style.display = 'block';
            document.getElementById('adoptionResultText').innerHTML = '❌ ' + data.message;
            document.getElementById('adoptionStatusBadge').textContent = '已拒绝';
            document.getElementById('adoptionStatusBadge').className = 'status-badge rejected';
        } else {
            alert('拒绝失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(err => alert('请求失败: ' + err.message));
});

function loadAdoptedDocs() {
    const panel = document.getElementById('adoptedDocsPanel');
    const list = document.getElementById('adoptedDocsList');
    if (!panel || !list) return;

    fetch('/requirement_analysis/api/adopted-docs/')
    .then(r => { if (!r.ok) { return r.text().then(t => { throw new Error("请求失败: " + (t || r.statusText)); }); } return r.json(); })
    .then(data => {
        if (data.success && data.data && data.data.length > 0) {
            panel.style.display = 'block';
            list.innerHTML = '';
            data.data.forEach(function(doc) {
                const score = doc.quality_score || 'N/A';
                const preview = (doc.content_preview || '').substring(0, 100);
                list.innerHTML += `
                    <div class="adopted-doc-item">
                        <div class="doc-info">
                            <div class="doc-name">📄 ${doc.document_name}</div>
                            <div class="doc-meta">
                                评分: ${score} | ${doc.word_count || 0} 字 | ${doc.total_sections || 0} 节
                                ${preview ? '<br>' + preview + '...' : ''}
                            </div>
                        </div>
                        <div class="doc-score">${score}分</div>
                    </div>
                `;
            });
        }
    })
    .catch(function(err) {
        console.log('加载已采纳文档失败:', err);
    });
}

// 页面加载时加载已采纳文档列表
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(loadAdoptedDocs, 500);
});

// 改用cookie方式获取CSRF Token，与系统中其他模块保持一致
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

function getCSRFToken() {
    return getCookie('csrftoken');
}
