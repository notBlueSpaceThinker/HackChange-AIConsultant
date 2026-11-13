from src.core.llm import generate_response
from src.schemas.domain.state import Message, ConsultantReply
from src.summarization.prompts import SummaryPrompt


async def run_pipeline(
    user_message: Message,
    assistant_message: ConsultantReply,
    summary: str | None = None,
) -> str:
    raw_answer = await generate_response(
        prompt=SummaryPrompt.format_user_prompt(
            user_message=user_message.content,
            assistant_message=assistant_message.answer,
            previous_summary=summary,
        ),
        system_prompt=SummaryPrompt.SYSTEM_PROMPT,
        temperature=0.0,
        additional_kwargs={"extra_body": {
            "chat_template_kwargs":{
                "enable_thinking": False
                },
            },
        },
    )
    return raw_answer.strip()
