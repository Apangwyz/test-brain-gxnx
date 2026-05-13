#!/usr/bin/env python3
"""
TestBrain 运维脚本主入口
统一管理所有运维功能
"""

import os
import sys
import argparse

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status

logger = setup_logger('main_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='TestBrain 运维管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用命令:
  start      启动项目服务
  stop       停止项目服务
  restart    重启项目服务
  status     检查服务状态
  logs       日志管理
  backup     备份管理

使用示例:
  python main.py start -p 8000 -d
  python main.py stop -f
  python main.py restart
  python main.py status
  python main.py logs rotate -k 7
  python main.py backup full
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='运维命令')
    
    # start 命令
    start_parser = subparsers.add_parser('start', help='启动服务')
    start_parser.add_argument('-e', '--env', help='环境变量文件')
    start_parser.add_argument('-p', '--port', type=int, default=8000, help='端口')
    start_parser.add_argument('-d', '--daemon', action='store_true', help='守护进程模式')
    
    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='停止服务')
    stop_parser.add_argument('-f', '--force', action='store_true', help='强制关闭')
    stop_parser.add_argument('-t', '--timeout', type=int, default=30, help='超时时间')
    
    # restart 命令
    restart_parser = subparsers.add_parser('restart', help='重启服务')
    restart_parser.add_argument('-e', '--env', help='环境变量文件')
    restart_parser.add_argument('-p', '--port', type=int, default=8000, help='端口')
    restart_parser.add_argument('-f', '--force', action='store_true', help='强制重启')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='检查状态')
    status_parser.add_argument('-j', '--json', action='store_true', help='JSON输出')
    
    # logs 命令
    logs_parser = subparsers.add_parser('logs', help='日志管理')
    logs_sub = logs_parser.add_subparsers(dest='logs_cmd')
    logs_sub.add_parser('rotate', help='日志轮转')
    logs_sub.add_parser('clean', help='清理旧日志')
    logs_sub.add_parser('list', help='列出日志文件')
    logs_sub.add_parser('status', help='日志状态')
    
    # backup 命令
    backup_parser = subparsers.add_parser('backup', help='备份管理')
    backup_sub = backup_parser.add_subparsers(dest='backup_cmd')
    backup_sub.add_parser('full', help='全量备份')
    backup_sub.add_parser('incremental', help='增量备份')
    backup_sub.add_parser('list', help='列出备份')
    backup_sub.add_parser('status', help='备份状态')
    
    return parser.parse_args()

def run_script(script_name, args_list):
    """运行指定脚本"""
    script_path = os.path.join(os.path.dirname(__file__), f"{script_name}.py")
    cmd = ['python', script_path] + args_list
    
    print_status(f"执行: {' '.join(cmd)}", 'info')
    exit_code = os.system(' '.join(cmd))
    return exit_code == 0

def main():
    """主函数"""
    args = parse_args()
    
    if not args.command:
        print("请指定运维命令")
        print("使用 -h 查看帮助")
        sys.exit(1)
    
    logger.info(f"执行运维命令: {args.command}")
    
    try:
        if args.command == 'start':
            args_list = []
            if args.env:
                args_list.extend(['-e', args.env])
            if args.port != 8000:
                args_list.extend(['-p', str(args.port)])
            if args.daemon:
                args_list.append('-d')
            run_script('start', args_list)
        
        elif args.command == 'stop':
            args_list = []
            if args.force:
                args_list.append('-f')
            if args.timeout != 30:
                args_list.extend(['-t', str(args.timeout)])
            run_script('stop', args_list)
        
        elif args.command == 'restart':
            args_list = []
            if args.env:
                args_list.extend(['-e', args.env])
            if args.port != 8000:
                args_list.extend(['-p', str(args.port)])
            if args.force:
                args_list.append('-f')
            run_script('restart', args_list)
        
        elif args.command == 'status':
            args_list = []
            if args.json:
                args_list.append('-j')
            run_script('status', args_list)
        
        elif args.command == 'logs':
            args_list = []
            if args.logs_cmd:
                args_list.append(args.logs_cmd)
            run_script('logs', args_list)
        
        elif args.command == 'backup':
            args_list = []
            if args.backup_cmd:
                args_list.append(args.backup_cmd)
            run_script('backup', args_list)
        
        else:
            print(f"未知命令: {args.command}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"执行命令失败: {e}")
        print_status(f"错误: {e}", 'error')
        sys.exit(1)

if __name__ == '__main__':
    main()