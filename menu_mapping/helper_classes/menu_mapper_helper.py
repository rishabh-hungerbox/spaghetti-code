import openai
import json
import asyncio
from llama_index.llms.openai import OpenAI
from menu_mapping.helper_classes.llm_helper import ItemFormatter
from llama_index.core import Settings, VectorStoreIndex, Document, StorageContext, load_index_from_storage
import os
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import QueryBundle
from llama_index.embeddings.openai import OpenAIEmbedding
from dotenv import load_dotenv
from llama_index.core.node_parser import SentenceWindowNodeParser
from etc.settings import DATABASES
import csv
from llama_index.core.postprocessor import LLMRerank
from menu_mapping.helper_classes.utility import MenuMappingUtility
from llama_index.llms.anthropic import Anthropic
from menu_mapping.helper_classes.llm_helper import NutritionFinder
from llama_index.llms.gemini import Gemini
import sys


class MenuMapperAI:
    def __init__(self, prompt_id, model, embedding, similarity_top_k, benchmark_on, debug_mode, sampling_size, with_reranker):
        self.prompt_id = prompt_id
        self.model = model
        self.embedding = embedding
        self.similarity_top_k = similarity_top_k
        self.benchmark_on = benchmark_on
        self.global_index = None
        self.debug_mode = debug_mode
        self.with_reranker = with_reranker
        self.app_id = f"prompt_{self.prompt_id}_{self.model}_{self.embedding}_top_k_{self.similarity_top_k}_with_reranker_{self.with_reranker}"
        self.sampling_size = sampling_size
        self.tru = None
        self.tru_recorder = None
        self.llm = None

        load_dotenv()
        openai.api_key = os.getenv('OPEN_API_KEY')
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        documents, self.item_id_map = MenuMappingUtility.fetch_data()
        self.global_index = self.generate_vector_index(documents)
        self.prompt = self.fetch_prompt()

    def execute(self, child_menu_name):
        return self.generate_response(child_menu_name)
    
    def generate_response(self, child_menu_name):
        RETRY_COUNT = 3
        response = ''
        try:
            item_data = ItemFormatter('models/gemini-2.0-flash').format(child_menu_name)
            print(f'{item_data['name']},{item_data['quantity_details']},{item_data['ambiguous']},{item_data['is_mrp']},{item_data['is_veg']}')
            format_result = {
                'name': child_menu_name,
                'root_item_name': None,
                'quantity_details': item_data['quantity_details'],
                'is_ambiguous': item_data['ambiguous'],
                'is_mrp': item_data['is_mrp'],
                'is_veg': item_data['is_veg'],
            }
            if item_data['ambiguous'] or item_data['is_mrp']:
                format_result['root_items'] = []
                return format_result

            nodes = asyncio.run(self.get_filtered_nodes(item_data['name']))
            text = "ID,Food Item Name,Vector Score\n"
            for node in nodes:
                text += f"{node.node.text},{node.score}\n"

            # preparing query engine on the filtered index
            filtered_index = VectorStoreIndex.from_documents([Document(text=text)])
            query_engine = filtered_index.as_query_engine(embeddings_enabled=True)

            while RETRY_COUNT > 0:
                try:
                    response = query_engine.query(self.prompt + item_data['name'])
                    break
                except Exception as e:
                    print(f"Error querying: {e}")
                    RETRY_COUNT -= 1
            RETRY_COUNT = 3
            if not response:
                raise Exception("LLM returned nothing even after retrying")
            print("response: ", response)
            relevant_items = self.process_response(response)
            final_root_items = []
            root_item_name = ''
            items_added = 0
            max_limit = len(item_data['name'].split(' | '))
            for item in relevant_items:
                if items_added >= max_limit:
                    break
                if items_added != 0:
                    root_item_name += " | "
                root_item_name += item['name']
                final_root_items.append(item)
                items_added += 1
            format_result['root_items'] = final_root_items
            format_result['root_item_name'] = root_item_name
            return format_result

        except Exception as e:
            raise Exception(f'Error: {str(e)}')

    def process_response(self, response) -> list:
        try:
            response = str(response).replace("'", '"')
            root_items = json.loads(str(response).strip("```json").strip("```"))
        except Exception as e:
            print(f"Error processing response: {e}")
            return [{
                        "id": -1,
                        "name": 'LLM JSON parsing failed',
                        "usage": 0,
                        "relevance_score": 0
                    }]
        filtered_items = []
        for item in root_items:
            if item.get('id') and str(item['id']) in self.item_id_map:
                item_data = self.item_id_map[str(item['id'])]
                filtered_items.append({
                    "id": item_data['id'],
                    "name": item_data['name'],
                })
        return filtered_items

    def generate_vector_index(self, documents):
        node_parser = SentenceWindowNodeParser.from_defaults(
                window_size=2,
                window_metadata_key="window",
                original_text_metadata_key="original_text",
            )

        if "deepseek" in self.model:
            # self.llm = DeepSeek(model=self.model, api_key=os.getenv('DEEP_SEEK_API_KEY'))
            self.llm = OpenAILike(model="deepseek-chat", api_base="https://api.deepseek.com/v1", api_key=os.getenv('DEEP_SEEK_API_KEY'), is_chat_model=True)
        elif "claude" in self.model:
            self.llm = Anthropic(model=self.model, api_key=os.getenv('CLAUDE_API_KEY'))
        elif "gemini" in self.model:
            self.llm = Gemini(model=self.model, api_key=os.getenv('GEMINI_API_KEY'))
        else:
            self.llm = OpenAI(model=self.model, temperature=0.3)
        Settings.llm = self.llm
        Settings.embed_model = OpenAIEmbedding(model=self.embedding)
        Settings.node_parser = node_parser

        # Build the index using pgvector
        from llama_index.vector_stores.postgres import PGVectorStore

        vector_store = PGVectorStore.from_params(
            database=DATABASES['default']['NAME'],
            host=DATABASES['default']['HOST'],
            password=DATABASES['default']['PASSWORD'],
            port=DATABASES['default']['PORT'],
            user=DATABASES['default']['USER'],
            table_name="root_item_vectors",
            embed_dim=1536,  # openai embedding dimension
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 64,
                "hnsw_ef_search": 40,
                "hnsw_dist_method": "vector_cosine_ops",
            },
        )

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        try:
            # Try to load existing index
            print("Loading pre-existing index...")
            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            print("Pre-existing Index loaded!")
        except Exception as e:
            print(f"Error loading pre-existing index: {str(e)}")
            # Create new index if loading fails
            print("Creating new index...")
            index = VectorStoreIndex.from_documents(
                documents=documents,
                storage_context=storage_context
            )
            print("Index created successfully!")

        return index

    def fetch_prompt(self):
        try:
            with open("menu_mapping/input/prompt_data.csv", 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if int(row['prompt_id']) == self.prompt_id:
                        return row['prompt']
            raise ValueError(f"No prompt found for prompt_id: {self.prompt_id}")

        except FileNotFoundError:
            raise FileNotFoundError("Prompt file 'xyz.csv' not found")
        except Exception as e:
            raise Exception(f"Error reading prompt file: {str(e)}")

    async def get_filtered_nodes(self, item_name: str):
        final_nodes = []
        if self.with_reranker:
            self.similarity_top_k = 50
        self.retriever = self.global_index.as_retriever(similarity_top_k=self.similarity_top_k)
        nodes = self.retriever.retrieve(item_name)
        if self.with_reranker:
            items = item_name.split(' | ')
            tasks = [asyncio.to_thread(self.get_reranked_nodes, food) for food in items]
            results = await asyncio.gather(*tasks)
            for filtered_nodes in results:
                final_nodes.extend(filtered_nodes)
        else:
            final_nodes = nodes
            print("ID,Food Item Name,Vector Score")
            for node in final_nodes:
                print(f"- {node.node.text}, {node.score}")
        return final_nodes
    
    def get_reranked_nodes(self, food: str):
        nodes = self.retriever.retrieve(food)
        reranker = LLMRerank(
            top_n=self.similarity_top_k,
            llm=self.llm
        )
        prompt = (
            "Food Item - {food}.Given a food item (e.g., \"Paneer Masala Kati Roll\"), extract its main component "
            "(e.g., \"Roll\") and prioritize nodes that exactly match this component when finding the most relevant food item.\n"
            "Examples:\n\n"
            "\"Paneer Masala Kati Roll\" → Roll\n"
            "\"Paneer Peri Peri Sandwich\" → Sandwich\n"
            "\"Bhindi ki bhurji\" → Bhindi\n"
            "\"Boiled Channa Salad\" → Salad\n"
            "\"Rose Tea\" -> Tea\n"
            "\"Dragon Juice\" -> Juice"
        )
        formatted_prompt = prompt.format(food=food)
        filter_nodes = reranker.postprocess_nodes(
            nodes, QueryBundle(formatted_prompt)
        )
        print("ID,Food Item Name,Vector Score")
        for node in filter_nodes:
            print(f"- {node.node.text}, {node.score}")
        return filter_nodes


if not any("migrat" in arg for arg in sys.argv):
    ai = MenuMapperAI(prompt_id=7, model="models/gemini-2.0-flash", embedding="text-embedding-3-small", similarity_top_k=10, benchmark_on=False, debug_mode=False, sampling_size=50, with_reranker=True)


def get_master_menu_response(child_menu_name: str):
    # ai = MenuMapperAI(prompt_id=7, model="models/gemini-2.0-flash", embedding="text-embedding-3-small", similarity_top_k=10, benchmark_on=False, debug_mode=False, sampling_size=50, with_reranker=True)
    nutrition_finder = NutritionFinder('models/gemini-2.0-flash')
    data = ai.execute(child_menu_name)
    qty_details = data['quantity_details']
    root_items_count = len(data['root_items'])
    if root_items_count == 0:
        return data
    count = 0
    for item in qty_details.split(' | '):
        nutrition = nutrition_finder.find_nutrition(item)
        data['root_items'][count]['nutrition'] = nutrition
        count += 1
        if count == root_items_count:
            break
    return data

