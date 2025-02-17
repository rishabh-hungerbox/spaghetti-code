import openai
import json
from llama_index.llms.openai import OpenAI
from menu_mapping.helper_classes.llm_helper import ItemFormatter, ItemSpellCorrector, Evaluator
from llama_index.core import Settings, VectorStoreIndex, Document, StorageContext, load_index_from_storage
import os
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import QueryBundle
from llama_index.embeddings.openai import OpenAIEmbedding
from dotenv import load_dotenv
from llama_index.core.node_parser import SentenceWindowNodeParser
import csv
import sys
from llama_index.core.postprocessor import LLMRerank
from menu_mapping.helper_classes.utility import MenuMappingUtility
from llama_index.llms.anthropic import Anthropic
from llama_index.llms.gemini import Gemini
from menu_mapping.models import LLMLogs, MenuMappingPrediction


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

        item_data = ItemFormatter('models/gemini-2.0-flash').format(child_menu_name)
        print(f'Item Name: {child_menu_name}, Formatted Name: {item_data['name']}, Ambiguous: {item_data['ambiguous']}, Is MRP: {item_data['is_mrp']}, Quantity Details: {item_data['quantity_details']}')

        if item_data['ambiguous']:
            print("Ambiguous item, skipping...")
            valid = False
            root_item_name = 'AMBIGUOUS ITEM DETECTED'
        if item_data['is_mrp']:
            print("MRP item, skipping...")
            valid = False
            root_item_name = 'MRP ITEM DETECTED'

        if valid:
            nodes, _, _, _, _ = self.get_filtered_nodes(item_data['name'])
            if len(nodes) == 0:
                print("Reranker returned nothing !!!!!")
                return 'No matching items found'

            text = "ID,Food Item Name,Vector Score\n"
            for node in nodes:
                text += f"{node.node.text},{node.score}\n"
            # preparing query engine on the filtered index
            filtered_index = VectorStoreIndex.from_documents([Document(text=text)])
            query_engine = filtered_index.as_query_engine(embeddings_enabled=True)

            response = query_engine.query(self.prompt + item_data['name'])

            print("response: ", response)
            relevant_items = self.process_response(response)
            root_item_name = ''
            items_added = 0
            max_limit = len(item_data['name'].split(' | '))
            for item in relevant_items:
                if items_added >= max_limit:
                    break
                if items_added != 0:
                    root_item_name += " | "
                root_item_name += item['name']
                items_added += 1

            print(f"Child Menu Name: {child_menu_name}\nRelevant Items:\n{json.dumps(relevant_items, indent=4)}\n")
            print("Most Relevant Item:\n")
        if root_item_name != '':
            print(root_item_name)
            return root_item_name
            
        else:
            print("NOT FOUND")
            return 'NOT FOUND'

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

        # Build the index
        if not os.path.exists("./menu_mapping_index_root"):
            print("Creating index...")
            index = VectorStoreIndex.from_documents(documents=documents)
            index.storage_context.persist(persist_dir="./menu_mapping_index_root")
            print("Index created successfully!")
        else:
            print("Loading pre-existing index...")
            index = load_index_from_storage(
                StorageContext.from_defaults(persist_dir="./menu_mapping_index_root"))
            print("Pre-existing Index loaded!")

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

    def get_filtered_nodes(self, item_name: str):
        final_nodes = []
        vs_best, vs_score, llmre_best, llmre_score = 'NULL', 0, 'NULL', 0
        if self.with_reranker:
            self.similarity_top_k = 50
        self.retriever = self.global_index.as_retriever(similarity_top_k=self.similarity_top_k)
        nodes = self.retriever.retrieve(item_name)
        if len(nodes) > 0:
            vs_best = nodes[0].node.text
            vs_score = nodes[0].score
        if self.with_reranker:

            items = item_name.split(' | ')
            for food in items:
                nodes = self.retriever.retrieve(food)
                reranker = LLMRerank(
                    top_n=self.similarity_top_k,
                    llm=self.llm
                )
                prompt = """Food Item - {food}.Given a food item (e.g., "Paneer Masala Kati Roll"), extract its main component (e.g., "Roll") and prioritize nodes that exactly match this component when finding the most relevant food item.
                            Examples:

                            "Paneer Masala Kati Roll" → Roll
                            "Paneer Peri Peri Sandwich" → Sandwich
                            "Bhindi ki bhurji" → Bhindi
                            "Boiled Channa Salad" → Salad
                            "Rose Tea" -> Tea
                            "Dragon Juice" -> Juice"""
                print(prompt.format(food=food))
                filter_nodes = reranker.postprocess_nodes(
                    nodes, QueryBundle(prompt.format(food=food))
                )
                print("ID,Food Item Name,Vector Score")
                for node in filter_nodes:
                    print(f"- {node.node.text}, {node.score}")
                final_nodes.extend(filter_nodes)
        else:
            final_nodes = nodes
            print("ID,Food Item Name,Vector Score")
            for node in final_nodes:
                print(f"- {node.node.text}, {node.score}")

        return final_nodes, vs_best, vs_score, llmre_best, llmre_score


if not any("migrat" in arg for arg in sys.argv):
    ai = MenuMapperAI(prompt_id=7, model="models/gemini-2.0-flash", embedding="text-embedding-3-small", similarity_top_k=10, benchmark_on=False, debug_mode=False, sampling_size=50, with_reranker=True)


def get_master_menu_response(child_menu_name: str):
    return ai.execute(child_menu_name)


def process_data(data, log_id):
    if not log_id:
        log = LLMLogs(model_name=ai.model, embedding_model=ai.embedding, prompt=ai.prompt)
        log.save()
        log_id = log.id
    ai.generate_response(data, log_id)
