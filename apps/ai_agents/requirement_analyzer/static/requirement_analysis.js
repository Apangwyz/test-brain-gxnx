let currentAnalysisId = null;
let currentFilePath = null;
let currentFileName = null;
let currentFileType = null;

function loadSystems() {
    fetch('/api/systems/?status=active')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var select = document.getElementById('system-select');
        if (!select) return;
        if (data.success && data.systems) {
            select.innerHTML = '<option value="">-- 请选择系统 --</option>';
            data.systems.forEach(function(s) {
                var opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name + ' (' + s.code + ')';
                select.appendChild(opt);
            });
        }
    })
    .catch(function(err) { console.error('[req_analysis] 加载系统列表失败:', err); });
}

document.addEventListener('DOMContentLoaded', function() {
    try {
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');

        if (!uploadZone) { console.error('[req_analysis] uploadZone not found'); return; }
        if (!fileInput) { console.error('[req_analysis] fileInput not found'); return; }

        // 加载系统列表
        loadSystems();

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
    
    // 验证系统选择
    const systemId = document.getElementById('system-select')?.value;
    if (!systemId) {
        alert('请先选择所属系统');
        document.getElementById('system-select')?.focus();
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    document.getElementById('selectedFileInfo').style.display = 'none';

    // 创建进度管理器
    const progressManager = new RequirementAnalysisProgressManager();

    // 设置完成回调
    progressManager.onComplete(function(result) {
        // 优先使用进度结果中的 analysisId 精准获取，避免 pollLatestAnalysis 取错记录
        var analysisId = result ? result.id : null;
        if (analysisId) {
            fetch('/requirement_analysis/api/result/' + analysisId + '/')
            .then(function(r) { return r.json(); })
            .then(function(resultData) {
                if (resultData.success) {
                    renderReport(resultData.data);
                }
                progressManager.hide(false);
                loadAdoptedDocs();
                if (result && result.already_adopted) {
                    setTimeout(function() {
                        alert('提示：该文档已被采纳，无需重复操作');
                    }, 500);
                }
            })
            .catch(function() {
                progressManager.hide(false);
                loadAdoptedDocs();
            });
        } else {
            pollLatestAnalysis().then(function(resultData) {
                if (resultData && resultData.success) {
                    renderReport(resultData.data);
                }
                progressManager.hide(false);
                loadAdoptedDocs();
            });
        }
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
                file_type: currentFileType,
                system_id: parseInt(document.getElementById('system-select')?.value) || null
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
    document.getElementById('exportReportActionBar').style.display = 'block';
    // 根据当前采纳状态显示正确UI
    var adoptStatus = data.adoption_status || 'pending';
    if (adoptStatus === 'adopted') {
        document.getElementById('adoptionActions').style.display = 'none';
        document.getElementById('adoptionResult').style.display = 'block';
        document.getElementById('adoptionResultText').innerHTML = '✅ 该需求文档已于' + (data.adopted_at ? new Date(data.adopted_at).toLocaleString() : '之前') + '被采纳';
        document.getElementById('adoptionStatusBadge').textContent = '已采纳';
        document.getElementById('adoptionStatusBadge').className = 'status-badge adopted';
    } else if (adoptStatus === 'rejected') {
        document.getElementById('adoptionActions').style.display = 'none';
        document.getElementById('adoptionResult').style.display = 'block';
        document.getElementById('adoptionResultText').innerHTML = '❌ 该需求文档已被拒绝';
        document.getElementById('adoptionStatusBadge').textContent = '已拒绝';
        document.getElementById('adoptionStatusBadge').className = 'status-badge rejected';
    } else {
        document.getElementById('adoptionActions').style.display = 'block';
        document.getElementById('adoptionResult').style.display = 'none';
        document.getElementById('adoptionStatusBadge').textContent = '待审核';
        document.getElementById('adoptionStatusBadge').className = 'status-badge pending';
    }

    // 滚动到报告区域
    document.getElementById('reportContainer').scrollIntoView({ behavior: 'smooth' });

    // 显示 SRS 生成卡片
    showSrsCard();

    // 加载分析报告预览（安全调用，防止未定义错误）
    try {
        if (typeof loadReportPreview === 'function') {
            loadReportPreview(data);
        } else {
            console.warn('[renderReport] loadReportPreview is not defined, skipping report preview');
        }
    } catch(e) {
        console.warn('[renderReport] loadReportPreview failed:', e);
    }
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
            // 刷新已采纳列表（报错可能是文档已采纳但列表未更新）
            loadAdoptedDocs();
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


function loadAdoptedSrs() {
    const panel = document.getElementById('adoptedSrsPanel');
    const list = document.getElementById('adoptedSrsList');
    if (!panel || !list) return;

    fetch('/requirement_analysis/api/adopted-srs/')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success && data.data && data.data.length > 0) {
            console.log('[loadAdoptedDocs] showing panel, rendering', data.data.length, 'docs');
            panel.style.display = 'block';
            list.innerHTML = '';
            data.data.forEach(function(doc) {
                const score = doc.quality_score || 'N/A';
                list.innerHTML += `
                    <div class="adopted-doc-item" style="cursor: pointer;">
                        <div class="doc-info">
                            <div class="doc-name">📄 ${doc.document_name}</div>
                            <div class="doc-meta">
                                <span class="issue-tag low" style="margin-right: 6px;">SRS 已采纳</span>
                                需求评分: ${score} | ${doc.word_count || 0} 字
                                ${doc.system_name ? '<br>所属系统: ' + doc.system_name : ''}
                                ${doc.srs_adopted_at ? '<br>SRS 采纳时间: ' + new Date(doc.srs_adopted_at).toLocaleString() : ''}
                            </div>
                        </div>
                        <div class="doc-score">
                            <i class="fas fa-check-circle" style="color: #2e7d32;"></i>
                        </div>
                    </div>
                `;
            });
        }
    })
    .catch(function(err) {
        console.log('加载已采纳 SRS 失败:', err);
    });
}


function loadAdoptedDocs() {
    console.log("[loadAdoptedDocs] called at " + new Date().toISOString());
    const adoptedPanel = document.getElementById('adoptedDocsPanel');
    const adoptedList = document.getElementById('adoptedDocsList');
    const rejectedPanel = document.getElementById('rejectedDocsPanel');
    const rejectedList = document.getElementById('rejectedDocsList');

    if (!adoptedPanel || !adoptedList) return;

    fetch('/requirement_analysis/api/my-docs/', { credentials: 'include' })
    .then(r => { if (!r.ok) { throw new Error("请求失败"); } return r.json(); })
    .then(data => {
        if (!data.success || !data.data) {
            return fallbackLoadAdoptedDocs(adoptedPanel, adoptedList);
        }

        var adoptedDocs = data.data.filter(function(d) { return d.adoption_status === 'adopted'; });
        var rejectedDocs = data.data.filter(function(d) { return d.adoption_status === 'rejected'; });

        if (adoptedDocs.length > 0) {
            adoptedPanel.style.display = 'block';
            adoptedList.innerHTML = '';
            adoptedDocs.forEach(function(doc) {
                renderDocItem(adoptedList, doc, 'adopted');
            });
        } else {
            adoptedPanel.style.display = 'none';
        }

        if (rejectedDocs.length > 0) {
            if (rejectedPanel && rejectedList) {
                rejectedPanel.style.display = 'block';
                rejectedList.innerHTML = '';
                rejectedDocs.forEach(function(doc) {
                    renderDocItem(rejectedList, doc, 'rejected');
                });
            }
        } else {
            if (rejectedPanel) rejectedPanel.style.display = 'none';
        }
        
        // 同时加载已采纳的 SRS
        loadAdoptedSrs();
    })
    .catch(function(err) {
        console.error('[loadAdoptedDocs] failed, fallback:', err);
        fallbackLoadAdoptedDocs(adoptedPanel, adoptedList);
    });
}

function renderDocItem(container, doc, status) {
    const score = doc.quality_score || 'N/A';
    const preview = (doc.content_preview || '').substring(0, 100);
    var actionButtons = '';
    if (status === 'adopted') {
        actionButtons = '<button class="btn btn-sm btn-outline-danger" style="margin-left: 8px; padding: 2px 8px; font-size: 12px;" onclick="deleteAdoptedDoc(' + doc.id + ')" title="删除此文档"><i class="fas fa-trash"></i></button>';
    } else if (status === 'rejected') {
        actionButtons = '<button class="btn btn-sm btn-outline-success" style="margin-left: 8px; padding: 2px 8px; font-size: 12px;" onclick="resubmitDocument(' + doc.id + ')" title="重新提交"><i class="fas fa-undo"></i> 重新提交</button>';
    }
    container.innerHTML += `
        <div class="adopted-doc-item">
            <div class="doc-info">
                <div class="doc-name">\u{1F4C4} ${doc.document_name}</div>
                <div class="doc-meta">
                    评分: ${score} | ${doc.word_count || 0} 字 | ${doc.total_sections || 0} 节
                    ${preview ? '<br>' + preview + '...' : ''}
                    <br>
                    <span class="issue-tag ${doc.has_srs ? (doc.srs_adoption_status === 'adopted' ? 'low' : doc.srs_adoption_status === 'rejected' ? 'high' : 'medium') : 'medium'}">
                        ${doc.has_srs ? (doc.srs_adoption_status === 'adopted' ? 'SRS \u5DF2\u91C7\u7EB3' : doc.srs_adoption_status === 'rejected' ? 'SRS \u5DF2\u62D2\u7EDD' : 'SRS \u5F85\u5BA1\u6838') : '\u672A\u751F\u6210 SRS'}
                    </span>
                </div>
            </div>
            <div class="doc-score">
                ${score}\u5206
                ${actionButtons}
            </div>
        </div>
    `;
}

function fallbackLoadAdoptedDocs(panel, list) {
    if (!panel || !list) return;
    fetch('/requirement_analysis/api/adopted-docs/', { credentials: 'include' })
    .then(r => { if (!r.ok) throw new Error('请求失败'); return r.json(); })
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
                            <div class="doc-name">\u{1F4C4} ${doc.document_name}</div>
                            <div class="doc-meta">
                                评分: ${score} | ${doc.word_count || 0} 字 | ${doc.total_sections || 0} 节
                                ${preview ? '<br>' + preview + '...' : ''}
                                <br>
                                <span class="issue-tag ${doc.has_srs ? (doc.srs_adoption_status === 'adopted' ? 'low' : doc.srs_adoption_status === 'rejected' ? 'high' : 'medium') : 'medium'}">
                                    ${doc.has_srs ? (doc.srs_adoption_status === 'adopted' ? 'SRS 已采纳' : doc.srs_adoption_status === 'rejected' ? 'SRS 已拒绝' : 'SRS 待审核') : '未生成 SRS'}
                                </span>
                            </div>
                        </div>
                        <div class="doc-score">
                            ${score}分
                            <button class="btn btn-sm btn-outline-danger" style="margin-left: 8px; padding: 2px 8px; font-size: 12px;" onclick="deleteAdoptedDoc(${doc.id})" title="删除此文档">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }
    })
    .catch(function(err) {
        console.error('[fallbackLoadAdoptedDocs] failed:', err);
        if (panel) panel.style.display = 'block';
        if (list) list.innerHTML = '<p style="color: var(--text-secondary);">⚠️ 加载失败，请刷新页面重试</p>';
    });
}

// 页面加载时加载已采纳文档列表
console.log('[DOMContentLoaded] registering adopted docs loader');
document.addEventListener('DOMContentLoaded', function() {
    console.log('[DOMContentLoaded] event fired, scheduling loadAdoptedDocs');
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


// ============================================================
// ============================================================

// ============================================================
// SRS（软件需求规格说明书）生成、预览、编辑与采纳功能
// ============================================================

// SRS 章节中文标题映射（含子章节）
const SRS_SECTION_TITLES = {
    "introduction": "一、引言",
    "overall_description": "二、总体描述",
    "functional_requirements": "三、功能需求",
    "external_interfaces": "四、外部接口需求",
    "non_functional_requirements": "五、非功能需求",
    "data_requirements": "六、数据需求",
    "appendix": "七、附录"
};

// 子章节中文标题映射
const SRS_SUB_SECTION_TITLES = {
    "purpose": "1.1 目的",
    "scope": "1.2 范围",
    "definitions": "1.3 定义与缩略语",
    "references": "1.4 参考文献",
    "product_overview": "2.1 产品概述",
    "product_functions": "2.2 功能概要",
    "user_characteristics": "2.3 用户特征",
    "constraints": "2.4 约束",
    "assumptions": "2.5 假设和依赖关系",
    "user_interfaces": "4.1 用户接口",
    "hardware_interfaces": "4.2 硬件接口",
    "software_interfaces": "4.3 软件接口",
    "communication_interfaces": "4.4 通信接口",
    "performance": "5.1 性能需求",
    "security": "5.2 安全需求",
    "usability": "5.3 可用性需求",
    "reliability": "5.4 可靠性需求",
    "maintainability": "5.5 可维护性需求",
    "entities": "6.1 数据实体描述",
    "dictionary": "6.2 数据字典",
    "management": "6.3 数据管理要求",
    "notes": "7.1 补充说明",
    "pending_items": "7.2 待确认事项"
};

// 当前视图模式: 'edit' 或 'preview'
let srsViewMode = 'edit';

function showSrsCard() {
    var card = document.getElementById('srsCard');
    if (card) card.style.display = 'block';
}

// ---------- Markdown 简单渲染 ----------
function renderMarkdown(text) {
    if (!text) return '';
    var html = text
        // 转义 HTML
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        // 代码块 ```...```
        .replace(/```(\w*)\n([\s\S]*?)```/g, function(m, lang, code) {
            return '<pre><code>' + code.trim() + '</code></pre>';
        })
        // 行内代码 `...`
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // 图片 ![](url)
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">')
        // 链接 [text](url)
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
        // 加粗 **text**
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        // 斜体 *text*
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        // 分割线 ---
        .replace(/^---$/gm, '<hr>')
        // 引用 > text
        .replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>')
        // 无序列表 - item
        .replace(/^[\s]*[-*+]\s+(.*)$/gm, '<li>$1</li>')
        // 有序列表 1. item
        .replace(/^[\s]*\d+\.\s+(.*)$/gm, '<li>$1</li>')
        // 标题 ### text
        .replace(/^######\s+(.*)$/gm, '<h6>$1</h6>')
        .replace(/^#####\s+(.*)$/gm, '<h5>$1</h5>')
        .replace(/^####\s+(.*)$/gm, '<h4>$1</h4>')
        .replace(/^###\s+(.*)$/gm, '<h3>$1</h3>')
        .replace(/^##\s+(.*)$/gm, '<h2>$1</h2>')
        .replace(/^#\s+(.*)$/gm, '<h1>$1</h1>')
        // 段落（连续文本用 <p> 包裹）
        .replace(/\n\n/g, '</p><p>')
        .replace(/^\n/, '')
        .replace(/\n$/, '');

    // 包裹列表
    html = html.replace(/(<li>[\s\S]*?)(?=<li>|<\/p>|<h|<blockquote|<pre|<hr|$)/g, function(m) {
        if (m.indexOf('<li>') >= 0) return '<ul>' + m + '</ul>';
        return m;
    });

    return '<p>' + html + '</p>';
}

// ---------- SRS 生成 ----------
function generateSRS(forceRegenerate) {
    if (!currentAnalysisId) {
        alert('请先完成需求分析');
        return;
    }

    var btn = document.getElementById('generateSrsBtn');
    var overlay = document.getElementById('srsGeneratingOverlay');
    var emptyState = document.getElementById('srsEmptyState');
    var contentArea = document.getElementById('srsContentArea');
    var previewArea = document.getElementById('srsPreviewArea');
    var refreshBtn = document.getElementById('refreshSrsBtn');
    var exportBtn = document.getElementById('exportSrsBtn');
    var toggleBtn = document.getElementById('toggleViewBtn');
    var adoptBar = document.getElementById('srsAdoptionBar');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    overlay.style.display = 'block';
    emptyState.style.display = 'none';
    contentArea.style.display = 'none';
    previewArea.style.display = 'none';
    refreshBtn.style.display = 'none';
    exportBtn.style.display = 'none';
    toggleBtn.style.display = 'none';
    if (adoptBar) adoptBar.style.display = 'none';

    fetch('/requirement_analysis/api/' + currentAnalysisId + '/generate-srs/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(forceRegenerate ? {force: true} : {})
    })
    .then(function(r) {
        if (!r.ok) { return r.text().then(function(t) { throw new Error('请求失败: ' + (t || r.statusText)); }); }
        return r.json();
    })
    .then(function(data) {
        if (!data.success) { throw new Error(data.error || '生成失败'); }

        if (data.srs_generated) {
            loadSRS();
        } else {
            pollSrsGeneration(data.task_id);
        }
    })
    .catch(function(err) {
        alert('SRS 生成失败: ' + err.message);
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> 生成 SRS';
        overlay.style.display = 'none';
        emptyState.style.display = 'block';
    });
}

function pollSrsGeneration(taskId) {
    var overlay = document.getElementById('srsGeneratingOverlay');
    var btn = document.getElementById('generateSrsBtn');

    var pollCount = 0;
    var maxPolls = 180;

    function check() {
        pollCount++;
        fetch('/api/progress/?task_id=' + encodeURIComponent(taskId))
        .then(function(r) {
            if (!r.ok) { throw new Error('进度查询失败: HTTP ' + r.status); }
            return r.json();
        })
        .then(function(data) {
            if (!data.success || !data.progress) {
                throw new Error(data.message || '进度数据异常');
            }
            var progress = data.progress;
            var status = progress.status || '';

            if (status === 'completed' || status === 'success') {
                loadSRS();
            } else if (status === 'error') {
                throw new Error(progress.message || '生成过程出错');
            } else if (pollCount < maxPolls) {
                setTimeout(check, 1500);
            } else {
                throw new Error('生成超时，请稍后重试或检查 LLM 服务状态');
            }
        })
        .catch(function(err) {
            console.error('SRS 进度轮询失败:', err);
            overlay.style.display = 'none';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-magic"></i> 生成 SRS';
            document.getElementById('srsEmptyState').style.display = 'block';
            alert('SRS 生成失败: ' + err.message + '\\n请重试或检查服务端日志');
        });
    }
    setTimeout(check, 2000);
}

// ---------- 加载并渲染 SRS ----------
function loadSRS() {
    var overlay = document.getElementById('srsGeneratingOverlay');
    var emptyState = document.getElementById('srsEmptyState');
    var contentArea = document.getElementById('srsContentArea');
    var previewArea = document.getElementById('srsPreviewArea');
    var btn = document.getElementById('generateSrsBtn');
    var refreshBtn = document.getElementById('refreshSrsBtn');
    var exportBtn = document.getElementById('exportSrsBtn');
    var toggleBtn = document.getElementById('toggleViewBtn');
    var adoptBar = document.getElementById('srsAdoptionBar');

    fetch('/requirement_analysis/api/' + currentAnalysisId + '/srs/')
    .then(function(r) {
        if (!r.ok) { return r.text().then(function(t) { throw new Error('请求失败: ' + (t || r.statusText)); }); }
        return r.json();
    })
    .then(function(data) {
        if (!data.success || !data.data || !data.data.srs_content) {
            throw new Error('SRS 内容为空');
        }

        var srs = data.data.srs_content;
        overlay.style.display = 'none';
        emptyState.style.display = 'none';
        contentArea.style.display = 'block';
        previewArea.style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> 生成 SRS';
        refreshBtn.style.display = 'inline-block';
        exportBtn.style.display = 'inline-block';
        toggleBtn.style.display = 'inline-block';
        document.getElementById('toggleViewLabel').textContent = '预览';
        srsViewMode = 'edit';

        // 渲染编辑模式
        contentArea.innerHTML = renderSrsEditMode(srs);
        // 渲染预览模式
        previewArea.innerHTML = renderSrsPreviewMode(srs);

        // 加载采纳状态
        loadSrsAdoptionStatus();
    })
    .catch(function(err) {
        overlay.style.display = 'none';
        emptyState.style.display = 'block';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> 生成 SRS';
        console.error('加载 SRS 失败:', err);
        alert('加载 SRS 失败: ' + err.message);
    });
}

// ---------- 渲染编辑模式 ----------
function renderSrsEditMode(srs) {
    var html = '';
    var sectionKeys = [
        'introduction', 'overall_description', 'functional_requirements',
        'external_interfaces', 'non_functional_requirements',
        'data_requirements', 'appendix'
    ];

    sectionKeys.forEach(function(key) {
        var title = SRS_SECTION_TITLES[key] || key;
        var sectionData = srs[key];
        if (!sectionData) return;

        html += '<div class="srs-section">';
        html += '<div class="srs-section-header" onclick="toggleSrsSection(this)">';
        html += '<span>' + title + '</span>';
        html += '<i class="fas fa-chevron-down"></i>';
        html += '</div>';
        html += '<div class="srs-section-body open">';

        if (key === 'functional_requirements' && Array.isArray(sectionData)) {
            sectionData.forEach(function(fr, idx) {
                html += '<div style="margin-bottom: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: 4px;">';
                html += '<strong>' + (fr.id || 'FR-' + (idx+1)) + ' ' + (fr.name || '') + '</strong>';
                html += ' <span class="issue-tag ' + (fr.priority === '高' ? 'high' : fr.priority === '中' ? 'medium' : 'low') + '">' + (fr.priority || '中') + '</span>';
                html += '<br><small>模块: ' + (fr.module || '') + ' | 来源: ' + (fr.source || '') + '</small>';
                html += '<textarea data-srs-key="' + key + '" data-srs-index="' + idx + '" data-srs-field="description" onchange="markSrsDirty(this)">' + escapeHtml(fr.description || '') + '</textarea>';
                html += '</div>';
            });
        } else if (typeof sectionData === 'object') {
            Object.keys(sectionData).forEach(function(subKey) {
                var subVal = sectionData[subKey];
                var subTitle = SRS_SUB_SECTION_TITLES[subKey] || subKey;
                if (typeof subVal === 'string') {
                    html += '<label style="font-weight: 500; margin-top: 8px; display: block;">' + subTitle + '</label>';
                    html += '<textarea data-srs-key="' + key + '" data-srs-subkey="' + subKey + '" onchange="markSrsDirty(this)">' + escapeHtml(subVal) + '</textarea>';
                } else if (typeof subVal === 'object') {
                    // 嵌套对象
                    html += '<label style="font-weight: 600; margin-top: 12px; display: block;">' + subTitle + '</label>';
                    Object.keys(subVal).forEach(function(deepKey) {
                        var deepTitle = SRS_SUB_SECTION_TITLES[deepKey] || deepKey;
                        if (typeof subVal[deepKey] === 'string') {
                            html += '<label style="font-weight: 500; margin-top: 6px; display: block;">' + deepTitle + '</label>';
                            html += '<textarea data-srs-key="' + key + '" data-srs-subkey="' + deepKey + '" onchange="markSrsDirty(this)">' + escapeHtml(subVal[deepKey]) + '</textarea>';
                        }
                    });
                }
            });
        } else if (typeof sectionData === 'string') {
            html += '<textarea data-srs-key="' + key + '" onchange="markSrsDirty(this)">' + escapeHtml(sectionData) + '</textarea>';
        }

        html += '<div class="srs-section-actions">';
        html += '<button class="btn btn-sm btn-outline-primary" onclick="saveSingleSection(\''
            + key
        + '\')"><i class="fas fa-save"></i> \u4fdd\u5b58</button>';
        html += '</div>';
        html += '</div></div>';
    });

    return html;
}

// ---------- 渲染预览模式（已渲染 Markdown）----------
function renderSrsPreviewMode(srs) {
    var html = '';
    html += '<div style="max-width: 900px; margin: 0 auto;">';
    html += '<h1 style="text-align:center; border-bottom: 3px solid var(--primary); padding-bottom: 16px; margin-bottom: 32px;">软件需求规格说明书</h1>';
    html += '<p style="text-align:center; color: var(--text-secondary); margin-bottom: 32px;">本文件由 TestBrain 系统根据业务需求文档（BRD）自动生成，遵循 GB/T 9385 标准</p>';

    var sectionKeys = [
        'introduction', 'overall_description', 'functional_requirements',
        'external_interfaces', 'non_functional_requirements',
        'data_requirements', 'appendix'
    ];

    sectionKeys.forEach(function(key) {
        var title = SRS_SECTION_TITLES[key] || key;
        var sectionData = srs[key];
        if (!sectionData) return;

        html += '<h2 style="border-bottom: 2px solid var(--border-color); padding-bottom: 8px; margin-top: 32px;">' + title + '</h2>';

        if (key === 'functional_requirements' && Array.isArray(sectionData)) {
            sectionData.forEach(function(fr, idx) {
                html += '<div style="margin: 16px 0; padding: 16px; background: var(--bg-tertiary); border-radius: 6px; border-left: 4px solid var(--primary);">';
                html += '<h3 style="margin: 0 0 8px;">' + (fr.id || 'FR-' + (idx+1)) + ' ' + (fr.name || '') + '</h3>';
                html += '<div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">';
                html += '模块: ' + (fr.module || '') + ' | 优先级: ' + (fr.priority || '') + ' | 来源: ' + (fr.source || '');
                html += '</div>';
                html += '<div class="srs-preview-markdown" style="padding: 0;">';
                html += renderMarkdown(fr.description || '');
                html += '</div>';
                html += '</div>';
            });
        } else if (typeof sectionData === 'object') {
            Object.keys(sectionData).forEach(function(subKey) {
                var subVal = sectionData[subKey];
                var subTitle = SRS_SUB_SECTION_TITLES[subKey] || subKey;
                if (typeof subVal === 'string') {
                    html += '<h3>' + subTitle + '</h3>';
                    html += '<div class="srs-preview-markdown" style="padding: 0;">' + renderMarkdown(subVal) + '</div>';
                } else if (typeof subVal === 'object') {
                    html += '<h3>' + subTitle + '</h3>';
                    Object.keys(subVal).forEach(function(deepKey) {
                        var deepTitle = SRS_SUB_SECTION_TITLES[deepKey] || deepKey;
                        if (typeof subVal[deepKey] === 'string') {
                            html += '<h4>' + deepTitle + '</h4>';
                            html += '<div class="srs-preview-markdown" style="padding: 0;">' + renderMarkdown(subVal[deepKey]) + '</div>';
                        }
                    });
                }
            });
        } else if (typeof sectionData === 'string') {
            html += '<div class="srs-preview-markdown" style="padding: 0;">' + renderMarkdown(sectionData) + '</div>';
        }
    });

    html += '<hr style="margin: 40px 0;">';
    html += '<p style="text-align:center; color: var(--text-secondary);"><em>报告由 TestBrain 系统自动生成</em></p>';
    html += '</div>';

    return html;
}

// ---------- 切换预览/编辑 ----------
function toggleSrsView() {
    var contentArea = document.getElementById('srsContentArea');
    var previewArea = document.getElementById('srsPreviewArea');
    var label = document.getElementById('toggleViewLabel');

    if (srsViewMode === 'edit') {
        // 切换到预览模式
        contentArea.style.display = 'none';
        previewArea.style.display = 'block';
        label.textContent = '编辑';
        srsViewMode = 'preview';
    } else {
        // 切换到编辑模式
        contentArea.style.display = 'block';
        previewArea.style.display = 'none';
        label.textContent = '预览';
        srsViewMode = 'edit';
    }
}

// ---------- 章节折叠 ----------
function toggleSrsSection(header) {
    var body = header.nextElementSibling;
    if (body) {
        body.classList.toggle('open');
        var icon = header.querySelector('i.fa-chevron-down, i.fa-chevron-up');
        if (icon) {
            icon.className = body.classList.contains('open') ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
        }
    }
}

function markSrsDirty(textarea) {
    textarea.style.borderColor = '#ff9800';
}

// ---------- 保存单章节 ----------
function saveSingleSection(sectionKey) {
    var textareas = document.querySelectorAll('textarea[data-srs-key="' + sectionKey + '"]');
    var sectionData = {};

    if (sectionKey === 'functional_requirements') {
        var frList = [];
        var items = {};
        textareas.forEach(function(ta) {
            var idx = ta.getAttribute('data-srs-index');
            var field = ta.getAttribute('data-srs-field') || 'description';
            if (!items[idx]) items[idx] = {};
            items[idx][field] = ta.value;
        });
        Object.keys(items).sort().forEach(function(idx) {
            frList.push(items[idx]);
        });
        sectionData = { "functional_requirements": frList };
    } else {
        textareas.forEach(function(ta) {
            var subKey = ta.getAttribute('data-srs-subkey');
            if (subKey) {
                if (!sectionData[sectionKey]) sectionData[sectionKey] = {};
                sectionData[sectionKey][subKey] = ta.value;
            } else {
                sectionData[sectionKey] = ta.value;
            }
        });
    }

    fetch('/requirement_analysis/api/' + currentAnalysisId + '/srs/', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ srs_content: sectionData })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            textareas.forEach(function(ta) { ta.style.borderColor = ''; });
            alert('章节「' + (SRS_SECTION_TITLES[sectionKey] || sectionKey) + '」已保存');
        } else {
            alert('保存失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(function(err) {
        alert('保存失败: ' + err.message);
    });
}

// ---------- 导出 SRS ----------
function exportSRS() {
    if (!currentAnalysisId) {
        alert('请先生成 SRS');
        return;
    }
    window.location.href = '/requirement_analysis/api/' + currentAnalysisId + '/srs/export/';
}

// ---------- SRS 采纳/拒绝 ----------
function loadSrsAdoptionStatus() {
    if (!currentAnalysisId) return;
    var adoptBar = document.getElementById('srsAdoptionBar');
    if (!adoptBar) return;

    fetch('/requirement_analysis/api/result/' + currentAnalysisId + '/')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (!data.success) return;
        var status = data.data.srs_adoption_status || 'pending';
        var adoptAt = data.data.srs_adopted_at;
        updateSrsAdoptionUI(status, adoptAt);
    })
    .catch(function(err) {
        console.log('加载 SRS 采纳状态失败:', err);
    });
}

function updateSrsAdoptionUI(status, adoptAt) {
    var adoptBar = document.getElementById('srsAdoptionBar');
    var actions = document.getElementById('srsAdoptionActions');
    var result = document.getElementById('srsAdoptionResult');
    var badge = document.getElementById('srsAdoptionStatusBadge');
    var resultText = document.getElementById('srsAdoptionResultText');

    if (!adoptBar) return;
    adoptBar.style.display = 'block';

    if (status === 'adopted') {
        actions.style.display = 'none';
        result.style.display = 'block';
        badge.textContent = '已采纳';
        badge.className = 'status-badge adopted';
        resultText.innerHTML = '✅ SRS 已于 ' + (adoptAt || '') + ' 采纳';
    } else if (status === 'rejected') {
        actions.style.display = 'none';
        result.style.display = 'block';
        badge.textContent = '已拒绝';
        badge.className = 'status-badge rejected';
        resultText.innerHTML = '❌ SRS 已于 ' + (adoptAt || '') + ' 拒绝';
    } else {
        actions.style.display = 'block';
        result.style.display = 'none';
        badge.textContent = '待审核';
        badge.className = 'status-badge pending';
    }
}

function adoptSRS() {
    if (!currentAnalysisId) return;
    fetch('/requirement_analysis/api/' + currentAnalysisId + '/srs/adopt/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            updateSrsAdoptionUI('adopted', new Date().toLocaleString());
        } else {
            alert('采纳失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(function(err) {
        alert('请求失败: ' + err.message);
    });
}

function rejectSRS() {
    if (!currentAnalysisId) return;
    fetch('/requirement_analysis/api/' + currentAnalysisId + '/srs/reject/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            updateSrsAdoptionUI('rejected', new Date().toLocaleString());
        } else {
            alert('拒绝失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(function(err) {
        alert('请求失败: ' + err.message);
    });
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// ===== 文档维护功能（删除已采纳 / 重新提交拒绝的文档） =====

function deleteAdoptedDoc(docId) {
    if (!confirm('确定要删除此需求文档吗？删除后不可恢复。')) {
        return;
    }

    fetch('/requirement_analysis/api/' + docId + '/delete/', {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(function(r) {
        if (!r.ok) { return r.text().then(function(t) { throw new Error('请求失败: ' + (t || r.statusText)); }); }
        return r.json();
    })
    .then(function(data) {
        if (data.success) {
            alert(data.message);
            loadAdoptedDocs();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(function(err) {
        alert('删除失败: ' + err.message);
    });
}

function resubmitDocument(docId) {
    if (!confirm('确定要重新提交此文档吗？状态将恢复为待审核，可以重新采纳。')) {
        return;
    }

    fetch('/requirement_analysis/api/' + docId + '/resubmit/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(function(r) {
        if (!r.ok) { return r.text().then(function(t) { throw new Error('请求失败: ' + (t || r.statusText)); }); }
        return r.json();
    })
    .then(function(data) {
        if (data.success) {
            alert(data.message);
            loadAdoptedDocs();
        } else {
            alert('重新提交失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(function(err) {
        alert('重新提交失败: ' + err.message);
    });
}


// 页面加载时检查是否有已有 SRS
document.addEventListener('DOMContentLoaded', function() {
    try {
        var savedId = sessionStorage.getItem('req_analysis_current_id');
        if (savedId) {
            currentAnalysisId = parseInt(savedId);
            fetch('/requirement_analysis/api/' + currentAnalysisId + '/srs/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success && data.data && data.data.srs_content) {
                    showSrsCard();
                    // 自动加载 SRS 内容（包含采纳状态）
                    loadSRS();
                }
            })
            .catch(function() {});
        }
    } catch(e) {}
});
