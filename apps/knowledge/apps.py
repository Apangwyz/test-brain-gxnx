from django.apps import AppConfig

class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.knowledge"

    embedder = None
    vector_store = None

    def ready(self):
        # 暂时禁用自动初始化，需要配置API Key后才能使用
        # from .embedding import create_embedder
        # from .vector_store import MilvusVectorStore
        #
        # if KnowledgeConfig.embedder is None:
        #     KnowledgeConfig.embedder = create_embedder()
        # if KnowledgeConfig.vector_store is None:
        #     KnowledgeConfig.vector_store = MilvusVectorStore()
        pass