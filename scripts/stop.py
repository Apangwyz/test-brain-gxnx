#!/usr/bin/env python3
"""
项目停止脚本
安全终止项目所有相关进程，确保资源正确释放
支持优雅关闭和强制关闭两种模式
"""

import os
import sys
import argparse
import time
import signal

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    setup_logger, read_pid, remove_pid_file, is_process_running, print_status,
    run_command
)

logger = setup_logger('stop_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='停止TestBrain项目服务')
    parser.add_argument(
        '-f', '--force', 
        action='store_true', 
        help='强制关闭模式（使用kill -9）'
    )
    parser.add_argument(
        '-t', '--timeout', 
        type=int, 
        default=30, 
        help='优雅关闭超时时间（秒），超时后自动强制关闭'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    return parser.parse_args()

def stop_process(pid, force=False, timeout=30):
    """停止进程"""
    logger.info(f"尝试停止进程，PID: {pid}")
    print_status(f"正在停止进程，PID: {pid}", 'info')
    
    if not is_process_running(pid):
        logger.warning(f"进程 {pid} 已不存在")
        print_status(f"进程 {pid} 已不存在", 'warning')
        return True
    
    try:
        if force:
            # 强制关闭
            logger.info(f"强制关闭进程 {pid}")
            os.kill(pid, signal.SIGKILL)
            print_status(f"已发送强制终止信号(SIGKILL)到进程 {pid}", 'warning')
        else:
            # 优雅关闭
            logger.info(f"优雅关闭进程 {pid}")
            os.kill(pid, signal.SIGTERM)
            print_status(f"已发送优雅终止信号(SIGTERM)到进程 {pid}", 'info')
            
            # 等待进程退出
            start_time = time.time()
            while is_process_running(pid):
                if time.time() - start_time > timeout:
                    logger.warning(f"优雅关闭超时({timeout}秒)，执行强制关闭")
                    print_status(f"优雅关闭超时，执行强制关闭", 'warning')
                    os.kill(pid, signal.SIGKILL)
                    break
                time.sleep(1)
        
        # 再次检查
        time.sleep(2)
        if is_process_running(pid):
            logger.error(f"进程 {pid} 无法停止")
            print_status(f"错误: 进程 {pid} 无法停止", 'error')
            return False
        else:
            logger.info(f"进程 {pid} 已成功停止")
            print_status(f"进程 {pid} 已成功停止", 'success')
            return True
            
    except OSError as e:
        logger.error(f"停止进程失败: {e}")
        print_status(f"停止进程失败: {e}", 'error')
        return False

def find_django_processes():
    """查找所有相关的Django进程"""
    success, stdout, stderr = run_command(
        'ps aux | grep -E "(manage.py runserver|gunicorn)" | grep -v grep'
    )
    if success and stdout:
        processes = []
        for line in stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 2:
                processes.append(int(parts[1]))
        return processes
    return []

def main():
    """主函数"""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("TestBrain 项目停止脚本")
    logger.info("=" * 60)
    
    # 从PID文件读取PID
    pid = read_pid()
    
    if pid:
        # 停止主进程
        if not stop_process(pid, args.force, args.timeout):
            sys.exit(1)
        
        # 删除PID文件
        remove_pid_file()
        logger.info("PID文件已删除")
    else:
        # 未找到PID文件，尝试查找所有相关进程
        logger.warning("未找到PID文件，尝试查找Django进程")
        print_status("未找到PID文件，尝试查找相关进程", 'warning')
        
        processes = find_django_processes()
        if processes:
            logger.info(f"找到 {len(processes)} 个相关进程")
            for p in processes:
                stop_process(p, args.force, args.timeout)
        else:
            logger.info("未找到任何运行中的Django进程")
            print_status("未找到任何运行中的Django进程", 'info')
    
    # 清理残留进程
    remaining = find_django_processes()
    if remaining:
        logger.warning(f"发现残留进程: {remaining}")
        print_status(f"警告: 发现残留进程 {remaining}", 'warning')
        if args.force:
            for p in remaining:
                stop_process(p, force=True)
    
    logger.info("停止流程完成")
    print_status("=" * 60, 'info')
    print_status("服务停止成功！", 'success')
    print_status("=" * 60, 'info')

if __name__ == '__main__':
    main()