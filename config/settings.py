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

# SECURITY WARNING: don't run with debug turned on in production!
# 根据环境变量设置DEBUG模式，生产环境应设置为False
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
        # 'model': 'deepseek-chat', #可以切换, deepseek-reasoner即【深度思考】模式, 可能会稍微慢一些
        # 'api_base': 'https://api.deepseek.com/v1', #deepseek官网base_url

        # ----使用AI团队部署在阿里云上的deepseek相关配置信息----
        'model': 'deepseek-v3.1',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', #AI团队使用的阿里云base_url
        # ----使用AI团队部署在阿里云上的deepseek相关配置信息----
        
        'temperature': 0.7,
        'max_tokens': 128000,
    },
    'qwen': {
        'name': '通义千问',
        'model': 'qwen-plus-2025-01-25',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'temperature': 0.7,
        'max_tokens': 65000,  # 修正为不超过65536的值
    },
}
# AI Agent LLM提供商配置, 每个AI Agent可定制LLM提供商
AGENT_LLM_DEFAULTS = {
    "test_case_generator":  {"provider": "qwen"},
    "test_case_reviewer":   {"provider": "qwen"},
    "prd_analyzer":         {"provider": "qwen"},
    "java_code_analyzer":   {"provider": "qwen"},
    "iface_case_generator": {"provider": "qwen"},
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
PROJECT_ID_REPO_MAPPING = {
    
    # 可以继续添加更多项目
}

# Git 凭据配置（用于内部GitLab）
GIT_CREDENTIALS = {
    'username': '',  # 替换为实际用户名
    'password': '',  # 替换为实际密码或访问令牌
    # 或者使用访问令牌（推荐）
    # 'token': 'your_gitlab_access_token',
}

# Hugging Face 的tokenizers库使用了多进程机制;
# 在自己的逻辑中使用时，需要注意在进程fork之前不要使用tokenizers库,否则可能会引起死锁
# 在Django启动时设置环境变量为false,禁止tokenizers库使用多进程
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


