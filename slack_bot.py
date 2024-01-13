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

from http.server import BaseHTTPRequestHandler, HTTPServer
from multiprocessing import Process

# --

# Event API & Web API
app = App(token=os.environ['SLACK_BOT_TOKEN']) 
client = WebClient(os.environ['SLACK_BOT_TOKEN'])
socket = SocketModeHandler(app, os.environ['SLACK_APP_TOKEN'])
scheduler = BackgroundScheduler()

active_conversations = []
conversation_lock = threading.RLock()

def find_conversation(channel, thread_ts):
    
    match = None
    with conversation_lock:
        for ref in active_conversations:            
            if(ref["channel"]==channel and ref["thread"]==str(thread_ts)):
                match = ref["conversation"]
                break
    return match        
        
def retire_inactive_conversation():
    
    with conversation_lock:
        print("Total conversations: "+str(len(active_conversations)))

        # dump state
        [print(ref) for ref in active_conversations]

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
                
        response_channel = body["event"]["channel"]
        response_thread = body["event"]["event_ts"]
        
        # register new conversation        
        conversation = Conversation(
            slack_client=client, 
            channel=response_channel, 
            thread_ts=response_thread
            )
        
        with conversation_lock:
            active_conversations.append({
                "channel": response_channel,
                "thread": str(response_thread), 
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
        
        response_channel = event.get("channel")
        response_thread = event.get("thread_ts")

        conversation = find_conversation(response_channel, response_thread)

        if(conversation is None):
            slack_response = client.chat_postMessage(
                channel=response_channel, 
                thread_ts=response_thread,
                text=f"Cannot find conversation ({response_thread}), is it expired?"
            )
            
        else:
            text = event.get('text')                
            conversation.inquire(text)

    else:
        # outside thread we ingore messages
        pass        


class HealthcheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Sending a 200 OK response
        self.send_response(200)
        # Setting the header
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        # Sending the response message
        message = "Hello, World! This is a simple HTTP server."
        # Writing the message body
        self.wfile.write(message.encode())

def run_healthcheck():            
    server_address = ("0.0.0.0", 8080)
    httpd = HTTPServer(server_address, HealthcheckHandler)

    print(f"Healthcheck running on {server_address}")
    # Running the server
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    

healthcheck_process = Process(target=run_healthcheck, daemon=True)    

# make sure conversation are retried when bot stops
def graceful_shutdown(signum, frame):    
    print("Shutdown bot ...")

    # retire all active conversations
    [ref["conversation"].retire() for ref in active_conversations]    
    time.sleep(3)

    # stop the scheduler
    scheduler.shutdown(wait=True)

    # stop the listener
    socket.disconnect()
    socket.close()

    healthcheck_process.kill()

    sys.exit(0)


if __name__ == "__main__":
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    # scheduler reaper
    scheduler.add_job(retire_inactive_conversation, 'interval', seconds=5, id='retirement_job')
    scheduler.start()

    # start healthecheck listener    
    healthcheck_process.start()
    
    # start listening for messages
    socket.start()
    
    
    