# import os
import json
import asyncio
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from asgiref.sync import sync_to_async
from apps.llm import LLMServiceFactory
from apps.ai_agents.test_case_generator.generator import TestCaseGeneratorAgent
from apps.core.models import TestCase, System
from apps.utils.logger_manager import get_logger
from apps.knowledge.service import get_knowledgeService_instance
from apps.llm.utils import get_agent_llm_configs
from apps.utils.file_parser import extract_text_from_uploaded_file, SUPPORTED_FILE_TYPES
from .progress_manager import (
    create_progress_manager, 
    get_progress_manager, 
    remove_progress_manager,
    GenerationStage
)
from .task_executor import submit_generation_task



logger = get_logger(__name__)

DEFAULT_PROVIDER, PROVIDERS = get_agent_llm_configs("test_case_generator")


knowledge_service = get_knowledgeService_instance()



# @login_required 先屏蔽登录
async def generate(request):
    """
    页面-测试用例生成页面视图函数
    """
    logger.info("===== 进入generate视图函数 =====")
    logger.info(f"请求方法: {request.method}")
    
    # 获取启用的系统列表 - 使用sync_to_async包装同步数据库操作
    active_systems = await sync_to_async(lambda: list(System.objects.filter(status='active').values('id', 'name', 'code')))()
    
    context = {
        'llm_providers': PROVIDERS,
        'llm_provider': DEFAULT_PROVIDER,
        'requirement': '',
        # 'api_description': '',
        'test_cases': None,  # 初始化为 None
        'systems': active_systems  # 添加系统列表
    }
    
    if request.method == 'GET':
        return render(request, 'generate.html', context)
    
    # POST 请求参数解析
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("JSON解析错误", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': '无效的JSON数据'
        }, status=400)
    
    # 参数获取和验证
    requirements = data.get('requirements', '')
    if not requirements:
        return JsonResponse({
            'success': False,
            'message': '需求描述不能为空'
        })
        
    llm_provider = data.get('llm_provider', DEFAULT_PROVIDER)
    case_design_methods = data.get('case_design_methods', [])  # 获取测试方法
    case_categories = data.get('case_categories', [])         # 获取测试类型
    case_count = int(data.get('case_count', 10))            # 获取生成用例条数
    
    logger.info(f"接收到的数据: {json.dumps(data, ensure_ascii=False)}")
    
    try:
        # 使用工厂创建选定的LLM服务
        logger.info(f"使用 {llm_provider} 生成测试用例")
        # llm_service = LLMServiceFactory.create(llm_provider, **PROVIDERS.get(llm_provider, {}))
        llm_service = LLMServiceFactory.create(llm_provider)

        
        
        generator_agent = TestCaseGeneratorAgent(llm_service=llm_service, knowledge_service=knowledge_service, case_design_methods=case_design_methods, case_categories=case_categories, case_count=case_count)
        logger.info(f"开始生成测试用例 - 需求: {requirements}...")
        logger.info(f"选择的测试用例设计方法: {case_design_methods}")
        logger.info(f"选择的测试用例类型: {case_categories}")
        logger.info(f"需要生成的用例条数: {case_count}")
        
        # 生成测试用例
        #mock数据
        # test_cases = [{'description': '测试系统对用户输入为纯文本时的处理', 'test_steps': ['1. 打开应用程序', "2. 在输入框中输入纯文本，例如：'肥肥的'", '3. 提交输入'], 'expected_results': ['1. 应用程序成功启动', "2. 输入框正确显示输入的文本：'肥肥的'", '3. 系统正确识别并处理为纯文本输入，不进行代码段处理']}, {'description': '测试系统对用户输入为代码段时的处理', 'test_steps': ['1. 打开应用程序', '2. 在输入框中输入代码段，例如：\'print("Hello, World!")\'', '3. 提交输入'], 'expected_results': ['1. 应用程序成功启动', '2. 输入框正确显示输入的代码段：\'print("Hello, World!")\'', '3. 系统正确识别并处理为代码段输入，进行相应的代码处理']}, {'description': '测试系统对用户输入为空时的处理', 'test_steps': ['1. 打开应用程序', '2. 在输入框中不输入任何内容', '3. 提交输入'], 'expected_results': ['1. 应用程序成功启动', '2. 输入框保持为空', '3. 系统提示输入不能为空，要求重新输入']}, {'description': '测试系统对用户输入为混合内容（文本和代码）时的处理', 'test_steps': ['1. 打开应用程序', '2. 在输入框中输入混合内容，例如：\'肥肥的 print("Hello, World!")\'', '3. 提交输入'], 'expected_results': ['1. 应用程序成功启动', '2. 输入框正确显示输入的混合内容：\'肥肥的 print("Hello, World!")\'', '3. 系统正确识别并处理为混合内容，分别对文本和代码段进行相应处理']}, {'description': '测试系统对用户输入为特殊字符时的处理', 'test_steps': ['1. 打开应用程序', "2. 在输入框中输入特殊字符，例如：'@#$%^&*()'", '3. 提交输入'], 'expected_results': ['1. 应用程序成功启动', "2. 输入框正确显示输入的特殊字符：'@#$%^&*()'", '3. 系统正确识别并处理为特殊字符输入，不进行代码段处理']}]
        # test_cases = generator_agent.generate(requirements, input_type="requirement")
        test_cases = await generator_agent.async_generate(requirements, input_type="requirement")

        logger.info(f"测试用例生成成功 - 生成数量: {len(test_cases)}")
        
        context.update({
            'test_cases': test_cases
        })
        
        return JsonResponse({
            'success': True,
            'test_cases': test_cases
        })
            
    except Exception as e:
        logger.error(f"生成测试用例时出错: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# @login_required 先屏蔽登录
@csrf_exempt
@require_http_methods(["POST"])
async def generate_with_progress(request):
    """
    带进度跟踪的测试用例生成API
    返回任务ID，前端通过SSE获取实时进度
    """
    logger.info("===== 进入generate_with_progress视图函数 =====")
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("JSON解析错误", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': '无效的JSON数据'
        }, status=400)
    
    # 参数获取和验证
    requirements = data.get('requirements', '')
    if not requirements:
        return JsonResponse({
            'success': False,
            'message': '需求描述不能为空'
        })
    
    llm_provider = data.get('llm_provider', DEFAULT_PROVIDER)
    case_design_methods = data.get('case_design_methods', [])
    case_categories = data.get('case_categories', [])
    case_count = int(data.get('case_count', 10))
    
    # 创建进度管理器
    progress_manager = create_progress_manager()
    task_id = progress_manager.task_id
    
    logger.info(f"创建任务 {task_id}，开始生成测试用例")
    
    # 使用线程池执行器提交任务（确保任务在请求完成后继续执行）
    submit_generation_task(
        task_id=task_id,
        requirements=requirements,
        llm_provider=llm_provider,
        case_design_methods=case_design_methods,
        case_categories=case_categories,
        case_count=case_count,
        generator_func=_generate_test_cases_async
    )
    
    logger.info(f"任务 {task_id} 已提交到线程池")
    
    # 立即返回任务ID
    return JsonResponse({
        'success': True,
        'task_id': task_id,
        'message': '任务已启动'
    })


async def _generate_test_cases_async(
    task_id: str,
    requirements: str,
    llm_provider: str,
    case_design_methods: list,
    case_categories: list,
    case_count: int
):
    """
    异步生成测试用例，带进度跟踪
    """
    progress_manager = get_progress_manager(task_id)
    if not progress_manager:
        logger.error(f"找不到进度管理器: {task_id}")
        return
    
    try:
        logger.info(f"任务 {task_id} 开始执行")
        
        # 阶段1: 初始化
        try:
            logger.info(f"任务 {task_id} - 阶段1: 初始化")
            progress_manager.start_stage(GenerationStage.INITIALIZING, "正在初始化生成环境...")
            
            # 验证参数
            if not requirements:
                raise ValueError("需求描述不能为空")
            if case_count <= 0:
                raise ValueError("用例数量必须大于0")
            
            progress_manager.complete_stage(GenerationStage.INITIALIZING)
            logger.info(f"任务 {task_id} - 阶段1完成")
        except Exception as e:
            logger.error(f"任务 {task_id} - 初始化阶段失败: {e}", exc_info=True)
            raise
        
        # 阶段2: 分析需求
        try:
            logger.info(f"任务 {task_id} - 阶段2: 分析需求")
            progress_manager.start_stage(
                GenerationStage.ANALYZING_REQUIREMENT, 
                f"正在分析需求: {requirements[:100]}..."
            )
            
            # 需求分析逻辑
            logger.info(f"任务 {task_id} - 需求内容: {requirements[:200]}")
            
            progress_manager.complete_stage(
                GenerationStage.ANALYZING_REQUIREMENT,
                f"需求分析完成，识别关键测试点"
            )
            logger.info(f"任务 {task_id} - 阶段2完成")
        except Exception as e:
            logger.error(f"任务 {task_id} - 需求分析阶段失败: {e}", exc_info=True)
            raise
        
        # 阶段3: 检索知识库
        try:
            logger.info(f"任务 {task_id} - 阶段3: 检索知识库")
            progress_manager.start_stage(
                GenerationStage.RETRIEVING_KNOWLEDGE,
                "正在检索知识库获取相关上下文..."
            )
            
            logger.info(f"任务 {task_id} - 开始检索知识库")
            
            # 检查知识库服务是否可用
            knowledge_context = ""
            try:
                knowledge_context = knowledge_service.search_relevant_knowledge(requirements, top_k=5)
                logger.info(f"任务 {task_id} - 检索到知识库内容")
            except AttributeError as e:
                # 知识库服务未正确初始化（embedder/vector_store为None）
                logger.warning(f"任务 {task_id} - 知识库服务不可用，跳过检索: {e}")
                knowledge_context = ""
            
            progress_manager.complete_stage(
                GenerationStage.RETRIEVING_KNOWLEDGE,
                knowledge_context if knowledge_context else "知识库服务未配置，跳过检索"
            )
            logger.info(f"任务 {task_id} - 阶段3完成")
        except Exception as e:
            logger.error(f"任务 {task_id} - 知识库检索阶段失败: {e}", exc_info=True)
            raise
        
        # 阶段4: 生成测试用例
        try:
            logger.info(f"任务 {task_id} - 阶段4: 生成测试用例")
            progress_manager.start_stage(
                GenerationStage.GENERATING_TESTCASES,
                f"AI正在生成 {case_count} 条测试用例..."
            )
            
            # 创建LLM服务
            logger.info(f"任务 {task_id} - 创建LLM服务: {llm_provider}")
            llm_service = LLMServiceFactory.create(llm_provider)
            
            # 创建生成器Agent
            logger.info(f"任务 {task_id} - 创建生成器Agent")
            generator_agent = TestCaseGeneratorAgent(
                llm_service=llm_service,
                knowledge_service=knowledge_service,
                case_design_methods=case_design_methods,
                case_categories=case_categories,
                case_count=case_count
            )
            
            # 更新进度 - 开始调用LLM
            progress_manager.update_stage_details(
                GenerationStage.GENERATING_TESTCASES,
                "正在调用大模型生成测试用例，这可能需要一些时间..."
            )
            
            logger.info(f"任务 {task_id} - 开始调用LLM生成测试用例")
            
            # 异步生成测试用例
            test_cases = await generator_agent.async_generate(requirements, input_type="requirement")
            
            logger.info(f"任务 {task_id} - LM返回 {len(test_cases)} 条测试用例")
            
            progress_manager.complete_stage(
                GenerationStage.GENERATING_TESTCASES,
                f"成功生成 {len(test_cases)} 条测试用例"
            )
            logger.info(f"任务 {task_id} - 阶段4完成")
        except Exception as e:
            logger.error(f"任务 {task_id} - 生成测试用例阶段失败: {e}", exc_info=True)
            raise
        
        # 阶段5: 验证结果
        try:
            logger.info(f"任务 {task_id} - 阶段5: 验证结果")
            progress_manager.start_stage(
                GenerationStage.VALIDATING_RESULTS,
                "正在验证生成的测试用例..."
            )
            
            # 验证测试用例
            if not test_cases or len(test_cases) == 0:
                raise ValueError("生成的测试用例为空")
            
            logger.info(f"任务 {task_id} - 验证完成，{len(test_cases)} 条用例有效")
            
            progress_manager.complete_stage(
                GenerationStage.VALIDATING_RESULTS,
                f"验证完成，{len(test_cases)} 条用例有效"
            )
            logger.info(f"任务 {task_id} - 阶段5完成")
        except Exception as e:
            logger.error(f"任务 {task_id} - 验证结果阶段失败: {e}", exc_info=True)
            raise
        
        # 完成任务
        logger.info(f"任务 {task_id} - 所有阶段完成，设置任务状态为完成")
        progress_manager.set_completed(test_cases)
        logger.info(f"任务 {task_id} 完成，生成 {len(test_cases)} 条测试用例")
        
    except Exception as e:
        logger.error(f"任务 {task_id} 执行失败: {str(e)}", exc_info=True)
        progress_manager.set_error(str(e))


@csrf_exempt
@require_http_methods(["GET"])
def get_progress(request, task_id):
    """
    SSE端点：获取任务进度
    """
    def event_stream():
        import time
        last_progress = None
        
        while True:
            progress_manager = get_progress_manager(task_id)
            if not progress_manager:
                # 任务不存在或已清理
                yield f"data: {json.dumps({'status': 'not_found', 'message': '任务不存在'}, ensure_ascii=False)}\n\n"
                break
            
            progress = progress_manager.get_progress()
            
            # 只在进度变化时发送
            if progress != last_progress:
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                last_progress = progress
            
            # 任务完成或出错时结束
            if progress['status'] in ['completed', 'error']:
                # 延迟清理任务数据
                import threading
                def cleanup():
                    time.sleep(30)  # 30秒后清理
                    remove_progress_manager(task_id)
                threading.Thread(target=cleanup).start()
                break
            
            time.sleep(0.5)  # 每500ms检查一次
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# @login_required 先屏蔽登录
@require_http_methods(["POST"])
def save_test_case(request):
    """保存测试用例"""
    try:
        data = json.loads(request.body)
        requirement = data.get('requirement')
        test_cases_list = data.get('test_cases', [])
        llm_provider = data.get('llm_provider')
        system_id = data.get('system_id')  # 获取系统ID
        
        # logger.info(f"接收到的保存请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        if not test_cases_list:
            return JsonResponse({
                'success': False,
                'message': '测试用例数据为空'
            }, status=400)
        
        # 验证系统是否存在且启用
        if system_id:
            try:
                system = System.objects.get(id=system_id, status='active')
            except System.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': '所选系统不存在或已停用'
                }, status=400)
        
        # 准备批量创建的测试用例列表
        test_cases_to_create = []
        
        # 遍历测试用例数据，创建TestCase实例
        for index, test_case in enumerate(test_cases_list, 1):
            test_case_instance = TestCase(
                title=f"测试用例-{index}",  # 可以根据需求调整标题格式
                description=test_case.get('description', ''),
                test_steps='\n'.join(test_case.get('test_steps', [])),
                expected_results='\n'.join(test_case.get('expected_results', [])),
                requirements=requirement,
                llm_provider=llm_provider,
                system_id=system_id,  # 关联系统
                status='pending'  # 默认状态为待评审
                # created_by=request.user  # 如果需要记录创建用户，取消注释此行
            )
            test_cases_to_create.append(test_case_instance)
        
        # 批量创建测试用例
        created_test_cases = TestCase.objects.bulk_create(test_cases_to_create)
        
        logger.info(f"成功保存 {len(created_test_cases)} 条测试用例")
        
        return JsonResponse({
            'success': True,
            'message': f'成功保存 {len(created_test_cases)} 条测试用例',
            'test_case_id': [case.id for case in created_test_cases]
        })
        
    except json.JSONDecodeError:
        logger.error("JSON解析错误", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': '无效的JSON数据'
        }, status=400)
    except Exception as e:
        logger.error(f"保存测试用例时出错: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'保存失败：{str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request):
    """
    上传并解析文件
    支持 .docx、.md、.txt、.pdf 格式的需求文档
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': '请选择要上传的文件'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        
        # 验证文件名
        filename = uploaded_file.name
        if not filename or '.' not in filename:
            return JsonResponse({
                'success': False,
                'message': '无效的文件名'
            }, status=400)
        
        # 验证文件类型
        ext = '.' + filename.rsplit('.', 1)[1].lower()
        if ext not in SUPPORTED_FILE_TYPES:
            return JsonResponse({
                'success': False,
                'message': f'不支持的文件类型: {ext}。支持的类型: {", ".join(SUPPORTED_FILE_TYPES.values())}'
            }, status=400)
        
        # 验证文件大小（最大50MB）
        from apps.utils.file_parser import MAX_FILE_SIZE
        if uploaded_file.size > MAX_FILE_SIZE:
            from apps.utils.file_parser import get_human_readable_size
            return JsonResponse({
                'success': False,
                'message': f'文件大小超过限制。当前大小: {get_human_readable_size(uploaded_file.size)}，最大允许: {get_human_readable_size(MAX_FILE_SIZE)}'
            }, status=400)
        
        logger.info(f"开始解析文件: {filename}, 大小: {uploaded_file.size} 字节")
        
        # 解析文件内容
        content, filename, file_type = extract_text_from_uploaded_file(uploaded_file)
        
        # 验证解析结果
        if not content or len(content.strip()) == 0:
            return JsonResponse({
                'success': False,
                'message': '文件内容为空或无法解析'
            }, status=400)
        
        logger.info(f"文件解析成功: {filename}, 提取内容长度: {len(content)} 字符")
        
        return JsonResponse({
            'success': True,
            'content': content,
            'filename': filename,
            'file_type': file_type,
            'content_length': len(content)
        })
        
    except ValueError as e:
        logger.error(f"文件上传验证失败: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"文件上传和解析失败: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'文件解析失败：{str(e)}'
        }, status=500)