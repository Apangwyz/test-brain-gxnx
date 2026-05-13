#!/usr/bin/env python3
"""
公共工具模块 - 提供运维脚本共用的功能
"""

import os
import sys
import subprocess
import time
import logging
import argparse
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name, log_file='operations.log'):
    """配置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 文件处理器
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file))
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def load_env_file(env_path=None):
    """加载环境变量文件"""
    if env_path is None:
        env_path = os.path.join(PROJECT_ROOT, '.env')
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        return True
    return False

def check_python_version(min_version=(3, 12)):
    """检查Python版本"""
    current_version = sys.version_info[:2]
    if current_version < min_version:
        return False, f"Python版本要求 {min_version[0]}.{min_version[1]}+, 当前版本 {current_version[0]}.{current_version[1]}"
    return True, f"Python版本检查通过: {current_version[0]}.{current_version[1]}"

def check_virtualenv():
    """检查是否在虚拟环境中运行"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return True, "当前在虚拟环境中运行"
    return False, "警告: 未在虚拟环境中运行"

def run_command(cmd, cwd=None, shell=True):
    """执行系统命令"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            shell=shell,
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def get_pid_file_path():
    """获取PID文件路径"""
    return os.path.join(LOG_DIR, 'testbrain.pid')

def read_pid():
    """读取PID文件"""
    pid_file = get_pid_file_path()
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            return int(f.read().strip())
    return None

def write_pid(pid):
    """写入PID文件"""
    pid_file = get_pid_file_path()
    with open(pid_file, 'w') as f:
        f.write(str(pid))

def remove_pid_file():
    """删除PID文件"""
    pid_file = get_pid_file_path()
    if os.path.exists(pid_file):
        os.remove(pid_file)

def is_process_running(pid):
    """检查进程是否运行"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def print_status(message, status='info'):
    """打印状态信息"""
    status_colors = {
        'success': '\033[92m',  # 绿色
        'error': '\033[91m',    # 红色
        'warning': '\033[93m',  # 黄色
        'info': '\033[94m'      # 蓝色
    }
    reset = '\033[0m'
    color = status_colors.get(status, status_colors['info'])
    print(f"{color}{message}{reset}")

def format_bytes(bytes_size):
    """格式化字节数为可读格式"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 ** 2:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 ** 3:
        return f"{bytes_size / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes_size / (1024 ** 3):.2f} GB"

def get_timestamp():
    """获取时间戳字符串"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def get_backup_dir():
    """获取备份目录"""
    backup_dir = os.path.join(PROJECT_ROOT, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir