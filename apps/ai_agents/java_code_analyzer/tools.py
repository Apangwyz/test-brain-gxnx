"""
工具函数集合：供大模型自主调用的各种工具。
包括 Git 信息提取工具和源码分析 REST API 工具。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import subprocess
from git import Repo
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


def _paginate_lines(
    lines: List[str],
    offset: int,
    limit: int,
    file_path: str,
    content_type: str = "文件"
) -> Tuple[str, str]:
    """
    通用的行内容分段处理辅助方法。
    
    Args:
        lines: 所有行的列表
        offset: 起始行号（从 0 开始）
        limit: 最多读取的行数
        file_path: 文件路径（用于元信息显示）
        content_type: 内容类型描述（如 "文件"、"Diff"）
        
    Returns:
        (分段内容, 元信息) 的元组
    """
    total_lines = len(lines)
    
    # 检查 offset 是否超出范围
    if offset >= total_lines:
        meta_info = f"\n{'='*70}\n"
        meta_info += f"📄 文件: {file_path}\n"
        meta_info += f"📊 {content_type}总行数: {total_lines} 行\n"
        meta_info += f"❌ 错误: offset ({offset}) 超出范围 (总行数: {total_lines})\n"
        meta_info += f"💡 提示: offset 应该在 0 到 {total_lines - 1} 之间\n"
        meta_info += f"{'='*70}\n"
        return "", meta_info
    
    # 分段提取
    end = min(offset + limit, total_lines)
    selected_lines = lines[offset:end]
    content = '\n'.join(selected_lines)
    
    # 添加元信息
    meta_info = f"\n{'='*70}\n"
    meta_info += f"📄 文件: {file_path}\n"
    meta_info += f"📊 {content_type}总行数: {total_lines} 行\n"
    meta_info += f"📍 当前读取范围: 第 {offset + 1} - {end} 行\n"
    
    if end < total_lines:
        remaining = total_lines - end
        meta_info += f"⚠️  还有 {remaining} 行未读取\n"
        meta_info += f"💡 继续读取请使用: offset={end}, limit={limit}\n"
    else:
        meta_info += f"✅ 已读取完整内容\n"
    
    meta_info += f"{'='*70}\n"
    
    return content, meta_info


class GitTools:
    """Git 相关工具函数"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
    
    def pull_latest(self, remote: str = "origin", branch: Optional[str] = None, allow_dirty: bool = True):
        """
        拉取最新代码
        
        Args:
            remote: 远程仓库名称
            branch: 要拉取的分支
            allow_dirty: 是否允许未提交修改
        """
        if self.repo.is_dirty(untracked_files=True) and not allow_dirty:
            raise RuntimeError("仓库存在未提交修改，放弃自动拉取")
        remote_obj = self.repo.remotes[remote]
        remote_obj.fetch()
        if self.repo.head.is_detached and branch is None:
            raise RuntimeError("当前为 detached HEAD，需显式指定要拉取的分支")
        target_branch = branch or self.repo.active_branch.name
        remote_obj.pull(target_branch)
    
    def get_commit_info(self, commit_hash: str) -> Dict[str, Any]:
        """
        获取 commit 的基本信息。
        
        Args:
            commit_hash: commit 哈希值
            
        Returns:
            包含 commit 信息的字典
        """
        try:
            commit = self.repo.commit(commit_hash)
            return {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:8],
                "author": str(commit.author),
                "email": commit.author.email,
                "date": commit.committed_datetime.isoformat(),
                "message": commit.message.strip(),
                "summary": commit.summary,
                "parents": [p.hexsha for p in commit.parents]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_changed_files(self, base_commit: str, new_commit: str) -> List[str]:
        """
        获取两个 commit 之间变更的文件列表。
        
        Args:
            base_commit: 基准 commit
            new_commit: 新 commit
            
        Returns:
            变更文件路径列表
        """
        try:
            base = self.repo.commit(base_commit)
            new = self.repo.commit(new_commit)
            
            diff_index = base.diff(new)
            files = []
            
            for diff in diff_index:
                if diff.a_path:
                    files.append(diff.a_path)
                if diff.b_path and diff.b_path != diff.a_path:
                    files.append(diff.b_path)
            
            return list(set(files))
        except Exception as e:
            return [f"Error: {e}"]
    
    def get_changed_files_detailed(self, base_commit: str, new_commit: str) -> List[Dict[str, Any]]:
        """
        获取详细的文件变更信息，包括变更类型、行数统计和 hunk 信息。
        
        Args:
            base_commit: 基准 commit
            new_commit: 新 commit
            
        Returns:
            详细变更信息列表，包含 path, changeType, hunks 字段
        """
        try:
            base = self.repo.commit(base_commit)
            new = self.repo.commit(new_commit)
            
            diff_index = base.diff(new, create_patch=True)
            changes = []
            
            for diff in diff_index:
                change_info = {
                    "a_path": diff.a_path,
                    "b_path": diff.b_path,
                    "change_type": self._get_change_type(diff),
                    "renamed": diff.renamed,
                    "deleted": diff.deleted_file,
                    "new_file": diff.new_file,
                }
                
                # 解析 hunks 信息
                hunks = []
                if diff.diff:
                    try:
                        diff_text = diff.diff.decode('utf-8', errors='ignore')
                        additions = diff_text.count('\n+') - diff_text.count('\n+++')
                        deletions = diff_text.count('\n-') - diff_text.count('\n---')
                        change_info["additions"] = additions
                        change_info["deletions"] = deletions
                        
                        # 解析 hunk 头（@@ -old_start,old_lines +new_start,new_lines @@）
                        import re
                        hunk_pattern = r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@'
                        for match in re.finditer(hunk_pattern, diff_text):
                            old_start = int(match.group(1))
                            old_lines = int(match.group(2)) if match.group(2) else 1
                            new_start = int(match.group(3))
                            new_lines = int(match.group(4)) if match.group(4) else 1
                            
                            hunks.append({
                                "oldStart": old_start,
                                "oldLines": old_lines,
                                "newStart": new_start,
                                "newLines": new_lines
                            })
                    except:
                        pass
                
                change_info["hunks"] = hunks
                changes.append(change_info)
            
            return changes
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_file_diff(
        self, 
        base_commit: str, 
        new_commit: str, 
        file_path: str,
        offset: int = 0,
        limit: int = 300
    ) -> str:
        """
        获取特定文件的详细 diff。支持分段读取大 diff。
        
        Args:
            base_commit: 基准 commit
            new_commit: 新 commit
            file_path: 文件路径
            offset: 起始行号（从 0 开始），用于分段读取
            limit: 最多读取的行数
            
        Returns:
            diff 文本，包含元信息（总行数、当前读取范围等）
        """
        try:
            result = subprocess.run(
                ['git', 'diff', f'{base_commit}..{new_commit}', '--', file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            full_diff = result.stdout
            
            # 使用统一的分段处理
            lines = full_diff.split('\n')
            content, meta_info = _paginate_lines(lines, offset, limit, file_path, "Diff")
            
            return content + meta_info
        except Exception as e:
            return f"Error: {e}"
    
    def get_file_content_by_commit(
        self, 
        commit_hash: str, 
        file_path: str,
        offset: int = 0,
        limit: int = 500
    ) -> str:
        """
        获取特定 commit 中某个文件的内容。支持分段读取大文件。
        
        Args:
            commit_hash: commit 哈希值
            file_path: 文件路径
            offset: 起始行号（从 0 开始），用于分段读取
            limit: 最多读取的行数
            
        Returns:
            文件内容，包含元信息（总行数、当前读取范围等）
        """
        try:
            commit = self.repo.commit(commit_hash)
            blob = commit.tree / file_path
            full_content = blob.data_stream.read().decode('utf-8', errors='ignore')
            
            # 使用统一的分段处理
            lines = full_content.split('\n')
            content, meta_info = _paginate_lines(lines, offset, limit, file_path, "文件")
            
            return content + meta_info
        except Exception as e:
            return f"Error: {e}"
    
    def get_commits_between(self, base_commit: str, new_commit: str, max_count: int = 20) -> List[Dict[str, Any]]:
        """
        获取两个 commit 之间的所有 commit 列表。
        
        Args:
            base_commit: 基准 commit
            new_commit: 新 commit
            max_count: 最多返回的 commit 数量
            
        Returns:
            commit 信息列表
        """
        try:
            commits = list(self.repo.iter_commits(f'{base_commit}..{new_commit}', max_count=max_count))
            return [
                {
                    "hash": c.hexsha[:8],
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                    "message": c.summary
                }
                for c in commits
            ]
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_file_history(self, file_path: str, max_count: int = 10) -> List[Dict[str, Any]]:
        """
        获取文件的修改历史。
        
        Args:
            file_path: 文件路径
            max_count: 最多返回的历史记录数
            
        Returns:
            修改历史列表
        """
        try:
            commits = list(self.repo.iter_commits(paths=file_path, max_count=max_count))
            return [
                {
                    "hash": c.hexsha[:8],
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                    "message": c.summary
                }
                for c in commits
            ]
        except Exception as e:
            return [{"error": str(e)}]
    
    def _get_change_type(self, diff) -> str:
        """判断变更类型"""
        if diff.new_file:
            return "ADD"
        elif diff.deleted_file:
            return "DELETE"
        elif diff.renamed:
            return "RENAME"
        else:
            return "MODIFY"
    
    def get_current_ref(self) -> str:
        """
        获取当前 Git 引用。
        
        Returns:
            分支名（如 "main"）或 commit hash（detached HEAD）
        """
        if self.repo.head.is_detached:
            # detached HEAD 状态，返回 commit hash
            return self.repo.head.commit.hexsha
        else:
            # 在某个分支上，返回分支名
            return self.repo.active_branch.name

    def checkout_version(self, ref: str):
        """
        切换到指定版本。
        
        Args:
            ref: 版本号（commit hash 或分支名）
        """
        self.repo.git.checkout(ref)

class AnalyzerAPITools:
    """源码分析 REST API 工具函数"""
    
    def __init__(self, base_url: str = "http://localhost:8089"):
        self.base_url = base_url.rstrip("/")
    
    def index_project(self, project_id: str) -> Dict[str, Any]:
        """
        索引项目，构建调用图。
        
        Args:
            project_id: 需要分析的目标java项目ID, 后端源码分析服务根据项目ID查找本地源码路径
            
        Returns:
            索引状态
        """
        try:
            url = f"{self.base_url}/index/project?projectId={project_id}"
            payload = {
                "sourceSets": ["main"],
                "maven": {"resolveDeps": True},
                "jdkHome": None
            }
            logger.info(f"API 调用: POST {url}")
            logger.info(f"项目ID: {project_id}")
            logger.info(f"请求体: {payload}")
            logger.info(f"完整URL: {url}")
            logger.info(f"请求详情: projectId={project_id}, sourceSets=main, maven.resolveDeps=True")
            
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            logger.info(f"响应成功: {result}")
            return result
        except Exception as e:
            logger.error(f"调用失败: {str(e)}")
            return {"error": str(e)}
    
    def get_index_status(self, project_id: str) -> Dict[str, Any]:
        """
        获取索引状态。
        
        Args:
            project_id: 项目ID, 后端源码分析服务根据项目ID查找本地源码路径

        Returns:
            索引状态信息
        """
        try:
            url = f"{self.base_url}/index/status?projectId={project_id}"
            logger.info(f"API 调用: GET {url}")
            logger.info(f"完整URL: {url}")
            logger.info(f"请求详情: 获取索引状态 projectId={project_id}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"响应成功: {result}")
            return result
        except Exception as e:
            logger.error(f"调用失败: {str(e)}")
            return {"error": str(e)}
    
    def map_hunks_to_symbols(self, changes: List[Dict[str, Any]], project_id: str) -> Dict[str, Any]:
        """
        将文件变更映射到受影响的方法和类。
        
        Args:
            changes: 变更列表（FileChange 格式）    
            project_id: 项目ID, 后端源码分析服务根据项目ID查找本地源码路径
            
        Returns:
            映射结果，包含 affected 方法和类
        """
        try:
            url = f"{self.base_url}/map/hunks-to-symbols?projectId={project_id}"
            payload = {"changes": changes}
            
            # 详细输出文件列表
            logger.info(f"筛选后的变更文件列表 ({len(changes)} 个):")
            logger.info(f"项目ID: {project_id}")
            for i, change in enumerate(changes, 1):
                # 兼容两种格式：path/changeType（标准格式）和 b_path/a_path/change_type（内部格式）
                path = change.get('path') or change.get('b_path') or change.get('a_path') or 'unknown'
                change_type = change.get('changeType') or change.get('change_type') or 'UNKNOWN'
                # 处理可能的 None 值
                additions = change.get('additions')
                deletions = change.get('deletions')
                
                # 格式化统计信息
                if additions is not None and deletions is not None:
                    stats = f"(+{additions:3d}/-{deletions:3d})"
                elif additions is not None:
                    stats = f"(+{additions} lines)"
                elif deletions is not None:
                    stats = f"(-{deletions} lines)"
                else:
                    stats = ""
                
                logger.info(f"  {i:2d}. {path:<60} [{change_type:6}] {stats}")
            
            logger.info(f"API 调用: POST {url}")
            logger.info(f"请求体: {len(changes)} 个文件变更")
            logger.info(f"完整URL: {url}")
            logger.info(f"请求详情: projectId={project_id}, changes={len(changes)} items")
            
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            logger.info(f"响应成功: {result}")
            return result
        except Exception as e:
            logger.error(f"调用失败: {str(e)}")
            return {"error": str(e)}
    
    def analyze_impact(
        self,
        seeds: Dict[str, Any],
        project_id: str,
        depth: int = 1,
        direction: str = "outbound",
        include_edges: bool = True
    ) -> Dict[str, Any]:
        """
        分析影响范围。
        
        Args:
            seeds: 种子方法/类
            project_id: 项目ID, 后端源码分析服务根据项目ID查找本地源码路径
            depth: 传播深度
            direction: 方向（inbound/outbound/both）
            include_edges: 是否包含调用边
            
        Returns:
            影响分析结果
        """
        try:
            url = f"{self.base_url}/analyze/impact?projectId={project_id}"
            payload = {
                "seeds": seeds,
                "direction": direction,
                "depth": depth,
                "includeEdges": include_edges
            }
            logger.info(f"API 调用: POST {url}")
            logger.info(f"项目ID: {project_id}")
            logger.info(f"请求体: seeds={seeds}, depth={depth}, direction={direction}")
            logger.info(f"完整URL: {url}")
            logger.info(f"请求详情: projectId={project_id}, seeds={len(seeds) if isinstance(seeds, list) else 1} items, depth={depth}, direction={direction}")
            
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            logger.info(f"响应成功: {result}")
            return result
        except Exception as e:
            logger.error(f"调用失败: {str(e)}")
            return {"error": str(e)}


class SourceCodeTools:
    """源码读取相关工具"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    def read_file(self, relative_path: str, max_lines: int = 500, offset: int = 0) -> str:
        """
        读取项目中的文件内容。支持分段读取大文件。
        
        Args:
            relative_path: 相对于项目根的路径
            max_lines: 最多读取的行数（每次读取的限制）
            offset: 起始行号（从 0 开始），用于分段读取
            
        Returns:
            文件内容，包含元信息（总行数、当前读取范围等）
        """
        try:
            file_path = self.repo_path / relative_path
            if not file_path.exists():
                return f"Error: File not found: {relative_path}"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用统一的分段处理
            lines = content.split('\n')
            paginated_content, meta_info = _paginate_lines(lines, offset, max_lines, relative_path, "文件")
            
            return paginated_content + meta_info
            
        except Exception as e:
            return f"Error: {e}"
    
    def search_in_file(self, relative_path: str, keyword: str) -> List[Dict[str, Any]]:
        """
        在文件中搜索关键字。
        
        Args:
            relative_path: 文件路径
            keyword: 搜索关键字
            
        Returns:
            匹配的行信息列表
        """
        try:
            file_path = self.repo_path / relative_path
            if not file_path.exists():
                return [{"error": f"File not found: {relative_path}"}]
            
            matches = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if keyword in line:
                        matches.append({
                            "line_number": line_num,
                            "content": line.strip()
                        })
            
            return matches
        except Exception as e:
            return [{"error": str(e)}]
    
    def list_java_files(self, directory: str = "") -> List[str]:
        """
        列出目录下的所有 Java 文件。
        
        Args:
            directory: 相对目录路径
            
        Returns:
            Java 文件路径列表
        """
        try:
            search_path = self.repo_path / directory if directory else self.repo_path
            java_files = []
            
            for path in search_path.rglob("*.java"):
                relative_path = path.relative_to(self.repo_path)
                java_files.append(str(relative_path))
            
            return sorted(java_files)
        except Exception as e:
            return [f"Error: {e}"]
    
    def list_directory(self, directory: str = "") -> Dict[str, Any]:
        """
        列出指定目录下的文件和子目录。
        
        Args:
            directory: 相对目录路径，空字符串表示项目根目录
            
        Returns:
            包含目录内容的字典
        """
        try:
            target_path = self.repo_path / directory if directory else self.repo_path
            
            if not target_path.exists():
                return {"error": f"目录不存在: {directory or '.'}"}
            
            if not target_path.is_dir():
                return {"error": f"不是目录: {directory or '.'}"}
            
            items = []
            for item in sorted(target_path.iterdir()):
                try:
                    relative = item.relative_to(self.repo_path)
                    if item.is_dir():
                        items.append({
                            "type": "directory",
                            "name": item.name,
                            "path": str(relative)
                        })
                    else:
                        size = item.stat().st_size
                        items.append({
                            "type": "file",
                            "name": item.name,
                            "path": str(relative),
                            "size": size
                        })
                except Exception:
                    # 忽略无法访问的文件
                    continue
            
            return {
                "directory": directory or ".",
                "total_items": len(items),
                "directories": [i for i in items if i["type"] == "directory"],
                "files": [i for i in items if i["type"] == "file"]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def find_file(self, pattern: str, max_results: int = 200) -> Dict[str, Any]:
        """
        在项目中查找特定文件名。
        
        Args:
            pattern: 文件名模式，支持通配符
            max_results: 最多返回的结果数
            
        Returns:
            包含匹配文件的字典
        """
        import fnmatch
        
        try:
            matches = []
            
            # 递归搜索所有文件
            for file_path in self.repo_path.rglob("*"):
                if file_path.is_file():
                    relative = file_path.relative_to(self.repo_path)
                    # 匹配文件名或完整路径
                    if fnmatch.fnmatch(file_path.name, pattern) or fnmatch.fnmatch(str(relative), pattern):
                        matches.append({
                            "name": file_path.name,
                            "path": str(relative),
                            "size": file_path.stat().st_size
                        })
                        if len(matches) >= max_results:
                            break
            
            result = {
                "pattern": pattern,
                "found_count": len(matches),
                "files": matches
            }
            
            if len(matches) >= max_results:
                result["note"] = f"搜索已达到上限，仅显示前 {max_results} 个结果"
            elif len(matches) == 0:
                result["note"] = f"未找到匹配 '{pattern}' 的文件"
            
            return result
        except Exception as e:
            return {"error": f"搜索失败: {str(e)}"}


def get_all_tools(repo_path: str, java_analyzer_service_url: str) -> Dict[str, Any]:
    """
    获取所有工具实例。
    
    Args:
        repo_path: 项目路径
        java_analyzer_service_url: java源码分析服务URL
        
    Returns:
        工具字典
    """
    return {
        "git": GitTools(repo_path),
        "api": AnalyzerAPITools(java_analyzer_service_url),
        "source": SourceCodeTools(repo_path)
    }
