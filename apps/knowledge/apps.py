from django.apps import AppConfig

class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.knowledge"

    embedder = None
    vector_store = None

    def ready(self):
        try:
            from django.conf import settings
            from .embedding import create_embedder
            from .vector_store import MilvusVectorStore

            if KnowledgeConfig.embedder is None:
                KnowledgeConfig.embedder = create_embedder()
            if KnowledgeConfig.vector_store is None:
                enabled = getattr(settings, 'ENABLE_MILVUS', False)
                if enabled:
                    KnowledgeConfig.vector_store = MilvusVectorStore()
                    print("Milvus 向量数据库已连接")
                else:
                    print("Milvus 未启用 (ENABLE_MILVUS=False)，向量数据库功能不可用")
            print("Knowledge service initialized successfully")
        except Exception as e:
            print(f"Warning: Knowledge service initialization failed: {e}")
            print("Knowledge base features may not be available")