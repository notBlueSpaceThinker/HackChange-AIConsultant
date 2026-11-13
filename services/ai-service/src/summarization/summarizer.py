from src.core.llm import generate_response
from src.schemas.domain.state import Message
from src.summarization.prompts import SummaryPrompt


async def run_pipeline(
    user_message: Message,
    assistant_message: str,
    summary: str | None = None,
) -> str:
    raw_answer = await generate_response(
        prompt=SummaryPrompt.format_user_prompt(
            user_message=user_message.content,
            assistant_message=assistant_message,
            previous_summary=summary,
        ),
        system_prompt=SummaryPrompt.SYSTEM_PROMPT,
        temperature=0.0,
        extra_body={"think": False},
    )
    return raw_answer.strip()
