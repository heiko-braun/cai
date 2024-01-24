import os
import sys
from dotenv import load_dotenv
load_dotenv()

TEXT_DIR = "./data/text/"
PROCESSED_DIR = "./data/processed/"

ASSISTANT_ID = None
try:
    ASSISTANT_ID = os.environ['ASSISTANT_ID']
except KeyError:
    print('ASSISTANT_ID is missing!')
    sys.exit()

QDRANT_KEY = None
try:
    QDRANT_KEY = os.environ['QDRANT_KEY']
except KeyError:
    print('QDRANT_KEY is missing!')
    sys.exit()

QDRANT_URL = None
try:
    QDRANT_URL = os.environ['QDRANT_URL']
except KeyError:
    print('QDRANT_URL is missing!')
    sys.exit()

PG_URL = None
try:
    PG_URL = os.environ['PG_URL']
except KeyError:
    print('PG_URL is missing!')
    sys.exit()
