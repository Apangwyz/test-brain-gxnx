"""
Django settings for test_brain project.
"""

import os
import sys
from pathlib import Path

# 配置pymysql作为MySQL驱动
import pymysql
pymysql.install_as_MySQLdb()

# 配置 Hugging Face 国内镜像，用于 SentenceTransformer 模型下载
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 采用北京时间
TIME_ZONE = 'Asia/Shanghai'
USE_TZ = False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 确保项目根目录在Python路径中
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# SECURITY WARNING: keep the secret key used in production secret!
# 使用环境变量注入SECRET_KEY，确保生产环境安全
# 强制从环境变量读取，不能依赖不安全的后备值
SECRET_KEY = os.environ.get('SECRET_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY 环境变量未设置！请设置 SECRET_KEY 环境变量后再启动。')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# 允许的主机列表，生产环境应限制为具体域名
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# 是否启用Milvus
ENABLE_MILVUS = os.environ.get("ENABLE_MILVUS", "false").lower() == "true"

# 添加上传测试用例文件目录配置
MEDIA_ROOT = os.path.join(BASE_DIR, 'uploads')
MEDIA_URL = '/uploads/'

# 跨域配置：仅开发环境允许所有跨域
CORS_ORIGIN_ALLOW_ALL = DEBUG

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # 自定义应用
    'apps.core',
    'apps.llm',
    # 'apps.knowledge',
    'apps.knowledge.apps.KnowledgeConfig',
    'apps.ai_agents.iface_case_generator.apps.IfaceCaseGeneratorConfig',
    'apps.ai_agents.java_code_analyzer.apps.JavaCodeAnalyzerConfig',
    'apps.ai_agents.prd_analyzer.apps.PrdAnalyzerConfig',
    'apps.ai_agents.test_case_generator.apps.TestCaseGeneratorConfig',
    'apps.ai_agents.test_case_reviewer.apps.TestCaseReviewerConfig',
    'apps.ai_agents.requirement_analyzer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]



ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'zh-hans'
USE_I18N = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== 认证配置 ====================
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# API Key 用于外部工具调用 JSON API 时的认证
API_KEY = os.getenv('API_KEY', '')



# LLM提供商配置
LLM_PROVIDERS = {
    'default_provider': 'deepseek',
    'deepseek': {
        'name': 'DeepSeek',
        'model': 'deepseek-v3.1',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'temperature': 0.7,
        'max_tokens': 128000,
    },
    'qwen': {
        'name': '通义千问',
        'model': 'qwen-plus-2025-01-25',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'temperature': 0.7,
        'max_tokens': 65000,
    },
}
# AI Agent LLM提供商配置, 每个AI Agent可定制LLM提供商
AGENT_LLM_DEFAULTS = {
    "test_case_generator":  {"provider": "qwen"},
    "test_case_reviewer":   {"provider": "qwen"},
    "prd_analyzer":         {"provider": "qwen"},
    "java_code_analyzer":   {"provider": "qwen"},
    "iface_case_generator": {"provider": "qwen"},
    "requirement_analyzer": {"provider": "qwen"},
}

# LLM Provider 优先级配置（降级容错）
# 当首选 Provider 调用失败时，按此列表顺序自动降级到下一个可用 Provider
# 环境变量 AGENT_PRIORITY__{agent_name} 和 LLM_PROVIDER_PRIORITY 可覆盖此配置
# 环境变量优先级: AGENT_PRIORITY__{agent_name} > LLM_PROVIDER_PRIORITY > settings.LLM_PROVIDER_PRIORITY
LLM_PROVIDER_PRIORITY = {
    "default": ["qwen", "deepseek"],
    "requirement_analyzer": ["deepseek", "qwen"],
}

# 向量数据库配置
VECTOR_DB_CONFIG = {
    'host': os.getenv('MILVUS_HOST', '127.0.0.1'),
    'port': os.getenv('MILVUS_PORT', '19530'),
    'db_name': os.getenv('MILVUS_DB_NAME', 'default'),
    'collection_name': os.getenv('MILVUS_COLLECTION', 'vv_knowledge_collection'),
}

# java源码分析服务调用地址
# JAVA_ANALYZER_SERVICE_URL = "http://localhost:8089" #调用本地服务
JAVA_ANALYZER_SERVICE_URL = "http://java-analyzer:80" #bj-uat服务间调用
# JAVA_ANALYZER_SERVICE_URL = "http://172.20.214.59:8089" #本地开发调用bj-uat服务,服务每次部署ip会变

# Java 项目配置
JAVA_PROJECTS_BASE_DIR = "../"  # Java 项目基础目录

# 项目ID与仓库URL映射，可通过环境变量 JAVA_REPO_MAPPING_FILE 指定外部JSON文件路径
# JSON格式: {"project_id": "repo_url", ...}
PROJECT_ID_REPO_MAPPING = {}
_repo_mapping_file = os.environ.get('JAVA_REPO_MAPPING_FILE')
if _repo_mapping_file and os.path.exists(_repo_mapping_file):
    try:
        import json
        with open(_repo_mapping_file, 'r') as _f:
            PROJECT_ID_REPO_MAPPING = json.load(_f)
    except Exception as _e:
        import logging
        logging.warning(f"读取项目映射文件失败 {_repo_mapping_file}: {_e}")

# Git 凭据配置（用于内部GitLab）
# 优先从环境变量读取，避免敏感信息硬编码
GIT_CREDENTIALS = {}
_git_username = os.environ.get('GIT_USERNAME', '')
_git_password = os.environ.get('GIT_PASSWORD', '')
_git_token = os.environ.get('GIT_TOKEN', '')
if _git_token:
    GIT_CREDENTIALS = {'token': _git_token}
elif _git_username and _git_password:
    GIT_CREDENTIALS = {'username': _git_username, 'password': _git_password}

# Hugging Face tokenizers 多进程设置
# 在Django启动时设置为 false，避免 fork 后死锁
os.environ["TOKENIZERS_PARALLELISM"] = "false" 


# 向量模型提供商配置: "local"(本地BGE-M3) | "aliyun"(阿里云text-embedding-v4)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "aliyun")

# 阿里云向量模型配置
ALIYUN_EMBEDDING_CONFIG = {
    'api_key': os.getenv('QWEN_API_KEY'),
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
    'model': 'text-embedding-v4',
    'batch_size': 10,  # 阿里云限制最大10条  # 阿里云限制每次最多25条
}


