import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style

from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)

from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import LLMResult
from langchain_core.messages import BaseMessage
from uuid import UUID
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, TypeVar, Union

from core.costs import TokenCostProcess, CostCalcAsyncHandler

from core.agent import agent_executor, agent_llm

import argparse

# ---

style = Style.from_dict(
    {
        "completion-menu.completion": "bg:#008888 #ffffff",
        "completion-menu.completion.current": "bg:#00aaaa #000000",
        "scrollbar.background": "bg:#88aaaa",
        "scrollbar.button": "bg:#222222",
    }
)

class CLIAsyncHandler(AsyncCallbackHandler):
            
    def on_llm_start( self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:        
        pass

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
      pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:      
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
        print(f"{tool_name} : {input_str}")                

    async def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:        
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
        print("Thinking ...")


def main(args):
    
    memory = AgentTokenBufferMemory(llm=agent_llm)
    
    session = PromptSession(
        lexer=None, completer=None, style=style
    )

    if(args.filename == None):
        
        # enter QA loop

        print("How can I help you?")

        while True:
            try:            
                prompt_text = session.prompt("> ")
            except KeyboardInterrupt:
                continue  # Control-C pressed. Try again.
            except EOFError:
                break  # Control-D pressed.

            # request chat completion
            try:
                response_handle = agent_executor(
                    {"input": prompt_text, "history": memory.buffer},
                    callbacks=[CLIAsyncHandler()],
                    include_run_info=True,
                )

                memory.save_context({"input": prompt_text}, response_handle)

                print(f"\n{response_handle['output']}")

            except Exception as e:
                print("Failed to call Openai API: ", str(e))                

        print("GoodBye!")

    else:

        # enter one-shot prompting from file

        with open(args.filename) as f:
            prompt = f.read()        
        prompt_text = prompt.replace('\n', ' ').replace('\r', '')        

        response_handle = agent_executor(
                {"input": prompt_text, "history": []},
                callbacks=[CLIAsyncHandler()],
                include_run_info=True,
            )

        print(f"\n{response_handle['output']}")



if __name__ == "__main__":    
    parser = argparse.ArgumentParser(description='Camel Quickstart Assistant')
    parser.add_argument('-f', '--filename', help='The input file that will be taken as a prompt', required=False)
    args = parser.parse_args()

    main(args)