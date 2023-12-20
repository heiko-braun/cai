from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

import cohere

from qdrant_client import QdrantClient

from langchain.tools import BaseTool, StructuredTool, Tool, tool
from langchain.docstore.document import Document
from openai import OpenAI

import jmespath
import json
import httpx
import time

from conf.constants import *

# ---

def query_qdrant(query, top_k=5, collection_name="rhaetor.github.io_components"):
    openai_client = create_openai_client()
    qdrant_client = create_qdrant_client()

    embedded_query = get_embedding(openai_client=openai_client, text=query)
    
    query_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=(embedded_query),
        limit=top_k,
    )
    
    return query_results

def get_embedding(openai_client, text, model="text-embedding-ada-002"):
   start = time.time()
   text = text.replace("\n", " ")
   resp = openai_client.embeddings.create(input = [text], model=model)
   print("Embedding ms: ", time.time() - start)
   return resp.data[0].embedding

def create_openai_client():
    client = OpenAI(
        timeout=httpx.Timeout(
            10.0, read=8.0, write=3.0, connect=3.0
            )
    )
    return client

def create_qdrant_client(): 
    client = QdrantClient(
       QDRANT_URL,
        api_key=QDRANT_KEY,
    )
    return client

def fetch_and_rerank(entities, collections):
    response_documents = []
    first_iteration_hits = []

    # lookup across multiple vector store
    for collection_name in collections:
            
        query_results = query_qdrant(entities, collection_name=collection_name)
        num_matches = len(query_results)
        
        print("First glance matches:")
        for i, article in enumerate(query_results):    
           print(f'{i + 1}. {article.payload["metadata"]["page_number"]} (Score: {round(article.score, 3)})')
           first_iteration_hits.append(
               {
                   "content": article.payload["page_content"],
                   "ref": article.payload["metadata"]["page_number"]
               }
           )


    # apply reranking
    hit_contents = []
    for match in first_iteration_hits:                             
        hit_contents.append(match["content"])            
    
    co = cohere.Client(os.environ['COHERE_KEY'])
    rerank_hits = co.rerank(
        model = 'rerank-english-v2.0',
        query = entities,
        documents = hit_contents,
        top_n = 5
    )
    
    # the final results
    second_iteration_hits = []
    print("Reranked matches ("+ collection_name+ "):")   
    for i, hit in enumerate(rerank_hits):                
        orig_result = first_iteration_hits[hit.index]

        doc = Document(
            page_content= first_iteration_hits[hit.index]["content"], 
            metadata={
                "page_number": first_iteration_hits[hit.index]["ref"]
            }
        )

        second_iteration_hits.append(str(doc)) # TODO, inefficient but the StreamlitCallback Handler expects this text structure

        print(f'{orig_result["ref"]} (Score: {round(hit.relevance_score, 3)})')                

    # squash into single response 
    response_documents.append(' '.join(second_iteration_hits))

    return ' '.join(response_documents)

class QuarkusReferenceTool(BaseTool):
    name = "search_quarkus_reference"
    description = "Useful when you need to answer questions about Camel Components used with Camel Quarkus. Input should be a list of camel components or the names of third-party systems."

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool."""
        return fetch_and_rerank(query, ["quarkus_reference", "rhaetor.github.io_components"])

    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("custom_search does not support async")


class CamelCoreTool(BaseTool):
    name = "search_camel_core"
    description = "Useful when you need to answer questions about enterprise integration patterns, languages or data formats in Camel, as well as the framework in general. Input should be a list of terms related to the core Camel framework"

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool."""
        return fetch_and_rerank(query, ["rhaetor.github.io", "rhaetor.github.io_components"])

    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("custom_search does not support async")


