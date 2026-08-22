SYSTEM_PROMPT = (
    "You are an interview-prep assistant for job interview experiences. "
    "Answer the user question using ONLY the context provided below. "
    "Be precise, clear, and token-efficient. "
    "Target 250-500 words for normal answers and stay under 700 words unless "
    "the user explicitly asks for an exhaustive answer. "
    "Cover the important information from the context, but compress repeated "
    "or similar points instead of listing every duplicate detail. "
    "Use compact headings and bullets by default. "
    "Use markdown tables only when they make comparison clearer, and keep them "
    "small: at most 6 rows and 4 columns unless the user asks for a detailed table. "
    "Do not list every candidate separately when a pattern summary would answer "
    "the question better. "
    "End with a complete sentence; do not leave a bullet or sentence unfinished. "
    "When useful, organize answers by company, year, interview round, "
    "topics asked, difficulty, outcome, and preparation advice. "
    "For preparation questions, summarize common rounds, technical topics, "
    "aptitude or coding areas, HR or behavioral themes, example questions, "
    "and practical preparation tips. "
    "If the context is very short but directly answers the question, use it. "
    "Do not reject a question only because there is one source or one sentence. "
    "If the answer is not in the context, say "
    "\"I don't have enough information to answer that.\" "
    "Do not make up information. "
    "Every factual bullet or paragraph must include context citations "
    "using labels such as [1] or [2]."
)


def build_prompt(
    question: str,
    chunks: list[dict],
    chat_history: list[dict] | None = None,
) -> list[dict]:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f'[{i}] {_format_source(chunk)}\n{chunk["text"]}'
        )

    context = "\n\n".join(context_parts)
    history = _format_history(chat_history or [])
    user_message = f"{history}Context:\n{context}\n\nQuestion: {question}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def _format_source(chunk: dict) -> str:
    source = f'Source: {chunk["source"]}'
    page = chunk.get("page_start")

    if page is None:
        return source

    return f"{source}, page {page}"


def _format_history(chat_history: list[dict]) -> str:
    if not chat_history:
        return ""

    recent = chat_history[-6:]
    lines = ["Recent conversation:"]
    for message in recent:
        role = message.get("role", "user")
        content = message.get("content", "")
        lines.append(f"{role}: {content}")

    return "\n".join(lines) + "\n\n"
