from openai import OpenAI
from conf.constants import *
from langchain.prompts import PromptTemplate

client = OpenAI()

def read_file(filename):
    with open(TEXT_DIR+DOMAIN+"/"+filename) as f:
        contents = f.read()
        return contents

def n_words(text, size):
    words = text.split()
    n_words = ' '.join(words[:size])
    return n_words

# --- 

test_files = [
    "camel.apache.org_components_4.0.x__kafka-component.html.txt",
    "camel.apache.org_components_4.0.x__eips_idempotentConsumer-eip.html.txt",
    "camel.apache.org_components_4.0.x__languages_jsonpath-language.html.txt",
    "camel.apache.org_components_4.0.x__sql-component.html.txt",
    "camel.apache.org_components_4.0.x__eips_split-eip.html.txt"
    ]

prompt_template = PromptTemplate.from_template(
        """
        Extract key pieces of information from the following text. 
        If a particular piece of information is not present, output \"Not specified\".

        Use the following format:
        0. What's the Camel compoment name            
        1. What others Camel components are mentioned
        2. What are relevant technical concepts mentioned
        3. What thirdparty services or tools are mentioned                

        Don't mention these entities or concepts in your response:
        - Apache Camel
        - Java 
        - Maven 
        
        Text: \"\"\"{text}\"\"\"

        """
    )

prompt_template2 = PromptTemplate.from_template(
        """
        Extract configuration properties from the following text. 

        Here is are two examples of the output format we expect:
        
        Name: autoCreateBucket 
        Description: Setting the autocreation of the S3 bucket bucketName. This will apply also in case of moveAfterRead option enabled and it will create the destinationBucket if it doesn’t exist already.
        Default: false
        Type: Boolean 
        
        Name: configuration
        Description: The component configuration.
        Default: 
        Type: AWS2S3Configuration

        Text: \"\"\"{text}\"\"\"

        """
    )


for file in test_files:

    test_doc = read_file(file)

    message = prompt_template.format(text=n_words(test_doc, 3000))

    # Request gpt-3.5-turbo for chat completion
    response = client.chat.completions.create(
    model="gpt-3.5-turbo-1106",
    messages=[
        {"role": "system", "content": "You are a service used to extract entities from text"},
        {"role": "user", "content": message}
    ]
    )

    # Print the response 
    reply = response.choices[0].message.content
    print(file, "\n")
    print(f"OpenAI: \n {reply}\n\n")
