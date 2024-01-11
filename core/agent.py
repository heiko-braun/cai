
__all__ = ['agent_executor', 'agent_llm', 'agent_memory'] 

from langchain.embeddings import OpenAIEmbeddings
from langchain.agents import OpenAIFunctionsAgent, AgentExecutor

from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage
from langchain.prompts import MessagesPlaceholder

from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient
from conf.constants import *


from langchain.tools import Tool


from core.CustomTools import QuarkusReferenceTool, CamelCoreTool


def create_qdrant_client(): 
    client = QdrantClient(
       QDRANT_URL,
        api_key=QDRANT_KEY,
    )
    return client

def configure_retriever(collection_name):
    
    qdrant = Qdrant(
        client=create_qdrant_client(), 
        collection_name=collection_name, 
        embeddings=OpenAIEmbeddings())
    
    retriever = qdrant.as_retriever(        
        search_type="mmr",
        search_kwargs={"fetch_k":15, "k": 6, "lambda_mult":0.85}
        ) 
        
    return retriever

def create_lookup_tool(retriever, name, description):
    return Tool(
        name=name,
        description=description,
        func=retriever.get_relevant_documents                       
    )

# tools offering access to explicit knowledge
tooling_guide = create_lookup_tool(
    configure_retriever("tooling_guide_2"),
    "search_tooling_guide",
    "Useful when you need to answer questions about tools (i.e. jbang, command line, maven plugins, vscode) for developing Camel applications. Input should be a list of 5-8 keywords from the original question",
)

spring_reference = create_lookup_tool(
    configure_retriever("spring_reference_2"),
    "search_spring_reference",
    "Useful when you need to answer questions about specific Camel Components used within a Spring Boot Application. Input should be a list of 5-8 keywords from the original question",
)

spring_started_tool = create_lookup_tool(
    configure_retriever("spring_get_started_2"),
    "search_spring_getting_started",
    "Useful when you need to answer questions about creating projects using Spring Boot and Camel. Input should be a list of 5-8 keywords from the original question",
)

quarkus_started_tool = create_lookup_tool(
    configure_retriever("quarkus_getting_started_2"),
    "search_quarkus_getting_started",
    "Useful when you need to answer questions about creating projects with Quarkus and Camel. Input should be a list of 5-8 keywords from the original question",
)

tools = [CamelCoreTool(), tooling_guide, QuarkusReferenceTool(), quarkus_started_tool, spring_reference, spring_started_tool]

# LLM instructions
agent_llm = ChatOpenAI(temperature=0, streaming=True, model="gpt-4-1106-preview")

message = SystemMessage(
    content=(
        """
        You are an assistant helping software developers develop applications using the Apache Camel framework. The framework is used to integrate systems.
        Unless otherwise explicitly stated, it is probably fair to assume that questions are about Apache Camel.         

        You always request additional information using the functions provided before answering the original question.        

        Please base your answer only on the search results and nothing else!
        Very important! Your answer MUST be grounded in the search results provided.
        Please explain why your answer is grounded in the search results!
        
        If the user asks for an example, provide end-to-end code examples, for instance the full Java source for a Camel route, any required configuration settings and maven artefacts references.
        Otherwise, respond by explaining key concepts based on the information provided in the context.
        """       
    )
)
prompt = OpenAIFunctionsAgent.create_prompt(
    system_message=message,
    extra_prompt_messages=[MessagesPlaceholder(variable_name="history")],
)
agent = OpenAIFunctionsAgent(
     llm=agent_llm, 
     tools=tools, 
     prompt=prompt
     ) 

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    return_intermediate_steps=True,
    max_iterations=5,
    early_stopping_method="generate",
)