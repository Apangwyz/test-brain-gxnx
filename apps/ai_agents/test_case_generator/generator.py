from typing import Dict, Any, List, Optional
import json
# from langchain_core.messages import SystemMessage, HumanMessage
from apps.llm.base import BaseLLMService
from apps.knowledge.service import KnowledgeService
from .prompts import TestCaseGeneratorPrompt
from apps.utils.logger_manager import get_logger
from .test_case_schema import extract_json_str
import json
class TestCaseGeneratorAgent:
    """测试用例生成Agent"""
    
    def __init__(self, llm_service: BaseLLMService, knowledge_service: KnowledgeService, case_design_methods: List[str], case_categories: List[str], case_count: int = 10, generation_strategy: Optional[Dict] = None):
        self.llm_service = llm_service
        self.case_design_methods = case_design_methods
        self.case_categories = case_categories
        self.case_count = case_count
        self.knowledge_service = knowledge_service
        self.prompt = TestCaseGeneratorPrompt()
        self.logger = get_logger(self.__class__.__name__)  # 添加logger
        self.generation_strategy = generation_strategy or {}
    

    async def async_generate(self, input_text: str, input_type: str = "requirement") -> List[Dict[str, Any]]:
        """异步方式生成测试用例"""
        self.logger.info(f"开始生成测试用例-异步方式,进入生成测试用例的TestCaseGeneratorAgent")
        # 确定输入类型描述
        input_type_desc = "需求描述" if input_type == "requirement" else "代码片段"
        
        # 获取知识上下文
        knowledge_context = self._get_knowledge_context(input_text)
        self.logger.info(f"获取到知识库上下文: \n{'='*50}\n{knowledge_context}\n{'='*50}")
        
        # 应用生成策略覆盖
        if self.generation_strategy:
            strategy_case_count = self.generation_strategy.get("case_count")
            if strategy_case_count:
                self.case_count = strategy_case_count
            strategy_suggestions = self.generation_strategy.get("quality_suggestions", [])
            if strategy_suggestions:
                input_text += "\n\n[分析策略提示]\n" + "\n".join(f"- {s}" for s in strategy_suggestions)
        
        # 处理设计方法和测试类型
        case_design_methods = ",".join(self.case_design_methods) if self.case_design_methods else ""
        case_categories = ",".join(self.case_categories) if self.case_categories else ""
        
        # 使用新的 format_messages 方法获取消息列表
        messages = self.prompt.format_messages(
            requirements=input_text,
            case_design_methods=case_design_methods,
            case_categories=case_categories,
            case_count=self.case_count,
            knowledge_context=knowledge_context
        )
        self.logger.info(f"构建后大模型提示词+用户需求消息: \n{'='*50}\n{messages}\n{'='*50}")
        
        # 调用LLM服务
        result = None
        try:
            response = await self.llm_service.ainvoke(messages)
            result = response.content
            self.logger.info(f"LLM原始响应: \n{'='*50}\n{result}\n{'='*50}")
            
            # 尝试提取JSON部分
            json_str = self._extract_json_from_response(result)
            if not json_str:
                raise ValueError("无法从响应中提取有效的JSON数据")
                
            # 尝试解析JSON
            test_cases = json.loads(json_str)
            self.logger.info(f"_validate_test_cases处理前的用例个数: {len(test_cases)}")
            
            valid_test_cases = self._validate_test_cases(test_cases)
            if len(valid_test_cases) > self.case_count:
                self.logger.warning(f"LLM 超量生成：期望 {self.case_count} 条，但拿到 {len(valid_test_cases)} 条，自动裁剪。")
                valid_test_cases = valid_test_cases[: self.case_count]
            return valid_test_cases
            
        except Exception as e:
            raise ValueError(f"无法解析生成的测试用例: {str(e)}\n原始响应: {result if result else '未获取到响应'}")


    
    def generate(self, input_text: str, input_type: str = "requirement") -> List[Dict[str, Any]]:
        """同步方式生成测试用例"""
        self.logger.info(f"开始生成测试用例-同步方式,进入生成测试用例的TestCaseGeneratorAgent")
        # 确定输入类型描述
        input_type_desc = "需求描述" if input_type == "requirement" else "代码片段"
        
        # 获取知识上下文
        knowledge_context = self._get_knowledge_context(input_text)
        self.logger.info(f"获取到知识库上下文: \n{'='*50}\n{knowledge_context}\n{'='*50}")
        
        # 应用生成策略覆盖
        if self.generation_strategy:
            strategy_case_count = self.generation_strategy.get("case_count")
            if strategy_case_count:
                self.case_count = strategy_case_count
            strategy_suggestions = self.generation_strategy.get("quality_suggestions", [])
            if strategy_suggestions:
                input_text += "\n\n[分析策略提示]\n" + "\n".join(f"- {s}" for s in strategy_suggestions)
        
        # 处理设计方法和测试类型
        case_design_methods = ",".join(self.case_design_methods) if self.case_design_methods else ""
        case_categories = ",".join(self.case_categories) if self.case_categories else ""
        
        # 使用新的 format_messages 方法获取消息列表
        messages = self.prompt.format_messages(
            requirements=input_text,
            case_design_methods=case_design_methods,
            case_categories=case_categories,
            case_count=self.case_count,
            knowledge_context=knowledge_context
        )
        self.logger.info(f"构建后大模型提示词+用户需求消息: \n{'='*50}\n{messages}\n{'='*50}")
        
        # 调用LLM服务
        try:
            response = self.llm_service.invoke(messages)
            result = response.content
            self.logger.info(f"LLM原始响应: \n{'='*50}\n{result}\n{'='*50}")
            
            # 尝试提取JSON部分
            json_str = self._extract_json_from_response(result)
            if not json_str:
                raise ValueError("无法从响应中提取有效的JSON数据")
                
            # 尝试解析JSON
            test_cases = json.loads(json_str)
            self.logger.info(f"_validate_test_cases处理前的用例个数: {len(test_cases)}")
            
            valid_test_cases = self._validate_test_cases(test_cases)
            return valid_test_cases
            
        except Exception as e:
            raise ValueError(f"无法解析生成的测试用例: {str(e)}\n原始响应: {result}")
    
    def _get_knowledge_context(self, input_text: str) -> str:
        """获取相关知识上下文"""
        try:
            # 检查知识库服务是否可用
            if self.knowledge_service and hasattr(self.knowledge_service, 'search_relevant_knowledge'):
                knowledge = self.knowledge_service.search_relevant_knowledge(input_text)
                if knowledge:
                    return f"{knowledge}"
            else:
                self.logger.info("知识库服务未配置，跳过知识上下文获取")
        except AttributeError as e:
            # embedder或vector_store为None时的处理
            self.logger.info(f"知识库服务组件未初始化，跳过知识上下文获取: {str(e)}")
        except Exception as e:
            self.logger.warning(f"获取知识上下文失败: {str(e)}")
        return ""
    
    def _validate_test_cases(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证并修复测试用例格式（使用 Pydantic 模型校验）
        
        Args:
            test_cases: 原始测试用例列表
            
        Returns:
            验证并修复后的测试用例列表
        """
        # 尝试使用 Pydantic 模型进行结构化验证
        from .test_case_schema import GeneratedTestCase
        pydantic_valid = []
        for tc in test_cases:
            try:
                validated = GeneratedTestCase(**tc)
                pydantic_valid.append({
                    "description": validated.description,
                    "test_steps": validated.test_steps,
                    "expected_results": validated.expected_results,
                })
            except Exception:
                pass
        if pydantic_valid:
            self.logger.info(f"Pydantic 校验通过 {len(pydantic_valid)}/{len(test_cases)} 条用例")
            return pydantic_valid
        valid_test_cases = []
        required_fields = {"description", "test_steps", "expected_results"}
        
        for i, test_case in enumerate(test_cases):
            try:
                # 如果不是字典格式，跳过这个测试用例
                if not isinstance(test_case, dict):
                    self.logger.warning(f"测试用例 #{i+1} 不是字典格式，已跳过")
                    continue
                
                # 检查必要字段是否存在
                missing_fields = required_fields - set(test_case.keys())
                if missing_fields:
                    self.logger.warning(f"测试用例 #{i+1} 缺少必要字段: {missing_fields}，已跳过")
                    continue
                
                # 验证并修复字段格式
                # 1. description必须是字符串
                if not isinstance(test_case['description'], str):
                    self.logger.warning(f"测试用例 #{i+1} 的description不是字符串格式，已跳过")
                    continue
                
                # 2. test_steps必须是列表
                if not isinstance(test_case['test_steps'], list):
                    self.logger.warning(f"测试用例 #{i+1} 的test_steps格式无法修复，已跳过")
                    continue
                
                # 3. expected_results必须是列表
                if not isinstance(test_case['expected_results'], list):
                    self.logger.warning(f"测试用例 #{i+1} 的expected_results格式无法修复，已跳过")
                    continue
                
                # 确保所有字段都不为空
                if not test_case['description'].strip():
                    self.logger.warning(f"测试用例 #{i+1} 的description为空，已跳过")
                    continue
                
                if not test_case['test_steps']:
                    self.logger.warning(f"测试用例 #{i+1} 的test_steps为空，已跳过")
                    continue
                
                if not test_case['expected_results']:
                    self.logger.warning(f"测试用例 #{i+1} 的expected_results为空，已跳过")
                    continue
                # 通过所有验证，添加到有效列表
                valid_test_cases.append(test_case)
                
            except Exception as e:
                self.logger.warning(f"处理测试用例 #{i+1} 时出错: {str(e)}，已跳过")
                continue
        
        if not valid_test_cases:
            raise ValueError("没有找到任何合法的测试用例")
        
        self.logger.info(f"共处理 {len(test_cases)} 个测试用例，"
                        f"其中 {len(valid_test_cases)} 个合法")
        
        return valid_test_cases
            
    def _extract_json_from_response(self, response: str) -> str:
        """从LLM响应中健壮地提取JSON数组，支持多种格式

        Args:
            response: 原始响应字符串

        Returns:
            修复后的JSON字符串（应为合法JSON数组）
        """
        import re as _re

        if not response or not response.strip():
            return ""

        text = response.strip()

        # 1. 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
        code_block = _re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block:
            text = code_block.group(1).strip()

        # 2. 尝试直接解析为合法JSON
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # 3. 尝试提取最外层的 [...] 数组，考虑嵌套
        start = text.find("[")
        if start != -1:
            depth = 0
            end = -1
            for i in range(start, len(text)):
                if text[i] == "[" :
                    depth += 1
                elif text[i] == "]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end != -1:
                candidate = text[start:end]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    fixed = self._repair_json(candidate)
                    if fixed:
                        return fixed

        # 4. 拖尾修复：从最后一个完整对象处截断
        last_obj_end = max(text.rfind("}"), text.rfind("]"))
        if last_obj_end != -1:
            arr_start = text.find("[")
            if arr_start != -1 and arr_start < last_obj_end:
                candidate = text[arr_start:last_obj_end + 1]
                if not candidate.endswith("]"):
                    candidate += "]"
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass

        return ""

    def _repair_json(self, text: str) -> str:
        """尝试修复常见的JSON格式问题"""
        import re as _re

        fixed = text

        # 移除尾随逗号（对象或数组最后一个元素后）
        fixed = _re.sub(r",\s*([\]}])", r"\1", fixed)

        # 修复未加引号的属性名
        fixed = _re.sub(r"(?<![\s:,\w])(\w+)\s*:", r"\":", fixed)

        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            return ""
