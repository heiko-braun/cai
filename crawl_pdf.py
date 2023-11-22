from langchain.document_loaders import PyPDFLoader
from conf.constants import *

loader = PyPDFLoader("./docs/red_hat_fuse-7.12-apache_camel_component_reference-en-us.pdf")
pages = loader.load_and_split()
COLLECTION_NAME="fuse_component_reference"

offset = 31
for page in pages[offset:]:
    page_num = page.metadata["page"]
    print("Parsing page ", page_num)
    try:        
        with open(TEXT_DIR+COLLECTION_NAME+'/page_'+str(page_num) + ".txt", "w", encoding="UTF-8") as f:                                
            f.write(page.page_content)
    except Exception as e:
        print("Unable to parse page " + page_num)
        print(e)