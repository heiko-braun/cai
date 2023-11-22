from openai import OpenAI
import httpx
from conf.constants import *
from langchain.prompts import PromptTemplate

from qdrant_client import QdrantClient
from qdrant_client.http import models
import glob
import traceback

from multiprocess import Process, Queue
import time
import queue # imported for using queue.Empty exception

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

import sys
import re

# ---

# create an embedding using openai
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def get_embedding(openai_client, text, model="text-embedding-ada-002"):
   start = time.time()
   text = text.replace("\n", " ")
   resp = openai_client.embeddings.create(input = [text], model=model)
   print("Embedding ms: ", time.time() - start)
   return resp.data[0].embedding

PROMPT_TEMPLATE = PromptTemplate.from_template(
        """
        Extract key pieces of information from the following text. 
        If a particular piece of information is not present, output \"Not specified\".

        Use the following format:
        0. What's the Camel compoment name                    
        1. What are relevant technical concepts mentioned
        3. What thirdparty services or tools are mentioned                

        Don't mention these entities in your response:
        - Apache Camel
        - Java 
        - Maven 
        - Configuring Options
        
        Text: \"\"\"{text}\"\"\"

        """
    )

# extract keywords using the chat API with custom prompt
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def extract_keywords(openai_client, document):
    start = time.time()
    message = PROMPT_TEMPLATE.format(text=document)
    response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": "You are a service used to extract entities from text"},
                {"role": "user", "content": message}
            ]
        )
    print("Extraction ms: ", time.time() - start)
    return response.choices[0].message.content

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

QDRANT_COLLECTION_NAME = "fuse_camel_development"

# Dataset to be upserted
docfiles = []
for _file in glob.glob(TEXT_DIR+QDRANT_COLLECTION_NAME+"/*.txt"):
    docfiles.append({
        "page": re.search("[0-9]", _file)[0],
        "content": docfiles
    })

print(docfiles[0])

print("Upserting N pages: ", len(docfiles))


sys.exit()

# start with a fresh DB everytime this file is run
create_qdrant_client().recreate_collection(
    collection_name=QDRANT_COLLECTION_NAME,
    vectors_config=models.VectorParams(
        size=1536,  # Vector size is defined by OpenAI model
        distance=models.Distance.COSINE,
    ),
)

def do_job(tasks_to_accomplish):
    while True:
        try:
            '''
                try to get task from the queue. get_nowait() function will 
                raise queue.Empty exception if the queue is empty. 
                queue(False) function would do the same task also.
            '''
            task = tasks_to_accomplish.get_nowait()
        except queue.Empty:

            break
        else:
            '''
                if no exception has been raised, add the task completion 
                message to task_that_are_done queue
            '''
            try:
                
                page_number = task["page_number"]
                page_content = task["page_content"]
                
                print("Start page ", page_number)

                openai_client = create_openai_client()    
                qdrant_client = create_qdrant_client()

                # extract keywords                
                entities = extract_keywords(openai_client, page_content)
                
                # Create embeddings            
                embeddings = get_embedding(openai_client=openai_client, text=entities)
                
                # Upsert        
                upsert_resp = qdrant_client.upsert(
                    collection_name=qdrant_collection_name,
                    points=[
                        models.PointStruct(
                            id=page_number,
                            vector=embeddings,
                            payload={
                                "page_number": page_number,
                                "entities": entities            
                            }
                        )
                    ]        
                )
               
                print("Page ", page_number, " completed \n")
                
            except Exception as e:
                print("Failed to process page (skipping ... ): ", page_number)
                traceback.print_exc()
                continue            
            
    return True


def main():
    
    number_of_processes = 1
    tasks_to_accomplish = Queue()
    
    processes = []

    for doc in docfiles:
        tasks_to_accomplish.put(
            {
                "page_number": doc["page"],
                "page_content": doc["content"]
            }
        )

    # creating processes
    for w in range(number_of_processes):
        p = Process(target=do_job, args=[tasks_to_accomplish])
        processes.append(p)
        p.start()

    # completing process
    for p in processes:
        p.join()
    
    return True


if __name__ == '__main__':
    main()
