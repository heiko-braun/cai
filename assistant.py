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

# ---

def get_response(thread):
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

# fetche the call arguments from an assistant callback
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
def fetch_docs(component_name):  
    print("Fetching docs for ", component_name)  
    
    query_results = query_qdrant(component_name)
    num_matches = len(query_results)
    print("Found N matches: ", num_matches)

    for i, article in enumerate(query_results):    
        print(f'{i + 1}. {article.payload["filename"]} (Score: {round(article.score, 3)})')

    if num_matches > 0:
        doc = query_results[0]
        with open(doc.payload["filename"]) as f:
            contents = f.read()
            return contents
    else:
        return "No matching file found for "+component_name        
                
def query_qdrant(query, top_k=5):
    openai_client = create_openai_client()
    qdrant_client = create_qdrant_client()

    embedded_query = get_embedding(openai_client=openai_client, text=query)
    
    query_results = qdrant_client.search(
        collection_name="camel_docs",
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
         
client = create_openai_client()

# Start a new Thread
thread = client.beta.threads.create()
show_json(thread)

# Add messages
prompt = input("Prompt: ")
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=prompt,
)

# Kickoff the thread 
run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=ASSISTANT_ID,
)

# Wait for completion
run = wait_on_run(client, run, thread)

# Eventually we get a callback requesting a function call
is_function_call = False
if(run.status == "requires_action"):      
    is_function_call = True
    args = get_call_arguments(run)

    outputs=[]              
    
    for a in args:
        doc = fetch_docs(a["call_arguments"]["component"])      
        outputs.append(
            {
                "tool_call_id": a["call_id"],
                "output": "'"+doc+"'"
            }
        )
    
    run = client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread.id,
        run_id=run.id,
        tool_outputs=outputs
        )    

if(is_function_call):    
    run = wait_on_run(client, run, thread)
    if(run.status == "completed"):
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        pretty_print(get_response(thread))
    else:
        show_json(run) # stop here for now. in reality it might be recursive
else:
    # Now that the Run has completed, we can list the Messages
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    pretty_print(get_response(thread))