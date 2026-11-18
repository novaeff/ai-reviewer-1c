from .system_prompt import *
from bsl_parser.analyzer import *
from bsl_parser.entities import *

import requests

MODEL = "qwen2.5-coder:7b"
OLLAMA_URL = "http://localhost:11434"
NUM_CTX = 2048

def review_method(method: BSLMethod, module: BSLModule) -> str:
    """Собирает запрос и отправляет метод в Ollama."""
    if (len(method.hints) == 0): return "Замечаний нет"

    sections = [
        f"Проведи ревью следующего метода 1С:\n"
        f"Сигнатура: {method.signature}\n"
        f"Описание: {method.comment or 'Нет'}",
        method.facts_text(),
    ]

    if method.hints_text():
        sections.append(method.hints_text())

    # Если метод большой, не подгружаем тела соседних методов, чтобы сэкономить память
    include_bodies = method.line_count < 60
    related = module.related_text(method, depth=2, include_bodies=include_bodies, max_chars=1500)
    if related:
        sections.append(related)

    sections.append(f"Код метода (с номерами строк файла):\n```bsl\n{method.numbered_body()}\n```")
    user_prompt = "\n\n".join(sections)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *EXAMPLES,
        {"role": "user", "content": user_prompt},
    ]

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_ctx": NUM_CTX,
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]

def unload_ollama_model() -> None:
    """Выгружает модель из памяти после завершения работы."""
    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "keep_alive": 0},
            timeout=2,
        )
    except Exception:
        pass