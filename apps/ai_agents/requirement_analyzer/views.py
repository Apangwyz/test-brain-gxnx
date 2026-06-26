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


def _run_analysis_async(task_id: str, file_path: str, file_name: str, file_type: str):
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

        llm_service = LLMServiceFactory.create_with_fallback(agent_name="requirement_analyzer", preferred_provider=DEFAULT_PROVIDER)
        orchestrator = AnalysisOrchestrator(llm_service)
        return orchestrator.analyze(file_name, content, progress_manager)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_analysis)
            # 3 分钟超时
            TIMEOUT_SECONDS = 180
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

        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"success": False, "error": "文件不存在"})

        task_id = generate_task_id("req_analysis")
        thread = threading.Thread(
            target=_run_analysis_async,
            args=(task_id, file_path, file_name, file_type),
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
        strategy = analysis.generation_strategy

        # 组装需求描述
        combined = analysis.content_preview or ""
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
            return JsonResponse({
                "success": False,
                "error": f"该文档已{ dict(RequirementAnalysis.ADOPTION_CHOICES).get(analysis.adoption_status, analysis.adoption_status) }，无法重复操作"
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
                "error": f"该文档已{ dict(RequirementAnalysis.ADOPTION_CHOICES).get(analysis.adoption_status, analysis.adoption_status) }，无法重复操作"
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
def adopted_docs_api(request):
    """获取当前用户已采纳的需求文档列表"""
    try:
        user = request.user if request.user.is_authenticated else None
        analyses = RequirementAnalysis.objects.filter(
            adoption_status='adopted'
        ).order_by('-adopted_at')

        docs = []
        for a in analyses:
            docs.append({
                "id": a.id,
                "document_name": a.document_name,
                "quality_score": a.quality_score.get("overall_score", "N/A") if isinstance(a.quality_score, dict) else "N/A",
                "content": a.content or "",
                "content_preview": (a.content_preview or "")[:300],
                "total_sections": a.total_sections,
                "word_count": a.word_count,
                "adopted_at": a.adopted_at.isoformat() if a.adopted_at else None,
            })

        return JsonResponse({"success": True, "data": docs})
    except Exception as e:
        logger.error(f"获取已采纳文档失败: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})



@session_or_apikey_auth
@require_http_methods(["GET"])
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
        lines.append("# 需求分析报告")
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
