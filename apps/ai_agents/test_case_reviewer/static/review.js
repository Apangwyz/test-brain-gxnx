// 测试用例评审页面专用脚本

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

// 注意：review.html 中已有内联 JS 处理 .review-button 和 .status-button
// review.js 仅保留辅助函数，避免与内联 JS 冲突
document.addEventListener('DOMContentLoaded', function() {
    // 获取 CSRF Token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // .review-button 事件由 review.html 内联 JS 处理（已映射到 /test_case_reviewer/<id>/）
    // .status-button 事件由 review.html 内联 JS 处理
    
    // 显示通知
    function showNotification(message, type = 'info') {
        // 如果页面上有通知容器，使用它
        let container = document.getElementById('notification-container');
        
        // 如果没有，创建一个
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.position = 'fixed';
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        // 添加到容器
        container.appendChild(notification);
        
        // 设置自动关闭
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
    
    // 更新标签页计数
    function updateTabCounts() {
        const pendingCount = document.querySelectorAll('#pending .test-case-item').length;
        const approvedCount = document.querySelectorAll('#approved .test-case-item').length;
        const rejectedCount = document.querySelectorAll('#rejected .test-case-item').length;
        
        document.querySelector('#pending-tab .badge').textContent = pendingCount;
        document.querySelector('#approved-tab .badge').textContent = approvedCount;
        document.querySelector('#rejected-tab .badge').textContent = rejectedCount;
    }

    // 添加分页链接的点击事件处理
    document.querySelectorAll('.pagination .page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const pageType = this.getAttribute('data-page-type');
            const url = new URL(this.href);
            const page = url.searchParams.get(`${pageType}_page`);
            
            // 保持当前标签页的状态
            const currentTab = document.querySelector('.nav-tabs .nav-link.active');
            if (currentTab) {
                url.searchParams.set('active_tab', currentTab.getAttribute('href').substring(1));
            }
            
            // 跳转到新页面
            window.location.href = url.toString();
        });
    });
});