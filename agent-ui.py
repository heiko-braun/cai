import streamlit as st
import psycopg2

from core.MyStreamlitCallbackHandler import MyStreamlitCallbackHandler

from langchain.schema import AIMessage, HumanMessage

from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)

from core.costs import TokenCostProcess, CostCalcAsyncHandler


from core.agent import agent_executor, agent_llm

from conf.constants import PG_URL

# --

st.set_page_config(
    page_title="Camel Quickstart Assistant",
    page_icon="🦜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

"# Camel Quickstart Assistant"

starter_message = "How can I help you?"
if "messages" not in st.session_state or st.button("Clear Thread"):
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
    except (Exception, psycopg2.DatabaseError) as error:
        print("Failed to insert feedback: ", str(error))        
    finally:
        if conn is not None:
            conn.close()    

agent_memory = AgentTokenBufferMemory(llm=agent_llm)
for msg in st.session_state.messages:
    
    # [hb] don't know how, but empty message sneak in an occupy the UI
    if msg.content == "":
        continue

    if isinstance(msg, AIMessage):        
        st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    
    agent_memory.chat_memory.add_message(msg)

if prompt := st.chat_input(placeholder=starter_message):
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        st_callback = MyStreamlitCallbackHandler(
            parent_container=st.container(),
            collapse_completed_thoughts=True,
            expand_new_thoughts=False,
            max_thought_containers=4            
            )

        token_cost_process = TokenCostProcess()
        response = agent_executor(
            {"input": prompt, "history": st.session_state.messages},
            callbacks=[st_callback, CostCalcAsyncHandler( "gpt-3.5-turbo-1106", token_cost_process )],
            include_run_info=True,
        )
        print(token_cost_process.get_cost_summary())

        st.session_state.messages.append(AIMessage(content=response["output"]))
        st.write(response["output"])
        st.caption("Total Tokens: " + str(token_cost_process.get_total_tokens()))
        agent_memory.save_context({"input": prompt}, response)
        st.session_state["messages"] = agent_memory.buffer
        run_id = response["__run"].run_id

        col_blank, col_text, col1, col2 = st.columns([10, 2, 1, 1])
        with col_text:
            st.text("Feedback:")

        with col1:
            st.button("👍", on_click=send_feedback, args=(run_id, 1, prompt, response["output"]))

        with col2:
            st.button("👎", on_click=send_feedback, args=(run_id, 0, prompt, response["output"]))