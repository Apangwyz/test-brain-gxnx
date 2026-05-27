from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
import json

from .models import TestCase, KnowledgeBase, System, TestPlan, RequirementDoc
from ..knowledge.service import get_knowledgeService_instance

# 初始化服务
from django.conf import settings
from apps.llm import LLMServiceFactory
# from ..knowledge.vector_store import MilvusVectorStore
# from ..knowledge.embedding import BGEM3Embedder
from apps.utils.logger_manager import get_logger
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
from datetime import datetime
from apps.knowledge.milvus_helper import process_singel_file

import hashlib



logger = get_logger(__name__)

# 获取LLM配置
llm_config = getattr(settings, 'LLM_PROVIDERS', {})

# 获取默认提供商
DEFAULT_PROVIDER = llm_config.get('default_provider', 'deepseek')

# 创建提供商字典，排除'default_provider'键
PROVIDERS = {k: v for k, v in llm_config.items() if k != 'default_provider'}

# 获取默认提供商的配置
DEFAULT_LLM_CONFIG = PROVIDERS.get(DEFAULT_PROVIDER, {})

# 延迟初始化LLM服务实例，避免在模块加载时就需要API key
llm_service = None

def get_llm_service():
    global llm_service
    if llm_service is None:
        llm_service = LLMServiceFactory.create(
            provider=DEFAULT_PROVIDER,
        )
    return llm_service

knowledge_service = get_knowledgeService_instance()

# test_case_generator = TestCaseGeneratorAgent(llm_service, knowledge_service)
#test_case_reviewer = TestCaseReviewerAgent(llm_service, knowledge_service)

# @login_required 先屏蔽登录
def index(request):
    """页面-首页视图"""
    # 获取测试用例统计数据
    total_test_cases = TestCase.objects.count()
    pending_count = TestCase.objects.filter(status='pending').count()
    approved_count = TestCase.objects.filter(status='approved').count()
    rejected_count = TestCase.objects.filter(status='rejected').count()
    
    # 获取最近的测试用例
    recent_test_cases = TestCase.objects.order_by('-created_at')[:10]
    
    context = {
        'total_test_cases': total_test_cases,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'recent_test_cases': recent_test_cases,
    }
    
    return render(request, 'index.html', context)


def format_test_cases_to_html(test_cases):
    """将测试用例格式化为HTML"""
    html = ""
    for i, test_case in enumerate(test_cases):
        html += f"<div class='test-case mb-4'>"
        html += f"<h4>测试用例 #{i+1}: {test_case.get('description', '无描述')}</h4>"
        
        # 测试步骤
        html += "<div class='test-steps mb-3'>"
        html += "<h5>测试步骤:</h5>"
        html += "<ol>"
        for step in test_case.get('test_steps', []):
            html += f"<li>{step}</li>"
        html += "</ol>"
        html += "</div>"
        
        # 预期结果
        html += "<div class='expected-results'>"
        html += "<h5>预期结果:</h5>"
        html += "<ol>"
        for result in test_case.get('expected_results', []):
            html += f"<li>{result}</li>"
        html += "</ol>"
        html += "</div>"
        
        html += "</div>"
    
    return html


# @login_required 先屏蔽登录
def knowledge_view(request):
    """知识库管理页面"""
    return render(request, 'knowledge.html')

# @login_required 先屏蔽登录
@require_http_methods(["POST"])
def add_knowledge(request):
    """添加知识条目"""
    try:
        data = json.loads(request.body)
        title = data.get('title')
        content = data.get('content')
        
        if not title or not content:
            return JsonResponse({
                'success': False,
                'message': '标题和内容不能为空'
            })
        
        # 添加到知识库
        knowledge_id = knowledge_service.add_knowledge(title, content)
        
        return JsonResponse({
            'success': True,
            'message': '知识条目添加成功',
            'knowledge_id': knowledge_id
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

# @login_required 先屏蔽登录
def knowledge_list(request):
    """获取知识库列表"""
    try:
        knowledge_items = KnowledgeBase.objects.all().order_by('-created_at')
        
        items = []
        for item in knowledge_items:
            items.append({
                'id': item.id,
                'title': item.title,
                'content': item.content,
                'created_at': item.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'knowledge_items': items
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

# @login_required 先屏蔽登录
@require_http_methods(["POST"])
def search_knowledge(request):
    """搜索知识库"""
    try:
        data = json.loads(request.body)
        query = data.get('query')
        
        if not query:
            return JsonResponse({
                'success': False,
                'message': '搜索关键词不能为空'
            })
        
        # 搜索知识库
        query_embedding = knowledge_service.embedder.get_embeddings(query)[0]
        logger.info(f"查询文本: '{query}', 向量维度: {len(query_embedding)}, 前5个维度: {query_embedding[:5]}")
        results = knowledge_service.search_knowledge(query)
        
        return JsonResponse({
            'success': True,
            'results': results
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@csrf_exempt
def upload_single_file(request):
    """处理文件上传的视图函数"""
    if request.method == 'GET':
        return render(request, 'upload.html')
    elif request.method == 'POST':
        if 'single_file' in request.FILES:  # 修改这里匹配前端的 name 属性
            uploaded_file = request.FILES['single_file']  # 修改这里匹配前端的 name 属性
            
            # 统一使用 MEDIA_ROOT 配置
            upload_dir = settings.MEDIA_ROOT
            file_path = os.path.join(upload_dir, uploaded_file.name)
            
            # 检查文件是否存在，如果存在则覆盖
            is_overwrite = False
            if os.path.exists(file_path):
                logger.info(f"检测到同名文件存在，将进行覆盖: {file_path}")
                is_overwrite = True
                
                # 1. 删除向量数据库中的旧记录
                try:
                    knowledge_service.vector_store.delete_by_source(file_path)
                    logger.info("成功删除旧的向量记录")
                except Exception as e:
                    logger.error(f"删除旧向量记录失败: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'error': f'覆盖文件时删除旧数据失败: {str(e)}'
                    })
                
                # 2. 删除旧文件
                try:
                    os.remove(file_path)
                    logger.info("成功删除旧文件")
                except Exception as e:
                    logger.error(f"删除旧文件失败: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'error': f'删除旧文件失败: {str(e)}'
                    })
                
            try:
                # 1. 接收文件
                logger.info(f"Uploaded file: {uploaded_file}")
                if not uploaded_file:
                    return JsonResponse({'success': False, 'error': '未接收到文件'})
                
                file_categories = {
                    "CSV": [".csv"],
                    "E-mail": [".eml", ".msg", ".p7s"],
                    "EPUB": [".epub"],
                    "Excel": [".xls", ".xlsx"],
                    "HTML": [".html"],
                    "Image": [".bmp", ".heic", ".jpeg", ".png", ".tiff"],
                    "Markdown": [".md"],
                    "Org Mode": [".org"],
                    "Open Office": [".odt"],
                    "PDF": [".pdf"],
                    "Plain text": [".txt"],
                    "PowerPoint": [".ppt", ".pptx"],
                    "reStructured Text": [".rst"],
                    "Rich Text": [".rtf"],
                    "TSV": [".tsv"],
                    "Word": [".doc", ".docx"],
                    "XML": [".xml"]
                }
                file_type = os.path.splitext(uploaded_file.name)[1]
                logger.info(f"上传文件类型: {file_type}")
                logger.info(f"上传文件名: {uploaded_file.name}")
                
                if not file_type:
                    logger.error("文件没有扩展名")
                    return JsonResponse({'success': False, 'error': '文件必须包含扩展名'})
                
                # 获取所有支持的文件扩展名
                supported_extensions = [ext.lower() for exts in file_categories.values() for ext in exts]

                if file_type not in supported_extensions:
                    return JsonResponse({'success': False, 'error': '不支持的文件类型'})
                
                # 2. 保存文件到统一目录
                os.makedirs(upload_dir, exist_ok=True)
                with open(file_path, 'wb+') as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)
                logger.info(f"文件保存成功, 文件保存路径: {file_path}")

                # 3. 处理文件
                chunks = process_singel_file(file_path)  # 获取原始数据和文本
                if not chunks:
                    return JsonResponse({'success': False, 'error': '文件中无有效内容'})

                # 提取所有chunk.text并记录日志
                if isinstance(chunks, list):
                    # 直接从chunks中提取text属性
                    text_contents = []
                    for i, chunk in enumerate(chunks):
                        if hasattr(chunk, 'text'):
                            text_contents.append(str(chunk.text))
                        else:
                            text_contents.append(str(chunk))
                
                    logger.info(f"共提取了 {len(text_contents)} 个文本内容")
                else:
                    # 单一文本块的情况
                    if hasattr(chunks, 'text'):
                        text_contents = [str(chunks.text)]
                    else:
                        text_contents = [str(chunks)]
                    logger.info(f"提取了单个文本内容: {text_contents[0][:100]}...")

                # 直接生成所有文本内容的向量
                logger.info("开始生成向量")
                start_time = datetime.now()

                try:
                    # 直接为所有文本内容生成向量
                    all_embeddings = knowledge_service.embedder.get_embeddings(texts=text_contents, show_progress_bar=False)
                    logger.info(f"成功生成 {len(all_embeddings)} 个向量")
                    
                    # 确保embeddings是列表格式
                    embeddings_list = []
                    for emb in all_embeddings:
                        if hasattr(emb, 'tolist'):
                            emb = emb.tolist()
                        embeddings_list.append(emb)
                    
                    # 准备插入数据
                    data_to_insert = []
                    for i in range(len(text_contents)):
                        item = {
                            "embedding": embeddings_list[i],  # 单个embedding向量
                            "content": text_contents[i],      # 文本内容
                            "metadata": '{}',                 # 元数据
                            "source": file_path,              # 来源
                            "doc_type": file_type,            # 文档类型
                            "chunk_id": f"{hashlib.md5(os.path.basename(file_path).encode()).hexdigest()[:10]}_{i:04d}",  # 块ID
                            "upload_time": datetime.now().isoformat()  # 上传时间
                        }
                        data_to_insert.append(item)
                    
                    # 插入数据到Milvus
                    logger.info(f"开始往milvus中插入 {len(data_to_insert)} 条数据")
                    knowledge_service.vector_store.add_data(data_to_insert)
                    logger.info("数据插入完成")
                    
                    total_time = (datetime.now() - start_time).total_seconds()
                    logger.info(f"向量生成和插入完成，总耗时: {total_time:.2f} 秒")
                    
                    return JsonResponse({
                        'success': True, 
                        'count': len(text_contents),
                        'message': f'成功{"覆盖" if is_overwrite else "导入"}文件到知识库'
                    })
                    
                except Exception as e:
                    logger.error(f"生成或插入向量时出错: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'success': False, 
                        'error': str(e)
                    })
                
            except Exception as e:
                logger.error(f"处理上传文件时出错: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False, 
                    'error': str(e)
                })
            finally:
                # 清理临时文件（注释掉，因为现在保存的是正式文件）
                # if os.path.exists(file_path):
                #     os.remove(file_path)
                pass
        else:
            return JsonResponse({
                'success': False,
                'error': '未接收到文件'
            })
    
    return JsonResponse({
        'success': False,
        'error': '不支持的请求方法'
    })


# ==================== 系统管理API ====================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def system_list(request):
    """获取系统列表或创建新系统"""
    try:
        if request.method == 'GET':
            # 获取查询参数
            name = request.GET.get('name', '')
            code = request.GET.get('code', '')
            status = request.GET.get('status', '')
            
            # 构建查询
            queryset = System.objects.all()
            
            if name:
                queryset = queryset.filter(name__icontains=name)
            if code:
                queryset = queryset.filter(code__icontains=code)
            if status:
                queryset = queryset.filter(status=status)
            
            # 按创建时间排序
            queryset = queryset.order_by('-created_at')
            
            systems = []
            for system in queryset:
                systems.append({
                    'id': system.id,
                    'name': system.name,
                    'code': system.code,
                    'description': system.description,
                    'status': system.status,
                    'status_display': dict(System.SYSTEM_STATUS_CHOICES).get(system.status, system.status),
                    'created_at': system.created_at.isoformat(),
                    'updated_at': system.updated_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'systems': systems
            })
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            name = data.get('name')
            code = data.get('code')
            description = data.get('description', '')
            
            # 验证必填字段
            if not name or not code:
                return JsonResponse({
                    'success': False,
                    'message': '系统名称和编码不能为空'
                })
            
            # 验证唯一性
            if System.objects.filter(name=name).exists():
                return JsonResponse({
                    'success': False,
                    'message': '系统名称已存在'
                })
            
            if System.objects.filter(code=code).exists():
                return JsonResponse({
                    'success': False,
                    'message': '系统编码已存在'
                })
            
            # 创建系统
            system = System.objects.create(
                name=name,
                code=code,
                description=description,
                status='active'
            )
            
            return JsonResponse({
                'success': True,
                'message': '系统创建成功',
                'system': {
                    'id': system.id,
                    'name': system.name,
                    'code': system.code,
                    'description': system.description,
                    'status': system.status
                }
            })
    
    except Exception as e:
        logger.error(f"系统管理API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def system_detail(request, system_id):
    """获取、更新或删除单个系统"""
    try:
        system = System.objects.get(id=system_id)
        
        if request.method == 'GET':
            return JsonResponse({
                'success': True,
                'system': {
                    'id': system.id,
                    'name': system.name,
                    'code': system.code,
                    'description': system.description,
                    'status': system.status,
                    'status_display': dict(System.SYSTEM_STATUS_CHOICES).get(system.status, system.status),
                    'created_at': system.created_at.isoformat(),
                    'updated_at': system.updated_at.isoformat(),
                }
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            name = data.get('name')
            code = data.get('code')
            description = data.get('description')
            status = data.get('status')
            
            # 验证唯一性（排除当前记录）
            if name and name != system.name and System.objects.filter(name=name).exists():
                return JsonResponse({
                    'success': False,
                    'message': '系统名称已存在'
                })
            
            if code and code != system.code and System.objects.filter(code=code).exists():
                return JsonResponse({
                    'success': False,
                    'message': '系统编码已存在'
                })
            
            # 更新字段
            if name:
                system.name = name
            if code:
                system.code = code
            if description is not None:
                system.description = description
            if status:
                system.status = status
            
            system.save()
            
            return JsonResponse({
                'success': True,
                'message': '系统更新成功',
                'system': {
                    'id': system.id,
                    'name': system.name,
                    'code': system.code,
                    'description': system.description,
                    'status': system.status
                }
            })
        
        elif request.method == 'DELETE':
            # 检查是否有关联数据
            if system.test_cases.exists() or system.test_plans.exists() or system.requirements.exists():
                return JsonResponse({
                    'success': False,
                    'message': '该系统存在关联数据，无法删除'
                })
            
            system.delete()
            return JsonResponse({
                'success': True,
                'message': '系统删除成功'
            })
    
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"系统详情API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def system_search(request):
    """模糊搜索系统"""
    try:
        keyword = request.GET.get('keyword', '')
        
        if not keyword:
            return JsonResponse({
                'success': False,
                'message': '搜索关键词不能为空'
            })
        
        systems = System.objects.filter(
            models.Q(name__icontains=keyword) | 
            models.Q(code__icontains=keyword)
        ).filter(status='active')[:10]
        
        results = []
        for system in systems:
            results.append({
                'id': system.id,
                'name': system.name,
                'code': system.code,
                'description': system.description
            })
        
        return JsonResponse({
            'success': True,
            'results': results
        })
    
    except Exception as e:
        logger.error(f"系统搜索API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def system_stats(request):
    """获取系统统计信息"""
    try:
        total = System.objects.count()
        active = System.objects.filter(status='active').count()
        inactive = System.objects.filter(status='inactive').count()
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total': total,
                'active': active,
                'inactive': inactive
            }
        })
    
    except Exception as e:
        logger.error(f"系统统计API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# ==================== 测试计划API ====================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def test_plan_list(request):
    """获取测试计划列表或创建新测试计划"""
    try:
        if request.method == 'GET':
            system_id = request.GET.get('system_id', '')
            
            queryset = TestPlan.objects.all()
            
            if system_id:
                queryset = queryset.filter(system_id=system_id)
            
            queryset = queryset.order_by('-created_at')
            
            plans = []
            for plan in queryset:
                plans.append({
                    'id': plan.id,
                    'title': plan.title,
                    'description': plan.description,
                    'system_id': plan.system.id if plan.system else None,
                    'system_name': plan.system.name if plan.system else None,
                    'status': plan.status,
                    'status_display': dict(TestPlan.PLAN_STATUS_CHOICES).get(plan.status, plan.status),
                    'created_at': plan.created_at.isoformat(),
                    'updated_at': plan.updated_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'plans': plans
            })
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            title = data.get('title')
            description = data.get('description', '')
            system_id = data.get('system_id')
            
            if not title:
                return JsonResponse({
                    'success': False,
                    'message': '测试计划标题不能为空'
                })
            
            system = None
            if system_id:
                system = System.objects.get(id=system_id)
            
            plan = TestPlan.objects.create(
                title=title,
                description=description,
                system=system
            )
            
            return JsonResponse({
                'success': True,
                'message': '测试计划创建成功',
                'plan': {
                    'id': plan.id,
                    'title': plan.title,
                    'description': plan.description,
                    'system_id': plan.system.id if plan.system else None,
                    'system_name': plan.system.name if plan.system else None
                }
            })
    
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"测试计划API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def test_plan_detail(request, plan_id):
    """获取、更新或删除单个测试计划"""
    try:
        plan = TestPlan.objects.get(id=plan_id)
        
        if request.method == 'GET':
            return JsonResponse({
                'success': True,
                'plan': {
                    'id': plan.id,
                    'title': plan.title,
                    'description': plan.description,
                    'system_id': plan.system.id if plan.system else None,
                    'system_name': plan.system.name if plan.system else None,
                    'status': plan.status,
                    'status_display': dict(TestPlan.PLAN_STATUS_CHOICES).get(plan.status, plan.status),
                    'created_at': plan.created_at.isoformat(),
                    'updated_at': plan.updated_at.isoformat(),
                }
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            title = data.get('title')
            description = data.get('description')
            system_id = data.get('system_id')
            status = data.get('status')
            
            if title:
                plan.title = title
            if description is not None:
                plan.description = description
            if system_id:
                plan.system = System.objects.get(id=system_id)
            elif system_id == '' or system_id == None:
                plan.system = None
            if status:
                plan.status = status
            
            plan.save()
            
            return JsonResponse({
                'success': True,
                'message': '测试计划更新成功',
                'plan': {
                    'id': plan.id,
                    'title': plan.title,
                    'description': plan.description,
                    'system_id': plan.system.id if plan.system else None,
                    'system_name': plan.system.name if plan.system else None,
                    'status': plan.status
                }
            })
        
        elif request.method == 'DELETE':
            plan.delete()
            return JsonResponse({
                'success': True,
                'message': '测试计划删除成功'
            })
    
    except TestPlan.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '测试计划不存在'
        })
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"测试计划详情API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# ==================== 需求文档API ====================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def requirement_doc_list(request):
    """获取需求文档列表或创建新需求文档"""
    try:
        if request.method == 'GET':
            system_id = request.GET.get('system_id', '')
            
            queryset = RequirementDoc.objects.all()
            
            if system_id:
                queryset = queryset.filter(system_id=system_id)
            
            queryset = queryset.order_by('-created_at')
            
            docs = []
            for doc in queryset:
                docs.append({
                    'id': doc.id,
                    'title': doc.title,
                    'content': doc.content,
                    'system_id': doc.system.id if doc.system else None,
                    'system_name': doc.system.name if doc.system else None,
                    'file_path': doc.file_path,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'documents': docs
            })
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            title = data.get('title')
            content = data.get('content')
            system_id = data.get('system_id')
            file_path = data.get('file_path', '')
            
            if not title or not content:
                return JsonResponse({
                    'success': False,
                    'message': '文档标题和内容不能为空'
                })
            
            system = None
            if system_id:
                system = System.objects.get(id=system_id)
            
            doc = RequirementDoc.objects.create(
                title=title,
                content=content,
                system=system,
                file_path=file_path
            )
            
            return JsonResponse({
                'success': True,
                'message': '需求文档创建成功',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'system_id': doc.system.id if doc.system else None,
                    'system_name': doc.system.name if doc.system else None
                }
            })
    
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"需求文档API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def requirement_doc_detail(request, doc_id):
    """获取、更新或删除单个需求文档"""
    try:
        doc = RequirementDoc.objects.get(id=doc_id)
        
        if request.method == 'GET':
            return JsonResponse({
                'success': True,
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'content': doc.content,
                    'system_id': doc.system.id if doc.system else None,
                    'system_name': doc.system.name if doc.system else None,
                    'file_path': doc.file_path,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat(),
                }
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            title = data.get('title')
            content = data.get('content')
            system_id = data.get('system_id')
            
            if title:
                doc.title = title
            if content is not None:
                doc.content = content
            if system_id:
                doc.system = System.objects.get(id=system_id)
            elif system_id == '' or system_id == None:
                doc.system = None
            
            doc.save()
            
            return JsonResponse({
                'success': True,
                'message': '需求文档更新成功',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'system_id': doc.system.id if doc.system else None,
                    'system_name': doc.system.name if doc.system else None
                }
            })
        
        elif request.method == 'DELETE':
            doc.delete()
            return JsonResponse({
                'success': True,
                'message': '需求文档删除成功'
            })
    
    except RequirementDoc.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '需求文档不存在'
        })
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"需求文档详情API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# ==================== 关联查询API ====================

@csrf_exempt
@require_http_methods(["GET"])
def get_system_related_data(request, system_id):
    """获取系统关联的所有数据（需求文档、测试用例、测试计划）"""
    try:
        system = System.objects.get(id=system_id)
        
        # 获取关联的需求文档
        requirements = []
        for req in system.requirements.all()[:10]:
            requirements.append({
                'id': req.id,
                'title': req.title,
                'type': 'requirement'
            })
        
        # 获取关联的测试用例
        test_cases = []
        for tc in system.test_cases.all()[:10]:
            test_cases.append({
                'id': tc.id,
                'title': tc.title,
                'type': 'test_case'
            })
        
        # 获取关联的测试计划
        test_plans = []
        for plan in system.test_plans.all()[:10]:
            test_plans.append({
                'id': plan.id,
                'title': plan.title,
                'type': 'test_plan'
            })
        
        return JsonResponse({
            'success': True,
            'system': {
                'id': system.id,
                'name': system.name,
                'code': system.code
            },
            'related_data': {
                'requirements': requirements,
                'test_cases': test_cases,
                'test_plans': test_plans,
                'counts': {
                    'requirements': system.requirements.count(),
                    'test_cases': system.test_cases.count(),
                    'test_plans': system.test_plans.count()
                }
            }
        })
    
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"系统关联数据API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# ==================== 测试用例系统关联API ====================

@csrf_exempt
@require_http_methods(["PUT"])
def update_testcase_system(request, case_id):
    """更新测试用例的系统关联"""
    try:
        case = TestCase.objects.get(id=case_id)
        data = json.loads(request.body)
        system_id = data.get('system_id')
        
        if system_id:
            case.system = System.objects.get(id=system_id)
        else:
            case.system = None
        
        case.save()
        
        return JsonResponse({
            'success': True,
            'message': '测试用例系统关联更新成功',
            'system_id': case.system.id if case.system else None,
            'system_name': case.system.name if case.system else None
        })
    
    except TestCase.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '测试用例不存在'
        })
    except System.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '系统不存在'
        })
    except Exception as e:
        logger.error(f"测试用例系统关联API错误: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# ==================== 系统管理页面 ====================

def system_management(request):
    """系统管理页面"""
    return render(request, 'system_management.html')
