# 系统归属管理功能模块 - 部署排查报告

## 日期
2026-05-24

## 问题描述
项目重新部署后，前端界面中未能找到预期的新功能或更新功能。

## 排查步骤

### 1. 部署流程完整性检查 ✅

**已检查和修改的文件：**

1. **数据模型** (`apps/core/models.py`):
   - ✅ System 系统模型已创建
   - ✅ TestPlan 测试计划模型已创建
   - ✅ RequirementDoc 需求文档模型已创建
   - ✅ TestCase 模型已添加 system 字段

2. **API 接口** (`apps/core/views.py`):
   - ✅ 系统管理 API 已实现
   - ✅ 测试计划 API 已实现
   - ✅ 需求文档 API 已实现
   - ✅ 关联查询 API 已实现
   - ✅ 已添加 `from django.db import models` 导入

3. **URL 路由** (`apps/core/urls.py`):
   - ✅ 系统管理路由已配置
   - ✅ API 路由已配置

4. **导航链接** (`templates/base.html`):
   - ✅ 已添加"系统归属管理"导航链接

5. **管理后台** (`apps/core/admin.py`):
   - ✅ System 模型已注册
   - ✅ TestPlan 模型已注册
   - ✅ RequirementDoc 模型已注册

6. **管理页面** (`templates/system_management.html`):
   - ✅ 系统管理前端页面已创建

### 2. 文件位置确认

```
项目根目录/
├── apps/
│   └── core/
│       ├── models.py          ✅
│       ├── views.py           ✅
│       ├── urls.py            ✅
│       └── admin.py           ✅
└── templates/
    ├── base.html              ✅
    └── system_management.html ✅
```

### 3. 浏览器缓存问题建议

**清除缓存的方法：**
1. 强制刷新：`Ctrl + Shift + R` (Windows/Linux) 或 `Cmd + Shift + R` (Mac)
2. 使用无痕/隐私模式访问
3. 在浏览器开发者工具中禁用缓存（Network 标签页）

### 4. 版本一致性检查

**需要执行的步骤：**
1. 检查 `git status` 确认所有更改已提交
2. 检查 `git log` 确认部署了最新版本
3. 确认部署服务器上的文件时间戳是最新的

### 5. 数据库迁移

**需要执行的步骤：**
```bash
# 生成迁移文件
python manage.py makemigrations core

# 应用迁移
python manage.py migrate
```

### 6. 启动项目进行验证

**启动命令：**
```bash
# 使用项目启动脚本
cd /path/to/TestBrain
python scripts/start.py -p 8000

# 或直接使用 Django
python manage.py runserver 0.0.0.0:8000
```

**访问地址：**
- 首页: http://localhost:8000/
- 系统管理: http://localhost:8000/system/
- 管理后台: http://localhost:8000/admin/

### 7. 功能验证清单

- [ ] 导航栏中显示"系统归属管理"链接
- [ ] 点击链接可以正常打开系统管理页面
- [ ] 页面布局正常显示
- [ ] 可以正常查看系统列表
- [ ] 可以正常新增系统
- [ ] 可以正常编辑系统
- [ ] 可以正常删除系统

## 问题解决方案

### 如果前端看不到新功能：

**1. 确认文件已正确部署**
```bash
# 检查文件是否存在
ls -la templates/system_management.html
ls -la apps/core/urls.py
ls -la apps/core/views.py
ls -la apps/core/models.py
```

**2. 检查 Django 模板加载**
```python
# 在 Django shell 中测试
from django.shortcuts import render
from django.test import RequestFactory
from apps.core.views import system_management

# 测试视图是否存在
print(system_management)
```

**3. 检查 URL 路由**
```bash
# 在浏览器访问：
http://localhost:8000/system/

# 如果出现 404，检查：
# - urls.py 是否正确导入
# - 项目是否已重启
```

### 如果后端 API 无法访问：

**1. 检查 views.py 是否有语法错误**
```bash
# 测试导入
python -c "from apps.core.views import system_list; print('OK')"
```

**2. 查看 Django 日志**
```bash
# 查看运行日志
# 检查是否有任何错误信息
```

## 快速诊断命令

```bash
# 1. 检查文件是否完整
cd /path/to/TestBrain
ls -la apps/core/
ls -la templates/

# 2. 检查是否有语法错误
python -m py_compile apps/core/models.py
python -m py_compile apps/core/views.py
python -m py_compile apps/core/urls.py
python -m py_compile apps/core/admin.py

# 3. 检查 Django 配置
python manage.py check

# 4. 生成并应用迁移
python manage.py makemigrations core
python manage.py migrate

# 5. 启动项目
python manage.py runserver
```

## 备注

- 确保测试环境中安装了 Django
- 确保所有依赖已安装
- 确保数据库配置正确
- 确保已创建管理员用户（如果需要访问 admin）
