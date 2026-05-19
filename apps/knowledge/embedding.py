from typing import List, Union
from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer
import os
import time
import logging
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """嵌入模型基类"""
    
    @abstractmethod
    def get_embeddings(self, texts: Union[str, List[str]], show_progress_bar: bool = False) -> List[List[float]]:
        """获取文本的嵌入向量"""
        pass


class BGEM3Embedder(BaseEmbedder):
    """BGE-M3嵌入模型本地服务 - 针对Apple Silicon优化"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        """
        初始化BGE-M3嵌入模型
        
        Args:
            model_name: 模型名称，默认为'BAAI/bge-m3'
        """
        logger.info("正在加载BGE-M3模型...")
        self.model = SentenceTransformer(model_name)
        
    def get_embeddings(self, texts: Union[str, List[str]], show_progress_bar: bool = False) -> List[List[float]]:
        """获取文本的嵌入向量"""
        if isinstance(texts, str):
            texts = [texts]
        embeddings = self.model.encode(sentences=texts, normalize_embeddings=True, show_progress_bar=show_progress_bar)
        return embeddings.tolist()
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本之间的相似度"""
        embeddings = self.get_embeddings([text1, text2])
        similarity = np.dot(embeddings[0], embeddings[1])
        return similarity


class AliyunEmbedder(BaseEmbedder):
    """阿里云text-embedding-v4向量模型服务"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None, batch_size: int = None):
        """
        初始化阿里云嵌入模型
        
        Args:
            api_key: 阿里云API Key
            base_url: 阿里云API基础URL
            model: 模型名称
            batch_size: 每次请求的最大文本数量，阿里云限制为10条
        """
        config = getattr(settings, 'ALIYUN_EMBEDDING_CONFIG', {})
        self.api_key = api_key or config.get('api_key')
        self.base_url = base_url or config.get('base_url')
        self.model = model or config.get('model')
        # 优先使用传入的参数，其次配置，最后默认10
        self.batch_size = batch_size if batch_size is not None else config.get('batch_size', 10)
        self.embeddings_url = self.base_url  # base_url已包含完整URL
        
        if not self.api_key:
            raise ValueError("阿里云API Key未配置，请设置环境变量 QWEN_API_KEY 或在settings.py中配置")
        
        logger.info(f"阿里云嵌入模型初始化完成，模型: {self.model}, batch_size: {self.batch_size}")
    
    def _get_embedding_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入向量（单次API调用）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": texts
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.embeddings_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                embeddings = []
                for item in data.get('data', []):
                    embedding = item.get('embedding', [])
                    embeddings.append(embedding)
                
                if len(embeddings) != len(texts):
                    raise ValueError(f"返回的嵌入向量数量({len(embeddings)})与请求文本数量({len(texts)})不匹配")
                
                return embeddings
                
            except requests.exceptions.RequestException as e:
                # 打印详细错误信息
                error_detail = ""
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.text
                    except:
                        error_detail = str(e.response)
                logger.error(f"阿里云嵌入API调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                logger.error(f"错误响应详情: {error_detail}")
                logger.error(f"请求参数: model={self.model}, texts数量={len(texts)}, 首条文本长度={len(texts[0]) if texts else 0}")
                if attempt == max_retries - 1:
                    raise Exception(f"阿里云嵌入API调用失败: {str(e)}, 详情: {error_detail}")
                time.sleep(1)  # 等待1秒后重试
            except Exception as e:
                logger.error(f"解析阿里云嵌入API响应失败: {str(e)}")
                raise
    
    def get_embeddings(self, texts: Union[str, List[str]], show_progress_bar: bool = False) -> List[List[float]]:
        """
        获取文本的嵌入向量
        使用线程池并发处理，提高效率
        """
        if isinstance(texts, str):
            texts = [texts]
        
        if not texts:
            return []
        
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        logger.info(f"开始生成嵌入向量，共 {len(texts)} 条文本，分 {total_batches} 批处理")
        
        # 准备批次数据
        batches = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            batches.append((batch_num, batch))
        
        all_embeddings = [None] * len(texts)  # 预分配位置
        
        # 使用线程池并发处理，最大10并发避免触发QPS限制
        max_workers = min(10, total_batches)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_batch = {
                executor.submit(self._get_embedding_batch, batch): (batch_num, batch, idx)
                for idx, (batch_num, batch) in enumerate(batches)
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_batch):
                batch_num, batch, batch_idx = future_to_batch[future]
                try:
                    batch_embeddings = future.result()
                    # 按正确位置存放结果
                    start_idx = batch_idx * self.batch_size
                    for i, embedding in enumerate(batch_embeddings):
                        all_embeddings[start_idx + i] = embedding
                    
                    completed += 1
                    if completed % 50 == 0 or completed == total_batches:
                        logger.info(f"嵌入进度: {completed}/{total_batches} 批完成")
                        
                except Exception as e:
                    logger.error(f"第 {batch_num}/{total_batches} 批嵌入请求失败: {str(e)}")
                    raise
        
        logger.info(f"全部嵌入请求完成，共处理 {len([e for e in all_embeddings if e is not None])} 条文本")
        return all_embeddings


# 工厂函数：根据配置创建对应的嵌入模型实例
def create_embedder():
    """根据settings配置创建嵌入模型实例"""
    provider = getattr(settings, 'EMBEDDING_PROVIDER', 'local')
    
    if provider == 'aliyun':
        logger.info("使用阿里云向量模型")
        return AliyunEmbedder()
    else:
        logger.info("使用本地BGE-M3向量模型")
        return BGEM3Embedder()


# 测试
if __name__ == "__main__":
    # 设置环境变量以优化MPS性能
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
    
    # 初始化嵌入模型
    logger.info("初始化BGE-M3嵌入模型...")
    embedder = BGEM3Embedder()
    
    # 测试单个文本
    logger.info("\n测试单个文本嵌入...")
    text = "BGE-M3是一个强大的多语言嵌入模型"
    embedding = embedder.get_embeddings(text)
    logger.info(f"嵌入维度: {len(embedding[0])}")
    logger.info(f"前5个维度: {embedding[0][:5]}")
    
    # 测试多个文本
    logger.info("\n测试多个文本嵌入...")
    texts = ["你好，世界", "Hello, world", "BGE-M3支持多种语言"]
    embeddings = embedder.get_embeddings(texts)
    logger.info(f"嵌入数量: {len(embeddings)}")
    logger.info(f"嵌入维度: {len(embeddings[0])}")
    
    # 测试相似度计算
    logger.info("\n测试文本相似度...")
    text1 = "我喜欢人工智能技术"
    text2 = "AI技术非常有趣"
    text3 = "今天天气真不错"
    
    sim1 = embedder.compute_similarity(text1, text2)
    sim2 = embedder.compute_similarity(text1, text3)
    
    logger.info(f"相似文本的相似度: {sim1:.4f}")
    logger.info(f"不相似文本的相似度: {sim2:.4f}")
    
    # 测试批处理性能
    logger.info("\n测试批处理性能...")
    import time
    batch_texts = ["测试文本" + str(i) for i in range(10)]
    
    start_time = time.time()
    batch_embeddings = embedder.get_embeddings(batch_texts)
    end_time = time.time()
    
    logger.info(f"处理10个文本耗时: {end_time - start_time:.2f}秒")