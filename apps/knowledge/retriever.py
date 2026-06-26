"""
知识库检索器 - 为 AI Agent 提供 RAG 上下文增强

注意：MilvusVectorStore 为惰性导入，避免无 pymilvus 时模块级崩溃。
"""
import logging
from typing import Optional
from ..core.models import KnowledgeBase

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """检索知识库并格式化上下文"""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self._vector_store = None

    @property
    def vector_store(self):
        if self._vector_store is None:
            try:
                from .vector_store import MilvusVectorStore
                self._vector_store = MilvusVectorStore()
            except Exception as e:
                logger.warning(f"Milvus 不可用，RAG 检索已降级: {e}")
                self._vector_store = None
        return self._vector_store

    def retrieve(self, query: str, system_ids: Optional[list[int]] = None) -> list[dict]:
        """
        检索知识库，返回匹配结果列表
        """
        try:
            results = self.vector_store.search(query, top_k=self.top_k)
        except Exception:
            return []

        enriched = []
        for r in results:
            try:
                kb = KnowledgeBase.objects.get(vector_id=str(r.get('id', '')))
            except KnowledgeBase.DoesNotExist:
                continue
            enriched.append({
                'id': kb.id,
                'title': kb.title,
                'content': kb.content[:500],
                'score': r.get('score', 0),
            })
        return enriched

    def format_context(self, results: list[dict]) -> str:
        """将检索结果格式化为 prompt 上下文字符串"""
        if not results:
            return ""
        lines = ["【参考知识库内容】"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r['title']}] (相关度: {r['score']:.2f})")
            lines.append(f"   {r['content'][:300]}")
        return "\n".join(lines)

    def retrieve_and_format(self, query: str, system_ids: Optional[list[int]] = None) -> str:
        """检索并格式化，一步到位"""
        results = self.retrieve(query, system_ids)
        return self.format_context(results)
