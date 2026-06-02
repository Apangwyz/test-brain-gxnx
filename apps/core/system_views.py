"""
系统管理 + 测试计划 + 需求文档视图模块
从 core/views.py 拆分而来
"""
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from apps.utils.auth_decorators import api_key_or_csrf_exempt, api_key_required

from ..core.models import System, TestPlan, RequirementDoc, TestCase
from apps.utils.logger_manager import get_logger


from django.contrib.auth.decorators import login_required


logger = get_logger(__name__)


# ==================== 系统管理API ====================

@api_key_or_csrf_exempt
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


@api_key_or_csrf_exempt
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


@api_key_required
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


@api_key_required
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

@api_key_or_csrf_exempt
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


@api_key_or_csrf_exempt
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

@api_key_or_csrf_exempt
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


@api_key_or_csrf_exempt
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

@api_key_required
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

@api_key_or_csrf_exempt
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

@login_required
@login_required
def system_management(request):
    """系统管理页面"""
    return render(request, 'system_management.html')

