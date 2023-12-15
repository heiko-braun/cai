import requests
import re
import urllib.request
from bs4 import BeautifulSoup
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse
import os

from conf.constants import *
import argparse

def relevant_content_links(body):
    relevant_links = []
    soup = BeautifulSoup(body, 'html.parser')

    # <div class="nav-panel-menu is-active">
    navigation_block = soup.find("div", class_="nav-panel-menu")    
    
    children = navigation_block.findChildren("a" , recursive=True)
    for link in children:
        relevant_links.append(link.attrs['href'])

    return relevant_links

def crawl(url, collection): 
    
    print("Parsing ... ", url) # for debugging and to see the progress
        
    # Try extracting the text from the link, if failed proceed with the next item in the queue
    try:
        # Save text from the url to a <url>.txt file
        with open(TEXT_DIR+collection+'/'+url[8:].replace("/", "_") + ".txt", "w", encoding="UTF-8") as f:

            # Get the text from the URL using BeautifulSoup
            soup = BeautifulSoup(requests.get(url).text, "html.parser")

            # Get the text but remove the tags
            el = soup.find("div", class_="content")
            text = None
            if(el is not None):                
                text = el.get_text()    

                # If the crawler gets to a page that requires JavaScript, it will stop the crawl
                if ("You need to enable JavaScript to run this app." in text):
                    print("Unable to parse page " + url + " due to JavaScript being required")            
            else:
                print("Could'nt find target element on page: ", url)

            if text is None:
                 text = "No contents"
                                 
            # Otherwise, write the text to the file in the text directory
            f.write("Article source: "+url+"\n\n")
            f.write(text)
            

    except Exception as e:
        print("Unable to parse page " + url)
        print(e)


def remove_data_dir(domain): 
    dir = TEXT_DIR+domain
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
     
def create_data_dir(domain): 
    # Create a directory to store the text files
    if not os.path.exists(TEXT_DIR):
            os.mkdir(TEXT_DIR)

    if not os.path.exists(TEXT_DIR+domain+"/"):
            os.mkdir(TEXT_DIR + domain + "/")

    # Create a directory to store the csv files
    if not os.path.exists(PROCESSED_DIR):
            os.mkdir(PROCESSED_DIR)
            

##
# Main execution
##

#DOMAIN = "rhaetor.github.io_components"
#FULL_URL = "https://rhaetor.github.io/rh-camel/components/next/"

parser = argparse.ArgumentParser(description='Upsert PDF pages')
parser.add_argument('-c', '--collection', help='The target collection name (local storage)', required=True)
parser.add_argument('-url', '--url', help='The full URL to scrape', required=True)
args = parser.parse_args()

# cleanup previous runs
remove_data_dir(args.collection)

# create new data dir
create_data_dir(args.collection)

# grab the relevant links 
entry_point = urllib.request.urlopen(args.url).read()
content_links = relevant_content_links(entry_point)
print('Found {0} links to relevant content'.format(len(content_links)))


# Parse each link one by one
for path in content_links:
    crawl(
         url=args.url+"/"+path, 
         collection=args.collection
         )
   

