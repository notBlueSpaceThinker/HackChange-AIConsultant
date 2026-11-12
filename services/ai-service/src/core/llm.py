from functools import lru_cache
from typing import Any

from llama_index.core.llms import (
    LLM,
    ChatMessage,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.llms.custom import CustomLLM
from llama_index.llms.openai_like import OpenAILike

from src.config import settings
from src.schemas.domain.state import Message


class MockLLM(CustomLLM):
    response_text: str = "Answer of mocked model"

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=settings.llm.context_window,
            num_output=settings.llm.max_tokens,
            model_name="mock-llm",
            is_chat_model=True,
        )

    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(text=self.response_text)

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        yield CompletionResponse(text=self.response_text, delta=self.response_text)


@lru_cache
def get_llm() -> LLM:
    if settings.is_llm_mock:
        llm = MockLLM()
    else:
        llm = OpenAILike(
            api_base=settings.llm.url,
            api_key=settings.llm.api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout,
            context_window=settings.llm.context_window,
            max_retries=settings.llm.max_retries,
            is_chat_model=True,
        )
    return llm


def _format_to_llama_message(
    message: Message,
) -> ChatMessage:
    return ChatMessage(
        role=MessageRole.USER if message.role == "user" else MessageRole.ASSISTANT,
        content=message.content,
    )


async def generate_response(
    prompt: str,
    history: list[Message] | None = None,
    system_prompt: str | None = None,
    **kwargs: Any,
) -> str:
    llm = get_llm()
    messages = []

    if system_prompt:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
    if history:
        messages.extend(_format_to_llama_message(message) for message in history)
    messages.append(ChatMessage(role=MessageRole.USER, content=prompt))

    response = await llm.achat(messages, **kwargs)
    return str(response.message.content).strip()
