
from llama_index.core import VectorStoreIndex, StorageContext
from etc.settings import DATABASES
from llama_index.vector_stores.postgres import PGVectorStore


class IndexManager:
    VENDOR_ORDER_DATA = 'vendor_order_data'
    VENDOR_REVIEW_DATA = 'vendor_review_data'

    @staticmethod
    def create_index(
        documents,
        table_name,
    ):
        vector_store = PGVectorStore.from_params(
            database=DATABASES['default']['NAME'],
            host=DATABASES['default']['HOST'],
            password=DATABASES['default']['PASSWORD'],
            port=DATABASES['default']['PORT'],
            user=DATABASES['default']['USER'],
            table_name=table_name,
            embed_dim=1536,
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 64,
                "hnsw_ef_search": 40,
                "hnsw_dist_method": "vector_cosine_ops",
            },
        )

        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
                documents=documents,
                storage_context=storage_context
            )
        return index

    @staticmethod
    def load_index(
        table_name,
    ):
        vector_store = PGVectorStore.from_params(
            database=DATABASES['default']['NAME'],
            host=DATABASES['default']['HOST'],
            password=DATABASES['default']['PASSWORD'],
            port=DATABASES['default']['PORT'],
            user=DATABASES['default']['USER'],
            table_name=table_name,
            embed_dim=1536,
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 64,
                "hnsw_ef_search": 40,
                "hnsw_dist_method": "vector_cosine_ops",
            },
        )
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        return index
