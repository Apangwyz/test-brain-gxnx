import os
import json
import threading

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from apps.llm import LLMServiceFactory
from apps.llm.utils import get_agent_llm_configs
from apps.utils.logger_manager import get_logger
from apps.utils.file_transfer import word_to_markdown
from apps.utils.file_parser import parse_pdf
from apps.utils.progress_manager import TaskProgressManager, generate_task_id
from apps.utils.auth_decorators import session_or_apikey_auth
from apps.core.models import RequirementAnalysis

from .orchestrator import AnalysisOrchestrator
from .srs_generator import SRSGenerator
from .srs_prompts import SRSGeneratorPrompt
import concurrent.futures


logger = get_logger(__name__)

DEFAULT_PROVIDER, PROVIDERS = get_agent_llm_configs("requirement_analyzer")
DEFAULT_LLM_CONFIG = PROVIDERS.get(DEFAULT_PROVIDER, {})


@login_required
def requirement_analysis_page(request):
    return render(request, "requirement_analysis.html")


@session_or_apikey_auth
@require_http_methods(["POST"])
def upload_api(request):
    """文件上传 API"""
    try:
        if "file" not in request.FILES:
            return JsonResponse({"success": False, "error": "未接收到文件"})

        uploaded_file = request.FILES["file"]
        file_name = uploaded_file.name
        file_type = os.path.splitext(file_name)[1].lower()

        if file_type not in [".docx", ".pdf", ".md"]:
            return JsonResponse({"success": False, "error": "仅支持 .docx、.pdf 和 .md 格式"})

        max_size = 10 * 1024 * 1024
        if uploaded_file.size > max_size:
            return JsonResponse({"success": False, "error": "文件大小超过限制（最大10MB）"})

        save_dir = "requirement_analysis/"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file_name)

        counter = 1
        while os.path.exists(file_path):
            base, ext = os.path.splitext(file_name)
            file_path = os.path.join(save_dir, f"{base}_{counter}{ext}")
            counter += 1

        with open(file_path, "wb+") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        return JsonResponse({
            "success": True,
            "file_path": file_path,
            "file_name": file_name,
            "file_type": file_type,
        })
    except Exception as e:
        logger.error(f"上传失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": f"上传失败: {str(e)}"})


def _extract_content(file_path: str, file_type: str) -> str:
    """从文件中提取文本内容"""
    if file_type == ".docx":
        md_path = file_path.replace(".docx", ".md")
        word_to_markdown(file_path, md_path)
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    elif file_type == ".pdf":
        return parse_pdf(file_path)
    elif file_type == ".md":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _run_analysis_async(task_id: str, file_path: str, file_name: str, file_type: str, system_id: int = None):
    """异步执行分析（含 3 分钟超时保护）"""
    stages = [
        {"stage": "extracting", "title": "提取内容", "description": "从文件中提取文本..."},
        {"stage": "scoring", "title": "质量评分", "description": "评估文档质量..."},
        {"stage": "deep_analysis", "title": "深度分析", "description": "完整度/风险/冲突/可测试性分析..."},
        {"stage": "summarize", "title": "汇总报告", "description": "生成分析报告与测试策略..."},
        {"stage": "completed", "title": "完成", "description": "分析完成"},
    ]
    progress_manager = TaskProgressManager(task_id, stages)

    def _do_analysis():
        """实际的执行体"""
        progress_manager.start_stage("extracting")
        content = _extract_content(file_path, file_type)
        if not content:
            progress_manager.error_stage("extracting", "无法提取文件内容")
            return None
        progress_manager.complete_stage("extracting")

        llm_service = LLMServiceFactory.create_with_fallback(
            agent_name="requirement_analyzer", preferred_provider=DEFAULT_PROVIDER,
            timeout=60, max_retries=0
        )
        orchestrator = AnalysisOrchestrator(llm_service)
        return orchestrator.analyze(file_name, content, progress_manager, system_id)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_analysis)
            # 3 分钟超时
            TIMEOUT_SECONDS = 300
            analysis = future.result(timeout=TIMEOUT_SECONDS)

    except concurrent.futures.TimeoutError:
        logger.error(f"分析超时（{180}秒）: task_id={task_id}, file={file_name}")
        progress_manager.error_stage("completed", f"分析超时（超过{180}秒），请检查 LLM 服务状态或稍后重试")
    except Exception as e:
        logger.error(f"分析过程出错: {str(e)}", exc_info=True)
        progress_manager.error_stage("completed", f"分析失败: {str(e)}")


@session_or_apikey_auth
@require_http_methods(["POST"])
def analyze_api(request):
    """开始分析 API"""
    try:
        data = json.loads(request.body)
        file_path = data.get("file_path")
        file_name = data.get("file_name")
        file_type = data.get("file_type", os.path.splitext(file_name)[1].lower())
        system_id = data.get("system_id")

        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"success": False, "error": "文件不存在"})

        task_id = generate_task_id("req_analysis")
        thread = threading.Thread(
            target=_run_analysis_async,
            args=(task_id, file_path, file_name, file_type, system_id),
            daemon=True,
        )
        thread.start()

        return JsonResponse({"success": True, "task_id": task_id})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "无效的JSON数据"})
    except Exception as e:
        logger.error(f"分析请求处理失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def analysis_result_api(request, analysis_id: int):
    """获取分析结果 API"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        return JsonResponse({
            "success": True,
            "data": {
                "id": analysis.id,
                "document_name": analysis.document_name,
                "quality_score": analysis.quality_score,
                "completeness": analysis.completeness,
                "consistency": analysis.consistency,
                "risk_identification": analysis.risk_identification,
                "category_stats": analysis.category_stats,
                "testability": analysis.testability,
                "generation_strategy": analysis.generation_strategy,
                "total_sections": analysis.total_sections,
                "word_count": analysis.word_count,
                "system_id": analysis.system_id,
                "adoption_status": analysis.adoption_status,
                "adopted_at": analysis.adopted_at.isoformat() if analysis.adopted_at else None,
                "srs_content": analysis.srs_content,
                "srs_generated_at": analysis.srs_generated_at.isoformat() if analysis.srs_generated_at else None,
                "srs_adoption_status": analysis.srs_adoption_status,
                "srs_adopted_at": analysis.srs_adopted_at.isoformat() if analysis.srs_adopted_at else None,
                "system_name": analysis.system.name if analysis.system else None,
                                "system_id": analysis.system_id,
                "system_name": analysis.system.name if analysis.system else None,
                "created_at": analysis.created_at.isoformat(),
            }
        })
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"获取分析结果失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def latest_result_api(request):
    """获取最近一次分析结果 API（供前端 fallback 使用）"""
    try:
        analysis = RequirementAnalysis.objects.order_by("-created_at").first()
        if not analysis:
            return JsonResponse({"success": False, "error": "暂无分析记录"})
        return JsonResponse({
            "success": True,
            "data": {
                "id": analysis.id,
                "document_name": analysis.document_name,
                "quality_score": analysis.quality_score,
                "completeness": analysis.completeness,
                "consistency": analysis.consistency,
                "risk_identification": analysis.risk_identification,
                "category_stats": analysis.category_stats,
                "testability": analysis.testability,
                "generation_strategy": analysis.generation_strategy,
                "total_sections": analysis.total_sections,
                "word_count": analysis.word_count,
                                "system_id": analysis.system_id,
                "adoption_status": analysis.adoption_status,
                "adopted_at": analysis.adopted_at.isoformat() if analysis.adopted_at else None,
                "system_name": analysis.system.name if analysis.system else None,
                "created_at": analysis.created_at.isoformat(),
            }
        })
    except Exception as e:
        logger.error(f"获取最近分析结果失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def generate_from_analysis_api(request):
    """
    基于分析结果生成测试用例（增强版联动）
    接收 analysis_id，获取分析记录中的 strategy 参数传入 test_case_generator
    """
    try:
        data = json.loads(request.body)
        analysis_id = data.get("analysis_id")

        if not analysis_id:
            return JsonResponse({"success": False, "error": "缺少 analysis_id"})

        analysis = RequirementAnalysis.objects.get(id=analysis_id)

        # 检查是否有关联的已采纳 SRS
        if not analysis.srs_content or analysis.srs_adoption_status != 'adopted':
            return JsonResponse({
                "success": False,
                "error": "该需求文档尚未生成并采纳对应的 SRS，请先生成并采纳 SRS 后再生成测试用例"
            })

        strategy = analysis.generation_strategy

        # 组装需求描述（BRD + SRS 内容合并）
        brd_content = analysis.content or analysis.content_preview or ""
        srs_content_text = ""
        if analysis.srs_content:
            try:
                # 将结构化 SRS 转换为文本描述
                srs_data = analysis.srs_content
                parts = []
                # 引言
                intro = srs_data.get("introduction", {})
                if isinstance(intro, dict):
                    for v in intro.values():
                        if isinstance(v, str) and v.strip():
                            parts.append(v)
                # 总体描述
                overall = srs_data.get("overall_description", {})
                if isinstance(overall, dict):
                    for v in overall.values():
                        if isinstance(v, str) and v.strip():
                            parts.append(v)
                # 功能需求
                fr_list = srs_data.get("functional_requirements", [])
                if isinstance(fr_list, list):
                    for fr in fr_list:
                        if isinstance(fr, dict):
                            fr_text = f"【{fr.get('id','')}】{fr.get('name','')}（{fr.get('module','')}，优先级：{fr.get('priority','')}）：{fr.get('description','')}"
                            parts.append(fr_text)
                # 非功能需求
                nfr = srs_data.get("non_functional_requirements", {})
                if isinstance(nfr, dict):
                    for v in nfr.values():
                        if isinstance(v, str) and v.strip():
                            parts.append(v)
                # 外部接口
                ext = srs_data.get("external_interfaces", {})
                if isinstance(ext, dict):
                    for v in ext.values():
                        if isinstance(v, str) and v.strip():
                            parts.append(v)
                # 数据需求
                data_req = srs_data.get("data_requirements", {})
                if isinstance(data_req, dict):
                    for v in data_req.values():
                        if isinstance(v, str) and v.strip():
                            parts.append(v)

                srs_content_text = "\n".join(parts)
            except Exception:
                import json
                srs_content_text = json.dumps(analysis.srs_content, ensure_ascii=False, indent=2)

        combined_parts = []
        if brd_content.strip():
            combined_parts.append("=== 业务需求文档（BRD）内容 ===")
            combined_parts.append(brd_content.strip())
        if srs_content_text.strip():
            combined_parts.append("\n=== 软件需求规格说明书（SRS）内容 ===")
            combined_parts.append(srs_content_text.strip())

        combined = "\n".join(combined_parts)
        if not combined.strip():
            return JsonResponse({"success": False, "error": "分析记录内容为空"})

        from apps.ai_agents.test_case_generator.progress_manager import create_progress_manager
        from apps.ai_agents.test_case_generator.task_executor import submit_generation_task
        from apps.ai_agents.test_case_generator.views import _generate_test_cases_async

        progress_manager = create_progress_manager()
        task_id = progress_manager.task_id

        case_count = strategy.get("case_count", 15) if isinstance(strategy, dict) else 15

        submit_generation_task(
            task_id=task_id,
            requirements=combined,
            llm_provider=DEFAULT_PROVIDER,
            case_design_methods=[],
            case_categories=[],
            case_count=case_count,
            system_id=analysis.system_id,
            generator_func=_generate_test_cases_async,
        )

        return JsonResponse({
            "success": True,
            "task_id": task_id,
            "message": f"基于分析结果生成 {case_count} 条测试用例（策略：高风险区域优先覆盖）",
        })

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"生成用例失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def adopt_document_api(request, analysis_id: int):
    """采纳需求文档：标记为已采纳并加入知识库"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if analysis.adoption_status != 'pending':
            status_label = dict(RequirementAnalysis.ADOPTION_CHOICES).get(analysis.adoption_status, analysis.adoption_status)
            hint = ''
            if analysis.adoption_status == 'adopted':
                hint = '，该文档已在「已采纳的需求文档」列表中，请勿重复操作'
            elif analysis.adoption_status == 'rejected':
                hint = '，该文档已被拒绝，请先「重新提交」后再操作'
            return JsonResponse({
                "success": False,
                "error": f"该文档当前状态为「{status_label}」{hint}"
            })

        analysis.adoption_status = 'adopted'
        analysis.adoption_reviewer = request.user if request.user.is_authenticated else None
        analysis.adopted_at = timezone.now()
        analysis.save()

        # 加入知识库
        knowledge_added = False
        try:
            from apps.knowledge.service import KnowledgeService
            ks = KnowledgeService()
            ks.add_knowledge(
                title=analysis.document_name,
                content=analysis.content_preview or ""
            )
            knowledge_added = True
        except Exception as kb_err:
            logger.warning(f"知识库添加失败（不影响采纳）: {str(kb_err)}")

        return JsonResponse({
            "success": True,
            "data": {
                "id": analysis.id,
                "adoption_status": "adopted",
                "knowledge_base_added": knowledge_added,
            },
            "message": "需求文档已采纳" + ("并加入知识库" if knowledge_added else "，但知识库入库失败（服务不可用）"),
        })

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"采纳失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def reject_document_api(request, analysis_id: int):
    """拒绝需求文档"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if analysis.adoption_status != 'pending':
            return JsonResponse({
                "success": False,
                "error": f"该文档当前状态为「{ dict(RequirementAnalysis.ADOPTION_CHOICES).get(analysis.adoption_status, analysis.adoption_status) }」，无法重复操作"
            })

        analysis.adoption_status = 'rejected'
        analysis.adoption_reviewer = request.user if request.user.is_authenticated else None
        analysis.adopted_at = timezone.now()
        analysis.save()

        return JsonResponse({
            "success": True,
            "message": "需求文档已拒绝",
        })

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"拒绝失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def adopted_srs_api(request):
    """获取已采纳 SRS 的列表"""
    try:
        analyses = RequirementAnalysis.objects.filter(
            srs_adoption_status='adopted'
        ).order_by('-srs_adopted_at')

        docs = []
        for a in analyses:
            docs.append({
                "id": a.id,
                "document_name": a.document_name,
                "quality_score": a.quality_score.get("overall_score", "N/A") if isinstance(a.quality_score, dict) else "N/A",
                "content_preview": (a.content_preview or "")[:200],
                "total_sections": a.total_sections,
                "word_count": a.word_count,
                "system_id": a.system_id,
                "system_name": a.system.name if a.system else None,
                "srs_adopted_at": a.srs_adopted_at.isoformat() if a.srs_adopted_at else None,
                "document_adopted_at": a.adopted_at.isoformat() if a.adopted_at else None,
            })

        return JsonResponse({"success": True, "data": docs})
    except Exception as e:
        logger.error(f"获取已采纳 SRS 列表失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def adopted_docs_api(request):
    """获取当前用户已采纳的需求文档列表"""
    try:
        user = request.user if request.user.is_authenticated else None
        analyses = RequirementAnalysis.objects.filter(
            adoption_status='adopted'
        ).order_by('-adopted_at')

        docs = []
        for a in analyses:
            has_srs = bool(a.srs_content)
            srs_status = a.srs_adoption_status if has_srs else None
            docs.append({
                "id": a.id,
                "document_name": a.document_name,
                "quality_score": a.quality_score.get("overall_score", "N/A") if isinstance(a.quality_score, dict) else "N/A",
                "content": a.content or "",
                "content_preview": (a.content_preview or "")[:300],
                "total_sections": a.total_sections,
                "word_count": a.word_count,
                "system_id": a.system_id,
                "system_name": a.system.name if a.system else None,
                "adopted_at": a.adopted_at.isoformat() if a.adopted_at else None,
                "has_srs": has_srs,
                "srs_adoption_status": srs_status,
                "srs_adopted_at": a.srs_adopted_at.isoformat() if a.srs_adopted_at else None,
            })

        return JsonResponse({"success": True, "data": docs})
    except Exception as e:
        logger.error(f"获取已采纳文档失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})



@session_or_apikey_auth
@require_http_methods(["POST"])
def generate_srs_api(request, analysis_id: int):
    """触发 SRS 生成（异步），支持 force 参数强制重新生成"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if analysis.adoption_status != 'adopted':
            return JsonResponse({"success": False, "error": "请先采纳需求文档后才能生成 SRS"})

        # 检查是否需要强制重新生成
        force = False
        try:
            body = json.loads(request.body) if request.body else {}
            force = body.get('force', False)
        except (json.JSONDecodeError, AttributeError):
            pass

        if analysis.srs_content and not force:
            return JsonResponse({"success": True, "message": "SRS 已存在，无需重新生成", "srs_generated": True})

        # 清除原有 SRS 内容（强制重新生成或之前生成失败时均清除）
        if analysis.srs_content:
            analysis.srs_content = {}
            analysis.srs_adoption_status = 'pending'
            analysis.srs_adopted_at = None
            analysis.srs_generated_at = None
            analysis.save(update_fields=["srs_content", "srs_adoption_status", "srs_adopted_at", "srs_generated_at"])

        task_id = generate_task_id("srs_generation")
        thread = threading.Thread(
            target=_generate_srs_async,
            args=(task_id, analysis_id),
            daemon=True,
        )
        thread.start()

        return JsonResponse({"success": True, "task_id": task_id, "message": "SRS 生成任务已启动"})

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"触发 SRS 生成失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


def _generate_srs_async(task_id: str, analysis_id: int):
    """异步执行 SRS 生成（含 3 分钟超时保护）"""
    from apps.utils.progress_manager import TaskProgressManager
    stages = [
        {"stage": "preparing", "title": "准备", "description": "准备生成环境..."},
        {"stage": "generating", "title": "生成中", "description": "AI 正在生成 SRS..."},
        {"stage": "completed", "title": "完成", "description": "SRS 生成完成"},
    ]
    progress_manager = TaskProgressManager(task_id, stages)

    def _do_generate():
        """实际执行体（供超时包装使用）"""
        progress_manager.start_stage("preparing")
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        progress_manager.complete_stage("preparing")

        progress_manager.start_stage("generating")
        llm_service = LLMServiceFactory.create_with_fallback(
            agent_name="requirement_analyzer", preferred_provider=DEFAULT_PROVIDER,
            timeout=120, max_retries=0
        )

        # 组装分析结果字典
        analysis_result = {
            "quality_score": analysis.quality_score or {},
            "category_stats": analysis.category_stats or {},
            "risk_identification": analysis.risk_identification or {},
            "completeness": analysis.completeness or {},
            "consistency": analysis.consistency or {},
            "testability": analysis.testability or {},
        }

        generator = SRSGenerator(llm_service)
        srs_data = generator.generate(analysis.content or "", analysis_result)

        # 存入数据库
        analysis.srs_content = srs_data
        analysis.srs_generated_at = timezone.now()
        analysis.save(update_fields=["srs_content", "srs_generated_at"])

        progress_manager.complete_stage("generating")
        progress_manager.set_completed(result={"analysis_id": analysis_id}, message="SRS 生成完成")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_generate)
            # 5 分钟超时（SRS 生成通常比分析快，但仍需足够时间）
            TIMEOUT_SECONDS = 300
            future.result(timeout=TIMEOUT_SECONDS)

    except concurrent.futures.TimeoutError:
        logger.error(f"SRS 生成超时（{300}秒）: task_id={task_id}, analysis_id={analysis_id}")
        progress_manager.error_stage("generating", f"SRS 生成超时（超过{300}秒），请检查 LLM 服务状态或稍后重试")
    except RequirementAnalysis.DoesNotExist:
        progress_manager.error_stage("preparing", "分析记录已被删除")
    except Exception as e:
        logger.error(f"SRS 生成失败: {str(e)}", exc_info=True)
        progress_manager.error_stage("generating", f"SRS 生成失败: {str(e)[:200]}")


@session_or_apikey_auth
@require_http_methods(["GET", "PUT"])
def srs_detail_api(request, analysis_id: int):
    """获取/更新 SRS 内容"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)

        if request.method == "GET":
            srs_content = analysis.srs_content or {}
            srs_generated_at = analysis.srs_generated_at
            return JsonResponse({
                "success": True,
                "data": {
                    "srs_content": srs_content,
                    "srs_generated_at": srs_generated_at.isoformat() if srs_generated_at else None,
                    "document_name": analysis.document_name,
                }
            })

        elif request.method == "PUT":
            data = json.loads(request.body)
            section_updates = data.get("srs_content", {})

            current_srs = analysis.srs_content or {}

            # 深度合并更新
            def deep_merge(base, updates):
                for key, val in updates.items():
                    if isinstance(val, dict) and isinstance(base.get(key), dict):
                        deep_merge(base[key], val)
                    else:
                        base[key] = val
                return base

            updated_srs = deep_merge(current_srs, section_updates)
            analysis.srs_content = updated_srs
            analysis.save(update_fields=["srs_content"])

            return JsonResponse({"success": True, "message": "SRS 已保存"})

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "无效的 JSON 数据"})
    except Exception as e:
        logger.error(f"SRS 详情操作失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})



@session_or_apikey_auth
@require_http_methods(["POST"])
def srs_adopt_api(request, analysis_id: int):
    """采纳 SRS"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if not analysis.srs_content:
            return JsonResponse({"success": False, "error": "SRS 尚未生成，无法采纳"})
        analysis.srs_adoption_status = "adopted"
        analysis.srs_adopted_at = timezone.now()
        analysis.save(update_fields=["srs_adoption_status", "srs_adopted_at"])
        return JsonResponse({"success": True, "message": "SRS 已采纳"})
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"SRS 采纳失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def srs_reject_api(request, analysis_id: int):
    """拒绝 SRS"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if not analysis.srs_content:
            return JsonResponse({"success": False, "error": "SRS 尚未生成"})
        analysis.srs_adoption_status = "rejected"
        analysis.srs_adopted_at = timezone.now()
        analysis.save(update_fields=["srs_adoption_status", "srs_adopted_at"])
        return JsonResponse({"success": True, "message": "SRS 已拒绝"})
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"SRS 拒绝失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["GET"])
def export_srs_api(request, analysis_id: int):
    """导出 SRS 为 Markdown 文件下载"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        srs_content = analysis.srs_content
        if not srs_content:
            return JsonResponse({"success": False, "error": "SRS 尚未生成"})

        generator = SRSGenerator.__new__(SRSGenerator)
        markdown = generator.srs_to_markdown(srs_content)

        safe_name = analysis.document_name.replace("/", "_").replace("\\", "_")
        ts = ""
        if hasattr(analysis.srs_generated_at, 'strftime'):
            ts = analysis.srs_generated_at.strftime('%Y%m%d_%H%M%S')
        elif hasattr(analysis.created_at, 'strftime'):
            ts = analysis.created_at.strftime('%Y%m%d_%H%M%S')
        filename = f"软件需求规格说明书_{safe_name}_{ts}.md"

        from urllib.parse import quote
        response = HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"导出 SRS 失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})





@session_or_apikey_auth
@require_http_methods(["GET"])
def my_docs_api(request):
    """获取当前用户的所有需求文档（已采纳 + 已拒绝），按状态分组"""
    try:
        analyses = RequirementAnalysis.objects.filter(
            adoption_status__in=['adopted', 'rejected']
        ).order_by('-adopted_at', '-created_at')

        docs = []
        for a in analyses:
            has_srs = bool(a.srs_content)
            srs_status = a.srs_adoption_status if has_srs else None
            docs.append({
                "id": a.id,
                "document_name": a.document_name,
                "adoption_status": a.adoption_status,
                "quality_score": a.quality_score.get("overall_score", "N/A") if isinstance(a.quality_score, dict) else "N/A",
                "content": a.content or "",
                "content_preview": (a.content_preview or "")[:300],
                "total_sections": a.total_sections,
                "word_count": a.word_count,
                "system_id": a.system_id,
                "system_name": a.system.name if a.system else None,
                "adopted_at": a.adopted_at.isoformat() if a.adopted_at else None,
                "has_srs": has_srs,
                "srs_adoption_status": srs_status,
                "srs_adopted_at": a.srs_adopted_at.isoformat() if a.srs_adopted_at else None,
            })

        return JsonResponse({"success": True, "data": docs})
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["DELETE"])
def delete_document_api(request, analysis_id: int):
    """删除需求文档记录（已采纳/已拒绝/待审核均可删除）"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        doc_name = analysis.document_name
        analysis.delete()
        logger.info(f"删除需求文档: id={analysis_id}, name={doc_name}")
        return JsonResponse({
            "success": True,
            "message": f"需求文档「{doc_name}」已删除"
        })
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"删除需求文档失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@session_or_apikey_auth
@require_http_methods(["POST"])
def resubmit_document_api(request, analysis_id: int):
    """重新提交已拒绝的需求文档：重置为待审核状态"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)
        if analysis.adoption_status != 'rejected':
            return JsonResponse({
                "success": False,
                "error": "仅已拒绝的文档可以重新提交"
            })

        analysis.adoption_status = 'pending'
        analysis.adoption_reviewer = None
        analysis.adopted_at = None
        analysis.save(update_fields=["adoption_status", "adoption_reviewer", "adopted_at"])

        logger.info(f"重新提交需求文档: id={analysis_id}, name={analysis.document_name}")
        return JsonResponse({
            "success": True,
            "message": f"需求文档「{analysis.document_name}」已重新提交，状态恢复为待审核"
        })
    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        logger.error(f"重新提交需求文档失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})

def export_report_api(request, analysis_id: int):
    """导出分析报告（Markdown 格式下载）"""
    try:
        analysis = RequirementAnalysis.objects.get(id=analysis_id)

        quality = analysis.quality_score
        if isinstance(quality, str):
            import json
            try: quality = json.loads(quality)
            except: quality = {}
        quality = quality or {}
        overall = quality.get("overall_score", "N/A")
        dims = quality.get("dimensions", {})
        dim_labels = {
            "completeness": "完整性", "clarity": "清晰度", "consistency": "一致性",
            "testability": "可测试性", "structure": "结构化"
        }

        completeness = analysis.completeness
        if isinstance(completeness, str):
            import json
            try: completeness = json.loads(completeness)
            except: completeness = {}
        completeness = completeness or {}
        consistency = analysis.consistency
        if isinstance(consistency, str):
            import json
            try: consistency = json.loads(consistency)
            except: consistency = {}
        consistency = consistency or {}
        risk = analysis.risk_identification
        if isinstance(risk, str):
            import json
            try: risk = json.loads(risk)
            except: risk = {}
        risk = risk or {}
        category_stats = analysis.category_stats
        if isinstance(category_stats, str):
            import json
            try: category_stats = json.loads(category_stats)
            except: category_stats = {}
        category_stats = category_stats or {}
        testability = analysis.testability
        if isinstance(testability, str):
            import json
            try: testability = json.loads(testability)
            except: testability = {}
        testability = testability or {}

        def sev_label(s):
            return {"high": "高", "medium": "中", "low": "低"}.get(s, s or "")

        def type_label(t):
            m = {
                "vague_description": "描述模糊", "incomplete_requirement": "需求不完整",
                "missing_business_rule": "缺少业务规则", "missing_error_handling": "缺少异常处理",
                "missing_boundary": "缺少边界条件", "contradiction": "相互矛盾",
                "duplicate": "重复定义", "duplication": "重复描述",
                "terminology": "术语不一致", "overscoped": "范围过大",
                "dependency_risk": "依赖风险", "security_risk": "安全风险",
                "performance_risk": "性能风险", "technical_risk": "技术风险",
                "technical_debt": "技术债务", "ambiguity": "表述歧义",
                "data_risk": "数据风险", "integration_risk": "集成风险",
                "design_issue": "设计问题", "requirement_gap": "需求遗漏",
            }
            return m.get(t, t or "其他")

        lines = []

        def _brd_rating(score):
            if score >= 90:
                return "优（Excellent）"
            elif score >= 80:
                return "良（Good）"
            elif score >= 60:
                return "中（Fair）"
            else:
                return "差（Poor）"

        lines.append("# 业务需求分析评分报告")
        lines.append("")
        lines.append(f"- **文档名称**: {analysis.document_name}")
        ct = analysis.created_at
        if hasattr(ct, 'strftime'):
            lines.append(f"- **分析时间**: {ct.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            lines.append(f"- **分析时间**: {ct}")
        lines.append(f"- **总章节数**: {analysis.total_sections}")
        lines.append(f"- **总字数**: {analysis.word_count}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 一、综合评分")
        lines.append("")
        lines.append(f"**综合得分**: {overall} 分")
        lines.append("")
        score_val = overall if isinstance(overall, (int, float)) else 0
        lines.append(f"**综合等级**: {_brd_rating(score_val)}")
        lines.append("")
        lines.append("### 业务需求文档（BRD）评分说明")
        lines.append("")
        lines.append("本评分基于以下六个维度对业务需求文档进行综合评估：")
        lines.append("- **完整性**：文档是否覆盖功能描述、业务流程、边界条件、异常处理等核心要素")
        lines.append("- **清晰度**：表述是否明确无歧义，业务术语是否统一")
        lines.append("- **一致性**：前后章节是否存在矛盾或重复描述")
        lines.append("- **可测试性**：需求是否能被有效验证和测试")
        lines.append("- **结构化程度**：文档是否有清晰的层次结构")
        lines.append("- **业务价值**：需求是否清晰地体现了业务目标和用户价值")
        lines.append("")
        lines.append("| 维度 | 评分 |")
        lines.append("|------|------|")
        for key, label in dim_labels.items():
            val = dims.get(key, "-")
            lines.append(f"| {label} | {val} |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 二、完整度检查")
        lines.append("")
        present = completeness.get("present_items", [])
        missing = completeness.get("missing_items", [])
        suggestions = completeness.get("suggestions", [])
        if present:
            lines.append("### ✅ 已覆盖")
            for item in present:
                lines.append(f"- {item}")
            lines.append("")
        if missing:
            lines.append("### ❌ 缺失")
            for item in missing:
                lines.append(f"- {item}")
            lines.append("")
        if suggestions:
            lines.append("### 💡 改进建议")
            for s in sorted(suggestions, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", ""), 99)):
                lines.append(f"- [{sev_label(s.get('severity', ''))}] {s.get('suggestion', '')}")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 三、一致性与冲突检测")
        lines.append("")
        conflicts = consistency.get("conflicts", [])
        if conflicts:
            for c in sorted(conflicts, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", ""), 99)):
                loc_a = (c.get("location_a") or {}).get("section", "?") if isinstance(c.get("location_a"), dict) else "?"
                loc_b = (c.get("location_b") or {}).get("section", "?") if isinstance(c.get("location_b"), dict) else "?"
                lines.append(f"- **[{sev_label(c.get('severity', ''))}]** {type_label(c.get('type', ''))}: {c.get('description', '')}")
                lines.append(f"  - 📍 {loc_a} ↔ {loc_b}")
        else:
            lines.append("✅ 未检测到明显的冲突或矛盾")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 四、风险识别")
        lines.append("")
        risk_items = risk.get("risk_items", [])
        if risk_items:
            by_type = {}
            for item in risk_items:
                t = item.get("type", "other")
                by_type.setdefault(t, []).append(item)
            for t, items in by_type.items():
                lines.append(f"### {type_label(t)}")
                for item in items:
                    lines.append(f"- [{sev_label(item.get('severity', ''))}] {item.get('description', '')}")
                    loc = (item.get("location") or {}).get("section", "") if isinstance(item.get("location"), dict) else ""
                    if loc:
                        lines.append(f"  - 📍 {loc}")
                lines.append("")
        else:
            lines.append("✅ 未识别到高风险项")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 五、需求分类统计")
        lines.append("")
        raw_categories = category_stats.get("categories", [])
        categories = raw_categories if isinstance(raw_categories, list) else list(raw_categories.values()) if isinstance(raw_categories, dict) else []
        if categories:
            lines.append("| 分类 | 数量 | 占比 |")
            lines.append("|------|------|------|")
            for cat in categories:
                if isinstance(cat, dict):
                    name = cat.get("name", "")
                    count = cat.get("count", 0)
                    pct = cat.get("percentage", "")
                else:
                    name = str(cat)
                    count = "-"
                    pct = "-"
                lines.append(f"| {name} | {count} | {pct} |")
        else:
            lines.append("暂无分类统计数据")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 六、可测试性评级")
        lines.append("")
        overall_test = testability.get("overall_rating", "")
        if overall_test:
            lines.append(f"**总体可测试性**: {overall_test}")
            lines.append("")
        items = testability.get("items", [])
        if items:
            for item in items:
                section = item.get("section", "")
                rating = item.get("rating", "")
                reason = item.get("reason", "")
                suggestion = item.get("suggestion", "")
                lines.append(f"### {section}")
                lines.append(f"- **评级**: {rating}")
                if reason:
                    lines.append(f"- **说明**: {reason}")
                if suggestion:
                    lines.append(f"- **建议**: {suggestion}")
                lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 七、生成策略")
        lines.append("")
        strategy = analysis.generation_strategy
        if isinstance(strategy, str):
            import json
            try: strategy = json.loads(strategy)
            except: strategy = {}
        strategy = strategy or {}
        if strategy:
            for key, val in strategy.items():
                lines.append(f"- **{key}**: {val}")
        else:
            lines.append("暂无生成策略数据")
        lines.append("")
        lines.append("---")
        lines.append(f"*报告由 TestBrain 需求分析系统自动生成*")

        report_content = "\n".join(lines)

        safe_name = analysis.document_name.replace("/", "_").replace("\\", "_")
        if hasattr(analysis.created_at, 'strftime'):
            ts = analysis.created_at.strftime('%Y%m%d_%H%M%S')
        else:
            ts = "unknown"
        filename = f"需求分析报告_{safe_name}_{ts}.md"

        from urllib.parse import quote
        response = HttpResponse(report_content, content_type="text/markdown; charset=utf-8")
        # RFC 5987 encoding for non-ASCII filenames
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response

    except RequirementAnalysis.DoesNotExist:
        return JsonResponse({"success": False, "error": "分析记录不存在"})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"导出报告失败: {str(e)}\n{tb}", exc_info=True)
        return JsonResponse({"success": False, "error": f"{type(e).__name__}: {str(e)}"})
