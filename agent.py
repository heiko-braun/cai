import streamlit as st

from langchain.embeddings import OpenAIEmbeddings
from langchain.agents import OpenAIFunctionsAgent, AgentExecutor
from langchain.agents.agent_toolkits import create_retriever_tool
from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, AIMessage, HumanMessage, BaseMessage, FunctionMessage
from langchain.prompts import MessagesPlaceholder

from langsmith import Client

# --
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient
from conf.constants import *
from core.MyStreamlitCallbackHandler import MyStreamlitCallbackHandler

import psycopg2
from langchain.tools import Tool


from core.CustomTools import QuarkusReferenceTool

client = Client()

st.set_page_config(
    page_title="Camel Quickstart Assitant",
    page_icon="🦜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

"# Camel Quickstart Assistant"

def create_qdrant_client(): 
    client = QdrantClient(
       QDRANT_URL,
        api_key=QDRANT_KEY,
    )
    return client

@st.cache_resource(ttl="1h")
def configure_retriever(collection_name):
    
    qdrant = Qdrant(
        client=create_qdrant_client(), 
        collection_name=collection_name, 
        embeddings=OpenAIEmbeddings())
    
    # top k and threshold settings see https://python.langchain.com/docs/modules/data_connection/retrievers/vectorstore
    return qdrant.as_retriever(        
        search_type="mmr",
        search_kwargs={"k": 5}
        ) 

def create_lookup_tool(retriever, name, description):
    return Tool(
        name=name,
        description=description,
        func=retriever.get_relevant_documents                       
    )


def query_quarkus_stores(query: str) -> str:
    """Sends a POST request to the given url with the given body and parameters."""
    result = requests.post(url, json=body, params=parameters)
    return f"Status: {result.status_code} - {result.text}"

# tools offering access to explicit knowledge
tooling_guide = create_lookup_tool(
    configure_retriever("tooling_guide"),
    "search_tooling_guide",
    "Useful when you need to answer questions about tools used when developing Camel application. Input should be terms of certain tools or workflows when developing",
)

spring_reference = create_lookup_tool(
    configure_retriever("spring_reference"),
    "search_spring_reference",
    "Useful when you need to answer questions about Camel Components used with Spring Boot, i.e component configuration options or specifics of third-party systems.",
)

spring_started_tool = create_lookup_tool(
    configure_retriever("spring_get_started"),
    "search_spring_getting_started",
    "Useful when you need to answer questions about setting up Spring Boot projects with Camel. Input should be a term related to spring boot project setup.",
)

tools = [spring_started_tool, spring_reference, tooling_guide, QuarkusReferenceTool()]

# LLM instructions
llm = ChatOpenAI(temperature=0, streaming=True, model="gpt-3.5-turbo-1106")
message = SystemMessage(
    content=(
        "You are an assistant helping software developers create integrations with third-party systems using the Apache Camel framework."
        "Unless otherwise explicitly stated, it is probably fair to assume that questions are about Apache Camel. "
        "You always request additional information using the functions provided before answering the original question."
        "If possible, provide examples that include Java code within the response."
    )
)
prompt = OpenAIFunctionsAgent.create_prompt(
    system_message=message,
    extra_prompt_messages=[MessagesPlaceholder(variable_name="history")],
)
agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt) # TODO: does it support a `max_iterations` parameter?
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    return_intermediate_steps=True,
)
memory = AgentTokenBufferMemory(llm=llm)
starter_message = "How can I help you?"
if "messages" not in st.session_state or st.sidebar.button("Clear message history"):
    st.session_state["messages"] = [AIMessage(content=starter_message)]

def replay_package():
    package = []
    for msg in st.session_state.messages:
        
        if msg.content == "":
            continue
        
        if isinstance(msg, AIMessage):        
            package.append("# Assistant: "+ msg.content + "\n")
        elif isinstance(msg, HumanMessage):
            package.append("# User: " + msg.content + "\n")

    orig_prompt = package[1:2][0]
    full_thread = '\n'.join(package)
    return orig_prompt, full_thread 
    

def send_feedback(run_id, score, prompt, response):
    orig_prompt, full_thread = replay_package()
    conn = None
    try:
        conn = psycopg2.connect(PG_URL)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO feedback (run_id, score, prompt, response)
            VALUES (%s, %s, %s, %s);    
            """,
            (str(run_id), score, orig_prompt, full_thread)
        )   
        
        conn.commit()
        # close the database communication
        cur.close()
    except psycopg2.DatabaseError as error:
        print("Failed to insert feedback: ", str(error))        
    finally:
        if conn is not None:
            conn.close()    


for msg in st.session_state.messages:
    
    # [hb] don't know how, but empty message sneak in an occupy the UI
    if msg.content == "":
        continue

    if isinstance(msg, AIMessage):        
        st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    
    memory.chat_memory.add_message(msg)

if prompt := st.chat_input(placeholder=starter_message):
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        st_callback = MyStreamlitCallbackHandler(
            parent_container=st.container(),
            collapse_completed_thoughts=True,
            expand_new_thoughts=False,
            max_thought_containers=4            
            )
        response = agent_executor(
            {"input": prompt, "history": st.session_state.messages},
            callbacks=[st_callback],
            include_run_info=True,
        )
        st.session_state.messages.append(AIMessage(content=response["output"]))
        st.write(response["output"])
        memory.save_context({"input": prompt}, response)
        st.session_state["messages"] = memory.buffer
        run_id = response["__run"].run_id

        col_blank, col_text, col1, col2 = st.columns([10, 2, 1, 1])
        with col_text:
            st.text("Feedback:")

        with col1:
            st.button("👍", on_click=send_feedback, args=(run_id, 1, prompt, response["output"]))

        with col2:
            st.button("👎", on_click=send_feedback, args=(run_id, 0, prompt, response["output"]))