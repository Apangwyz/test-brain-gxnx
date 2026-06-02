#!/usr/bin/env python3
"""
项目状态检查脚本
实时监控项目运行状态，包括进程存活情况、资源占用率、关键服务健康状态等
"""

import os
import sys
import argparse
import psutil

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    setup_logger, read_pid, is_process_running, print_status, format_bytes,
    PROJECT_ROOT, run_command
)

logger = setup_logger('status_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='检查TestBrain项目运行状态')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('-j', '--json', action='store_true', help='JSON格式输出')
    parser.add_argument('-p', '--port', type=int, default=8000, help='检查指定端口')
    return parser.parse_args()

def get_process_info(pid):
    """获取进程信息"""
    try:
        process = psutil.Process(pid)
        info = {
            'pid': pid,
            'name': process.name(),
            'status': process.status(),
            'cpu_percent': process.cpu_percent(),
            'memory_percent': process.memory_percent(),
            'memory_rss': format_bytes(process.memory_info().rss),
            'memory_vms': format_bytes(process.memory_info().vms),
            'create_time': process.create_time(),
            'cmdline': ' '.join(process.cmdline())
        }
        return info
    except psutil.NoSuchProcess:
        return None

def check_database_connection():
    """检查数据库连接"""
    logger.info("检查数据库连接...")
    try:
        success, stdout, stderr = run_command('python manage.py check --database default')
        if success:
            return True, "数据库连接正常"
        else:
            return False, f"数据库连接失败: {stderr}"
    except Exception as e:
        return False, f"检查数据库失败: {str(e)}"

def check_django_status():
    """检查Django状态"""
    logger.info("检查Django状态...")
    try:
        success, stdout, stderr = run_command('python manage.py check')
        if success:
            return True, "Django配置正常"
        else:
            return False, f"Django配置异常: {stderr}"
    except Exception as e:
        return False, f"检查Django失败: {str(e)}"

def check_port_listening(port=8000):
    """检查端口监听状态"""
    logger.info(f"检查端口 {port} 监听状态...")
    try:
        # 使用系统命令检查端口，避免psutil权限问题
        import subprocess
        result = subprocess.run(
            ['lsof', '-i', f':{port}'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and 'LISTEN' in result.stdout:
            return True, f"端口 {port} 正在监听"
        return False, f"端口 {port} 未监听"
    except Exception as e:
        logger.warning(f"端口检查失败: {e}")
        return False, f"端口检查失败: {e}"

def check_disk_usage():
    """检查磁盘使用情况"""
    logger.info("检查磁盘使用情况...")
    disk = psutil.disk_usage(PROJECT_ROOT)
    usage_percent = (disk.used / disk.total) * 100
    return {
        'total': format_bytes(disk.total),
        'used': format_bytes(disk.used),
        'free': format_bytes(disk.free),
        'percent': round(usage_percent, 2)
    }

def check_memory_usage():
    """检查系统内存使用情况"""
    logger.info("检查系统内存使用情况...")
    memory = psutil.virtual_memory()
    return {
        'total': format_bytes(memory.total),
        'available': format_bytes(memory.available),
        'used': format_bytes(memory.used),
        'percent': memory.percent
    }

def check_cpu_usage():
    """检查CPU使用情况"""
    logger.info("检查CPU使用情况...")
    return {
        'percent': psutil.cpu_percent(interval=1),
        'count': psutil.cpu_count()
    }

def print_status_report(process_info, db_status, django_status, port_status, 
                       disk_usage, memory_usage, cpu_usage, args):
    """打印状态报告"""
    if args.json:
        import json
        report = {
            'service': 'running' if process_info else 'stopped',
            'pid': process_info['pid'] if process_info else None,
            'process': process_info,
            'database': {'status': db_status[0], 'message': db_status[1]},
            'django': {'status': django_status[0], 'message': django_status[1]},
            'port': {'status': port_status[0], 'message': port_status[1]},
            'disk': disk_usage,
            'memory': memory_usage,
            'cpu': cpu_usage
        }
        print(json.dumps(report, indent=2))
        return
    
    print("=" * 70)
    print("                TestBrain 项目状态报告")
    print("=" * 70)
    
    # 服务状态
    print("\n【服务状态】")
    if process_info:
        print_status(f"状态: 运行中 ✓", 'success')
        print(f"  PID: {process_info['pid']}")
        print(f"  进程名: {process_info['name']}")
        print(f"  状态: {process_info['status']}")
        print(f"  CPU占用: {process_info['cpu_percent']}%")
        print(f"  内存占用: {process_info['memory_percent']}% ({process_info['memory_rss']})")
        print(f"  命令行: {process_info['cmdline']}")
    else:
        print_status(f"状态: 未运行 ✗", 'error')
    
    # 数据库状态
    print("\n【数据库状态】")
    if db_status[0]:
        print_status(f"状态: 正常 ✓", 'success')
    else:
        print_status(f"状态: 异常 ✗", 'error')
        print(f"  原因: {db_status[1]}")
    
    # Django状态
    print("\n【Django状态】")
    if django_status[0]:
        print_status(f"状态: 正常 ✓", 'success')
    else:
        print_status(f"状态: 异常 ✗", 'error')
        print(f"  原因: {django_status[1]}")
    
    # 端口状态
    print("\n【端口状态】")
    if port_status[0]:
        print_status(f"状态: 正常 ✓", 'success')
    else:
        print_status(f"状态: 异常 ✗", 'error')
        print(f"  原因: {port_status[1]}")
    
    # 系统资源
    print("\n【系统资源】")
    print(f"  CPU: {cpu_usage['percent']}% ({cpu_usage['count']}核)")
    print(f"  内存: {memory_usage['used']} / {memory_usage['total']} ({memory_usage['percent']}%)")
    print(f"  磁盘: {disk_usage['used']} / {disk_usage['total']} ({disk_usage['percent']}%)")
    
    print("\n" + "=" * 70)
    
    # 综合判断
    all_ok = process_info and db_status[0] and django_status[0] and port_status[0]
    if all_ok:
        print_status("综合状态: 所有服务运行正常 ✓", 'success')
    else:
        print_status("综合状态: 存在异常，请检查 ✗", 'warning')
    
    return all_ok

def main():
    """主函数"""
    args = parse_args()
    
    logger.info("开始检查项目状态...")
    
    # 获取进程信息
    pid = read_pid()
    process_info = None
    if pid and is_process_running(pid):
        process_info = get_process_info(pid)
    
    # 检查数据库
    db_status = check_database_connection()
    
    # 检查Django
    django_status = check_django_status()
    
    # 检查端口
    port_status = check_port_listening(args.port)
    
    # 检查系统资源
    disk_usage = check_disk_usage()
    memory_usage = check_memory_usage()
    cpu_usage = check_cpu_usage()
    
    # 打印报告
    all_ok = print_status_report(
        process_info, db_status, django_status, port_status,
        disk_usage, memory_usage, cpu_usage, args
    )
    
    # 返回退出码
    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    main()