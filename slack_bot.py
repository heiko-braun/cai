import os
from openai import OpenAI
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_bolt import App, Ack, Respond
import os
from core.agent import agent_executor, agent_llm
import signal
import sys
import time

from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)

from abc import ABC, abstractmethod
from statemachine import State
from statemachine import StateMachine

# --

# Event API & Web API
app = App(token=os.environ['SLACK_BOT_TOKEN']) 
client = WebClient(os.environ['SLACK_BOT_TOKEN'])
socket = SocketModeHandler(app, os.environ['SLACK_APP_TOKEN'])

starter_message = "How can I help you?"

active_conversations = []

class StatusStrategy(ABC):
    @abstractmethod
    def print(self, message) -> str:
        pass

    @abstractmethod    
    def set_visible(self, is_visible):
        pass

    @abstractmethod    
    def set_tagline(self, tagline):
        pass
        
class SlackStatus(StatusStrategy):

    def __init__(self, slack_client, channel, thread_ts):
        self.client = slack_client
        self.channel = channel
        self.thread_ts = thread_ts

        super().__init__()


    def print(self, message):
        slack_response = client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            text=f"{message}"
            )

    def set_visible(self, is_visible):
        pass  

    def set_tagline(self, tagline):
        slack_response = client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            text=f"{tagline}"
            )

class Conversation(StateMachine):
    "Conversation state machine"    
    
    greeting = State(initial=True)    
    running = State()
    lookup = State()
    answered = State()
    retired = State(final=True)

    listening = greeting.to(answered)
    inquire = answered.to(running)
    resolved = running.to(answered)        
    retire = answered.to(retired)    

    request_docs = running.to(lookup)
    docs_supplied = lookup.to(running)
    
    def __init__(self, slack_client, channel, thread_ts):
        
        self.client = slack_client
        self.feedback = SlackStatus(slack_client=slack_client, channel=channel, thread_ts=thread_ts)

        # the slack thread representing this conversation
        self.channel = channel
        self.thread_ts = thread_ts

        # internal states
        self.prompt_text = None
        self.thread = None
        self.run = None
        
        # the main interface towards the LLM
        self.agent = agent_executor

        # keeps track of previous messages
        self.memory = AgentTokenBufferMemory(llm=agent_llm)

        # interim, runtime states
        self.response_handle = None

        super().__init__()

    def on_enter_greeting(self):            
            # mimic the first LLM response to get things started
            self.response_handle = {
                "output": "How can I help you?"
            }
            self.feedback.print("New Thread: " + str(self.thread_ts)) 
                                

    def on_enter_lookup(self):
        
        self.feedback.set_tagline("Working ...")
        self.feedback.print("Lookup additional information ...")
        
        self.lookups_total = self.lookups_total +1

        # take call arguments and invoke lookup
        args = get_call_arguments(self.run)
        outputs=[]              
        
        for a in args:
            entity_args = a["call_arguments"]["entities"]
            self.feedback.print("Keywords: " + ' | '.join(entity_args)       )
 
            keywords = ' '.join(entity_args)
            
            # we may end up with no keywrods at all
            if(len(keywords)==0 or keywords.isspace()):
                outputs.append(
                    {
                        "tool_call_id": a["call_id"],
                        "output": "'No additional information found.'"
                    }
                )
                continue

            
            #doc = fetch_pdf_pages(entities=keywords, feedback=self.feedback)
            docs = fetch_and_rerank(
                entities=keywords, 
                collections=["rhaetor.github.io_2", "rhaetor.github.io_components_2"],
                feedback=self.feedback
                )
            
            response_content = []
            response_content = [str(d.page_content) for d in docs]
            
            outputs.append(
                {
                    "tool_call_id": a["call_id"],
                    "output": "'"+(' '.join(response_content))+"'"
                }
            )
        
        # submit lookup results (aka tool outputs)
        self.run = self.openai_client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id,
            run_id=self.run.id,
            tool_outputs=outputs
            )    
        
        self.docs_supplied()
        self.feedback.print("Processing new information ...")

    # starting a thinking loop    
    def on_enter_running(self):

        print("running ..")

        self.feedback.set_tagline("Thinking ...")    
        
        # request chat completion
        self.response_handle = self.agent(
            {"input": self.prompt_text, "history": self.memory.buffer},
            callbacks=[],
            include_run_info=True,
        )

        memory.save_context({"input": self.prompt_text}, self.response_handle)
                
        self.resolved()
            
    # the assistant has resolved the question
    def on_enter_answered(self):

        print("answered ..")
        response_content = self.response_handle["output"]

        # question complete, show answer         
        slack_response = self.client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            text=f"{response_content}")
       

        self.feedback.set_visible(False)

    def on_exit_answered(self, text=None):
        print("exit_answered ..")        
        self.prompt_text = text          
        
        # display status widget
        self.feedback.set_visible(True)        

    def on_enter_retired(self):
        self.feedback.set_tagline("This conversation is retired and cannot be activated anymore.")  
        
def graceful_shutdown(signum, frame):
    print("Shutdown bot ...")

    # retire all active conversations
    [ref["conversation"].retire() for ref in active_conversations]    
    time.sleep(3)

    socket.disconnect()
    socket.close()
    sys.exit(0)

memory = AgentTokenBufferMemory(llm=agent_llm)

def find_conversation(thread_ts):

    for ref in active_conversations:
        if(ref["id"]==thread_ts):
            return ref["conversation"]
        else:
            return None
            
# This gets activated when the bot is tagged in a channel    
# it will start a new thread that will hold the conversation
@app.event("app_mention")
def handle_message_events(body, logger):
        
    thread_ts = body["event"].get("thread_ts")

    if thread_ts:
        # handle direct mention in thread
        pass
    else:
        # handle direct mention outside thread (in channel)

        print(str(body["event"]["text"]).split(">")[1])
        
        response_channel = body["event"]["channel"]
        response_thread = body["event"]["event_ts"]

        # register new conversation        
        conversation = Conversation(
            slack_client=client, 
            channel=response_channel, 
            thread_ts=response_thread
            )
        
        active_conversations.append({
            "id": response_thread, 
            "conversation": conversation
            })
        
        conversation.listening()  
        
# the main loop for interaction with the bot
# the bot ignores messages outsides threads        
@app.event("message")
def handle_message_events(event, say):
    
    if event.get("thread_ts"):
        # within threads we listen to messages
        print("handle message within thread")

        text = event.get('text')                
        response_channel = event.get("channel")
        response_thread = event.get("thread_ts")

        conversation = find_conversation(response_thread)

        if(conversation is None):
            slack_response = client.chat_postMessage(
                channel=response_channel, 
                thread_ts=response_thread,
                text=f"This conversation has been retired"
            )
            
        else:
            conversation.inquire(text)

    else:
        # outside thread we ingore messages
        pass        

if __name__ == "__main__":
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    socket.start()
