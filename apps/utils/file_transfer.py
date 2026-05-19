import pypandoc
import logging

logger = logging.getLogger(__name__)

def word_to_markdown(input_file, output_file):
    '''
    将Word文档转换为Markdown格式
    '''
    try:
        # 调用 pypandoc 进行转换
        output = pypandoc.convert_file(input_file, 'markdown', outputfile=output_file)
        if output == '':
            logger.info(f"成功将 {input_file} 转换为 {output_file}")
        else:
            logger.warning(f"转换过程中出现问题: {output}")
    except Exception as e:
        logger.error(f"转换失败: {e}")


