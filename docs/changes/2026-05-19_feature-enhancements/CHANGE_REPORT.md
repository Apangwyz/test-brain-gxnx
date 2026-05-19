# 功能增强变更报告

## 变更基本信息

- **变更日期**: 2026-05-19
- **变更类型**: 功能增强与优化
- **变更负责人**: 开发团队
- **关联 Issue**: 进度页面交互优化、PDF文件上传支持

---

## 变更概述

本次变更包含两个重要功能增强：

1. **进度页面最小化后重新唤醒功能**：添加悬浮按钮组件，当测试用例生成任务在后台运行时显示，支持点击唤醒进度页面
2. **PDF文件上传支持**：扩展需求文档上传功能，增加对PDF格式文件的支持，包括文件类型验证、大小限制处理和上传状态反馈

---

## 问题描述

### 问题 1: 进度页面最小化后无法唤醒

**现象**:
- 用户点击"后台运行"按钮后，进度页面消失
- 用户无法重新查看任务进度或操作进度页面
- 缺乏明确的唤醒入口

**影响范围**:
- 所有使用测试用例生成功能的用户

### 问题 2: 不支持PDF文件上传

**现象**:
- 用户无法上传PDF格式的需求文档
- 文件类型验证只支持 .docx、.md、.txt
- 文件大小限制仅为10MB，无法满足大文件需求

**影响范围**:
- 需要上传PDF格式需求文档的用户

---

## 解决方案

### 1. 进度页面悬浮按钮

#### 1.1 前端实现

**文件**: `apps/ai_agents/test_case_generator/static/progress.js`

**修改内容**:

```javascript
// 添加悬浮按钮相关方法
createFloatButton() {
    // 创建悬浮按钮DOM元素
    const button = document.createElement('div');
    button.id = 'progress-float-button';
    // ...
}

showFloatButton() {
    // 显示悬浮按钮
    this.floatButton.classList.add('active');
}

wakeFromBackground() {
    // 从后台模式唤醒进度页面
    this.show();
    this.hideFloatButton();
}
```

**关键特性**:
- ✅ 悬浮按钮位于页面右下角，不影响其他操作
- ✅ 显示实时进度百分比
- ✅ 任务完成后按钮变为绿色
- ✅ 支持平滑动画效果
- ✅ 鼠标悬停显示提示信息

#### 1.2 CSS样式

**文件**: `apps/ai_agents/test_case_generator/static/progress.css`

**修改内容**:

```css
.progress-float-button {
    position: fixed;
    right: 24px;
    bottom: 24px;
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 50%;
    /* ... */
}
```

### 2. PDF文件上传支持

#### 2.1 文件解析器增强

**文件**: `apps/utils/file_parser.py`

**修改内容**:

```python
# 新增支持的文件类型
SUPPORTED_FILE_TYPES = {
    '.docx': 'Microsoft Word文档',
    '.md': 'Markdown文档',
    '.txt': '纯文本文件',
    '.pdf': 'PDF文档',
}

# 新增文件大小限制（50MB）
MAX_FILE_SIZE = 50 * 1024 * 1024

# 新增PDF解析函数
def parse_pdf(file_path):
    """解析PDF文档"""
    from PyPDF2 import PdfReader
    reader = PdfReader(file_path)
    content = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            content.append(text.strip())
    return '\n\n'.join(content)
```

#### 2.2 前端更新

**文件**: `apps/ai_agents/test_case_generator/static/generate.js`

**修改内容**:

```javascript
// 更新支持的文件类型
const allowedExtensions = ['.docx', '.md', '.txt', '.pdf'];

// 更新文件图标映射
function getFileIconClass(extension) {
    switch (extension) {
        case 'pdf':
            return 'fas fa-file-pdf text-red';
        // ...
    }
}
```

#### 2.3 前端模板更新

**文件**: `apps/ai_agents/test_case_generator/templates/generate.html`

**修改内容**:

```html
<p class="upload-hint">支持 .docx、.md、.txt、.pdf 格式，最大50MB，可多选</p>
<input type="file" id="file-input" name="documents" multiple accept=".docx,.md,.txt,.pdf">
```

#### 2.4 后端视图更新

**文件**: `apps/ai_agents/test_case_generator/views.py`

**修改内容**:

```python
# 更新文件大小限制验证
from apps.utils.file_parser import MAX_FILE_SIZE, get_human_readable_size

if uploaded_file.size > MAX_FILE_SIZE:
    return JsonResponse({
        'success': False,
        'message': f'文件大小超过限制。当前大小: {get_human_readable_size(uploaded_file.size)}，最大允许: {get_human_readable_size(MAX_FILE_SIZE)}'
    })
```

---

## 修改文件清单

| 文件路径 | 修改类型 | 修改内容 | 说明 |
|---------|---------|---------|------|
| `apps/ai_agents/test_case_generator/static/progress.js` | 修改 | 添加悬浮按钮组件、后台模式唤醒功能 | 核心交互逻辑 |
| `apps/ai_agents/test_case_generator/static/progress.css` | 修改 | 添加悬浮按钮样式、动画效果 | 样式优化 |
| `apps/utils/file_parser.py` | 修改 | 添加PDF解析支持、文件大小限制 | 文件处理模块 |
| `apps/ai_agents/test_case_generator/static/generate.js` | 修改 | 更新支持文件类型列表、添加PDF图标 | 前端上传逻辑 |
| `apps/ai_agents/test_case_generator/templates/generate.html` | 修改 | 更新文件类型提示、accept属性 | 页面模板 |
| `apps/ai_agents/test_case_generator/views.py` | 修改 | 更新文件大小限制验证逻辑 | 后端视图 |

---

## 测试验证

### 1. 悬浮按钮功能测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| 点击后台运行按钮 | 悬浮按钮显示在右下角 | ✅ 通过 |
| 悬浮按钮显示进度 | 实时更新进度百分比 | ✅ 通过 |
| 点击悬浮按钮 | 唤醒进度页面 | ✅ 通过 |
| 任务完成 | 按钮变为绿色 | ✅ 通过 |
| 关闭页面 | 按钮隐藏 | ✅ 通过 |

### 2. PDF上传功能测试

| 测试项 | 预期结果 | 实际结果 |
|--------|---------|---------|
| 选择PDF文件 | 文件列表显示PDF图标 | ✅ 通过 |
| 上传有效PDF | 解析成功，内容填充到文本框 | ✅ 通过 |
| 上传超大PDF (>50MB) | 提示文件大小超限 | ✅ 通过 |
| 上传损坏PDF | 提示解析失败 | ✅ 通过 |

---

## 使用示例

### 1. 后台任务唤醒流程

```javascript
// 用户点击后台运行
progressManager.hide(true);  // 进入后台模式，显示悬浮按钮

// 用户点击悬浮按钮
progressManager.wakeFromBackground();  // 唤醒进度页面
```

### 2. PDF文件上传

```javascript
// 前端自动识别PDF文件
const allowedExtensions = ['.docx', '.md', '.txt', '.pdf'];

// 后端解析PDF
content, filename, file_type = extract_text_from_uploaded_file(uploaded_file);
// file_type = "PDF文档"
```

---

## 验证清单

- [x] 悬浮按钮创建完成
- [x] 悬浮按钮显示/隐藏功能完成
- [x] 悬浮按钮进度更新完成
- [x] 后台模式唤醒功能完成
- [x] PDF解析功能添加完成
- [x] 文件类型验证更新完成
- [x] 文件大小限制更新完成（50MB）
- [x] 前端文件类型提示更新完成
- [x] 前端文件图标更新完成
- [x] 测试验证通过

---

## 后续优化建议

### 短期优化
1. 添加悬浮按钮拖拽位置功能
2. 支持多个后台任务管理
3. 添加PDF加密文件处理支持

### 长期优化
1. 实现文件预览功能
2. 添加批量文件上传支持
3. 实现文件内容预览和编辑

---

## 变更记录

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-05-19 | 创建 | 初始实现完成 |
| 2026-05-19 | 测试 | 功能测试通过 |
| 2026-05-19 | 归档 | 变更文档整理归档 |

---

## 相关文档

- [进度按钮修复报告](../2026-05-19_progress-button-fix/CHANGE_REPORT.md)
- [日志长度修复报告](../2026-05-19_log-length-fix/CHANGE_REPORT.md)
- [测试用例生成器修复报告](../2026-05-19_test-case-generator-fix/CHANGE_REPORT.md)
- [项目初始化报告](../2024-12-00_project-initialization/CHANGE_REPORT.md)