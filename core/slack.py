import os
from core.agent import agent_executor, agent_llm

from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)

import datetime

from abc import ABC, abstractmethod
from statemachine import State
from statemachine import StateMachine

# --

# the time in seconds, after which a conversation will be retried if inactive
CONVERSATION_EXPIRY_TIME=120

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
        slack_response = self.client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            text=f"{message}"
            )

    def set_visible(self, is_visible):
        pass  

    def set_tagline(self, tagline):

        blocks= [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "*"+tagline+"*"
                    }
                ]
            }
	    ]

        slack_response = self.client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            blocks=blocks,
            text=tagline
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
        
        self.last_activity = datetime.datetime.now()
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

    def is_expired(self):
        return self.last_activity < datetime.datetime.now()-datetime.timedelta(seconds=CONVERSATION_EXPIRY_TIME)
     
    def on_enter_greeting(self):            
            # mimic the first LLM response to get things started
            self.response_handle = {
                "output": "How can I help you?"
            }            
                                
    # starting a thinking loop    
    def on_enter_running(self):

        print("running ..")

        self.last_activity = datetime.datetime.now()
        self.feedback.set_tagline("Thinking ...")    
        
        # request chat completion
        self.response_handle = self.agent(
            {"input": self.prompt_text, "history": self.memory.buffer},
            callbacks=[],
            include_run_info=True,
        )

        self.memory.save_context({"input": self.prompt_text}, self.response_handle)
                
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
        
