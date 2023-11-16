import requests
import re
import urllib.request
from bs4 import BeautifulSoup
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse
import os
import pandas as pd
import tiktoken
import openai
import numpy as np
from openai.embeddings_utils import distances_from_embeddings, cosine_similarity
from ast import literal_eval

from conf.constants import domain, full_url

# Define OpenAI api_key
# openai.api_key = '<Your API Key>'


def relevant_content_links(body):
    relevant_links = []
    soup = BeautifulSoup(body, 'html.parser')

    # <div class="nav-panel-menu is-active">
    navigation_block = soup.find("div", class_="nav-panel-menu")    
    
    children = navigation_block.findChildren("a" , recursive=True)
    for link in children:
        relevant_links.append(link.attrs['href'])

    return relevant_links

def crawl(url): 
    
    print("Parsing ... ", url) # for debugging and to see the progress
        
    # Try extracting the text from the link, if failed proceed with the next item in the queue
    try:
        # Save text from the url to a <url>.txt file
        with open('text/'+domain+'/'+url[8:].replace("/", "_") + ".txt", "w", encoding="UTF-8") as f:

            # Get the text from the URL using BeautifulSoup
            soup = BeautifulSoup(requests.get(url).text, "html.parser")

            # Get the text but remove the tags
            text = soup.find("div", class_="content").get_text()    

            # If the crawler gets to a page that requires JavaScript, it will stop the crawl
            if ("You need to enable JavaScript to run this app." in text):
                print("Unable to parse page " + url + " due to JavaScript being required")
        
            # Otherwise, write the text to the file in the text directory
            f.write("Article source: "+url+"\n\n")
            f.write(text)
    except Exception as e:
        print("Unable to parse page " + url)
        print(e)

def remove_data_dir(): 
    dir = "texts/"
    if os.path.exists(dir):
        for the_file in os.listdir(dir):
            file_path = os.path.join(dir, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                else:
                    clear_folder(file_path)
                    os.rmdir(file_path)
            except Exception as e:
                print(e)
     
def create_data_dir(): 
    # Create a directory to store the text files
    if not os.path.exists("text/"):
            os.mkdir("text/")

    if not os.path.exists("text/"+domain+"/"):
            os.mkdir("text/" + domain + "/")

    # Create a directory to store the csv files
    if not os.path.exists("processed"):
            os.mkdir("processed")
            

##
# Main execution
##

# cleanup previous runs
remove_data_dir()

# grab the relevant links 
entry_point = urllib.request.urlopen(full_url).read()
content_links = relevant_content_links(entry_point)
print('Found {0} links to relevant content'.format(len(content_links)))

# create new data dir
create_data_dir()

# Parse each link one by one
for path in content_links:
    crawl(full_url+"/"+path)
   

