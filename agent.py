import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY", ""),
    base_url=os.environ.get("LLM_API_BASE", "https://api.openai.com/v1"),
)

MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are OpenClaw, an autonomous AI agent. "
    "Think step by step. Be precise and helpful. "
    "If you need to reason, show your reasoning."
)


def chat_stream(message: str, history: list[dict]):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=4096,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


def chat(message: str, history: list[dict]) -> str:
    return "".join(chat_stream(message, history))