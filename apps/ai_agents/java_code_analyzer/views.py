from apps.utils.logger_manager import get_logger
from django.conf import settings
from apps.llm import LLMServiceFactory
from apps.ai_agents.java_code_analyzer.java_code_analyzer_agent import JavaCodeAnalyzerAgent
import json
import os
from django.http import JsonResponse
from apps.ai_agents.java_code_analyzer.tools import GitTools
from pathlib import Path
from datetime import datetime
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.http import FileResponse, Http404
from urllib.parse import quote
from apps.llm.utils import get_agent_llm_configs
from apps.utils.progress_manager import (
    TaskProgressManager, 
    generate_task_id, 
    get_progress_manager,
    remove_progress_manager
)
import threading

logger = get_logger(__name__)


def java_code_analyzer(request):
    """Java源码分析页面视图"""
    if request.method == 'GET':
        from apps.llm.utils import get_agent_llm_configs
        DEFAULT_PROVIDER, PROVIDERS = get_agent_llm_configs("java_code_analyzer")
        
        context = {
            'llm_providers': PROVIDERS,
            'llm_provider': DEFAULT_PROVIDER,
        }
        return render(request, 'java_code_analyzer.html', context)


@require_http_methods(["GET"])
def download_report(request):
    """下载java源码分析报告"""
    filename = request.GET.get('filename', '')
    if not filename:
        raise Http404("缺少文件名")

    if '/' in filename or '\\' in filename:
        raise Http404("非法文件名")
    if not filename.endswith('.md'):
        raise Http404("仅支持下载 .md 文件")

    outputs_dir = (Path(settings.BASE_DIR) / 'outputs').resolve()
    file_path = (outputs_dir / filename).resolve()
    if outputs_dir not in file_path.parents:
        raise Http404("非法文件路径")
    if not file_path.exists() or not file_path.is_file():
        raise Http404("文件不存在")

    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    response['Content-Type'] = 'text/markdown; charset=utf-8'
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def analyze_java_code_async(task_id, project_id, base_commit, new_commit, llm_provider):
    """异步执行Java代码分析任务"""
    # 定义阶段
    stages = [
        {'stage': 'initializing', 'title': '初始化', 'description': '准备分析环境...'},
        {'stage': 'fetching', 'title': '获取代码', 'description': '从版本库获取代码...'},
        {'stage': 'diffing', 'title': '代码对比', 'description': '对比两个commit的代码差异...'},
        {'stage': 'analyzing', 'title': '分析变更', 'description': 'AI分析代码变更内容...'},
        {'stage': 'reporting', 'title': '生成报告', 'description': '生成分析报告...'},
        {'stage': 'completed', 'title': '完成', 'description': '分析完成'}
    ]
    
    # 创建进度管理器
    progress_manager = TaskProgressManager(task_id, stages)
    
    try:
        # 初始化阶段
        progress_manager.start_stage('initializing')
        
        base_dir = getattr(settings, 'JAVA_PROJECTS_BASE_DIR', None)
        project_mapping = getattr(settings, 'PROJECT_ID_REPO_MAPPING', {})
        
        if not base_dir:
            progress_manager.error_stage('initializing', 'JAVA_PROJECTS_BASE_DIR 未配置')
            return
        
        repo_path = os.path.join(base_dir, project_id)
        logger.info(f"构建出来的项目路径是: {repo_path}")
        
        if not os.path.exists(repo_path):
            progress_manager.error_stage('initializing', f'项目 {project_id} 不存在。路径: {repo_path}')
            return
        
        progress_manager.complete_stage('initializing')
        
        # 获取代码阶段
        progress_manager.start_stage('fetching')
        git_tools = GitTools(repo_path)
        
        logger.info("拉取最新代码...")
        git_tools.pull_latest()
        
        logger.info("记录当前 Git 状态...")
        original_ref = git_tools.get_current_ref()
        logger.info(f"当前引用: {original_ref}")
        progress_manager.complete_stage('fetching')
        
        # 代码对比阶段
        progress_manager.start_stage('diffing')
        logger.info(f"切换到目标版本: {new_commit}")
        git_tools.checkout_version(new_commit)
        logger.info(f"已切换到: {new_commit}")
        progress_manager.complete_stage('diffing')
        
        # 分析阶段
        progress_manager.start_stage('analyzing')
        analyzer_agent = JavaCodeAnalyzerAgent(
            repo_path=repo_path,
            java_analyzer_service_url=getattr(settings, 'JAVA_ANALYZER_SERVICE_URL'),
            max_iterations=100,
            verbose=True,
            llm_provider=llm_provider,
        )
        
        result = analyzer_agent.analyze(base_commit, new_commit)
        
        if not isinstance(result, dict):
            logger.error(f"分析返回值类型错误: {type(result)}, 值: {result}")
            progress_manager.error_stage('analyzing', f'分析返回值类型错误: {str(result)}')
            return
        
        if not result.get('success'):
            error_msg = result.get('error', '分析失败')
            logger.error(f"分析失败: {error_msg}")
            progress_manager.error_stage('analyzing', error_msg)
            return
        
        report_content = result.get('output', '')
        progress_manager.complete_stage('analyzing')
        
        # 生成报告阶段
        progress_manager.start_stage('reporting')
        output_dir = Path(settings.BASE_DIR) / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{project_id}_analyzer_{base_commit[:8]}_{new_commit[:8]}_{timestamp}.md"
        output_path = output_dir / output_filename
        
        if report_content:
            output_path.write_text(report_content, encoding='utf-8')
            logger.info(f"分析报告已写入: {output_path}")
        
        progress_manager.complete_stage('reporting')
        
        # 设置任务完成
        progress_manager.set_completed({
            'type': 'analysis',
            'message': 'Java源码分析完成',
            'content': report_content or '分析完成，但没有返回详细结果',
            'report_path': str(output_path),
            'report_filename': output_filename,
            'report_download_url': f"/java_code_analyzer/api/download-report/?filename={quote(output_filename)}"
        })
        
    except Exception as e:
        logger.error(f"Java代码分析时出错: {str(e)}", exc_info=True)
        progress_manager.set_error(f'分析失败: {str(e)}')
    finally:
        # 清理git状态
        if 'original_ref' in locals():
            try:
                git_tools.checkout_version(original_ref)
                logger.info(f"已恢复到原始引用: {original_ref}")
            except Exception as restore_error:
                logger.error(f"恢复原始引用失败: {restore_error}")


@require_http_methods(["POST"])
def java_code_analyzer_service_api(request):
    """Java源码分析API接口"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        base_commit = data.get('base_commit')
        new_commit = data.get('new_commit')
        llm_provider = data.get('llm_provider')
        
        logger.info(f"Java代码分析请求: 项目={project_id}, 基础提交={base_commit}, 新提交={new_commit}, LLM提供商={llm_provider}")
        
        if not project_id or not base_commit or not new_commit:
            return JsonResponse({
                'success': False,
                'error': '项目ID、基础提交和新提交均为必填项'
            }, status=400)
        
        # 生成任务ID
        task_id = generate_task_id('java_analysis')
        
        # 启动异步任务
        thread = threading.Thread(
            target=analyze_java_code_async,
            args=(task_id, project_id, base_commit, new_commit, llm_provider),
            daemon=True
        )
        thread.start()
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'message': '分析任务已启动'
        })
        
    except json.JSONDecodeError:
        logger.error("JSON解析错误", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': '无效的JSON数据'
        }, status=400)
    except Exception as e:
        logger.error(f"Java代码分析请求处理失败: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'请求处理失败: {str(e)}'
        }, status=500)