import ollama

from config.settings import LLM_MODEL, LLM_NUM_CTX, LLM_NUM_GPU, LLM_TEMPERATURE


def get_answer(messages: list[dict]) -> str:
    options = {
        "temperature": LLM_TEMPERATURE,
        "num_ctx": LLM_NUM_CTX,
    }
    if LLM_NUM_GPU is not None:
        options["num_gpu"] = int(LLM_NUM_GPU)

    response = ollama.chat(
        model=LLM_MODEL,
        messages=messages,
        options=options,
    )
    return response["message"]["content"]
