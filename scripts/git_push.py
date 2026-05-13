#!/usr/bin/env python3
"""
Git 推送脚本
实现项目代码上传至远程仓库的全流程自动化
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status, PROJECT_ROOT

logger = setup_logger('git_push_script')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Git 推送脚本 - 将项目上传至远程仓库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python git_push.py --remote origin --branch main --message "Initial commit"
  python git_push.py --init --remote https://github.com/user/repo.git
  python git_push.py --force --tag v1.0.0
        """
    )
    
    parser.add_argument(
        '-r', '--remote',
        default='origin',
        help='远程仓库名称或URL (默认: origin)'
    )
    parser.add_argument(
        '-b', '--branch',
        default='main',
        help='分支名称 (默认: main)'
    )
    parser.add_argument(
        '-m', '--message',
        default=f"Auto commit - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        help='提交消息'
    )
    parser.add_argument(
        '--init',
        action='store_true',
        help='初始化Git仓库（如果尚未初始化）'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制推送（使用 --force 标志）'
    )
    parser.add_argument(
        '--tag',
        help='创建并推送标签'
    )
    parser.add_argument(
        '--user-name',
        help='设置Git用户名'
    )
    parser.add_argument(
        '--user-email',
        help='设置Git邮箱'
    )
    parser.add_argument(
        '--add-all',
        action='store_true',
        help='添加所有文件（包括删除的文件）'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出模式'
    )
    
    return parser.parse_args()

def run_git_command(cmd, cwd=None, check_error=True):
    """执行Git命令"""
    if cwd is None:
        cwd = PROJECT_ROOT
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        if check_error and result.returncode != 0:
            logger.error(f"Git命令失败: {' '.join(cmd)}")
            logger.error(f"错误信息: {result.stderr}")
            return False, result.stderr
        
        return True, result.stdout
        
    except Exception as e:
        logger.error(f"执行Git命令时发生异常: {e}")
        return False, str(e)

def check_git_installed():
    """检查Git是否安装"""
    logger.info("检查Git是否安装...")
    try:
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Git版本: {result.stdout.strip()}")
            print_status(f"✅ Git版本: {result.stdout.strip()}", 'success')
            return True
        else:
            logger.error("Git未安装")
            print_status("❌ Git未安装，请先安装Git", 'error')
            return False
    except FileNotFoundError:
        logger.error("Git命令未找到")
        print_status("❌ Git命令未找到，请先安装Git", 'error')
        return False

def check_git_repo():
    """检查是否已为Git仓库"""
    logger.info("检查是否为Git仓库...")
    git_dir = os.path.join(PROJECT_ROOT, '.git')
    is_repo = os.path.exists(git_dir)
    
    if is_repo:
        logger.info("已存在Git仓库")
        print_status("✅ 已存在Git仓库", 'success')
    else:
        logger.info("未找到Git仓库")
        print_status("⚠️ 未找到Git仓库", 'warning')
    
    return is_repo

def init_git_repo():
    """初始化Git仓库"""
    logger.info("初始化Git仓库...")
    print_status("=== 初始化Git仓库 ===", 'info')
    
    success, output = run_git_command(['git', 'init'])
    if success:
        logger.info("Git仓库初始化成功")
        print_status("✅ Git仓库初始化成功", 'success')
        return True
    else:
        logger.error(f"Git仓库初始化失败: {output}")
        print_status(f"❌ Git仓库初始化失败: {output}", 'error')
        return False

def configure_git(user_name=None, user_email=None):
    """配置Git用户信息"""
    logger.info("配置Git用户信息...")
    print_status("=== 配置Git用户信息 ===", 'info')
    
    # 设置用户名
    if user_name:
        success, output = run_git_command(['git', 'config', 'user.name', user_name])
        if success:
            logger.info(f"设置用户名: {user_name}")
            print_status(f"✅ 设置用户名: {user_name}", 'success')
        else:
            print_status(f"❌ 设置用户名失败: {output}", 'error')
            return False
    
    # 设置邮箱
    if user_email:
        success, output = run_git_command(['git', 'config', 'user.email', user_email])
        if success:
            logger.info(f"设置邮箱: {user_email}")
            print_status(f"✅ 设置邮箱: {user_email}", 'success')
        else:
            print_status(f"❌ 设置邮箱失败: {output}", 'error')
            return False
    
    # 检查配置
    success, name = run_git_command(['git', 'config', 'user.name'])
    success, email = run_git_command(['git', 'config', 'user.email'])
    
    if name.strip() and email.strip():
        logger.info(f"当前Git配置 - 用户名: {name.strip()}, 邮箱: {email.strip()}")
        print_status(f"当前配置: {name.strip()} <{email.strip()}>", 'info')
        return True
    else:
        logger.warning("Git用户信息未配置")
        print_status("⚠️ Git用户信息未配置，请使用 --user-name 和 --user-email 参数设置", 'warning')
        return True

def add_files(add_all=False):
    """添加文件到暂存区"""
    logger.info("添加文件到暂存区...")
    print_status("=== 添加文件到暂存区 ===", 'info')
    
    if add_all:
        success, output = run_git_command(['git', 'add', '-A'])
    else:
        success, output = run_git_command(['git', 'add', '.'])
    
    if success:
        logger.info("文件添加成功")
        print_status("✅ 文件添加成功", 'success')
        return True
    else:
        logger.error(f"文件添加失败: {output}")
        print_status(f"❌ 文件添加失败: {output}", 'error')
        return False

def commit_changes(message):
    """提交更改"""
    logger.info("提交更改...")
    print_status("=== 提交更改 ===", 'info')
    
    success, output = run_git_command(['git', 'commit', '-m', message])
    
    if success:
        logger.info(f"提交成功: {message}")
        print_status(f"✅ 提交成功: {message}", 'success')
        return True
    else:
        # 如果没有更改，这是正常情况
        if "nothing to commit" in output:
            logger.info("没有需要提交的更改")
            print_status("ℹ️ 没有需要提交的更改", 'info')
            return True
        else:
            logger.error(f"提交失败: {output}")
            print_status(f"❌ 提交失败: {output}", 'error')
            return False

def add_remote(remote_name, remote_url):
    """添加远程仓库"""
    logger.info(f"添加远程仓库: {remote_name} -> {remote_url}")
    print_status(f"=== 添加远程仓库 ===", 'info')
    
    # 检查是否已存在该远程仓库
    success, output = run_git_command(['git', 'remote', 'get-url', remote_name], check_error=False)
    
    if success:
        # 远程仓库已存在，更新URL
        logger.info(f"远程仓库 {remote_name} 已存在，更新URL")
        print_status(f"⚠️ 远程仓库 {remote_name} 已存在，更新URL", 'warning')
        
        success, output = run_git_command(['git', 'remote', 'set-url', remote_name, remote_url])
        if success:
            logger.info(f"远程仓库URL更新成功: {remote_url}")
            print_status(f"✅ 远程仓库URL更新成功", 'success')
            return True
        else:
            logger.error(f"更新远程仓库URL失败: {output}")
            print_status(f"❌ 更新远程仓库URL失败: {output}", 'error')
            return False
    else:
        # 远程仓库不存在，添加新的
        success, output = run_git_command(['git', 'remote', 'add', remote_name, remote_url])
        if success:
            logger.info(f"远程仓库添加成功: {remote_name} -> {remote_url}")
            print_status(f"✅ 远程仓库添加成功: {remote_name}", 'success')
            return True
        else:
            logger.error(f"添加远程仓库失败: {output}")
            print_status(f"❌ 添加远程仓库失败: {output}", 'error')
            return False

def push_to_remote(remote_name, branch_name, force=False):
    """推送到远程仓库"""
    logger.info(f"推送到远程仓库: {remote_name}/{branch_name}")
    print_status("=== 推送到远程仓库 ===", 'info')
    
    cmd = ['git', 'push', remote_name, branch_name]
    if force:
        cmd.append('--force')
        logger.warning("使用强制推送模式")
        print_status("⚠️ 使用强制推送模式", 'warning')
    
    success, output = run_git_command(cmd)
    
    if success:
        logger.info(f"推送成功: {remote_name}/{branch_name}")
        print_status(f"✅ 推送成功: {remote_name}/{branch_name}", 'success')
        return True
    else:
        logger.error(f"推送失败: {output}")
        print_status(f"❌ 推送失败: {output}", 'error')
        return False

def create_and_push_tag(tag_name):
    """创建并推送标签"""
    logger.info(f"创建标签: {tag_name}")
    print_status("=== 创建标签 ===", 'info')
    
    # 创建标签
    success, output = run_git_command(['git', 'tag', tag_name])
    if not success:
        logger.error(f"创建标签失败: {output}")
        print_status(f"❌ 创建标签失败: {output}", 'error')
        return False
    
    logger.info(f"标签创建成功: {tag_name}")
    print_status(f"✅ 标签创建成功: {tag_name}", 'success')
    
    # 推送标签
    success, output = run_git_command(['git', 'push', 'origin', tag_name])
    if success:
        logger.info(f"标签推送成功: {tag_name}")
        print_status(f"✅ 标签推送成功: {tag_name}", 'success')
        return True
    else:
        logger.error(f"标签推送失败: {output}")
        print_status(f"❌ 标签推送失败: {output}", 'error')
        return False

def get_repo_status():
    """获取仓库状态"""
    logger.info("获取仓库状态...")
    
    # 获取当前分支
    success, branch = run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    if success:
        branch = branch.strip()
    
    # 获取当前提交
    success, commit = run_git_command(['git', 'rev-parse', 'HEAD'])
    if success:
        commit = commit.strip()[:7]
    
    # 获取状态
    success, status = run_git_command(['git', 'status', '--porcelain'])
    has_changes = bool(status.strip())
    
    # 获取远程仓库信息
    success, remotes = run_git_command(['git', 'remote', '-v'])
    
    return {
        'branch': branch,
        'commit': commit,
        'has_changes': has_changes,
        'remotes': remotes.strip()
    }

def main():
    """主函数"""
    args = parse_args()
    
    logger.info("=" * 70)
    logger.info("Git 推送脚本")
    logger.info("=" * 70)
    
    print("\n" + "=" * 70)
    print("           Git 推送脚本")
    print("=" * 70)
    
    # 检查Git是否安装
    if not check_git_installed():
        sys.exit(1)
    
    # 检查/初始化Git仓库
    is_repo = check_git_repo()
    if not is_repo:
        if args.init:
            if not init_git_repo():
                sys.exit(1)
        else:
            print_status("❌ 当前目录不是Git仓库，请使用 --init 参数初始化", 'error')
            sys.exit(1)
    
    # 配置Git用户信息
    if not configure_git(args.user_name, args.user_email):
        sys.exit(1)
    
    # 获取仓库状态
    status = get_repo_status()
    print(f"\n📋 当前仓库状态")
    print(f"  分支: {status['branch']}")
    print(f"  提交: {status['commit']}")
    print(f"  有未提交更改: {'是' if status['has_changes'] else '否'}")
    if status['remotes']:
        print(f"  远程仓库:\n{status['remotes']}")
    
    # 如果URL是完整的远程仓库地址，需要添加远程
    remote_url = args.remote
    if remote_url.startswith('http://') or remote_url.startswith('https://') or remote_url.startswith('git@'):
        # 这是一个URL，需要添加为origin
        if not add_remote('origin', remote_url):
            sys.exit(1)
        remote_name = 'origin'
    else:
        remote_name = remote_url
    
    # 添加文件
    if not add_files(args.add_all):
        sys.exit(1)
    
    # 提交更改
    if not commit_changes(args.message):
        sys.exit(1)
    
    # 推送到远程仓库
    if not push_to_remote(remote_name, args.branch, args.force):
        sys.exit(1)
    
    # 创建并推送标签
    if args.tag:
        if not create_and_push_tag(args.tag):
            sys.exit(1)
    
    # 完成
    logger.info("Git推送完成")
    print("\n" + "=" * 70)
    print_status("✅ Git推送完成!", 'success')
    print(f"  远程仓库: {remote_name}")
    print(f"  分支: {args.branch}")
    if args.tag:
        print(f"  标签: {args.tag}")
    print("=" * 70)

if __name__ == '__main__':
    main()