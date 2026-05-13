import os
import re
import quopri
import spacy
from bs4 import BeautifulSoup
from django.conf import settings
from sentence_transformers import SentenceTransformer
from apps.utils.logger_manager import get_logger

# 尝试引入依赖
try:
    from docx import Document
except ImportError:
    Document = None

from unstructured.partition.auto import partition
from unstructured.partition.html import partition_html
from unstructured.partition.text import partition_text
from unstructured.chunking.title import chunk_by_title

logger = get_logger(__name__)

# ── 1. 强制解除全局 NLP 限制 ────────────────────────────────────────────────
try:
    # 针对中文和英文默认模型调大上限到 1000 万字符
    for lang_code in ["zh", "en"]:
        from spacy.util import get_lang_class
        lang_class = get_lang_class(lang_code)
        lang_class.max_length = 10000000
    logger.info("已成功调大 SpaCy 全局 max_length 限制至 10,000,000")
except Exception as e:
    logger.warning(f"调大 SpaCy 限制失败: {e}")

# ── 2. 嵌入模型单例 ──────────────────────────────────────────────────────────
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("BAAI/bge-m3", trust_remote_code=True)
    return _embedding_model

# ── 3. Confluence 专用终极清洗逻辑 ───────────────────────────────────────────

def clean_confluence_content(raw_content):
    """
    针对 Confluence MHTML 的高级清洗策略：
    1. 提取第一个 Boundary 块 (HTML 部分)
    2. 解码 Quoted-Printable
    3. BeautifulSoup 提取文本
    """
    initial_len = len(raw_content)
    try:
        # Step 1: 识别并提取 HTML 部分 (Multipart 处理)
        # 寻找第一个 HTML 块的开始和下一个 boundary 的结束
        html_content = raw_content
        boundary_match = re.search(r'boundary="([^"]+)"', raw_content)
        if boundary_match:
            boundary = boundary_match.group(1)
            # 分割块
            parts = raw_content.split(f"--{boundary}")
            for part in parts:
                if "Content-Type: text/html" in part:
                    # 找到 HTML 块，去掉 MIME 头
                    html_content = part.split("\r\n\r\n", 1)[-1]
                    break

        # Step 2: Quoted-Printable 解码
        decoded_bytes = quopri.decodestring(html_content.encode('utf-8'))
        decoded_content = decoded_bytes.decode('utf-8', errors='ignore')

        # Step 3: BeautifulSoup 精细化提取
        soup = BeautifulSoup(decoded_content, 'html.parser')
        
        # 彻底移除不需要的节点
        for tag in soup(["style", "script", "xml", "meta", "link", "v:imagedata", "o:SmartTagType"]):
            tag.decompose()
            
        # 移除带有大量 base64 的图片标签属性，防止被识别为文本
        for img in soup.find_all('img'):
            img.decompose()

        # Step 4: 提取文本并清理
        clean_text = soup.get_text(separator="\n")
        
        # 过滤非打印字符，保留换行
        clean_text = "".join(ch for ch in clean_text if ch.isprintable() or ch in "\n\t")
        
        # 合并连续的空白行
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text).strip()
        
        final_len = len(clean_text)
        reduction = ((initial_len - final_len) / initial_len * 100) if initial_len > 0 else 0
        
        logger.info(f"[深度预处理] 成功。原始 {initial_len} -> 现存 {final_len} (缩减率: {reduction:.2f}%)")
        return clean_text

    except Exception as e:
        logger.error(f"❌ 深度清洗失败: {e}")
        # 最后的兜底：如果解析失败，只取前 10% 的内容（通常 HTML 在开头）
        return raw_content[:int(initial_len * 0.1)]
# ── 4. 核心解析逻辑 ──────────────────────────────────────────────────────────

def process_single_word(file_path):
    """
    Word 文件解析主入口
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    is_confluence = False
    
    # 检测是否为 Confluence 格式
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(4096)
            if "Exported From Confluence" in head or "MIME-Version" in head:
                is_confluence = True
    except Exception as e:
        logger.warning(f"读取文件头失败: {e}")

    if is_confluence:
        logger.info(f"🔍 [类型检测] 确认文件为 Confluence 导出格式，启动终极清洗。")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_data = f.read()
            
            # 获取纯净文本
            pure_text = clean_confluence_content(raw_data)
            
            # 既然已经是纯净文本了，直接使用 partition_text，效率最高
            elements = partition_text(text=pure_text)
            return chunk_by_title(elements=elements, max_characters=3000, combine_text_under_n_chars=500)
        except Exception as e:
            logger.error(f"❌ Confluence 专用处理失败: {e}", exc_info=True)

    # 标准文件处理路径
    if file_ext == ".docx" and Document is not None:
        try:
            elements = partition(filename=file_path, strategy="fast")
            return chunk_by_title(elements=elements, max_characters=4000)
        except Exception as e:
            logger.warning(f"标准 docx 解析失败: {e}")

    # 其他 .doc 兜底
    elements = partition(filename=file_path, strategy="fast")
    return chunk_by_title(elements=elements, max_characters=4000)

def process_singel_file(file_path):
    """
    总入口函数
    """
    file_type = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_type in [".doc", ".docx"]:
            chunks = process_single_word(file_path)
        elif file_type in [".xlsx", ".xls"]:
            from unstructured.partition.xlsx import partition_xlsx
            elements = partition_xlsx(filename=file_path)
            chunks = chunk_by_title(elements=elements, max_characters=4000)
        elif file_type == ".pdf":
            elements = partition(filename=file_path, strategy="fast")
            chunks = chunk_by_title(elements=elements, max_characters=4000)
        else:
            elements = partition(filename=file_path, strategy="fast")
            chunks = chunk_by_title(elements=elements, max_characters=4000)

        if chunks:
            logger.info(f"✅ 解析完成: {os.path.basename(file_path)}, 最终生成 {len(chunks)} 个块")
        return chunks
    except Exception as e:
        logger.error(f"❌ 处理文件 {file_path} 时发生严重错误: {e}", exc_info=True)
        return None