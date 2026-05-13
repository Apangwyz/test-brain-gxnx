#!/usr/bin/env python3
"""
项目备份脚本
定期备份项目关键配置文件和数据，支持全量备份和增量备份两种模式
"""

import os
import sys
import argparse
import shutil
import gzip
import json
import glob
from datetime import datetime, timedelta
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status, PROJECT_ROOT, get_backup_dir, get_timestamp

logger = setup_logger('backup_script')

# 需要备份的文件和目录
BACKUP_CONFIG = {
    'directories': [
        'apps',
        'config',
        'static',
        'templates'
    ],
    'files': [
        'manage.py',
        'requirements.txt',
        '.env'
    ],
    'database': {
        'type': 'sqlite',
        'path': 'db.sqlite3'
    }
}

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份TestBrain项目数据')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # full - 全量备份
    full_parser = subparsers.add_parser('full', help='执行全量备份')
    full_parser.add_argument('-o', '--output', help='指定备份输出目录')
    
    # incremental - 增量备份
    inc_parser = subparsers.add_parser('incremental', help='执行增量备份')
    inc_parser.add_argument('-b', '--base', help='指定基准备份目录')
    inc_parser.add_argument('-o', '--output', help='指定备份输出目录')
    
    # restore - 恢复备份
    restore_parser = subparsers.add_parser('restore', help='恢复备份')
    restore_parser.add_argument('-f', '--file', required=True, help='指定备份文件')
    restore_parser.add_argument('-t', '--target', default=PROJECT_ROOT, help='恢复目标目录')
    
    # list - 列出备份文件
    list_parser = subparsers.add_parser('list', help='列出所有备份文件')
    list_parser.add_argument('-s', '--size', action='store_true', help='显示文件大小')
    
    # status - 备份状态
    subparsers.add_parser('status', help='查看备份状态')
    
    # clean - 清理旧备份
    clean_parser = subparsers.add_parser('clean', help='清理旧备份')
    clean_parser.add_argument('-d', '--days', type=int, default=30, help='清理多少天前的备份')
    
    return parser.parse_args()

def create_backup_dir(output_dir=None):
    """创建备份目录"""
    if output_dir:
        backup_dir = output_dir
    else:
        backup_dir = get_backup_dir()
    
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def get_backup_name(prefix='backup'):
    """生成备份文件名"""
    return f"{prefix}_{get_timestamp()}.tar.gz"

def get_backup_info():
    """获取备份信息"""
    return {
        'timestamp': datetime.now().isoformat(),
        'version': '1.0',
        'project': 'TestBrain',
        'config': BACKUP_CONFIG
    }

def backup_database(backup_dir):
    """备份数据库"""
    logger.info("备份数据库...")
    db_path = os.path.join(PROJECT_ROOT, BACKUP_CONFIG['database']['path'])
    
    if os.path.exists(db_path):
        backup_db_path = os.path.join(backup_dir, 'db.sqlite3')
        shutil.copy2(db_path, backup_db_path)
        logger.info(f"数据库备份完成: {backup_db_path}")
        return True
    else:
        logger.warning(f"数据库文件不存在: {db_path}")
        print_status(f"警告: 数据库文件不存在", 'warning')
        return False

def backup_files(backup_dir):
    """备份文件和目录"""
    logger.info("备份文件和目录...")
    
    for dir_name in BACKUP_CONFIG['directories']:
        src_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.exists(src_path):
            dest_path = os.path.join(backup_dir, dir_name)
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            logger.info(f"备份目录: {dir_name}")
    
    for file_name in BACKUP_CONFIG['files']:
        src_path = os.path.join(PROJECT_ROOT, file_name)
        if os.path.exists(src_path):
            dest_path = os.path.join(backup_dir, file_name)
            shutil.copy2(src_path, dest_path)
            logger.info(f"备份文件: {file_name}")

def create_tarball(source_dir, output_path):
    """创建压缩包"""
    logger.info(f"创建压缩包: {output_path}")
    shutil.make_archive(output_path.replace('.tar.gz', ''), 'gztar', source_dir)
    logger.info(f"压缩包创建完成")

def full_backup(output_dir=None):
    """执行全量备份"""
    logger.info("执行全量备份")
    print_status("=== 执行全量备份 ===", 'info')
    
    backup_dir = create_backup_dir(output_dir)
    timestamp = get_timestamp()
    temp_dir = os.path.join(backup_dir, f"full_{timestamp}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 备份数据库
    backup_database(temp_dir)
    
    # 备份文件
    backup_files(temp_dir)
    
    # 写入备份信息
    info_path = os.path.join(temp_dir, 'backup_info.json')
    with open(info_path, 'w') as f:
        info = get_backup_info()
        info['type'] = 'full'
        json.dump(info, f, indent=2)
    
    # 创建压缩包
    backup_name = get_backup_name('full')
    output_path = os.path.join(backup_dir, backup_name)
    create_tarball(temp_dir, output_path)
    
    # 清理临时目录
    shutil.rmtree(temp_dir)
    
    logger.info(f"全量备份完成: {output_path}")
    print_status(f"全量备份完成: {backup_name}", 'success')
    print_status(f"备份大小: {os.path.getsize(output_path) / (1024 * 1024):.2f} MB", 'info')

def incremental_backup(base_backup=None, output_dir=None):
    """执行增量备份"""
    logger.info("执行增量备份")
    print_status("=== 执行增量备份 ===", 'info')
    
    backup_dir = create_backup_dir(output_dir)
    timestamp = get_timestamp()
    temp_dir = os.path.join(backup_dir, f"inc_{timestamp}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 确定基准时间
    if base_backup:
        base_time = os.path.getmtime(base_backup)
    else:
        # 使用最近的全量备份作为基准
        backups = sorted(glob.glob(os.path.join(backup_dir, 'full_*.tar.gz')))
        if backups:
            base_backup = backups[-1]
            base_time = os.path.getmtime(base_backup)
        else:
            logger.error("未找到基准备份，请先执行全量备份")
            print_status("错误: 未找到基准备份，请先执行全量备份", 'error')
            return
    
    logger.info(f"基准备份: {base_backup}")
    print_status(f"基准备份: {os.path.basename(base_backup)}", 'info')
    
    # 查找增量文件
    changed_files = []
    for dir_name in BACKUP_CONFIG['directories']:
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.exists(dir_path):
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.getmtime(file_path) > base_time:
                        rel_path = os.path.relpath(file_path, PROJECT_ROOT)
                        changed_files.append(rel_path)
    
    for file_name in BACKUP_CONFIG['files']:
        file_path = os.path.join(PROJECT_ROOT, file_name)
        if os.path.exists(file_path) and os.path.getmtime(file_path) > base_time:
            changed_files.append(file_name)
    
    if not changed_files:
        logger.info("没有增量文件需要备份")
        print_status("没有增量文件需要备份", 'info')
        shutil.rmtree(temp_dir)
        return
    
    # 备份增量文件
    for rel_path in changed_files:
        src_path = os.path.join(PROJECT_ROOT, rel_path)
        dest_path = os.path.join(temp_dir, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        else:
            shutil.copy2(src_path, dest_path)
        logger.info(f"备份增量文件: {rel_path}")
    
    # 写入备份信息
    info_path = os.path.join(temp_dir, 'backup_info.json')
    with open(info_path, 'w') as f:
        info = get_backup_info()
        info['type'] = 'incremental'
        info['base_backup'] = os.path.basename(base_backup)
        info['changed_files'] = changed_files
        json.dump(info, f, indent=2)
    
    # 创建压缩包
    backup_name = get_backup_name('inc')
    output_path = os.path.join(backup_dir, backup_name)
    create_tarball(temp_dir, output_path)
    
    # 清理临时目录
    shutil.rmtree(temp_dir)
    
    logger.info(f"增量备份完成: {output_path}")
    print_status(f"增量备份完成: {backup_name}", 'success')
    print_status(f"备份大小: {os.path.getsize(output_path) / (1024 * 1024):.2f} MB", 'info')
    print_status(f"增量文件数量: {len(changed_files)}", 'info')

def restore_backup(backup_file, target_dir):
    """恢复备份"""
    logger.info(f"恢复备份: {backup_file}")
    print_status(f"=== 恢复备份: {os.path.basename(backup_file)} ===", 'info')
    
    if not os.path.exists(backup_file):
        logger.error(f"备份文件不存在: {backup_file}")
        print_status(f"错误: 备份文件不存在", 'error')
        return
    
    # 创建临时目录
    temp_dir = os.path.join(target_dir, 'temp_restore')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 解压备份文件
        shutil.unpack_archive(backup_file, temp_dir)
        
        # 复制文件到目标目录
        for item in os.listdir(temp_dir):
            src_path = os.path.join(temp_dir, item)
            dest_path = os.path.join(target_dir, item)
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
        
        logger.info("备份恢复完成")
        print_status("备份恢复完成", 'success')
        
    except Exception as e:
        logger.error(f"恢复失败: {e}")
        print_status(f"错误: 恢复失败 - {e}", 'error')
    finally:
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def list_backups(show_size=False):
    """列出所有备份文件"""
    import glob
    
    backup_dir = get_backup_dir()
    backups = sorted(glob.glob(os.path.join(backup_dir, '*.tar.gz')))
    
    print("=" * 60)
    print("                    备份文件列表")
    print("=" * 60)
    
    if show_size:
        print(f"{'文件名':<40} {'创建时间':<20} {'大小':<10} {'类型'}")
        print("-" * 80)
        for backup in backups:
            mtime = datetime.fromtimestamp(os.path.getmtime(backup))
            size = os.path.getsize(backup)
            size_str = f"{size / 1024:.2f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.2f} MB"
            backup_type = "全量" if backup.startswith('full_') else "增量"
            print(f"{os.path.basename(backup):<40} {mtime.strftime('%Y-%m-%d %H:%M:%S'):<20} {size_str:<10} {backup_type}")
    else:
        print(f"{'文件名':<50} {'创建时间':<20} {'类型'}")
        print("-" * 80)
        for backup in backups:
            mtime = datetime.fromtimestamp(os.path.getmtime(backup))
            backup_type = "全量" if backup.startswith('full_') else "增量"
            print(f"{os.path.basename(backup):<50} {mtime.strftime('%Y-%m-%d %H:%M:%S'):<20} {backup_type}")
    
    print("\n" + "=" * 60)
    print(f"总计: {len(backups)} 个备份文件")

def show_backup_status():
    """显示备份状态"""
    import glob
    
    backup_dir = get_backup_dir()
    backups = glob.glob(os.path.join(backup_dir, '*.tar.gz'))
    
    total_size = sum(os.path.getsize(b) for b in backups)
    full_backups = [b for b in backups if b.startswith('full_')]
    inc_backups = [b for b in backups if b.startswith('inc_')]
    
    print("=" * 60)
    print("                  备份系统状态报告")
    print("=" * 60)
    
    print(f"\n【备份目录】")
    print(f"  路径: {backup_dir}")
    
    print("\n【备份统计】")
    print(f"  备份文件总数: {len(backups)}")
    print(f"  全量备份数量: {len(full_backups)}")
    print(f"  增量备份数量: {len(inc_backups)}")
    print(f"  总大小: {total_size / (1024 * 1024):.2f} MB")
    
    if full_backups:
        last_full = sorted(full_backups)[-1]
        last_full_time = datetime.fromtimestamp(os.path.getmtime(last_full))
        print(f"\n【最近全量备份】")
        print(f"  文件: {os.path.basename(last_full)}")
        print(f"  时间: {last_full_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if inc_backups:
        last_inc = sorted(inc_backups)[-1]
        last_inc_time = datetime.fromtimestamp(os.path.getmtime(last_inc))
        print(f"\n【最近增量备份】")
        print(f"  文件: {os.path.basename(last_inc)}")
        print(f"  时间: {last_inc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n" + "=" * 60)

def clean_old_backups(days=30):
    """清理旧备份"""
    import glob
    
    backup_dir = get_backup_dir()
    backups = glob.glob(os.path.join(backup_dir, '*.tar.gz'))
    
    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_timestamp = cutoff_date.timestamp()
    
    cleaned_count = 0
    for backup in backups:
        mtime = os.path.getmtime(backup)
        if mtime < cutoff_timestamp:
            os.remove(backup)
            cleaned_count += 1
            logger.info(f"清理旧备份: {backup}")
            print_status(f"清理: {os.path.basename(backup)}", 'info')
    
    print_status(f"清理完成，共清理 {cleaned_count} 个备份文件", 'success')

def main():
    """主函数"""
    args = parse_args()
    
    if not args.command:
        print("请指定命令: full, incremental, restore, list, status, clean")
        print("使用 -h 查看帮助")
        sys.exit(1)
    
    logger.info(f"执行备份命令: {args.command}")
    
    if args.command == 'full':
        full_backup(args.output)
    elif args.command == 'incremental':
        incremental_backup(args.base, args.output)
    elif args.command == 'restore':
        restore_backup(args.file, args.target)
    elif args.command == 'list':
        list_backups(args.size)
    elif args.command == 'status':
        show_backup_status()
    elif args.command == 'clean':
        clean_old_backups(args.days)

if __name__ == '__main__':
    main()