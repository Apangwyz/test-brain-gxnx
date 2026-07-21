"""
知识库管理 + 文件上传视图模块
从 core/views.py 拆分而来
"""
import json
import os
import hashlib
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings

from apps.utils.auth_decorators import api_key_required, session_or_apikey_auth
from ..core.models import KnowledgeBase
from ..knowledge.service import get_knowledgeService_instance
from ..knowledge.milvus_helper import process_singel_file
from apps.utils.logger_manager import get_logger


logger = get_logger(__name__)
knowledge_service = get_knowledgeService_instance()


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------

@login_required
def knowledge_view(request):
    """知识库管理页面（含手动添加 / 文件上传 / 列表三合一）"""
    return render(request, 'knowledge.html')


# ---------------------------------------------------------------------------
# 手动添加
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@session_or_apikey_auth
def add_knowledge(request):
    """添加知识条目"""
    try:
        data = json.loads(request.body)
        title = data.get('title')
        content = data.get('content')

        if not title or not content:
            return JsonResponse({
                'success': False, 'message': '标题和内容不能为空'
            })

        knowledge_id = knowledge_service.add_knowledge(title, content)

        return JsonResponse({
            'success': True, 'message': '知识条目添加成功',
            'knowledge_id': knowledge_id
        })
    except Exception as e:
        logger.error(f"添加知识条目失败: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def upload_single_file(request):
    """处理文件上传（迁移自旧的 /upload/ 独立页面）"""
    if 'single_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': '未接收到文件'})

    uploaded_file = request.FILES['single_file']
    upload_dir = settings.MEDIA_ROOT
    file_path = os.path.join(upload_dir, uploaded_file.name)
    is_overwrite = False

    if os.path.exists(file_path):
        logger.info(f"检测到同名文件存在，将进行覆盖: {file_path}")
        is_overwrite = True
        try:
            knowledge_service.vector_store.delete_by_source(file_path)
            logger.info("成功删除旧的向量记录")
        except Exception as e:
            logger.error(f"删除旧向量记录失败: {str(e)}")
            return JsonResponse({
                'success': False, 'error': f'覆盖文件时删除旧数据失败: {str(e)}'
            })
        try:
            os.remove(file_path)
            logger.info("成功删除旧文件")
        except Exception as e:
            logger.error(f"删除旧文件失败: {str(e)}")
            return JsonResponse({
                'success': False, 'error': f'删除旧文件失败: {str(e)}'
            })

    try:
        # 保存文件
        os.makedirs(upload_dir, exist_ok=True)
        with open(file_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        logger.info(f"文件保存成功: {file_path}")

        # 解析文件内容
        file_type = os.path.splitext(uploaded_file.name)[1]
        chunks = process_singel_file(file_path)
        if not chunks:
            return JsonResponse({'success': False, 'error': '文件中无有效内容'})

        text_contents = []
        if isinstance(chunks, list):
            for chunk in chunks:
                if hasattr(chunk, 'text'):
                    text_contents.append(str(chunk.text))
                elif isinstance(chunk, str):
                    text_contents.append(chunk)
        else:
            text_contents.append(str(chunks))

        if not text_contents:
            return JsonResponse({'success': False, 'error': '未能提取文件内容'})

        # 生成向量并插入 Milvus
        from apps.knowledge.embedding import create_embedder
        embedder = create_embedder()
        start_time = datetime.now()
        embeddings_list = embedder.get_embeddings(text_contents)
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"向量生成完成，耗时: {elapsed:.2f} 秒，共 {len(embeddings_list)} 条")

        data_to_insert = []
        for i in range(len(text_contents)):
            data_to_insert.append({
                "embedding": embeddings_list[i],
                "content": text_contents[i],
                "metadata": '{}',
                "source": file_path,
                "doc_type": file_type,
                "chunk_id": f"{hashlib.md5(os.path.basename(file_path).encode()).hexdigest()[:10]}_{i:04d}",
                "upload_time": datetime.now().isoformat()
            })

        if knowledge_service.vector_store is None:
            return JsonResponse({
                'success': False,
                'error': '知识库服务未初始化：向量数据库(Milvus)未连接'
            })

        knowledge_service.vector_store.add_data(data_to_insert)
        logger.info(f"向 Milvus 插入 {len(data_to_insert)} 条数据完成")

        # 保存到 KnowledgeBase (MySQL)
        try:
            kb_title = os.path.splitext(uploaded_file.name)[0]
            KnowledgeBase.objects.create(
                title=kb_title,
                content="\n".join(text_contents)
            )
            logger.info(f"知识库条目已保存: {kb_title}")
        except Exception as e:
            logger.error(f"保存知识库条目失败: {e}")

        return JsonResponse({
            'success': True,
            'count': len(text_contents),
            'message': f'成功{"覆盖" if is_overwrite else "导入"}文件到知识库'
        })

    except Exception as e:
        logger.error(f"处理上传文件时出错: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})


# ---------------------------------------------------------------------------
# 知识库列表 + 搜索 + 删除
# ---------------------------------------------------------------------------

@api_key_required
def knowledge_list(request):
    """获取知识库列表"""
    try:
        items = KnowledgeBase.objects.all().order_by('-created_at')
        data = [{
            'id': item.id,
            'title': item.title,
            'content': item.content,
            'created_at': item.created_at.isoformat()
        } for item in items]
        return JsonResponse({'success': True, 'knowledge_items': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def search_knowledge(request):
    """搜索知识库"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        if not query:
            return JsonResponse({'success': False, 'message': '搜索关键词不能为空'})

        query_embedding = knowledge_service.embedder.get_embeddings(query)[0]
        logger.info(f"搜索: '{query}', 向量维度: {len(query_embedding)}")
        results = knowledge_service.search_knowledge(query)

        return JsonResponse({'success': True, 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_http_methods(["POST"])
def retrieve_knowledge(request):
    """知识库检索 API"""
    data = json.loads(request.body)
    query = data.get('query', '')
    top_k = data.get('top_k', 5)

    from ..knowledge.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever(top_k=top_k)
    results = retriever.retrieve(query)
    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def knowledge_list_select(request):
    """知识库文档列表（供前端选择器用，带分页+搜索）"""
    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '')
    qs = KnowledgeBase.objects.all()
    if search:
        qs = qs.filter(title__icontains=search)
    total = qs.count()
    items = qs.order_by('-created_at')[(page - 1) * 20:page * 20]
    data = [{'id': k.id, 'title': k.title, 'created_at': k.created_at.isoformat()} for k in items]
    return JsonResponse({'items': data, 'total': total, 'page': page})


@session_or_apikey_auth
@require_http_methods(["DELETE"])
def delete_knowledge(request, item_id):
    """删除知识条目（MySQL + Milvus 双删）"""
    try:
        item = get_object_or_404(KnowledgeBase, id=item_id)

        # 尝试从 Milvus 删除对应向量
        try:
            # 根据标题搜索匹配的 source（文件上传产生的记录用文件路径做 source）
            # 对于手动添加的记录，Milvus 中可能没有对应的 source 字段
            knowledge_service.vector_store.delete_by_source(item.title)
        except AttributeError:
            logger.warning("vector_store 未启用或没有 delete_by_source 方法")
        except Exception as e:
            logger.warning(f"Milvus 删除（非关键）: {e}")

        # 删除 MySQL 记录
        item.delete()
        logger.info(f"知识条目已删除: id={item_id}, title={item.title}")

        return JsonResponse({'success': True, 'message': '知识条目已删除'})
    except Exception as e:
        logger.error(f"删除知识条目失败: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})
