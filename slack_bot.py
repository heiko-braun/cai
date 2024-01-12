import os
import signal
import sys
import time
import threading

import datetime as dt
from apscheduler.schedulers.background import BackgroundScheduler

from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_bolt import App, Ack, Respond

from core.agent import agent_executor, agent_llm
from core.slack import Conversation

# --

# Event API & Web API
app = App(token=os.environ['SLACK_BOT_TOKEN']) 
client = WebClient(os.environ['SLACK_BOT_TOKEN'])
socket = SocketModeHandler(app, os.environ['SLACK_APP_TOKEN'])
scheduler = BackgroundScheduler()

active_conversations = []
conversation_lock = threading.Lock()

# make sure conversation are retried when bot stops
def graceful_shutdown(signum, frame):    
    print("Shutdown bot ...")

    # retire all active conversations
    [ref["conversation"].retire() for ref in active_conversations]    
    time.sleep(3)

    # stop the scheduler
    scheduler.shutdown(wait=False)

    # stop the listener
    socket.disconnect()
    socket.close()

    sys.exit(0)

def find_conversation(thread_ts):
    with conversation_lock:
        for ref in active_conversations:
            if(ref["id"]==thread_ts):
                return ref["conversation"]
            else:
                return None
        
def retire_inactive_conversation():
    with conversation_lock:        
        for ref in active_conversations:
            conversation = ref["conversation"]
            if(conversation.is_expired()):
                if(conversation.current_state!='answered'):            
                    conversation.retire()
                    active_conversations.remove(ref)
                else:
                    print("Conversation is still active, keep for next cycle: ", str(conversation))    
                    
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
                text=f"This conversation has been retired. Please start a new one ine the main thread."
            )
            
        else:
            conversation.inquire(text)

    else:
        # outside thread we ingore messages
        pass        


if __name__ == "__main__":
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # scheduler reaper
    scheduler.add_job(retire_inactive_conversation, 'interval', seconds=5, id='retirement_job')
    scheduler.start()

    # start listening for messages
    socket.start()
    
    
    