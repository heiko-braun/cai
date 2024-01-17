import os
from core.agent import agent_executor, agent_llm

from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)

from langchain.schema import messages_from_dict, messages_to_dict
from langchain.memory.chat_message_histories.in_memory import ChatMessageHistory

import datetime

from abc import ABC, abstractmethod
from statemachine import State
from statemachine import StateMachine

from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import LLMResult
from langchain_core.messages import BaseMessage
from uuid import UUID
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, TypeVar, Union

import psycopg2
import json

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

        blocks= [
            {
                "type": "context",
                "elements": [                   
                    {
                        "type": "mrkdwn",
                        "text": "*"+message+"*"
                    }
                ]
            }
	    ]
         
        slack_response = self.client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            blocks=blocks,
            text=f"{message}"
            )
        
        #print(slack_response)

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
    
    def __init__(self, owner, slack_client, channel, thread_ts, memory, start_message="How can I help you?"):
        
        self.last_activity = datetime.datetime.now()
        self.owner = owner
        self.client = slack_client
        self.feedback = SlackStatus(slack_client=slack_client, channel=channel, thread_ts=thread_ts)
        self.callback_handler = SlackAsyncHandler(feedback=self.feedback)
        # the slack thread representing this conversation
        self.channel = channel
        self.thread_ts = thread_ts

        # internal states
        self.prompt_text = None                
        self.start_message = start_message
        
        # the main interface towards the LLM
        self.agent = agent_executor

        # keeps track of previous messages
        self.memory = memory

        # interim, runtime states
        self.response_handle = None

        super().__init__()

    def get_channel(self):
        return self.channel    

    def get_thread(self):
        return self.thread_ts
    
    def export_memory(self):
        extracted_messages = self.memory.chat_memory.messages
        return messages_to_dict(extracted_messages)        
    
    def is_expired(self):
        return self.last_activity < datetime.datetime.now()-datetime.timedelta(seconds=CONVERSATION_EXPIRY_TIME)
     
    def on_enter_greeting(self):            
            # mimic the first LLM response to get things started
            self.response_handle = {
                "output": self.start_message
            } 

            # lookup owner
            #user_info = self.client.users_info(user=self.owner)

            # share context with thread
            response_text = ":robot: New session: "+self.thread_ts+", owned by: <@"+self.owner+">"    
            blocks = [
               		{
                        "type": "context",
                        "elements": [                           
                            {
                                "type": "mrkdwn",
                                "text": response_text
                            }
                        ]
                    } 
            ]    

            self.client.chat_postMessage(
                channel=self.channel, 
                thread_ts=self.thread_ts,
                blocks=blocks,
                text=response_text            
            )        
            
                                
    # starting a thinking loop    
    def on_enter_running(self):

        print("running ..")

        self.last_activity = datetime.datetime.now()
        self.feedback.set_tagline("Thinking ...")    
        
        # request chat completion
        try:
            self.response_handle = self.agent(
                {"input": self.prompt_text, "history": self.memory.buffer},
                callbacks=[self.callback_handler],
                include_run_info=True,
            )

            self.memory.save_context({"input": self.prompt_text}, self.response_handle)
        except Exception as e:
            print("Failed to call openai (skipping ... ): ", str(e))    
            slack_response = self.client.chat_postMessage(
                channel=self.channel, 
                thread_ts=self.thread_ts,
                text=f"(An error occured during the LLM invocation)",
                mrkdwn=True
            )    
        
        self.resolved()

        
            
    # the assistant has resolved the question
    def on_enter_answered(self):

        print("answered ..")
        response_content = self.response_handle["output"]

        # question complete, show answer         
        slack_response = self.client.chat_postMessage(
            channel=self.channel, 
            thread_ts=self.thread_ts,
            text=f"{response_content}",
            mrkdwn=True
            )
               
        self.feedback.set_visible(False)

    def on_exit_answered(self, text=None):
        print("exit_answered ..")        
        self.prompt_text = text          
        
        # display status widget
        self.feedback.set_visible(True)        

    def on_enter_retired(self):
        self.feedback.set_tagline("Session expired.")  
        
class SlackAsyncHandler(AsyncCallbackHandler):
        
    websocketaction: str = "appendtext"
    
    def __init__( self, feedback):
        self.feedback = feedback                
    
    def on_llm_start( self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
       print("llm start")
       pass

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
      pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
      print("llm end")
      pass

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool starts running."""
        tool_name = serialized["name"]
        self.feedback.print(tool_name + ": " + input_str)                

    async def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        print("tool end")
        pass
        
    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run when a chat model starts running."""
        print("chat model start")
        

def save_session(conversation):
        
    json_export = json.dumps(conversation.export_memory())          
    
    conn = None
    try:
        conn = psycopg2.connect(os.environ['PG_URL'])
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM slack_sessions WHERE channel=%s AND thread=%s;            
            """,
            (conversation.get_channel(), conversation.get_thread())
        )   

        cur.execute("""
            INSERT INTO slack_sessions (channel, thread, data)
            VALUES (%s, %s, %s);    
            """,
            (conversation.get_channel(), conversation.get_thread(), (json_export))
        )   
        
        conn.commit()        
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print("Failed to persist session: ", str(error))        
    finally:
        if conn is not None:
            conn.close()    


def restore_session(client, channel, thread_ts, owner):
    
    conn = None
    try:
        conn = psycopg2.connect(os.environ['PG_URL'])
        cur = conn.cursor()

        
        cur.execute("""
            SELECT id, data FROM slack_sessions WHERE channel=%s AND thread=%s;            
            """,
            (channel, thread_ts)
        )   
        
        row = cur.fetchone()        
        data = row[1]        
        cur.close()      

        if row is not None:            
            message_import = messages_from_dict(data)
            message_history = ChatMessageHistory(messages=message_import)
            
            restored_memory = AgentTokenBufferMemory(llm=agent_llm, chat_memory=message_history)

            conversation = Conversation(
                owner=owner,
                slack_client=client, 
                channel=channel, 
                thread_ts=thread_ts,
                memory=restored_memory,
                start_message="OK, I remember what we talked about - how can I help?"
            )
            return conversation
        else:
            return None
        
    except (Exception, psycopg2.DatabaseError) as error:
        print("Failed to recover session: ", str(error))        
    finally:
        if conn is not None:
            conn.close()    
