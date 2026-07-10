import os
import json
import threading
from django.http import JsonResponse
from apps.utils.logger_manager import get_logger
from apps.ai_agents.prd_analyzer.analyser import PrdAnalyserAgent
from django.conf import settings
from apps.llm import LLMServiceFactory
from django.shortcuts import render
from apps.utils.file_transfer import word_to_markdown
from apps.llm.utils import get_agent_llm_configs
from apps.utils.progress_manager import (
    TaskProgressManager, 
    generate_task_id,
    get_progress_manager,
    remove_progress_manager
)
from django.views.decorators.http import require_http_methods
from apps.utils.auth_decorators import session_or_apikey_auth

from django.contrib.auth.decorators import login_required


logger = get_logger(__name__)

# LLM配置通过中心化管理器获取
DEFAULT_PROVIDER, PROVIDERS = get_agent_llm_configs("prd_analyzer")
DEFAULT_LLM_CONFIG = PROVIDERS.get(DEFAULT_PROVIDER, {})

llm_service = None

def get_llm_service():
    global llm_service
    if llm_service is None:
        llm_service = LLMServiceFactory.create_with_fallback(
            agent_name="prd_analyzer",
            preferred_provider=DEFAULT_PROVIDER,
        )
    return llm_service


def prd_analyzer(request):
    """从PRD文件中提取测试点&测试场景"""
    if request.method == 'GET':
        return render(request, 'prd_analyzer.html')


@session_or_apikey_auth
@require_http_methods(["POST"])
def prd_upload_api(request):
    """PRD文件上传API"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': '未接收到文件'})
        
        uploaded_file = request.FILES['file']
        file_name = uploaded_file.name
        file_type = os.path.splitext(file_name)[1].lower()
        
        # 验证文件类型
        if file_type not in ['.docx', '.pdf']:
            return JsonResponse({'success': False, 'error': '不支持的文件类型，仅支持 .docx 和 .pdf 格式'})
        
        # 验证文件大小（限制10MB）
        max_size = 10 * 1024 * 1024  # 10MB
        if uploaded_file.size > max_size:
            return JsonResponse({'success': False, 'error': '文件大小超过限制，最大支持10MB'})
        
        # 保存文件
        save_dir = 'prd/'
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file_name)
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 添加时间戳避免覆盖
            base_name, ext = os.path.splitext(file_name)
            file_path = os.path.join(save_dir, f"{base_name}_{os.path.getmtime(file_path)}_{file_name}")
        
        with open(file_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        
        logger.info(f"PRD文件上传成功: {file_path}")
        
        return JsonResponse({
            'success': True,
            'file_path': file_path,
            'file_name': file_name,
            'file_type': file_type
        })
        
    except Exception as e:
        logger.error(f"PRD文件上传失败: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'上传失败: {str(e)}'})


def analyze_prd_async(task_id, file_path, file_name, system_id=None):
    """异步执行PRD分析任务"""
    # 定义阶段
    stages = [
        {'stage': 'initializing', 'title': '初始化', 'description': '准备解析环境...'},
        {'stage': 'extracting', 'title': '提取内容', 'description': '从文件中提取文本内容...'},
        {'stage': 'analyzing', 'title': '分析文档', 'description': 'AI分析PRD文档内容...'},
        {'stage': 'extracting_points', 'title': '提取测试点', 'description': '提取测试点和测试场景...'},
        {'stage': 'validating', 'title': '验证结果', 'description': '验证提取结果...'},
        {'stage': 'completed', 'title': '完成', 'description': '解析完成'}
    ]
    
    # 创建进度管理器
    progress_manager = TaskProgressManager(task_id, stages)
    
    try:
        # 初始化阶段
        progress_manager.start_stage('initializing')
        
        # 提取内容阶段
        progress_manager.start_stage('extracting')
        
        file_type = os.path.splitext(file_name)[1].lower()
        prd_content = ''
        
        if file_type == '.docx':
            # Word文档处理
            md_file_path = file_path.replace('.docx', '.md')
            word_to_markdown(file_path, md_file_path)
            with open(md_file_path, 'r', encoding='utf-8') as f:
                prd_content = f.read()
        elif file_type == '.pdf':
            # PDF文档处理
            prd_content = extract_text_from_pdf(file_path)
        
        if not prd_content:
            progress_manager.error_stage('extracting', '无法从文件中提取内容')
            return
        
        logger.info(f"PRD内容提取完成，长度: {len(prd_content)}")
        progress_manager.complete_stage('extracting')
        
        # 分析文档阶段
        progress_manager.start_stage('analyzing')
        analyser = PrdAnalyserAgent(llm_service=get_llm_service())
        progress_manager.complete_stage('analyzing')
        
        # 提取测试点阶段
        progress_manager.start_stage('extracting_points')

        # --- RAG 知识库增强 ---
        from apps.knowledge.retriever import KnowledgeRetriever
        retriever = KnowledgeRetriever(top_k=3)
        query = f"{file_name} {prd_content[:200]}"
        rag_context = retriever.retrieve_and_format(query)
        if rag_context:
            prd_content = prd_content + "\n\n---\n" + rag_context
        # --- RAG 结束 ---

        result = analyser.analyse(prd_content)

        progress_manager.complete_stage('extracting_points')
        
        # 验证结果阶段
        progress_manager.start_stage('validating')
        if not result or not isinstance(result, dict):
            progress_manager.error_stage('validating', '分析结果格式错误')
            return
        
        progress_manager.complete_stage('validating')
        
        # 设置任务完成
        progress_manager.set_completed({
            'type': 'analysis',
            'message': 'PRD文档解析完成',
            'summary': result.get('summary', {}),
            'test_points': result.get('test_points', [])
        })
        
    except Exception as e:
        logger.error(f"PRD分析失败: {str(e)}", exc_info=True)
        progress_manager.set_error(f'分析失败: {str(e)}')


def extract_text_from_pdf(file_path):
    """从PDF文件中提取文本内容"""
    try:
        # 尝试使用PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ''
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n\n'
            return text.strip()
        except ImportError:
            pass
        
        # 尝试使用pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = ''
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n\n'
            return text.strip()
        except ImportError:
            pass
        
        # 尝试使用pdftotext命令行工具
        try:
            import subprocess
            result = subprocess.run(
                ['pdftotext', file_path, '-'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        logger.error("无法提取PDF内容：未安装PDF解析库")
        return ''
        
    except Exception as e:
        logger.error(f"PDF提取失败: {str(e)}", exc_info=True)
        return ''


@session_or_apikey_auth
@require_http_methods(["POST"])
def prd_analyze_api(request):
    """PRD分析API接口"""
    try:
        data = json.loads(request.body)
        file_path = data.get('file_path')
        file_name = data.get('file_name')
        system_id = data.get('system_id')
        
        if not file_path or not file_name:
            return JsonResponse({'success': False, 'error': '缺少文件路径或文件名'})
        
        # 将文件路径解析为绝对路径，检查是否在允许的目录内
        allowed_dirs = [
            os.path.abspath("prd"),
            os.path.abspath("uploads"),
        ]
        resolved_path = os.path.abspath(file_path)
        if not any(os.path.commonpath([resolved_path, d]) == d for d in allowed_dirs):
            return JsonResponse({"success": False, "error": "非法文件路径"})
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return JsonResponse({'success': False, 'error': '文件不存在'})
        
        # 生成任务ID
        task_id = generate_task_id('prd_analysis')
        
        # 启动异步任务
        thread = threading.Thread(
            target=analyze_prd_async,
            args=(task_id, file_path, file_name, system_id),
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
        return JsonResponse({'success': False, 'error': '无效的JSON数据'})
    except Exception as e:
        logger.error(f"PRD分析请求处理失败: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'请求处理失败: {str(e)}'})

@session_or_apikey_auth
@require_http_methods(["POST"])
def prd_to_testcase_api(request):
    """
    将 PRD 分析结果传入 test_case_generator 生成用例
    """
    try:
        data = json.loads(request.body)
        test_points = data.get('test_points', [])
        notes = data.get('notes', '')
        system_id = data.get('system_id')
        
        # 将测试点合并为需求描述
        combined_lines = []
        for i, tp in enumerate(test_points, 1):
            combined_lines.append(f"{i}. {tp.get('point', '')}")
            for sc in tp.get('scenarios', []):
                combined_lines.append(f"   - {sc}")
        if notes:
            combined_lines.append(f"补充说明：{notes}")
        combined = "\n".join(combined_lines)
        
        if not combined.strip():
            return JsonResponse({'success': False, 'error': '测试点列表为空'})
        
        # --- 联动 test_case_generator 实际触发生成 ---
        from apps.ai_agents.test_case_generator.progress_manager import create_progress_manager
        from apps.ai_agents.test_case_generator.task_executor import submit_generation_task
        from apps.ai_agents.test_case_generator.views import _generate_test_cases_async
        
        # 创建进度管理器
        progress_manager = create_progress_manager()
        task_id = progress_manager.task_id
        
        # 使用默认配置生成用例
        submit_generation_task(
            task_id=task_id,
            requirements=combined,
            llm_provider=DEFAULT_PROVIDER,
            case_design_methods=[],
            case_categories=[],
            case_count=10,
            system_id=system_id,
            generator_func=_generate_test_cases_async
        )
        # --- 联动结束 ---
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'message': f'正在为 {len(test_points)} 个测试点生成用例',
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '无效的JSON数据'})
    except Exception as e:
        logger.error(f"PRD→用例联动失败: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})
