from openai import OpenAI
from util.utils import show_json, as_json
import time
import jmespath
import json
import httpx

from qdrant_client import QdrantClient
from qdrant_client.http import models

from conf.constants import *

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

from statemachine import State
from statemachine import StateMachine

import argparse
import cohere

import streamlit as st

# ---

def get_response(client, thread):
    return client.beta.threads.messages.list(thread_id=thread.id, order="asc")

def pretty_print(messages):
    print("# Messages")
    for m in messages:
        print(f"{m.role}: {m.content[0].text.value}")
    print()

# primitive wait condition for API requests, needs improvement
def wait_on_run(client, run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        print("Thinking ... ", run.status)
        time.sleep(0.5)        
    return run    

# fetch the call arguments from an assistant callback
def get_call_arguments(run):    
    tool_calls = jmespath.search(
        "required_action.submit_tool_outputs.tool_calls", 
        as_json(run)
    )
    print(json.dumps(tool_calls, indent=2))
    call_arguments = []
    for call in tool_calls:
        id = jmespath.search("id", call)    
        arguments = jmespath.search("function.arguments", call)    
        call_arguments.append(
            {
                "call_id": id,
                "call_arguments":json.loads(arguments)
            }
        )
    return call_arguments 
    
# search local storage for documentation related to componment    
def fetch_docs(entities):  
    print("Fetching docs for query: ", entities)  
    
    query_results = query_qdrant(entities, collection_name="camel_docs")
    num_matches = len(query_results)
    
    # print("First glance matches:")
    # for i, article in enumerate(query_results):    
    #    print(f'{i + 1}. {article.payload["filename"]} (Score: {round(article.score, 3)})')

    if num_matches > 0:

        docs = []
        for _, article in enumerate(query_results):
            with open(article.payload["filename"]) as f:                
                docs.append(f.read())

        # apply reranking
        co = cohere.Client(os.environ['COHERE_KEY'])
        rerank_hits = co.rerank(
            model = 'rerank-english-v2.0',
            query = entities,
            documents = docs,
            top_n = 3
        )

        print("Reranked matches: ")   
        for hit in rerank_hits:
            orig_result = query_results[hit.index]
            print(f'{orig_result.payload["filename"]} (Score: {round(hit.relevance_score, 3)})')            

        # TODO: This is wrong and needs to be fixed. it must consider the rerank
        doc = query_results[0]
        with open(doc.payload["filename"]) as f:
            contents = f.read()
            return contents
    else:
        return "No matching file found for "+entities  

def fetch_pdf_pages(entities, collection_name):  
    print("Fetching PDF pages for query: ", entities)  
    
    query_results = query_qdrant(entities, collection_name=collection_name)
    num_matches = len(query_results)
    
    # print("First glance matches:")
    # for i, article in enumerate(query_results):    
    #    print(f'{i + 1}. {article.payload["filename"]} (Score: {round(article.score, 3)})')

    if num_matches > 0:

        page_hits = []        
        for _, article in enumerate(query_results):
            page_number = article.payload["page_number"]
            with open(TEXT_DIR+collection_name+"/page_"+str(page_number)+".txt") as f:                
                page_hits.append(f.read())            

        # apply reranking
        co = cohere.Client(os.environ['COHERE_KEY'])
        rerank_hits = co.rerank(
            model = 'rerank-english-v2.0',
            query = entities,
            documents = page_hits,
            top_n = 3
        )

        print("Reranked matches: ")   
        for hit in rerank_hits:
            orig_result = query_results[hit.index]
            print(f'{orig_result.payload["page_number"]} (Score: {round(hit.relevance_score, 3)})')
            #print(orig_result.payload["filename"])

        # return the reanked hits as a single results
        return ' '.join(page_hits)
    
    else:
        return "No matching file found for "+entities            
                
def query_qdrant(query, top_k=5, collection_name="camel_docs"):
    openai_client = create_openai_client()
    qdrant_client = create_qdrant_client()

    embedded_query = get_embedding(openai_client=openai_client, text=query)
    
    query_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=(embedded_query),
        limit=top_k,
    )
    
    return query_results

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
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
            
# ---
         
class Assistant(StateMachine):
    "Assistant state machine"

    prompt = State(initial=True)
    running = State()
    lookup = State()
    answered = State(final=True)

    kickoff = prompt.to(running)
    request_docs = running.to(lookup)
    docs_supplied = lookup.to(running)
    resolved = running.to(answered)

    def __init__(self, st_callback=None):
        
        # streamlit callback, if present
        self.st_callback = st_callback

        # internal states
        self.prompt_text = None
        self.thread = None
        self.run = None
        
        self.openai_client = create_openai_client()
        self.lookups_total = 0        
        
        super().__init__()

    def display_message(self, message):
        if self.st_callback is not None:
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message, unsafe_allow_html=True)      
        
    def on_exit_prompt(self, text):
        self.prompt_text = text        

        if(self.st_callback is not None):
            self.st_callback.empty()
                    
        # start a new thread
        self.thread = self.openai_client.beta.threads.create()
        print("New Thread: ", self.thread.id)

        # Add initial message
        message = self.openai_client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=text,
        )

        # create a run
        self.run = self.openai_client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=ASSISTANT_ID,
        )

    def on_enter_lookup(self):
        if(self.st_callback is None):
            self._on_enter_lookup()
        else:
            with self.st_callback.spinner('Lookup additional information ...'):    
                self._on_enter_lookup()

    def _on_enter_lookup(self):
        print("Lookup requested")
        self.lookups_total = self.lookups_total +1

        # take call arguments and invoke lookup
        args = get_call_arguments(self.run)
        outputs=[]              
        
        for a in args:
            entity_args = a["call_arguments"]["entities"]
            keywords = ' '.join(entity_args)
            # it often includes camel itself. remove it
            keywords = keywords.replace('Apache', '').replace('Camel', '')

            # TODO: Needs a strategy implementation
            #doc = fetch_docs(self.prompt_text + " | " + keywords)                  
            doc = fetch_pdf_pages(
                entities=self.prompt_text + " | " + keywords, 
                collection_name="fuse_camel_development"
                )
            outputs.append(
                {
                    "tool_call_id": a["call_id"],
                    "output": "'"+doc+"'"
                }
            )
        
        # submit lookup results (aka tool outputs)
        self.run = self.openai_client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id,
            run_id=self.run.id,
            tool_outputs=outputs
            )    
        
        self.docs_supplied()

    # starting a thinking loop
    def on_enter_running(self):
        print("Enter running ...")   

        if(self.st_callback is None):
            self._on_enter_running()
        else:                    
            with self.st_callback.spinner('Thinking ...'):    
                self._on_enter_running()

    def _on_enter_running(self):
        self.run = wait_on_run(self.openai_client, self.run, self.thread)        

        if(self.run.status == "requires_action"):            
            self.request_docs()
        elif(self.run.status == "completed"):    
            self.resolved()
        else:
            print("Illegal state: ", self.run.status)            
            print(self.run.last_error)
            
    # the assistant has resolved the question
    def on_enter_answered(self):

        # thread complete, show answer
        assistant_response = get_response(self.openai_client, self.thread)
        for m in assistant_response:
            if(m.role == "assistant"):
                self.display_message(m.content[0].text.value)

        pretty_print(assistant_response)

        # delete the thread
        self.openai_client.beta.threads.delete(self.thread.id)
        print("Deleted Thread: ", self.thread.id)

# --

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Camel Docs Assistant')
    parser.add_argument('-f', '--filename', help='The inut file that will be taken as a prompt', required=False)
    args = parser.parse_args()

    if(args.filename == None):
        prompt = input("Prompt: ")  
    else:
        with open(args.filename) as f:
            prompt = f.read()        
        prompt = prompt.replace('\n', ' ').replace('\r', '')        
        
        
    sm = Assistant()        
    sm.kickoff(prompt)

