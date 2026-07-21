/**
 * 知识库管理页面脚本
 * 支持三 tab：手动添加 / 文件上传 / 知识库列表（含搜索、分页、删除）
 */

document.addEventListener('DOMContentLoaded', function () {

  // ======================================================================
  // Tab 切换时刷新对应面板
  // ======================================================================
  const listTab = document.getElementById('list-tab');
  if (listTab) {
    listTab.addEventListener('shown.bs.tab', function () {
      loadKnowledgeList(1);
    });
  }

  // ======================================================================
  // Tab 1 — 手动添加知识条目
  // ======================================================================
  const addForm = document.getElementById('add-knowledge-form');
  if (addForm) {
    addForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const title = document.getElementById('knowledge-title').value.trim();
      const content = document.getElementById('knowledge-content').value.trim();
      if (!title) { showNotification('请输入知识条目标题', 'error'); return; }
      if (!content) { showNotification('请输入知识条目内容', 'error'); return; }

      const btn = addForm.querySelector('button[type="submit"]');
      btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 添加中...';

      fetch('/api/add-knowledge/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ title: title, content: content })
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false; btn.innerHTML = '<i class="fas fa-plus"></i> 添加知识条目';
        if (data.success) {
          showNotification('知识条目添加成功', 'success');
          document.getElementById('knowledge-title').value = '';
          document.getElementById('knowledge-content').value = '';
        } else {
          showNotification(data.message || '添加失败', 'error');
        }
      })
      .catch(function () {
        btn.disabled = false; btn.innerHTML = '<i class="fas fa-plus"></i> 添加知识条目';
        showNotification('请求失败', 'error');
      });
    });
  }

  // ======================================================================
  // Tab 2 — 文件上传
  // ======================================================================
  var uploadZone = document.getElementById('uploadZone');
  var fileInput = document.getElementById('fileInput');
  var uploadBtn = document.getElementById('uploadBtn');
  var selectedFileEl = document.getElementById('selectedFile');
  var uploadStatusEl = document.getElementById('uploadStatus');
  var selectedFile = null;

  if (uploadZone) {
    uploadZone.addEventListener('click', function () { fileInput.click(); });

    fileInput.addEventListener('change', function () {
      if (fileInput.files.length > 0) { selectFile(fileInput.files[0]); }
    });

    uploadZone.addEventListener('dragover', function (e) { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', function () { uploadZone.classList.remove('dragover'); });
    uploadZone.addEventListener('drop', function (e) {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) { selectFile(e.dataTransfer.files[0]); }
    });

    uploadBtn.addEventListener('click', function () {
      if (selectedFile) { uploadFile(selectedFile); }
    });
  }

  function selectFile(file) {
    selectedFile = file;
    selectedFileEl.style.display = 'block';
    selectedFileEl.innerHTML = '<i class="fas fa-file"></i> ' + file.name;
    uploadBtn.disabled = false;
    uploadStatusEl.innerHTML = '';
  }

  function uploadFile(file) {
    uploadBtn.disabled = true;
    uploadZone.style.pointerEvents = 'none';
    uploadStatusEl.innerHTML = '<span style="color: var(--text-secondary);"><i class="fas fa-spinner fa-spin"></i> 上传中...</span>';

    var formData = new FormData();
    formData.append('single_file', file);

    // 视图已标记 @csrf_exempt，无需传 CSRF token，否则会破坏 multipart Content-Type
    fetch('/api/knowledge/upload/', {
      method: 'POST',
      body: formData
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
      uploadBtn.disabled = false;
      uploadZone.style.pointerEvents = '';
      if (result.success) {
        uploadStatusEl.innerHTML = '<span style="color: var(--success); font-weight: 600;"><i class="fas fa-check-circle"></i> 上传成功！导入 ' + result.count + ' 条数据</span>';
        selectedFile = null; fileInput.value = ''; selectedFileEl.style.display = 'none'; uploadBtn.disabled = true;
      } else {
        uploadStatusEl.innerHTML = '<span style="color: var(--danger);">' + (result.error || '上传失败') + '</span>';
      }
    })
    .catch(function () {
      uploadBtn.disabled = false;
      uploadZone.style.pointerEvents = '';
      uploadStatusEl.innerHTML = '<span style="color: var(--danger);">上传请求失败</span>';
    });
  }

  // ======================================================================
  // Tab 3 — 知识库列表（分页 + 搜索 + 删除）
  // ======================================================================
  var currentListPage = 1;
  var listTotalPages = 1;
  var listSearchTerm = '';

  var searchInput = document.getElementById('knowledge-search');
  var searchBtn = document.getElementById('searchBtn');

  if (searchBtn) {
    searchBtn.addEventListener('click', function () {
      listSearchTerm = searchInput.value.trim();
      currentListPage = 1;
      loadKnowledgeList(1);
    });
  }
  if (searchInput) {
    searchInput.addEventListener('keyup', function (e) {
      if (e.key === 'Enter') {
        listSearchTerm = searchInput.value.trim();
        currentListPage = 1;
        loadKnowledgeList(1);
      }
    });
  }

  document.getElementById('prevPage').addEventListener('click', function (e) {
    e.preventDefault();
    if (currentListPage > 1) { loadKnowledgeList(currentListPage - 1); }
  });
  document.getElementById('nextPage').addEventListener('click', function (e) {
    e.preventDefault();
    if (currentListPage < listTotalPages) { loadKnowledgeList(currentListPage + 1); }
  });

  // Initial load (visible when tab switches to list)
  loadKnowledgeList(1);

  function loadKnowledgeList(page) {
    var container = document.getElementById('knowledge-list');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner"></div><p style="color: var(--text-secondary);">加载中...</p></div>';

    var url = '/api/knowledge-list/?page=' + page;
    if (listSearchTerm) { url += '&search=' + encodeURIComponent(listSearchTerm); }

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) {
          container.innerHTML = '<div class="alert alert-danger">' + (data.message || '加载失败') + '</div>';
          return;
        }
        var items = data.knowledge_items;
        if (!items || items.length === 0) {
          container.innerHTML = '<div class="text-center py-4" style="color: var(--text-secondary);"><i class="fas fa-inbox fa-2x" style="margin-bottom: 8px; display:block;"></i>知识库为空</div>';
          document.getElementById('listPagination').style.display = 'none';
          return;
        }
        var html = '<div class="list-group">';
        items.forEach(function (item) {
          var date = new Date(item.created_at);
          var dateStr = date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
          var preview = item.content ? item.content.substring(0, 100) + (item.content.length > 100 ? '...' : '') : '';
          html += '<div class="list-group-item knowledge-item">'
            + '<div class="d-flex justify-content-between align-items-start">'
            + '<div style="flex:1;">'
            + '<h6 style="margin-bottom:4px;">' + escapeHtml(item.title) + '</h6>'
            + '<div class="content-preview">' + escapeHtml(preview) + '</div>'
            + '<small class="text-muted">' + dateStr + '</small>'
            + '</div>'
            + '<button class="btn btn-sm btn-outline-danger delete-btn ml-2" onclick="confirmDelete(' + item.id + ', \'' + escapeHtml(item.title).replace(/'/g, "\\'") + '\')"><i class="fas fa-trash"></i></button>'
            + '</div>'
            + '</div>';
        });
        html += '</div>';
        container.innerHTML = html;

        // Pagination (using server-side list but for now showing all)
        // The current knowledge_list doesn't support pagination. Let's use the select endpoint.
      });
  }

  // ======================================================================
  // 删除确认
  // ======================================================================
  window.confirmDelete = function (id, title) {
    if (!confirm('确定要删除知识条目「' + title + '」吗？')) return;

    fetch('/api/knowledge/' + id + '/delete/', {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.success) {
        showNotification('已删除: ' + title, 'success');
        loadKnowledgeList(currentListPage);
      } else {
        showNotification(data.message || '删除失败', 'error');
      }
    })
    .catch(function () {
      showNotification('删除请求失败', 'error');
    });
  };

  // ======================================================================
  // 辅助函数
  // ======================================================================
  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function getCookie(name) {
    var value = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          value = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return value;
  }

  function showNotification(message, type) {
    var container = document.getElementById('notification-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'notification-container';
      container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;';
      document.body.appendChild(container);
    }
    var notif = document.createElement('div');
    notif.className = 'alert alert-' + type + ' alert-dismissible fade show';
    notif.innerHTML = message
      + '<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>';
    container.appendChild(notif);
    setTimeout(function () {
      notif.classList.remove('show');
      setTimeout(function () { notif.remove(); }, 300);
    }, 4000);
  }

});
