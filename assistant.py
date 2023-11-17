from openai import OpenAI
from util.utils import show_json, as_json
import time
import sys
import jmespath
import json
import os
import fnmatch

from conf.constants import *

client = OpenAI()

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
    num_matches, matching_files = find_files(component_name)
    if num_matches > 0:
        with open(matching_files[0]) as f:
            contents = f.read()
            return contents
    else:
        return "No matching file found for "+component_name        
                
def find_files(keyword):    
    path = TEXT_DIR+DOMAIN
    # List all files in the directory and its subdirectories
    files = []
    for root, directories, file_path in os.walk(path, topdown=False):
        for name in file_path:
            files.append(os.path.join(root, name))

    # Find files that contain the keyword in their name
    matching_files = [filename for filename in files if fnmatch.fnmatch(filename, f'*{keyword}*')]
    num_matches = len(matching_files)
    print("Num matches: ", num_matches)
    return num_matches, matching_files
    
        
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
    assistant_id=CAMEL_ASSISTANT_ID,
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