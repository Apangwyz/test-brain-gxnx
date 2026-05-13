#!/usr/bin/env python3
"""
项目启动脚本
实现项目的初始化启动，包含环境变量加载、依赖检查、服务进程启动等功能
"""

import os
import sys
import argparse
import subprocess
import time
import signal

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    setup_logger, load_env_file, check_python_version, check_virtualenv,
    run_command, write_pid, is_process_running, print_status, PROJECT_ROOT,
    read_pid, LOG_DIR
)

logger = setup_logger('start_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='启动TestBrain项目服务')
    parser.add_argument('-e', '--env', help='指定环境变量文件路径')
    parser.add_argument('-p', '--port', type=int, default=8000, help='服务端口')
    parser.add_argument('-d', '--daemon', action='store_true', help='以守护进程模式运行')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    return parser.parse_args()

def check_dependencies():
    """检查项目依赖"""
    logger.info("=== 开始检查依赖 ===")
    
    # 检查Python版本
    success, msg = check_python_version()
    if success:
        logger.info(msg)
        print_status(msg, 'success')
    else:
        logger.error(msg)
        print_status(msg, 'error')
        return False
    
    # 检查虚拟环境
    success, msg = check_virtualenv()
    logger.info(msg)
    if not success:
        print_status(msg, 'warning')
    
    # 检查关键依赖包
    required_packages = ['django', 'pymysql', 'langchain_core']
    for pkg in required_packages:
        try:
            __import__(pkg)
            logger.info(f"依赖包 {pkg} 检查通过")
        except ImportError:
            logger.error(f"依赖包 {pkg} 未安装")
            print_status(f"错误: 依赖包 {pkg} 未安装", 'error')
            return False
    
    logger.info("=== 依赖检查完成 ===")
    return True

def check_migrations():
    """检查并执行数据库迁移"""
    logger.info("=== 检查数据库迁移 ===")
    
    # 检查迁移状态
    success, stdout, stderr = run_command(
        'python manage.py showmigrations --list 2>&1 | grep -E "(\\[ \\]|no migrations)"'
    )
    
    if success and stdout:
        logger.info("发现未应用的迁移，执行迁移")
        print_status("发现未应用的迁移，正在执行...", 'info')
        
        success, stdout, stderr = run_command('python manage.py migrate')
        if success:
            logger.info(f"迁移执行成功: {stdout}")
            print_status("数据库迁移执行成功", 'success')
        else:
            logger.error(f"迁移执行失败: {stderr}")
            print_status(f"数据库迁移失败: {stderr}", 'error')
            return False
    else:
        logger.info("所有迁移已应用")
        print_status("数据库迁移状态正常", 'success')
    
    return True

def start_server(port, daemon=False):
    """启动Django开发服务器"""
    logger.info(f"=== 启动Django服务器，端口: {port} ===")
    
    python_path = sys.executable
    
    if daemon:
        # 守护进程模式
        cmd = (
            f'nohup {python_path} manage.py runserver 0.0.0.0:{port} '
            f'> {os.path.join(LOG_DIR, "django.log")} 2>&1 &'
        )
    else:
        # 前台模式
        cmd = f'{python_path} manage.py runserver 0.0.0.0:{port}'
    
    success, stdout, stderr = run_command(cmd)
    
    if daemon:
        # 守护进程模式需要等待一下再检查
        time.sleep(3)
        # 获取后台进程PID
        success, stdout, stderr = run_command(
            f'ps aux | grep "runserver 0.0.0.0:{port}" | grep -v grep | awk "{{print $2}}"'
        )
        if success and stdout.strip():
            pid = int(stdout.strip())
            write_pid(pid)
            logger.info(f"Django服务器启动成功，PID: {pid}")
            print_status(f"Django服务器启动成功，PID: {pid}", 'success')
            return True
        else:
            logger.error(f"Django服务器启动失败")
            print_status("Django服务器启动失败，请检查日志", 'error')
            return False
    else:
        # 前台模式直接执行
        process = subprocess.Popen(cmd, shell=True, cwd=PROJECT_ROOT)
        write_pid(process.pid)
        logger.info(f"Django服务器启动成功，PID: {process.pid}")
        print_status(f"Django服务器启动成功，PID: {process.pid}", 'success')
        
        # 前台模式需要保持运行
        try:
            process.wait()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭服务器...")
            process.terminate()
            process.wait()
            print_status("服务器已停止", 'info')
        
        return True

def main():
    """主函数"""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("TestBrain 项目启动脚本")
    logger.info("=" * 60)
    
    # 检查是否已在运行
    existing_pid = read_pid()
    if existing_pid and is_process_running(existing_pid):
        logger.error(f"服务已在运行，PID: {existing_pid}")
        print_status(f"错误: 服务已在运行，PID: {existing_pid}", 'error')
        sys.exit(1)
    
    # 加载环境变量
    logger.info("加载环境变量...")
    env_path = args.env if args.env else os.path.join(PROJECT_ROOT, '.env')
    if load_env_file(env_path):
        logger.info(f"环境变量加载成功: {env_path}")
        print_status("环境变量加载成功", 'success')
    else:
        logger.warning(f"环境变量文件不存在: {env_path}")
        print_status("警告: 环境变量文件不存在", 'warning')
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查迁移
    if not check_migrations():
        sys.exit(1)
    
    # 启动服务
    if not start_server(args.port, args.daemon):
        sys.exit(1)
    
    logger.info("启动流程完成")
    print_status("=" * 60, 'info')
    print_status("服务启动成功！", 'success')
    print_status(f"访问地址: http://localhost:{args.port}", 'info')
    print_status("=" * 60, 'info')

if __name__ == '__main__':
    main()