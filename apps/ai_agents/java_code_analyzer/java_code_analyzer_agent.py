"""
基于 LangChain 的测试范围分析 Agent。
使用 LangChain 的 Agent 框架进行工具编排和决策。
"""

from typing import Optional, List, Dict, Any
from .java_code_analyzer_tools import create_langchain_tools
from .prompts import JavaCodeAnalyzerPromptManager
from apps.llm.base import LLMServiceFactory
from django.conf import settings
import os
import json
import time
import logging

from .tools_callback_log import invoke_tool, log_node_start, log_node_end

from langgraph.graph import StateGraph, END


logger = logging.getLogger(__name__)


class JavaCodeAnalyzerAgent:
    """基于 LangChain 的 Java 代码分析 Agent"""
    
    def __init__(
        self,
        repo_path: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        java_analyzer_service_url: str = getattr(settings, 'JAVA_ANALYZER_SERVICE_URL'),
        max_iterations: int = None,  
        verbose: bool = True,
        llm_provider: Optional[str] = None,
    ):
        """
        初始化 Agent。
        
        Args:
            repo_path: 项目路径
            api_key: DeepSeek API 密钥（或其他兼容 OpenAI API 的密钥）
            base_url: API 基础 URL（DeepSeek: https://api.deepseek.com）
            java_analyzer_service_url: java源码分析服务URL (从settings.JAVA_ANALYZER_SERVICE_URL获取，如果未设置则使用默认值)
            max_iterations: 最大迭代次数
            verbose: 是否输出详细日志
            llm_provider: LLM提供商（deepseek/qwen），优先使用此参数
        """
        self.repo_path = repo_path
        self.verbose = verbose
        
        # 从 repo_path 推导出 project_id
        self.project_id = self._extract_project_id(repo_path)
        print("_extract_project_id函数推到出的project_id是:", self.project_id)
        
        # 初始化提示词管理器
        self.prompt_manager = JavaCodeAnalyzerPromptManager()
        
        # 优先使用传入的 llm_provider，否则使用默认配置
        llm_config = getattr(settings, 'LLM_PROVIDERS', {})
        provider = llm_provider or llm_config.get('default_provider', 'deepseek')
        provider_config = llm_config.get(provider, {})
        
        # 获取模型配置
        model = provider_config.get('model')
        self.model = model  # 保存模型名称用于显示
        
        # 从模型名称推断提供商
        provider_name = model.split('-')[0].lower()
        if 'qwen' in provider_name:
            provider_name = 'qwen'
        if 'deepseek' in provider_name:
            provider_name = 'deepseek'
        
        # 简化调用：工厂函数会自动从settings.py读取所有配置
        self.llm = LLMServiceFactory.create(provider_name)
        
        # 创建工具（传递 project_id）
        self.tools = create_langchain_tools(repo_path, java_analyzer_service_url, self.project_id)

        # LangGraph 版本不再使用 ReAct/AgentExecutor
        self.max_iterations = max_iterations

    def _get_tool_by_name(self, name: str):
        """按工具 `name` 从已注册的 LangChain tools 中获取工具实例。

        Args:
            name: 工具名称（对应 BaseTool.name）

        Returns:
            匹配的工具对象。

        Raises:
            ValueError: 未找到指定名称的工具。
        """
        for tool in self.tools:
            if getattr(tool, "name", None) == name:
                return tool
        raise ValueError(f"Tool not found: {name}")

    def _safe_json_loads(self, s: Any) -> Any:
        """尽量把字符串解析为 JSON；失败则原样返回。

        用途：工具输出/LLM 输出可能是 JSON 字符串，也可能已是 dict/list。
        """
        if isinstance(s, (dict, list)):
            return s
        if not isinstance(s, str):
            return s
        try:
            return json.loads(s)
        except Exception:
            return s

    def _merge_seeds(self, seeds_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多次 `map_hunks_to_symbols` 的 seeds 输出并去重。

        Returns:
            {"methods": [...], "classes": [...]}，其中 methods 按 (class, method, paramTypes) 去重。
        """
        merged: Dict[str, Any] = {"methods": [], "classes": []}
        seen_methods = set()
        seen_classes = set()

        for seeds in seeds_list:
            if not isinstance(seeds, dict):
                continue

            methods = seeds.get("methods") or []
            classes = seeds.get("classes") or []

            if isinstance(methods, list):
                for m in methods:
                    if not isinstance(m, dict):
                        continue
                    key = (
                        m.get("fqnClass"),
                        m.get("methodName"),
                        tuple(m.get("paramTypes") or []),
                    )
                    if key in seen_methods:
                        continue
                    seen_methods.add(key)
                    merged["methods"].append(m)

            if isinstance(classes, list):
                for c in classes:
                    if not isinstance(c, str):
                        continue
                    if c in seen_classes:
                        continue
                    seen_classes.add(c)
                    merged["classes"].append(c)

        return merged

    def _build_langgraph(self):
        """构建LangGraph工作流（确定性调用工具 + 最终LLM生成报告）。"""

        index_project = self._get_tool_by_name("index_project")
        get_index_status = self._get_tool_by_name("get_index_status")
        get_commit_info = self._get_tool_by_name("get_commit_info")
        get_changed_files_detailed = self._get_tool_by_name("get_changed_files_detailed")
        get_file_diff = self._get_tool_by_name("get_file_diff")
        map_hunks_to_symbols = self._get_tool_by_name("map_hunks_to_symbols")
        analyze_impact = self._get_tool_by_name("analyze_impact")

        def _invoke_tool(tool, args: Dict[str, Any], *, label: str) -> Any:
            return invoke_tool(logger, tool, args, label=label)

        def _log_node_start(name: str, state: Dict[str, Any]) -> float:
            return log_node_start(logger, name, state, project_id=self.project_id)

        def _log_node_end(name: str, start: float, **extra) -> None:
            return log_node_end(logger, name, start, **extra)

        def node_index(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：触发项目索引构建（index_project）。"""
            t0 = _log_node_start("index", state)
            if self.verbose:
                print("\n🧩 [LangGraph] index_project")
            out = _invoke_tool(index_project, {"project_id": self.project_id}, label="index_project")
            _log_node_end("index", t0)
            return {**state, "index_result": out}

        def node_wait_ready(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：轮询索索引状态直到 READY 或超时。"""
            t0 = _log_node_start("wait_ready", state)
            if self.verbose:
                print("\n🧩 [LangGraph] wait_index_ready")

            max_attempts = 30
            last = None
            for i in range(max_attempts):
                out = _invoke_tool(
                    get_index_status,
                    {"project_id": self.project_id},
                    label=f"get_index_status[{i+1}]",
                )
                last = out
                parsed = self._safe_json_loads(out)
                status = None
                if isinstance(parsed, dict):
                    status = parsed.get("status") or parsed.get("state")
                if self.verbose:
                    print(f"   attempt={i+1}/{max_attempts}, status={status}")
                if status == "READY":
                    break
                time.sleep(1)
            _log_node_end("wait_ready", t0, last_status=status)
            return {**state, "index_status": last}

        def node_commits(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：获取 base/new 两个 commit 的详细信息（get_commit_info）。"""
            t0 = _log_node_start("commits", state)
            if self.verbose:
                print("\n🧩 [LangGraph] get_commit_info")
            base_commit = state.get("base_commit")
            new_commit = state.get("new_commit")
            if not base_commit or not new_commit:
                raise KeyError("base_commit/new_commit missing in state")
            base_info = _invoke_tool(get_commit_info, {"commit_hash": base_commit}, label="get_commit_info.base")
            new_info = _invoke_tool(get_commit_info, {"commit_hash": new_commit}, label="get_commit_info.new")
            _log_node_end("commits", t0)
            return {**state, "base_commit_info": base_info, "new_commit_info": new_info}

        def node_changes(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：获取变更文件清单及 hunks 明细（get_changed_files_detailed）。"""
            t0 = _log_node_start("changes", state)
            if self.verbose:
                print("\n🧩 [LangGraph] get_changed_files_detailed")
            base_commit = state.get("base_commit")
            new_commit = state.get("new_commit")
            if not base_commit or not new_commit:
                raise KeyError("base_commit/new_commit missing in state")
            out = _invoke_tool(
                get_changed_files_detailed,
                {"base_commit": base_commit, "new_commit": new_commit},
                label="get_changed_files_detailed",
            )
            parsed = self._safe_json_loads(out)
            changes_count = len(parsed) if isinstance(parsed, list) else None
            _log_node_end("changes", t0, changes_count=changes_count)
            return {**state, "changed_files_detailed": out}

        def node_diff_snippets(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：为 Top 变更文件拉取 diff，并抽取 Before/After 代码片段。"""
            t0 = _log_node_start("diff_snippets", state)
            if self.verbose:
                print("\n🧩 [LangGraph] get_file_diff (snippets)")

            base_commit = state.get("base_commit")
            new_commit = state.get("new_commit")
            raw = state.get("changed_files_detailed")
            parsed = self._safe_json_loads(raw)
            if not isinstance(parsed, list):
                _log_node_end("diff_snippets", t0, selected=0)
                return {**state, "diff_snippets": {}}

            def _score(c: Dict[str, Any]) -> int:
                add = c.get("additions")
                dele = c.get("deletions")
                if isinstance(add, int) and isinstance(dele, int):
                    return add + dele
                hunks = c.get("hunks")
                if isinstance(hunks, list):
                    return len(hunks)
                return 0

            candidates = [c for c in parsed if isinstance(c, dict) and c.get("path")]
            candidates = sorted(candidates, key=_score, reverse=True)
            selected = candidates[:5]

            def _extract_before_after(diff_text: Any, *, max_lines: int = 80) -> Dict[str, str]:
                """从 unified diff 文本中抽取“变更前/变更后”两段代码。

                说明：该实现是轻量级抽取（按 +/-/空格行归并），用于向 LLM 提供可直接引用的代码片段。
                """
                text = diff_text if isinstance(diff_text, str) else str(diff_text)
                before_lines: List[str] = []
                after_lines: List[str] = []
                for line in text.splitlines():
                    if (
                        line.startswith("diff --git ")
                        or line.startswith("index ")
                        or line.startswith("--- ")
                        or line.startswith("+++ ")
                        or line.startswith("@@")
                    ):
                        continue
                    if line.startswith("-") and not line.startswith("---"):
                        before_lines.append(line[1:])
                        continue
                    if line.startswith("+") and not line.startswith("+++"):
                        after_lines.append(line[1:])
                        continue
                    if line.startswith(" "):
                        before_lines.append(line[1:])
                        after_lines.append(line[1:])
                        continue
                if len(before_lines) > max_lines:
                    before_lines = before_lines[:max_lines]
                if len(after_lines) > max_lines:
                    after_lines = after_lines[:max_lines]
                return {
                    "before": "\n".join(before_lines).strip(),
                    "after": "\n".join(after_lines).strip(),
                }

            snippets: Dict[str, Any] = {}
            for item in selected:
                path = str(item.get("path"))
                try:
                    diff_text = _invoke_tool(
                        get_file_diff,
                        {
                            "base_commit": base_commit,
                            "new_commit": new_commit,
                            "file_path": path,
                            "offset": 0,
                            "limit": 200,
                        },
                        label=f"get_file_diff:{path}",
                    )
                    snippets[path] = _extract_before_after(diff_text)
                except Exception as e:
                    snippets[path] = {"before": "", "after": f"Error: {e}"}

            _log_node_end("diff_snippets", t0, selected=len(selected))
            return {**state, "diff_snippets": snippets}

        def node_map_symbols(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：将变更 hunks 映射到 Java 符号（类/方法），并汇总 seeds。"""
            t0 = _log_node_start("map_symbols", state)
            if self.verbose:
                print("\n🧩 [LangGraph] map_hunks_to_symbols (batched)")

            raw = state.get("changed_files_detailed")
            parsed = self._safe_json_loads(raw)
            if not isinstance(parsed, list):
                return {**state, "map_results": [], "seeds": {"methods": [], "classes": []}}

            java_changes = [c for c in parsed if isinstance(c, dict) and str(c.get("path", "")).endswith(".java")]
            batch_size = 15
            map_outputs: List[Any] = []
            seeds_candidates: List[Dict[str, Any]] = []

            for i in range(0, len(java_changes), batch_size):
                batch = java_changes[i : i + batch_size]
                changes_json = json.dumps(batch, ensure_ascii=False)
                out = _invoke_tool(
                    map_hunks_to_symbols,
                    {"changes": changes_json, "project_id": self.project_id},
                    label=f"map_hunks_to_symbols[{i//batch_size+1}]",
                )
                map_outputs.append(out)
                out_parsed = self._safe_json_loads(out)

                # 兼容多种返回结构：直接 methods/classes，或嵌套在 data/result 中
                if isinstance(out_parsed, dict):
                    if isinstance(out_parsed.get("methods"), list) or isinstance(out_parsed.get("classes"), list):
                        seeds_candidates.append({
                            "methods": out_parsed.get("methods") or [],
                            "classes": out_parsed.get("classes") or [],
                        })
                    else:
                        for k in ("data", "result", "seeds"):
                            inner = out_parsed.get(k)
                            if isinstance(inner, dict) and (isinstance(inner.get("methods"), list) or isinstance(inner.get("classes"), list)):
                                seeds_candidates.append({
                                    "methods": inner.get("methods") or [],
                                    "classes": inner.get("classes") or [],
                                })
                                break

            merged_seeds = self._merge_seeds(seeds_candidates)
            _log_node_end(
                "map_symbols",
                t0,
                java_files=len(java_changes),
                methods=len(merged_seeds.get("methods") or []),
                classes=len(merged_seeds.get("classes") or []),
            )
            return {**state, "map_results": map_outputs, "seeds": merged_seeds}

        def node_impact(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：基于 seeds 调用 analyze_impact 计算调用链影响范围。"""
            t0 = _log_node_start("impact", state)
            if self.verbose:
                print("\n🧩 [LangGraph] analyze_impact")

            seeds = state.get("seeds") or {"methods": [], "classes": []}
            seeds_json = json.dumps(seeds, ensure_ascii=False)
            out = _invoke_tool(
                analyze_impact,
                {
                    "seeds": seeds_json,
                    "project_id": self.project_id,
                    "depth": 3,
                    "direction": "both",
                    "include_edges": True,
                },
                label="analyze_impact",
            )
            _log_node_end("impact", t0)
            return {**state, "impact_result": out}

        def node_render(state: Dict[str, Any]) -> Dict[str, Any]:
            """节点：汇总事实数据并调用 LLM 生成最终 Markdown 报告。

            约束：该节点不再调用任何工具，只对已采集到的事实做格式化与裁剪。
            """
            t0 = _log_node_start("render", state)
            if self.verbose:
                print("\n🧩 [LangGraph] render_markdown")

            # 将核心数据喂给LLM生成Markdown报告（此阶段不再调用工具）
            base_info = state.get("base_commit_info", "")
            new_info = state.get("new_commit_info", "")
            changes = state.get("changed_files_detailed", "")
            map_results = state.get("map_results", [])
            impact = state.get("impact_result", "")
            diff_snippets = state.get("diff_snippets") or {}

            # 控制输入长度，避免把超大JSON直接塞进prompt导致不稳定
            def clip(x: Any, limit: int = 20000) -> str:
                if x is None:
                    return ""
                if not isinstance(x, str):
                    try:
                        x = json.dumps(x, ensure_ascii=False)
                    except Exception:
                        x = str(x)
                return x if len(x) <= limit else x[:limit] + "\n...<truncated>"

            def safe_parse_json(value: Any) -> Any:
                try:
                    return self._safe_json_loads(value)
                except Exception:
                    return value

            def summarize_changes(changes_value: Any) -> Dict[str, Any]:
                parsed = safe_parse_json(changes_value)
                if not isinstance(parsed, list):
                    return {
                        "total": None,
                        "java_count": None,
                        "top_files": [],
                        "raw_type": type(parsed).__name__,
                    }

                total = len(parsed)
                java_items = [c for c in parsed if isinstance(c, dict) and str(c.get("path", "")).endswith(".java")]

                def _line_count(c: Dict[str, Any]) -> int:
                    for k in ("lines_changed", "changed_lines", "changed", "additions", "deletions"):
                        v = c.get(k)
                        if isinstance(v, int):
                            return v
                    hunks = c.get("hunks")
                    if isinstance(hunks, list):
                        return len(hunks)
                    return 0

                sorted_items = sorted(
                    [c for c in parsed if isinstance(c, dict)],
                    key=_line_count,
                    reverse=True,
                )
                top = []
                for c in sorted_items[:12]:
                    top.append({
                        "path": c.get("path"),
                        "status": c.get("status") or c.get("change_type") or c.get("type"),
                        "lines_changed": _line_count(c),
                    })

                return {
                    "total": total,
                    "java_count": len(java_items),
                    "top_files": top,
                }

            def summarize_impact(impact_value: Any) -> Dict[str, Any]:
                parsed = safe_parse_json(impact_value)
                if isinstance(parsed, dict):
                    nodes = parsed.get("nodes")
                    edges = parsed.get("edges")
                    return {
                        "nodes_count": len(nodes) if isinstance(nodes, list) else None,
                        "edges_count": len(edges) if isinstance(edges, list) else None,
                        "raw_keys": list(parsed.keys())[:20],
                    }
                return {"nodes_count": None, "edges_count": None, "raw_type": type(parsed).__name__}

            changes_summary = summarize_changes(changes)
            seeds_summary = state.get("seeds") or {"methods": [], "classes": []}
            impact_summary = summarize_impact(impact)

            template = self.prompt_manager.get_system_prompt()
            if not template:
                raise ValueError("java_code_analyzer_system_prompt is empty in prompt_config.yaml")

            prompt = template.format_map({
                "repo_path": self.repo_path,
                "project_id": self.project_id,
                "base_commit": state.get("base_commit"),
                "new_commit": state.get("new_commit"),
                "summary_changed_files": json.dumps(changes_summary, ensure_ascii=False),
                "summary_seeds": json.dumps(seeds_summary, ensure_ascii=False),
                "summary_impact": json.dumps(impact_summary, ensure_ascii=False),
                "raw_base_commit_info": clip(base_info),
                "raw_new_commit_info": clip(new_info),
                "raw_changed_files_detailed": clip(changes, limit=12000),
                "raw_map_hunks_to_symbols_outputs": clip(map_results, limit=12000),
                "raw_analyze_impact_result": clip(impact, limit=12000),
                "raw_diff_snippets": clip(diff_snippets, limit=12000),
            })

            llm_out = self.llm.invoke(prompt)
            content = getattr(llm_out, "content", llm_out)
            _log_node_end("render", t0, markdown_len=len(content) if isinstance(content, str) else None)
            return {**state, "final_markdown": content}

        builder = StateGraph(dict)
        builder.add_node("index", node_index)
        builder.add_node("wait_ready", node_wait_ready)
        builder.add_node("commits", node_commits)
        builder.add_node("changes", node_changes)
        builder.add_node("diff_snippets", node_diff_snippets)
        builder.add_node("map_symbols", node_map_symbols)
        builder.add_node("impact", node_impact)
        builder.add_node("render", node_render)

        builder.set_entry_point("index")
        builder.add_edge("index", "wait_ready")
        builder.add_edge("wait_ready", "commits")
        builder.add_edge("commits", "changes")
        builder.add_edge("changes", "diff_snippets")
        builder.add_edge("diff_snippets", "map_symbols")
        builder.add_edge("map_symbols", "impact")
        builder.add_edge("impact", "render")
        builder.add_edge("render", END)

        return builder.compile()
    
    def analyze(self, base_commit: str, new_commit: str) -> Dict[str, Any]:
        '''
        分析两个 commit 之间的变更影响。
        
        Args:
            base_commit: 基准 commit
            new_commit: 新 commit
            
        Returns:
            包含分析结果的字典
        '''
        if self.verbose:
            print("="*70)
            print("🤖 开始 LangGraph 工作流分析")
            print("="*70)
            print(f"📁 项目: {self.repo_path}")
            print(f"🔄 变更: {base_commit[:8]} → {new_commit[:8]}")
            print(f"🏷️  project_id: {self.project_id}")
            print(f"🧠 模型: {getattr(self.llm, 'model_name', self.model)}")
            print("="*70)
            print()

        graph = self._build_langgraph()

        try:
            result_state = graph.invoke({
                "base_commit": base_commit,
                "new_commit": new_commit,
            })

            final_output = result_state.get("final_markdown", "")

            if self.verbose:
                print(f"\n{'='*70}")
                print("✅ LangGraph 执行完成")
                print(f"{'='*70}")
                print(f"最终输出长度: {len(final_output)} 字符")
                if final_output:
                    print(f"最终输出预览: {final_output[:200]}{'...' if len(final_output) > 200 else ''}")
                print(f"{'='*70}\n")

            return {
                "output": final_output,
                "intermediate_steps": [],
                "success": True,
                "langgraph_state": {
                    "index_result": result_state.get("index_result"),
                    "index_status": result_state.get("index_status"),
                    "base_commit_info": result_state.get("base_commit_info"),
                    "new_commit_info": result_state.get("new_commit_info"),
                    "changed_files_detailed": result_state.get("changed_files_detailed"),
                    "map_results": result_state.get("map_results"),
                    "impact_result": result_state.get("impact_result"),
                },
            }
        except Exception as e:
            error_str = str(e)
            if self.verbose:
                print(f"\n❌ Agent 执行失败: {error_str}")
            
            # 识别不同类型的错误并提供友好的提示
            if "JSONDecodeError" in error_str or "Unterminated string" in error_str:
                friendly_error = f"""## 工具调用参数格式错误

**错误原因**: LLM在生成工具调用参数时出现了格式错误，参数中包含了非法字符。

**可能原因**:
- LLM生成的JSON格式不正确
- 参数中混入了中文字符或其他特殊字符
- 字符串引号未正确闭合

**建议解决方案**:
1. 检查输入的commit哈希是否包含特殊字符
2. 尝试重新运行分析
3. 如果问题持续，可能需要调整提示词或模型参数

**原始错误**: {error_str}"""
            elif "invalid_tool_call" in error_str.lower() or "tool_calls" in error_str.lower():
                friendly_error = f"""## 工具调用失败

**错误原因**: LLM生成的工具调用格式不符合要求。

**可能原因**:
- 工具名称或参数格式错误
- 工具不存在或参数类型不匹配

**建议解决方案**:
1. 检查工具名称是否正确
2. 验证参数格式和类型
3. 重新运行分析

**原始错误**: {error_str}"""
            else:
                friendly_error = f"""## 分析执行失败

**错误原因**: {error_str}

**建议解决方案**:
1. 检查项目路径和Git仓库状态
2. 确认网络连接正常
3. 验证输入参数格式
4. 重新运行分析

如果问题持续，请联系技术支持。"""
            
            return {
                "output": friendly_error,
                "intermediate_steps": [],
                "success": False,
                "error": error_str,
                "error_type": "json_parse_error" if "JSONDecodeError" in error_str else "execution_error"
            }
    
    def _monitor_required_steps(self, tool_name: str, args: dict) -> None:
        """监控强制步骤的执行"""
        # 这个方法现在只是占位符，不执行实际的监控逻辑
        # 如果需要恢复监控功能，可以重新实现
        pass
    
    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return [tool.name for tool in self.tools]
    
    def _extract_project_id(self, repo_path: str) -> str:
        """
        从 repo_path 提取 project_id
        
        Args:
            repo_path: 项目路径
            
        Returns:
            project_id: 项目ID
        """
        # 修复点4：删除重复的settings导入（已全局导入）
        # 获取新的项目映射配置
        project_mapping = getattr(settings, 'PROJECT_ID_REPO_MAPPING', {})
        
        # 反向查找：通过路径找到 project_id
        base_dir = getattr(settings, 'JAVA_PROJECTS_BASE_DIR', '/home')
        
        for project_id in project_mapping.keys():
            expected_path = os.path.join(base_dir, project_id)
            if repo_path == expected_path or repo_path.startswith(expected_path):
                return project_id
        
        # 如果没有找到，尝试从路径中提取
        # 例如：/home/education-service -> education-service
        basename = os.path.basename(repo_path.rstrip('/'))
        return basename