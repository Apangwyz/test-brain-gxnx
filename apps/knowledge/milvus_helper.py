import os
import re
import quopri
from bs4 import BeautifulSoup
from django.conf import settings
from apps.utils.logger_manager import get_logger

try:
    from docx import Document
except ImportError:
    Document = None


logger = get_logger(__name__)

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("BAAI/bge-m3", trust_remote_code=True)
    return _embedding_model

try:
    import spacy
    for lang_code in ["zh", "en"]:
        from spacy.util import get_lang_class
        lang_class = get_lang_class(lang_code)
        lang_class.max_length = 10000000
    logger.info("已成功调大 SpaCy 全局 max_length 限制至 10,000,000")
except Exception as e:
    logger.warning(f"调大 SpaCy 限制失败: {e}")
    spacy = None

def clean_confluence_content(raw_content):
    """
    针对 Confluence MHTML 的高级清洗策略：
    1. 提取第一个 Boundary 块 (HTML 部分)
    2. 解码 Quoted-Printable
    3. BeautifulSoup 提取文本
    """
    initial_len = len(raw_content)
    try:
        html_content = raw_content
        boundary_match = re.search(r'boundary="([^"]+)"', raw_content)
        if boundary_match:
            boundary = boundary_match.group(1)
            parts = raw_content.split(f"--{boundary}")
            for part in parts:
                if "Content-Type: text/html" in part:
                    html_content = part.split("\r\n\r\n", 1)[-1]
                    break

        decoded_bytes = quopri.decodestring(html_content.encode('utf-8'))
        decoded_content = decoded_bytes.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(decoded_content, 'html.parser')

        for tag in soup(["style", "script", "xml", "meta", "link", "v:imagedata", "o:SmartTagType"]):
            tag.decompose()

        for img in soup.find_all('img'):
            img.decompose()

        clean_text = soup.get_text(separator="\n")

        clean_text = "".join(ch for ch in clean_text if ch.isprintable() or ch in "\n\t")

        clean_text = re.sub(r'\n\s*\n', '\n', clean_text).strip()

        final_len = len(clean_text)
        reduction = ((initial_len - final_len) / initial_len * 100) if initial_len > 0 else 0

        logger.info(f"[深度预处理] 成功。原始 {initial_len} -> 现存 {final_len} (缩减率: {reduction:.2f}%)")
        return clean_text

    except Exception as e:
        logger.error(f"❌ 深度清洗失败: {e}")
        return raw_content[:int(initial_len * 0.1)] if initial_len > 0 else ""

def process_single_word(file_path):
    """
    Word 文件解析主入口
    """
    from unstructured.partition.auto import partition
    from unstructured.chunking.title import chunk_by_title
    file_ext = os.path.splitext(file_path)[1].lower()
    is_confluence = False

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

            pure_text = clean_confluence_content(raw_data)

            if not pure_text or len(pure_text.strip()) == 0:
                logger.warning(f"⚠️ Confluence清洗后内容为空")
                return []

            from unstructured.partition.text import partition_text
            elements = partition_text(text=pure_text)
            chunks = chunk_by_title(elements=elements, max_characters=3000, combine_text_under_n_chars=500)
            logger.info(f"Confluence文件解析完成，共 {len(chunks)} 个块")
            return chunks
        except Exception as e:
            logger.error(f"❌ Confluence 专用处理失败: {e}", exc_info=True)

    if file_ext == ".docx" and Document is not None:
        try:
            elements = partition(filename=file_path, strategy="fast")
            chunks = chunk_by_title(elements=elements, max_characters=4000)
            logger.info(f"DOCX文件解析完成，共 {len(chunks)} 个块")
            return chunks
        except Exception as e:
            logger.warning(f"标准 docx 解析失败: {e}")

    try:
        elements = partition(filename=file_path, strategy="fast")
        chunks = chunk_by_title(elements=elements, max_characters=4000)
        logger.info(f"文件解析完成，共 {len(chunks)} 个块")
        return chunks
    except Exception as e:
        logger.error(f"❌ partition解析失败: {e}", exc_info=True)
        return []

class SimpleTextChunk:
    """简单的文本块对象，用于替代unstructured的Element对象"""
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"SimpleTextChunk(text={self.text[:50]}...)"

def process_markdown_file(file_path):
    """
    Markdown 文件专用解析器
    直接读取文件内容，按标题分割成块，不依赖 NLTK
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content or len(content.strip()) == 0:
            logger.warning(f"⚠️ Markdown文件内容为空: {file_path}")
            return []

        logger.info(f"Markdown文件读取成功，内容长度: {len(content)} 字符")

        chunks = []
        current_section = []
        current_title = "文档开头"

        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                if current_section:
                    section_text = '\n'.join(current_section).strip()
                    if section_text:
                        chunks.append(SimpleTextChunk(section_text))
                    current_section = []

                heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
                if heading_match:
                    current_title = heading_match.group(2).strip()
                    current_section.append(stripped)
            else:
                current_section.append(stripped)

        if current_section:
            section_text = '\n'.join(current_section).strip()
            if section_text:
                chunks.append(SimpleTextChunk(section_text))

        if not chunks and content.strip():
            chunks.append(SimpleTextChunk(content.strip()))

        logger.info(f"Markdown文件解析完成，共 {len(chunks)} 个块")
        return chunks

    except Exception as e:
        logger.error(f"❌ Markdown文件解析失败: {e}", exc_info=True)
        return []

def process_singel_file(file_path):
    """
    from unstructured.partition.auto import partition
    from unstructured.chunking.title import chunk_by_title
    总入口函数
    """
    logger.info(f"开始处理文件: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"❌ 文件不存在: {file_path}")
        return None

    file_size = os.path.getsize(file_path)
    logger.info(f"文件大小: {file_size} bytes")

    if file_size == 0:
        logger.error(f"❌ 文件为空: {file_path}")
        return None

    file_type = os.path.splitext(file_path)[1].lower()
    logger.info(f"文件类型: {file_type}")

    try:
        chunks = None

        if file_type in [".doc", ".docx"]:
            logger.info(f"使用Word解析器处理: {file_type}")
            chunks = process_single_word(file_path)
        elif file_type in [".xlsx", ".xls"]:
            logger.info(f"使用Excel解析器处理: {file_type}")
            from unstructured.partition.xlsx import partition_xlsx
            elements = partition_xlsx(filename=file_path)
            chunks = chunk_by_title(elements=elements, max_characters=4000)
        elif file_type in [".md", ".markdown"]:
            logger.info(f"使用Markdown专用解析器处理: {file_type}")
            chunks = process_markdown_file(file_path)
        elif file_type == ".pdf":
            logger.info("使用PDF解析器处理")
            elements = partition(filename=file_path, strategy="fast")
            chunks = chunk_by_title(elements=elements, max_characters=4000)
        else:
            logger.info(f"使用通用解析器处理: {file_type}")
            elements = partition(filename=file_path, strategy="fast")
            chunks = chunk_by_title(elements=elements, max_characters=4000)

        if chunks is None:
            logger.error(f"❌ 解析器返回None")
            return None

        if not chunks:
            logger.warning(f"⚠️ 解析完成但无有效内容块，文件: {file_path}")
            return None

        logger.info(f"✅ 解析完成: {os.path.basename(file_path)}, 最终生成 {len(chunks)} 个块")
        return chunks

    except Exception as e:
        logger.error(f"❌ 处理文件 {file_path} 时发生严重错误: {e}", exc_info=True)
        return None
