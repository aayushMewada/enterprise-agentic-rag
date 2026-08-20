from groq import Groq

from config.settings import GROQ_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE

_client = None


def _groq_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def get_answer(messages: list[dict]) -> str:
    response = _groq_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=LLM_TEMPERATURE,
        max_completion_tokens=LLM_MAX_TOKENS,
        stream=False,
    )
    return response.choices[0].message.content or ""


def stream_answer(messages: list[dict]):
    stream = _groq_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=LLM_TEMPERATURE,
        max_completion_tokens=LLM_MAX_TOKENS,
        stream=True,
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
