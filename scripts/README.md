# TestBrain 运维脚本使用说明

## 概述

本目录包含 TestBrain 项目的完整运维脚本集合，提供服务管理、状态监控、日志管理和数据备份等核心功能。

## 脚本清单

| 脚本名称 | 功能描述 |
|---------|---------|
| `main.py` | 运维命令统一入口 |
| `deploy.py` | **一键部署脚本**（全流程自动化） |
| `git_push.py` | **Git推送脚本**（代码上传至远程仓库） |
| `start.py` | 启动项目服务 |
| `stop.py` | 停止项目服务 |
| `restart.py` | 重启项目服务 |
| `status.py` | 检查服务状态 |
| `logs.py` | 日志管理 |
| `backup.py` | 数据备份 |
| `utils.py` | 公共工具模块 |

## 快速入门

### 基本使用方式

```bash
# 使用主入口脚本
python scripts/main.py <command> [options]

# 或直接调用子脚本
python scripts/start.py [options]
```

### 常见操作示例

```bash
# 启动服务（守护进程模式，端口8000）
python scripts/main.py start -p 8000 -d

# 停止服务（优雅关闭）
python scripts/main.py stop

# 强制停止服务
python scripts/main.py stop -f

# 重启服务
python scripts/main.py restart

# 检查服务状态
python scripts/main.py status

# 创建全量备份
python scripts/main.py backup full

# 日志轮转（保留7个轮转文件）
python scripts/main.py logs rotate -k 7
```

---

## 命令详细说明

### 1. start - 启动服务

```bash
python scripts/main.py start [options]
```

**选项：**
- `-e, --env <path>`     指定环境变量文件路径
- `-p, --port <number>`  指定服务端口（默认：8000）
- `-d, --daemon`         以守护进程模式运行
- `-h, --help`           显示帮助信息

**示例：**
```bash
# 前台启动（开发模式）
python scripts/main.py start -p 8000

# 后台启动（生产模式）
python scripts/main.py start -p 8000 -d

# 指定环境变量文件
python scripts/main.py start -e /path/to/.env -d
```

### 2. stop - 停止服务

```bash
python scripts/main.py stop [options]
```

**选项：**
- `-f, --force`          强制关闭（使用 kill -9）
- `-t, --timeout <sec>`  优雅关闭超时时间（默认：30秒）
- `-h, --help`           显示帮助信息

**示例：**
```bash
# 优雅关闭（等待30秒）
python scripts/main.py stop

# 强制关闭（立即终止）
python scripts/main.py stop -f

# 设置超时时间为10秒
python scripts/main.py stop -t 10
```

### 3. restart - 重启服务

```bash
python scripts/main.py restart [options]
```

**选项：**
- `-e, --env <path>`     指定环境变量文件路径
- `-p, --port <number>`  指定服务端口（默认：8000）
- `-f, --force`          强制重启
- `-w, --wait <sec>`     停止后等待时间（默认：5秒）
- `-h, --help`           显示帮助信息

**示例：**
```bash
# 正常重启
python scripts/main.py restart

# 强制重启并指定端口
python scripts/main.py restart -f -p 8080
```

### 4. status - 检查状态

```bash
python scripts/main.py status [options]
```

**选项：**
- `-j, --json`           以JSON格式输出
- `-h, --help`           显示帮助信息

**示例：**
```bash
# 查看状态（文本格式）
python scripts/main.py status

# 查看状态（JSON格式，便于脚本处理）
python scripts/main.py status -j
```

**状态报告内容：**
- 服务运行状态（运行中/未运行）
- 进程PID和资源占用
- 数据库连接状态
- Django配置状态
- 端口监听状态
- 系统资源使用（CPU、内存、磁盘）

### 5. logs - 日志管理

```bash
python scripts/main.py logs <subcommand> [options]
```

**子命令：**
- `rotate`      执行日志轮转
- `clean`       清理旧日志
- `list`        列出日志文件
- `status`      查看日志系统状态

**示例：**
```bash
# 执行日志轮转（保留7个轮转文件）
python scripts/main.py logs rotate -k 7

# 清理30天前的日志
python scripts/main.py logs clean -d 30

# 列出所有日志文件（显示大小）
python scripts/main.py logs list -s

# 查看日志系统状态
python scripts/main.py logs status
```

### 6. backup - 备份管理

```bash
python scripts/main.py backup <subcommand> [options]
```

**子命令：**
- `full`         执行全量备份
- `incremental`  执行增量备份
- `restore`      恢复备份
- `list`         列出备份文件
- `status`       查看备份状态
- `clean`        清理旧备份

**示例：**
```bash
# 创建全量备份
python scripts/main.py backup full

# 创建增量备份
python scripts/main.py backup incremental

# 恢复备份
python scripts/main.py backup restore -f backup_full_20240101_120000.tar.gz

# 列出备份文件
python scripts/main.py backup list -s

# 清理30天前的备份
python scripts/main.py backup clean -d 30
```

### 7. deploy - 一键部署

```bash
python scripts/deploy.py -e <环境> [选项]
```

**选项：**
- `-e, --env {dev,test,prod}`  指定部署环境（必需）
- `-b, --branch <分支>`         指定Git分支（默认：main）
- `--skip-pull`                跳过代码拉取步骤
- `--skip-deps`                跳过依赖安装步骤
- `--skip-migrate`             跳过数据库迁移步骤
- `--skip-start`               跳过服务启动步骤
- `--rollback <备份名>`         回滚到指定备份版本
- `--backup-only`              仅创建备份，不执行部署
- `-v, --verbose`              详细输出模式

**环境配置：**
| 环境 | 名称 | 调试模式 | 数据库 | 默认端口 |
|------|------|---------|--------|---------|
| dev | 开发环境 | 开启 | SQLite | 8000 |
| test | 测试环境 | 关闭 | SQLite | 8001 |
| prod | 生产环境 | 关闭 | MySQL | 80 |

**部署流程：**
1. 检查版本控制状态
2. 从Git拉取代码
3. 创建部署前备份
4. 安装项目依赖
5. 配置环境变量
6. 执行数据库迁移
7. 启动服务

**示例：**
```bash
# 部署到开发环境
python scripts/deploy.py --env dev

# 部署到测试环境，跳过代码拉取
python scripts/deploy.py --env test --skip-pull

# 部署到生产环境（需要确认）
python scripts/deploy.py --env prod

# 仅创建备份
python scripts/deploy.py --env dev --backup-only

# 回滚到指定备份
python scripts/deploy.py --env dev --rollback backup_20240101_120000.tar.gz
```

**特性：**
- ✅ 环境参数配置（开发/测试/生产）
- ✅ 错误处理与自动回滚机制
- ✅ 部署日志记录（logs/deploy_logs/）
- ✅ 版本控制检查
- ✅ 部署前自动备份
- ✅ 生产环境部署确认
- ✅ 详细的执行状态反馈

---

## 目录结构

```
scripts/                 # 运维脚本目录
├── main.py              # 统一入口
├── deploy.py            # 一键部署脚本
├── git_push.py          # Git推送脚本
├── start.py             # 启动脚本
├── stop.py              # 停止脚本
├── restart.py           # 重启脚本
├── status.py            # 状态检查
├── logs.py              # 日志管理
├── backup.py            # 备份脚本
├── utils.py             # 工具模块
└── README.md            # 本说明文档

logs/                    # 日志文件目录
├── operations.log       # 运维操作日志
├── django.log           # Django服务日志
└── testbrain.pid        # 进程PID文件

backups/                 # 备份文件目录
└── full_*.tar.gz        # 全量备份文件
└── inc_*.tar.gz         # 增量备份文件
```

---

## 运行注意事项

### 1. 虚拟环境

建议在项目虚拟环境中运行脚本：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行脚本
python scripts/main.py start -d
```

### 2. 权限要求

- 确保 `logs/` 和 `backups/` 目录具有读写权限
- 部分系统命令（如端口检查）可能需要管理员权限

### 3. 日志轮转

建议定期执行日志轮转，避免日志文件过大：

```bash
# 每日轮转，保留7天
python scripts/main.py logs rotate -k 7
```

### 4. 备份策略

推荐备份策略：
- **每日**：创建增量备份
- **每周**：创建全量备份
- **每月**：清理30天前的旧备份

---

## 故障排除

### 服务启动失败

1. 检查端口是否被占用：
   ```bash
   lsof -i :8000
   ```

2. 检查依赖是否完整：
   ```bash
   pip install -r requirements.txt
   ```

3. 检查数据库配置：
   ```bash
   python manage.py check
   ```

### 备份恢复失败

1. 确保备份文件存在且完整
2. 检查目标目录权限
3. 确保服务已停止后再恢复

### 日志文件过大

1. 执行日志轮转：
   ```bash
   python scripts/main.py logs rotate
   ```

2. 清理旧日志：
   ```bash
   python scripts/main.py logs clean -d 7
   ```

---

## 联系信息

如有问题或建议，请联系开发团队。