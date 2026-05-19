#!/usr/bin/env python3
"""
项目停止脚本
安全终止项目所有相关进程，确保资源正确释放
支持优雅关闭和强制关闭两种模式
增加完善的端口清理机制，确保跨平台兼容性
"""

import os
import sys
import argparse
import time
import signal
import platform

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    setup_logger, read_pid, remove_pid_file, is_process_running, print_status,
    run_command
)

logger = setup_logger('stop_script')

# 定义默认端口
DEFAULT_PORTS = [8000, 8080]

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
    parser.add_argument(
        '-p', '--ports', 
        type=str, 
        default='8000,8080',
        help='要检查和释放的端口列表，逗号分隔（默认: 8000,8080）'
    )
    return parser.parse_args()

def get_os_type():
    """获取操作系统类型"""
    os_name = platform.system().lower()
    if os_name == 'darwin':
        return 'macos'
    elif os_name == 'linux':
        return 'linux'
    elif os_name == 'windows':
        return 'windows'
    else:
        return 'unknown'

def get_processes_using_port(port):
    """
    获取占用指定端口的进程列表
    支持跨平台：macOS/Linux使用lsof，Windows使用netstat
    """
    os_type = get_os_type()
    processes = []
    
    if os_type in ['macos', 'linux']:
        # macOS/Linux 使用 lsof
        success, stdout, stderr = run_command(
            f'lsof -i :{port} -P -n -t 2>/dev/null'
        )
        if success and stdout.strip():
            for pid_str in stdout.strip().split('\n'):
                pid_str = pid_str.strip()
                if pid_str.isdigit():
                    processes.append(int(pid_str))
    
    elif os_type == 'windows':
        # Windows 使用 netstat
        success, stdout, stderr = run_command(
            f'netstat -ano | findstr :{port}'
        )
        if success and stdout.strip():
            for line in stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 5:
                    pid_str = parts[-1]
                    if pid_str.isdigit():
                        processes.append(int(pid_str))
    
    logger.info(f"端口 {port} 被进程占用: {processes}")
    return processes

def release_port(port, force=False):
    """
    释放指定端口，停止占用该端口的所有进程
    """
    logger.info(f"=== 开始释放端口 {port} ===")
    print_status(f"检查端口 {port} 占用情况...", 'info')
    
    processes = get_processes_using_port(port)
    
    if not processes:
        logger.info(f"端口 {port} 未被占用")
        print_status(f"端口 {port} 未被占用", 'success')
        return True
    
    logger.warning(f"端口 {port} 被 {len(processes)} 个进程占用: {processes}")
    print_status(f"端口 {port} 被 {len(processes)} 个进程占用", 'warning')
    
    success_count = 0
    for pid in processes:
        try:
            if force:
                logger.info(f"强制终止占用端口 {port} 的进程 {pid}")
                os.kill(pid, signal.SIGKILL)
            else:
                logger.info(f"优雅终止占用端口 {port} 的进程 {pid}")
                os.kill(pid, signal.SIGTERM)
                
            # 等待进程结束
            time.sleep(1)
            if not is_process_running(pid):
                logger.info(f"进程 {pid} 已停止，端口 {port} 已释放")
                print_status(f"进程 {pid} 已停止", 'success')
                success_count += 1
            else:
                logger.warning(f"进程 {pid} 停止失败，尝试强制终止")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                if not is_process_running(pid):
                    logger.info(f"进程 {pid} 强制终止成功")
                    print_status(f"进程 {pid} 强制终止成功", 'warning')
                    success_count += 1
                else:
                    logger.error(f"无法终止进程 {pid}")
                    print_status(f"无法终止进程 {pid}", 'error')
                    
        except OSError as e:
            logger.error(f"终止进程 {pid} 失败: {e}")
            print_status(f"终止进程 {pid} 失败: {e}", 'error')
    
    # 验证端口是否已释放
    time.sleep(2)
    remaining = get_processes_using_port(port)
    if remaining:
        logger.error(f"端口 {port} 仍被占用: {remaining}")
        print_status(f"警告: 端口 {port} 仍被部分进程占用", 'warning')
        return False
    else:
        logger.info(f"端口 {port} 已成功释放")
        print_status(f"端口 {port} 已成功释放", 'success')
        return True

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
    logger.info(f"操作系统: {get_os_type().upper()}")
    logger.info("=" * 60)
    
    # 解析端口列表
    ports = []
    try:
        ports = [int(p.strip()) for p in args.ports.split(',') if p.strip().isdigit()]
    except ValueError:
        logger.warning(f"无效的端口列表: {args.ports}，使用默认端口")
        ports = DEFAULT_PORTS
    
    logger.info(f"待检查端口列表: {ports}")
    
    # 从PID文件读取PID
    pid = read_pid()
    
    if pid:
        # 停止主进程
        logger.info(f"从PID文件读取到PID: {pid}")
        if not stop_process(pid, args.force, args.timeout):
            # 即使主进程停止失败，继续清理其他进程和端口
            logger.warning("主进程停止失败，继续清理其他资源")
        
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
        for p in remaining:
            stop_process(p, force=True)
    
    # 端口清理机制
    logger.info("=" * 60)
    logger.info("开始端口清理流程")
    logger.info("=" * 60)
    
    all_ports_released = True
    for port in ports:
        if not release_port(port, args.force):
            all_ports_released = False
    
    # 最终验证
    logger.info("=" * 60)
    logger.info("执行最终验证")
    logger.info("=" * 60)
    
    final_remaining = find_django_processes()
    if final_remaining:
        logger.error(f"最终验证失败: 仍有残留进程 {final_remaining}")
        print_status(f"错误: 仍有残留进程 {final_remaining}", 'error')
    
    # 检查所有端口状态
    port_status = []
    for port in ports:
        procs = get_processes_using_port(port)
        if procs:
            port_status.append(f"端口 {port}: 被占用")
            logger.warning(f"端口 {port} 仍被占用")
        else:
            port_status.append(f"端口 {port}: 已释放")
            logger.info(f"端口 {port} 已释放")
    
    # 输出最终状态
    logger.info("=" * 60)
    logger.info("停止流程完成")
    logger.info("=" * 60)
    
    print_status("=" * 60, 'info')
    print_status("服务停止完成！", 'success' if all_ports_released else 'warning')
    if port_status:
        print_status("端口状态:", 'info')
        for status in port_status:
            print_status(f"  - {status}", 'info')
    print_status("=" * 60, 'info')

if __name__ == '__main__':
    main()
