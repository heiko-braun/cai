from openai import OpenAI
from conf.constants import *

from qdrant_client import QdrantClient

# ---

# create an embedding using openai
def get_embedding(openai_client, text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   resp = openai_client.embeddings.create(input = [text], model=model)
   return resp.data[0].embedding

# query the vector store
def query_qdrant(openai_client, qdrant_client, query, collection_name, top_k=5):
    
    embedded_query = get_embedding(openai_client=openai_client, text=query)
    
    query_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=(embedded_query),
        limit=top_k,
    )
    
    return query_results

# ---

# OpenAI Client
openai_client = OpenAI()

# Vector DB
qdrant_client = QdrantClient(
    QDRANT_URL,
    api_key=QDRANT_KEY,
)

query_results = query_qdrant(
    openai_client=openai_client, 
    qdrant_client=qdrant_client, 
    query=input("Prompt:"), 
    collection_name='agent_fuse_comp_ref'
    )

print("Found N matches: ", len(query_results))
for i, article in enumerate(query_results):    
    #print(article)
    print(f'{i + 1}. {article.payload["metadata"]["page_number"]} (Score: {round(article.score, 3)})')

