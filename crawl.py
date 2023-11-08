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

# Regex pattern to match a URL
HTTP_URL_PATTERN = r'^http[s]{0,1}://.+$'

# Define OpenAI api_key
# openai.api_key = '<Your API Key>'

# Define root domain to crawl
domain = "camel.apache.org"
full_url = "https://camel.apache.org/components/4.0.x"

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
    
    print(url) # for debugging and to see the progress
        
    # Try extracting the text from the link, if failed proceed with the next item in the queue
    try:
        # Save text from the url to a <url>.txt file
        with open('text/'+domain+'/'+url[8:].replace("/", "_") + ".txt", "w", encoding="UTF-8") as f:

            # Get the text from the URL using BeautifulSoup
            soup = BeautifulSoup(requests.get(url).text, "html.parser")

            # Get the text but remove the tags
            text = soup.get_text()

            # If the crawler gets to a page that requires JavaScript, it will stop the crawl
            if ("You need to enable JavaScript to run this app." in text):
                print("Unable to parse page " + url + " due to JavaScript being required")
        
            # Otherwise, write the text to the file in the text directory
            f.write(text)
    except Exception as e:
        print("Unable to parse page " + url)
        print(e)

    
# grab the releavtn links first, before parsing them one by one
entry_point = urllib.request.urlopen(full_url).read()
content_links = relevant_content_links(entry_point)
print('Found {0} links to relevant content'.format(len(content_links)))

# for path in content_links:
#     crawl(full_url+"/"+path)
   

