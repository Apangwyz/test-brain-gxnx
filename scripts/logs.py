#!/usr/bin/env python3
"""
日志管理脚本
实现日志文件的轮转、压缩、清理功能
"""

import os
import sys
import argparse
import glob
import gzip
import shutil
from datetime import datetime, timedelta

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status, LOG_DIR, get_timestamp

logger = setup_logger('logs_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='管理TestBrain项目日志')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # rotate - 日志轮转
    rotate_parser = subparsers.add_parser('rotate', help='执行日志轮转')
    rotate_parser.add_argument('-k', '--keep', type=int, default=7, help='保留轮转文件数量')
    
    # clean - 清理旧日志
    clean_parser = subparsers.add_parser('clean', help='清理旧日志')
    clean_parser.add_argument('-d', '--days', type=int, default=30, help='清理多少天前的日志')
    
    # list - 列出日志文件
    list_parser = subparsers.add_parser('list', help='列出所有日志文件')
    list_parser.add_argument('-s', '--size', action='store_true', help='显示文件大小')
    
    # compress - 压缩日志文件
    compress_parser = subparsers.add_parser('compress', help='压缩日志文件')
    compress_parser.add_argument('-f', '--file', help='指定要压缩的日志文件')
    
    # status - 日志状态
    subparsers.add_parser('status', help='查看日志系统状态')
    
    return parser.parse_args()

def get_log_files():
    """获取所有日志文件"""
    log_pattern = os.path.join(LOG_DIR, '*.log')
    return sorted(glob.glob(log_pattern))

def get_compressed_files():
    """获取所有压缩的日志文件"""
    gz_pattern = os.path.join(LOG_DIR, '*.log.gz')
    return sorted(glob.glob(gz_pattern))

def rotate_logs(keep_count=7):
    """执行日志轮转"""
    logger.info(f"执行日志轮转，保留 {keep_count} 个轮转文件")
    print_status(f"执行日志轮转，保留 {keep_count} 个轮转文件", 'info')
    
    log_files = get_log_files()
    
    for log_file in log_files:
        if os.path.exists(log_file):
            # 获取文件名和扩展名
            base_name = os.path.basename(log_file)
            name, ext = os.path.splitext(base_name)
            
            # 获取轮转文件列表
            rotated_pattern = os.path.join(LOG_DIR, f"{name}.*{ext}")
            rotated_files = sorted(glob.glob(rotated_pattern))
            
            # 删除超出保留数量的旧轮转文件
            if len(rotated_files) >= keep_count:
                files_to_remove = rotated_files[:-keep_count+1]
                for rf in files_to_remove:
                    os.remove(rf)
                    logger.info(f"删除旧轮转文件: {rf}")
                    print_status(f"删除旧轮转文件: {os.path.basename(rf)}", 'info')
            
            # 轮转当前日志文件
            timestamp = get_timestamp()
            rotated_name = f"{name}.{timestamp}{ext}"
            rotated_path = os.path.join(LOG_DIR, rotated_name)
            
            # 重命名当前日志文件
            shutil.move(log_file, rotated_path)
            logger.info(f"日志轮转: {base_name} -> {rotated_name}")
            print_status(f"日志轮转: {base_name} -> {rotated_name}", 'success')
            
            # 创建新的空日志文件
            with open(log_file, 'w') as f:
                pass
            logger.info(f"创建新日志文件: {base_name}")
    
    print_status("日志轮转完成", 'success')

def clean_old_logs(days=30):
    """清理旧日志文件"""
    logger.info(f"清理 {days} 天前的日志文件")
    print_status(f"清理 {days} 天前的日志文件", 'info')
    
    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_timestamp = cutoff_date.timestamp()
    
    all_files = get_log_files() + get_compressed_files()
    cleaned_count = 0
    
    for log_file in all_files:
        try:
            mtime = os.path.getmtime(log_file)
            if mtime < cutoff_timestamp:
                os.remove(log_file)
                cleaned_count += 1
                logger.info(f"清理旧日志: {log_file}")
                print_status(f"清理: {os.path.basename(log_file)}", 'info')
        except Exception as e:
            logger.error(f"清理日志失败 {log_file}: {e}")
            print_status(f"清理失败 {os.path.basename(log_file)}: {e}", 'error')
    
    print_status(f"清理完成，共清理 {cleaned_count} 个文件", 'success')

def list_log_files(show_size=False):
    """列出所有日志文件"""
    logger.info("列出日志文件")
    
    print("=" * 60)
    print("                    日志文件列表")
    print("=" * 60)
    
    log_files = get_log_files()
    gz_files = get_compressed_files()
    
    all_files = []
    for f in log_files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        size = os.path.getsize(f)
        all_files.append((f, mtime, size, False))
    
    for f in gz_files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        size = os.path.getsize(f)
        all_files.append((f, mtime, size, True))
    
    # 按修改时间排序
    all_files.sort(key=lambda x: x[1], reverse=True)
    
    if show_size:
        print(f"{'文件名':<40} {'修改时间':<20} {'大小':<10} {'类型'}")
        print("-" * 80)
        for f, mtime, size, is_compressed in all_files:
            size_str = f"{size / 1024:.2f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.2f} MB"
            file_type = "[压缩]" if is_compressed else "[日志]"
            print(f"{os.path.basename(f):<40} {mtime.strftime('%Y-%m-%d %H:%M:%S'):<20} {size_str:<10} {file_type}")
    else:
        print(f"{'文件名':<50} {'修改时间':<20} {'类型'}")
        print("-" * 80)
        for f, mtime, _, is_compressed in all_files:
            file_type = "[压缩]" if is_compressed else "[日志]"
            print(f"{os.path.basename(f):<50} {mtime.strftime('%Y-%m-%d %H:%M:%S'):<20} {file_type}")
    
    print("\n" + "=" * 60)
    print(f"总计: {len(log_files)} 个日志文件, {len(gz_files)} 个压缩文件")

def compress_log_file(file_path=None):
    """压缩日志文件"""
    if file_path:
        # 压缩指定文件
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            print_status(f"错误: 文件不存在 {file_path}", 'error')
            return
        
        gz_path = f"{file_path}.gz"
        if os.path.exists(gz_path):
            logger.error(f"压缩文件已存在: {gz_path}")
            print_status(f"错误: 压缩文件已存在", 'error')
            return
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        os.remove(file_path)
        logger.info(f"压缩完成: {file_path} -> {gz_path}")
        print_status(f"压缩完成: {os.path.basename(file_path)}", 'success')
    else:
        # 压缩所有未压缩的日志文件
        log_files = get_log_files()
        for log_file in log_files:
            gz_path = f"{log_file}.gz"
            if not os.path.exists(gz_path):
                with open(log_file, 'rb') as f_in:
                    with gzip.open(gz_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(log_file)
                logger.info(f"压缩完成: {log_file}")
                print_status(f"压缩: {os.path.basename(log_file)}", 'info')
        
        print_status("批量压缩完成", 'success')

def show_log_status():
    """显示日志系统状态"""
    logger.info("查看日志系统状态")
    
    print("=" * 60)
    print("                  日志系统状态报告")
    print("=" * 60)
    
    log_files = get_log_files()
    gz_files = get_compressed_files()
    
    total_size = 0
    for f in log_files + gz_files:
        total_size += os.path.getsize(f)
    
    print(f"\n【日志目录】")
    print(f"  路径: {LOG_DIR}")
    
    print("\n【文件统计】")
    print(f"  日志文件数量: {len(log_files)}")
    print(f"  压缩文件数量: {len(gz_files)}")
    print(f"  总大小: {total_size / (1024 * 1024):.2f} MB")
    
    # 最大的几个文件
    print("\n【最大文件】")
    files_with_size = []
    for f in log_files + gz_files:
        files_with_size.append((f, os.path.getsize(f)))
    
    files_with_size.sort(key=lambda x: x[1], reverse=True)
    for f, size in files_with_size[:5]:
        size_str = f"{size / 1024:.2f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.2f} MB"
        print(f"  {os.path.basename(f):<30} {size_str}")
    
    print("\n" + "=" * 60)

def main():
    """主函数"""
    args = parse_args()
    
    if not args.command:
        print("请指定命令: rotate, clean, list, compress, status")
        print("使用 -h 查看帮助")
        sys.exit(1)
    
    logger.info(f"执行日志管理命令: {args.command}")
    
    if args.command == 'rotate':
        rotate_logs(args.keep)
    elif args.command == 'clean':
        clean_old_logs(args.days)
    elif args.command == 'list':
        list_log_files(args.size)
    elif args.command == 'compress':
        compress_log_file(args.file)
    elif args.command == 'status':
        show_log_status()

if __name__ == '__main__':
    main()