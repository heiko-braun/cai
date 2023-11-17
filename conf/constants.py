import os
import sys

DOMAIN = "camel.apache.org"
FULL_URL = "https://camel.apache.org/components/4.0.x/"
TEXT_DIR = "./data/text/"
PROCESSED_DIR = "./data/processed/"

ASSISTANT_ID = None
try:
    ASSISTANT_ID = os.environ['ASSISTANT_ID']
except KeyError:
    print('ASSISTANT_ID is missing!')
    sys.exit()

