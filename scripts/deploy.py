#!/usr/bin/env python3
"""
TestBrain 一键部署脚本
实现从代码拉取、依赖安装、构建打包、环境配置到服务部署的全流程自动化
"""

import os
import sys
import argparse
import subprocess
import shutil
import json
from datetime import datetime
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, print_status, PROJECT_ROOT, get_timestamp, format_bytes

logger = setup_logger('deploy_script')

# 部署配置
DEPLOY_CONFIG = {
    'environments': {
        'dev': {
            'name': '开发环境',
            'debug': True,
            'database': 'sqlite',
            'port': 8000,
            'settings_file': 'config/settings.py'
        },
        'test': {
            'name': '测试环境',
            'debug': False,
            'database': 'sqlite',
            'port': 8001,
            'settings_file': 'config/settings.py'
        },
        'prod': {
            'name': '生产环境',
            'debug': False,
            'database': 'mysql',
            'port': 80,
            'settings_file': 'config/settings.py'
        }
    },
    'required_packages': [
        'django>=6.0',
        'pymysql',
        'psutil',
        'langchain_core',
        'sentence_transformers'
    ],
    'backup_dir': 'backups/deploy_backups',
    'log_dir': 'logs/deploy_logs'
}

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='TestBrain 一键部署脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
部署流程:
  1. 代码拉取 → 2. 依赖安装 → 3. 环境配置 → 4. 数据库迁移 → 5. 服务启动

环境配置:
  dev   - 开发环境 (调试模式, SQLite)
  test  - 测试环境 (生产模式, SQLite)
  prod  - 生产环境 (生产模式, MySQL)

使用示例:
  python deploy.py --env dev --branch main
  python deploy.py --env prod --skip-pull
  python deploy.py --env test --rollback backup_20240101_120000
        """
    )
    
    parser.add_argument(
        '-e', '--env', 
        required=True,
        choices=['dev', 'test', 'prod'],
        help='部署环境: dev(开发), test(测试), prod(生产)'
    )
    parser.add_argument(
        '-b', '--branch', 
        default='main',
        help='Git分支名称 (默认: main)'
    )
    parser.add_argument(
        '--skip-pull', 
        action='store_true',
        help='跳过代码拉取步骤'
    )
    parser.add_argument(
        '--skip-deps', 
        action='store_true',
        help='跳过依赖安装步骤'
    )
    parser.add_argument(
        '--skip-migrate', 
        action='store_true',
        help='跳过数据库迁移步骤'
    )
    parser.add_argument(
        '--skip-start', 
        action='store_true',
        help='跳过服务启动步骤'
    )
    parser.add_argument(
        '--rollback', 
        help='回滚到指定备份版本'
    )
    parser.add_argument(
        '--backup-only', 
        action='store_true',
        help='仅创建备份，不执行部署'
    )
    parser.add_argument(
        '-v', '--verbose', 
        action='store_true',
        help='详细输出模式'
    )
    
    return parser.parse_args()

def create_deploy_backup(env):
    """创建部署前备份"""
    logger.info("创建部署前备份...")
    backup_dir = os.path.join(PROJECT_ROOT, DEPLOY_CONFIG['backup_dir'], env)
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_name = f"backup_{get_timestamp()}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # 备份关键文件和目录
    items_to_backup = ['apps', 'config', 'manage.py', 'requirements.txt']
    
    for item in items_to_backup:
        src = os.path.join(PROJECT_ROOT, item)
        dst = os.path.join(backup_path, item)
        if os.path.exists(src):
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
    
    # 创建备份信息文件
    backup_info = {
        'timestamp': datetime.now().isoformat(),
        'environment': env,
        'backup_name': backup_name,
        'items': items_to_backup
    }
    with open(os.path.join(backup_path, 'backup_info.json'), 'w') as f:
        json.dump(backup_info, f, indent=2)
    
    # 创建压缩包
    shutil.make_archive(backup_path, 'gztar', backup_path)
    shutil.rmtree(backup_path)
    
    logger.info(f"备份创建完成: {backup_path}.tar.gz")
    print_status(f"✅ 备份创建完成: {backup_name}.tar.gz", 'success')
    
    return f"{backup_name}.tar.gz"

def rollback_deploy(env, backup_name):
    """回滚到指定备份"""
    logger.info(f"执行回滚操作，恢复备份: {backup_name}")
    print_status(f"=== 执行回滚操作 ===", 'warning')
    
    backup_dir = os.path.join(PROJECT_ROOT, DEPLOY_CONFIG['backup_dir'], env)
    backup_path = os.path.join(backup_dir, backup_name)
    
    if not os.path.exists(backup_path):
        logger.error(f"备份文件不存在: {backup_path}")
        print_status(f"❌ 备份文件不存在: {backup_name}", 'error')
        return False
    
    # 停止服务
    print_status("🔹 停止当前服务...", 'info')
    stop_script = os.path.join(os.path.dirname(__file__), 'stop.py')
    subprocess.run(['python', stop_script, '-f'], capture_output=True)
    
    # 解压备份
    print_status("🔹 解压备份文件...", 'info')
    temp_dir = os.path.join(PROJECT_ROOT, 'temp_rollback')
    shutil.unpack_archive(backup_path, temp_dir)
    
    # 恢复文件
    print_status("🔹 恢复项目文件...", 'info')
    for item in os.listdir(temp_dir):
        src = os.path.join(temp_dir, item)
        dst = os.path.join(PROJECT_ROOT, item)
        if os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
        shutil.move(src, dst)
    
    # 清理临时目录
    shutil.rmtree(temp_dir)
    
    logger.info("回滚完成")
    print_status("✅ 回滚操作完成", 'success')
    return True

def pull_code(branch='main'):
    """从Git拉取代码"""
    logger.info(f"拉取代码，分支: {branch}")
    print_status(f"=== 拉取代码 (分支: {branch}) ===", 'info')
    
    try:
        # 检查是否有未提交的更改
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            logger.warning("检测到未提交的更改")
            print_status("⚠️ 检测到未提交的更改，已自动 stash", 'warning')
            subprocess.run(['git', 'stash'], cwd=PROJECT_ROOT, capture_output=True)
        
        # 拉取代码
        result = subprocess.run(
            ['git', 'pull', 'origin', branch],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"代码拉取成功: {result.stdout}")
            print_status("✅ 代码拉取成功", 'success')
            return True
        else:
            logger.error(f"代码拉取失败: {result.stderr}")
            print_status(f"❌ 代码拉取失败: {result.stderr}", 'error')
            return False
            
    except Exception as e:
        logger.error(f"拉取代码时发生错误: {e}")
        print_status(f"❌ 拉取代码时发生错误: {e}", 'error')
        return False

def install_dependencies():
    """安装项目依赖"""
    logger.info("安装项目依赖")
    print_status("=== 安装项目依赖 ===", 'info')
    
    try:
        # 检查虚拟环境
        if not hasattr(sys, 'real_prefix') and (not hasattr(sys, 'base_prefix') or sys.base_prefix == sys.prefix):
            logger.warning("未在虚拟环境中运行")
            print_status("⚠️ 建议在虚拟环境中运行部署脚本", 'warning')
        
        # 安装依赖
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--timeout=120'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("依赖安装成功")
            print_status("✅ 依赖安装成功", 'success')
            return True
        else:
            logger.error(f"依赖安装失败: {result.stderr}")
            print_status(f"❌ 依赖安装失败: {result.stderr}", 'error')
            return False
            
    except Exception as e:
        logger.error(f"安装依赖时发生错误: {e}")
        print_status(f"❌ 安装依赖时发生错误: {e}", 'error')
        return False

def configure_environment(env):
    """配置部署环境"""
    logger.info(f"配置环境: {env}")
    config = DEPLOY_CONFIG['environments'].get(env)
    print_status(f"=== 配置环境 ({config['name']}) ===", 'info')
    
    try:
        # 创建必要的目录
        dirs_to_create = ['logs', 'backups', 'media', 'static']
        for d in dirs_to_create:
            os.makedirs(os.path.join(PROJECT_ROOT, d), exist_ok=True)
        
        # 设置环境变量
        env_file = os.path.join(PROJECT_ROOT, '.env')
        env_config = {
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'ENVIRONMENT': env,
            'DEBUG': str(config['debug']),
            'PORT': str(config['port'])
        }
        
        with open(env_file, 'w') as f:
            for key, value in env_config.items():
                f.write(f"{key}={value}\n")
        
        logger.info(f"环境配置完成: {env}")
        print_status(f"✅ 环境配置完成 ({config['name']})", 'success')
        return True
        
    except Exception as e:
        logger.error(f"配置环境时发生错误: {e}")
        print_status(f"❌ 配置环境时发生错误: {e}", 'error')
        return False

def run_migrations():
    """执行数据库迁移"""
    logger.info("执行数据库迁移")
    print_status("=== 执行数据库迁移 ===", 'info')
    
    try:
        # 先检查迁移状态
        result = subprocess.run(
            [sys.executable, 'manage.py', 'showmigrations'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"检查迁移状态失败: {result.stderr}")
            print_status(f"❌ 检查迁移状态失败: {result.stderr}", 'error')
            return False
        
        # 执行迁移
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate', '--noinput'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("数据库迁移成功")
            print_status("✅ 数据库迁移成功", 'success')
            return True
        else:
            logger.error(f"数据库迁移失败: {result.stderr}")
            print_status(f"❌ 数据库迁移失败: {result.stderr}", 'error')
            return False
            
    except Exception as e:
        logger.error(f"执行迁移时发生错误: {e}")
        print_status(f"❌ 执行迁移时发生错误: {e}", 'error')
        return False

def start_service(env):
    """启动服务"""
    logger.info(f"启动服务，环境: {env}")
    config = DEPLOY_CONFIG['environments'].get(env)
    print_status(f"=== 启动服务 ({config['name']}) ===", 'info')
    
    try:
        # 停止现有服务
        stop_script = os.path.join(os.path.dirname(__file__), 'stop.py')
        subprocess.run([sys.executable, stop_script, '-f'], capture_output=True)
        
        # 启动服务
        start_script = os.path.join(os.path.dirname(__file__), 'start.py')
        result = subprocess.run(
            [sys.executable, start_script, '-p', str(config['port']), '-d'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"服务启动成功，端口: {config['port']}")
            print_status(f"✅ 服务启动成功", 'success')
            print_status(f"🔗 访问地址: http://localhost:{config['port']}", 'info')
            return True
        else:
            logger.error(f"服务启动失败: {result.stderr}")
            print_status(f"❌ 服务启动失败: {result.stderr}", 'error')
            return False
            
    except Exception as e:
        logger.error(f"启动服务时发生错误: {e}")
        print_status(f"❌ 启动服务时发生错误: {e}", 'error')
        return False

def check_version():
    """检查版本控制状态"""
    logger.info("检查版本控制状态")
    print_status("=== 检查版本控制状态 ===", 'info')
    
    try:
        # 获取当前分支
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        branch = result.stdout.strip()
        
        # 获取当前提交
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        commit = result.stdout.strip()[:7]
        
        # 获取状态
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        has_changes = bool(result.stdout)
        
        logger.info(f"当前分支: {branch}, 提交: {commit}, 有未提交更改: {has_changes}")
        print_status(f"当前分支: {branch}", 'info')
        print_status(f"当前提交: {commit}", 'info')
        if has_changes:
            print_status("存在未提交的更改", 'warning')
        
        return True
        
    except Exception as e:
        logger.error(f"检查版本控制状态失败: {e}")
        print_status(f"❌ 检查版本控制状态失败: {e}", 'error')
        return False

def main():
    """主部署流程"""
    args = parse_args()
    
    # 初始化部署日志
    deploy_log_dir = os.path.join(PROJECT_ROOT, DEPLOY_CONFIG['log_dir'])
    os.makedirs(deploy_log_dir, exist_ok=True)
    deploy_log_file = os.path.join(deploy_log_dir, f"deploy_{get_timestamp()}.log")
    
    # 添加文件日志处理器
    file_handler = __import__('logging').FileHandler(deploy_log_file)
    formatter = __import__('logging').Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info("=" * 70)
    logger.info(f"TestBrain 一键部署脚本 - 环境: {args.env}")
    logger.info("=" * 70)
    
    print("\n" + "=" * 70)
    print("         TestBrain 一键部署脚本")
    print("=" * 70)
    
    # 回滚模式
    if args.rollback:
        if not rollback_deploy(args.env, args.rollback):
            sys.exit(1)
        return
    
    # 仅备份模式
    if args.backup_only:
        create_deploy_backup(args.env)
        return
    
    # 显示部署配置
    config = DEPLOY_CONFIG['environments'].get(args.env)
    print(f"\n📋 部署配置")
    print(f"  环境: {config['name']} ({args.env})")
    print(f"  分支: {args.branch}")
    print(f"  端口: {config['port']}")
    print(f"  调试: {'开启' if config['debug'] else '关闭'}")
    print(f"  数据库: {config['database']}")
    
    # 确认部署
    if args.env == 'prod':
        confirm = input("\n⚠️  即将部署到生产环境，确认继续? (y/N): ")
        if confirm.lower() != 'y':
            print_status("部署已取消", 'info')
            sys.exit(0)
    
    # 部署步骤
    steps = [
        ('check_version', '检查版本控制', not args.skip_pull),
        ('pull_code', '拉取代码', not args.skip_pull),
        ('create_deploy_backup', '创建备份', True),
        ('install_dependencies', '安装依赖', not args.skip_deps),
        ('configure_environment', '配置环境', True),
        ('run_migrations', '数据库迁移', not args.skip_migrate),
        ('start_service', '启动服务', not args.skip_start),
    ]
    
    # 执行部署步骤
    success_count = 0
    failed_step = None
    
    for func_name, step_name, enabled in steps:
        if not enabled:
            print_status(f"⏭️  跳过: {step_name}", 'info')
            continue
        
        print(f"\n{'='*60}")
        print(f"步骤 {success_count + 1}/{len([s for s in steps if s[2]])}: {step_name}")
        print('='*60)
        
        try:
            func = globals()[func_name]
            if func_name == 'pull_code':
                success = func(args.branch)
            elif func_name == 'configure_environment' or func_name == 'start_service':
                success = func(args.env)
            elif func_name == 'create_deploy_backup':
                success = func(args.env) is not None
            else:
                success = func()
            
            if success:
                success_count += 1
                print_status(f"✅ 步骤完成: {step_name}", 'success')
            else:
                failed_step = step_name
                break
                
        except Exception as e:
            logger.error(f"步骤失败 {step_name}: {e}")
            print_status(f"❌ 步骤失败 {step_name}: {e}", 'error')
            failed_step = step_name
            break
    
    # 部署结果汇总
    print("\n" + "=" * 70)
    if failed_step:
        logger.error(f"部署失败，失败步骤: {failed_step}")
        print_status("❌ 部署失败", 'error')
        print(f"  失败步骤: {failed_step}")
        print(f"  部署日志: {deploy_log_file}")
        
        # 询问是否回滚
        if input("\n是否执行回滚操作? (y/N): ").lower() == 'y':
            rollback_deploy(args.env, create_deploy_backup(args.env))
        
        sys.exit(1)
    else:
        logger.info("部署成功")
        print_status("✅ 部署成功!", 'success')
        print(f"  环境: {config['name']}")
        print(f"  端口: {config['port']}")
        print(f"  访问地址: http://localhost:{config['port']}")
        print(f"  部署日志: {deploy_log_file}")
        print("=" * 70)

if __name__ == '__main__':
    main()