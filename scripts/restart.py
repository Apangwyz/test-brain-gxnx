#!/usr/bin/env python3
"""
项目重启脚本
整合停止与启动功能，实现项目服务的无缝重启
"""

import os
import sys
import argparse
import time
import subprocess

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status, read_pid, is_process_running

logger = setup_logger('restart_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='重启TestBrain项目服务')
    parser.add_argument('-e', '--env', help='指定环境变量文件路径')
    parser.add_argument('-p', '--port', type=int, default=8000, help='服务端口')
    parser.add_argument(
        '-f', '--force', 
        action='store_true', 
        help='强制重启（使用kill -9停止）'
    )
    parser.add_argument(
        '-w', '--wait', 
        type=int, 
        default=5, 
        help='停止后等待秒数再启动'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("TestBrain 项目重启脚本")
    logger.info("=" * 60)
    
    # 获取当前运行状态
    current_pid = read_pid()
    was_running = current_pid and is_process_running(current_pid)
    
    if was_running:
        logger.info(f"当前服务正在运行，PID: {current_pid}")
        print_status(f"当前服务正在运行，PID: {current_pid}", 'info')
    else:
        logger.info("当前服务未运行，将直接启动")
        print_status("当前服务未运行，将直接启动", 'info')
    
    # 停止服务
    logger.info("=== 停止服务 ===")
    print_status("=== 停止服务 ===", 'info')
    
    stop_args = ['-t', '30']
    if args.force:
        stop_args.append('-f')
    
    stop_script = os.path.join(os.path.dirname(__file__), 'stop.py')
    result = subprocess.run([sys.executable, stop_script] + stop_args, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    exit_code = result.returncode
    
    if exit_code != 0 and was_running:
        logger.error("服务停止失败")
        print_status("错误: 服务停止失败", 'error')
        sys.exit(1)
    
    # 等待指定时间
    if args.wait > 0 and was_running:
        logger.info(f"等待 {args.wait} 秒...")
        print_status(f"等待 {args.wait} 秒...", 'info')
        time.sleep(args.wait)
    
    # 启动服务
    logger.info("=== 启动服务 ===")
    print_status("=== 启动服务 ===", 'info')
    
    start_args = ['-p', str(args.port), '-d']
    if args.env:
        start_args.extend(['-e', args.env])
    
    start_script = os.path.join(os.path.dirname(__file__), 'start.py')
    result = subprocess.run([sys.executable, start_script] + start_args, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    exit_code = result.returncode
    
    if exit_code != 0:
        logger.error("服务启动失败")
        print_status("错误: 服务启动失败", 'error')
        sys.exit(1)
    
    logger.info("重启流程完成")
    print_status("=" * 60, 'info')
    print_status("服务重启成功！", 'success')
    print_status(f"访问地址: http://localhost:{args.port}", 'info')
    print_status("=" * 60, 'info')

if __name__ == '__main__':
    main()