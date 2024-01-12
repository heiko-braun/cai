# Inspired by https://raw.githubusercontent.com/langchain-ai/langchain/master/libs/community/langchain_community/callbacks/openai_info.py
# Inspierd by https://github.com/langchain-ai/langchain/issues/3114

from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import LLMResult
from langchain_core.messages import BaseMessage
from uuid import UUID
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, TypeVar, Union

import tiktoken

MODEL_COST_PER_1K_TOKENS = {        
    "prompt": 0.001,       
    "completion": 0.002,
}


class TokenCostProcess:
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    successful_requests: int = 0

    def sum_prompt_tokens( self, tokens: int ):
      self.prompt_tokens = self.prompt_tokens + tokens
      self.total_tokens = self.total_tokens + tokens

    def sum_completion_tokens( self, tokens: int ):
      self.completion_tokens = self.completion_tokens + tokens
      self.total_tokens = self.total_tokens + tokens

    def sum_successful_requests( self, requests: int ):
      self.successful_requests = self.successful_requests + requests

    def get_openai_total_cost_for_model( self, model: str ) -> float:
       return MODEL_COST_PER_1K_TOKENS[model] * self.total_tokens / 1000
    
    def compute_costs(self) -> int:
        prompt_costs = MODEL_COST_PER_1K_TOKENS["prompt"] * self.prompt_tokens / 1000
        completion_costs = MODEL_COST_PER_1K_TOKENS["completion"] * self.completion_tokens / 1000
        cost = prompt_costs+completion_costs
        return cost
    
    def get_cost_summary(self) -> str:

        cost = self.compute_costs()

        return (
            f"Tokens Used: {self.total_tokens}\n"
            f"\tPrompt Tokens: {self.prompt_tokens}\n"
            f"\tCompletion Tokens: {self.completion_tokens}\n"
            f"Successful Requests: {self.successful_requests}\n"
            f"Total Cost (USD): {cost}"
        )
    
    def get_total_tokens(self):
       return self.total_tokens
    
    def get_total_costs(self):
       return self.compute_costs()

class CostCalcAsyncHandler(AsyncCallbackHandler):
    
    model: str = ""
    socketprint = None
    websocketaction: str = "appendtext"
    token_cost_process: TokenCostProcess

    def __init__( self, token_cost_process ):
       self.model = "gpt-3.5-turbo-1106"
       self.token_cost_process = token_cost_process

    def on_llm_start( self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
       encoding = tiktoken.encoding_for_model( self.model )

       if self.token_cost_process == None: return

       for prompt in prompts:
          self.token_cost_process.sum_prompt_tokens( len(encoding.encode(prompt)) )

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
      self.token_cost_process.sum_completion_tokens( 1 )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
      self.token_cost_process.sum_successful_requests( 1 )

    async def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
       
        encoding = tiktoken.encoding_for_model( self.model )              
        self.token_cost_process.sum_prompt_tokens( len(encoding.encode(output)) )
        
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
        
     