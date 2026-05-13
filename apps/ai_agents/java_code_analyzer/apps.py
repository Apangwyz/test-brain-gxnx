import logging
import os
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class JavaCodeAnalyzerConfig(AppConfig):
    """Java 代码分析器应用配置"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_agents.java_code_analyzer'
    
    def ready(self):
        """应用启动时调用"""
        # 延迟导入，避免在 Django 初始化完成前访问 settings
        try:
            from django.conf import settings
            
            # 获取配置
            base_dir = getattr(settings, 'JAVA_PROJECTS_BASE_DIR', None)
            project_mapping = getattr(settings, 'PROJECT_ID_REPO_MAPPING', {})
            git_credentials = getattr(settings, 'GIT_CREDENTIALS', {})
            
            if not base_dir:
                logger.warning("JAVA_PROJECTS_BASE_DIR 未配置，跳过项目初始化")
                return
                
            if not project_mapping:
                logger.info("PROJECT_ID_REPO_MAPPING 为空，无需初始化项目")
                return
            
            logger.info("正在检查和初始化 Java 项目...")
            logger.info(f"基础目录: {base_dir}")
            logger.info(f"已配置项目: {list(project_mapping.keys())}")
            
            # 确保基础目录存在
            os.makedirs(base_dir, exist_ok=True)
            
            # 初始化统计
            total_projects = len(project_mapping)
            cloned_count = 0
            updated_count = 0
            error_count = 0
            
            # 检查每个项目
            for project_id, repo_url in project_mapping.items():
                try:
                    project_path = os.path.join(base_dir, project_id)
                    
                    if os.path.exists(project_path):
                        # 项目已存在，尝试更新
                        logger.info(f"项目 {project_id} 已存在，检查更新...")
                        if self._update_project(project_path, git_credentials):
                            logger.info(f"✅ 项目 {project_id} 更新成功")
                            updated_count += 1
                        else:
                            logger.info(f"✅ 项目 {project_id} 已是最新")
                    else:
                        # 项目不存在，克隆
                        logger.info(f"项目 {project_id} 不存在，开始克隆...")
                        if self._clone_project(repo_url, project_path, git_credentials):
                            logger.info(f"✅ 项目 {project_id} 克隆成功")
                            cloned_count += 1
                        else:
                            logger.error(f"❌ 项目 {project_id} 克隆失败")
                            error_count += 1
                            
                except Exception as e:
                    logger.error(f"❌ 处理项目 {project_id} 时发生错误: {e}")
                    error_count += 1
            
            # 输出统计信息
            logger.info(f"Java 项目初始化完成:")
            logger.info(f"  总项目数: {total_projects}")
            logger.info(f"  新克隆: {cloned_count}")
            logger.info(f"  已更新: {updated_count}")
            logger.info(f"  错误数: {error_count}")
            
        except Exception as e:
            logger.error(f"Java 项目初始化检查失败: {e}")
            # 不阻止应用启动，只记录错误
    
    def _clone_project(self, repo_url, project_path, git_credentials):
        """克隆项目"""
        try:
            from git import Repo
            
            # 构建带认证的URL
            auth_url = self._build_auth_url(repo_url, git_credentials)
            
            # 克隆项目
            repo = Repo.clone_from(auth_url, project_path)
            
            # 如果使用了token，重置远程URL为原始URL（避免暴露凭据）
            if git_credentials.get('token'):
                origin = repo.remotes.origin
                origin.set_url(repo_url)
            
            return True
            
        except Exception as e:
            logger.error(f"克隆项目失败 {repo_url}: {e}")
            return False
    
    def _update_project(self, project_path, git_credentials):
        """更新项目"""
        try:
            from git import Repo
            
            repo = Repo(project_path)
            
            # 配置认证（如果需要）
            if git_credentials:
                self._configure_git_credentials(repo, git_credentials)
            
            # 获取当前提交
            current_commit = repo.head.commit.hexsha
            
            # 拉取最新代码
            origin = repo.remotes.origin
            origin.fetch()
            
            # 获取远程最新提交
            remote_commit = origin.refs['main'].commit.hexsha if 'main' in origin.refs else origin.refs['master'].commit.hexsha
            
            # 如果有更新，执行pull
            if current_commit != remote_commit:
                origin.pull()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"更新项目失败 {project_path}: {e}")
            return False
    
    def _build_auth_url(self, repo_url, git_credentials):
        """构建带认证的URL"""
        if not git_credentials:
            return repo_url
            
        if git_credentials.get('token'):
            # 使用token认证
            return repo_url.replace('http://', f'http://oauth2:{git_credentials["token"]}@').replace('https://', f'https://oauth2:{git_credentials["token"]}@')
        elif git_credentials.get('username') and git_credentials.get('password'):
            # 使用用户名密码认证
            return repo_url.replace('http://', f'http://{git_credentials["username"]}:{git_credentials["password"]}@').replace('https://', f'https://{git_credentials["username"]}:{git_credentials["password"]}@')
        
        return repo_url
    
    def _configure_git_credentials(self, repo, git_credentials):
        """配置Git凭据"""
        try:
            with repo.config_writer() as config:
                if git_credentials.get('token'):
                    config.set_value('user', 'name', 'GitLab CI')
                    config.set_value('user', 'email', 'ci@example.com')
                elif git_credentials.get('username'):
                    config.set_value('user', 'name', git_credentials['username'])
                    config.set_value('user', 'email', f'{git_credentials["username"]}@example.com')
        except Exception as e:
            logger.warning(f"配置Git凭据失败: {e}")