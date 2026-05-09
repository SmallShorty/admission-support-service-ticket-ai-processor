import requests
import json
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "deepseek-r1:8b"
PROXIES = {"http": None, "https": None}

SHORT_PROMPT = 'Напиши обращение абитуриента о проблеме со входом в личный кабинет. Персона: студент с высокими баллами, официальный стиль. 2-5 предложений, без эмодзи. Верни JSON: {"persona_id": "A", "category_id": "tech_issue", "ticket_text": "..."}'

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "Отвечай только валидным JSON без лишнего текста."},
        {"role": "user", "content": SHORT_PROMPT},
    ],
    "stream": False,
    "options": {
        "temperature": 0.9,
        "num_ctx": 1024,
    },
    "format": "json",
}

print(f"Модель: {MODEL}")
print(f"URL:    {OLLAMA_URL}")
print("Отправляю запрос...\n")
t0 = time.monotonic()

try:
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120, proxies=PROXIES)
    elapsed = time.monotonic() - t0
    resp.raise_for_status()
    data = resp.json()

    content = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    tps = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else 0

    print("--- Результат ---")
    print(f"Время ответа:        {elapsed:.1f}с")
    print(f"Токены prompt:       {prompt_eval_count}")
    print(f"Токены generated:    {eval_count}")
    print(f"Скорость:            {tps:.1f} tok/s")
    print(f"\nОтвет модели:\n{content[:500]}")

except Exception as e:
    elapsed = time.monotonic() - t0
    print(f"ОШИБКА после {elapsed:.1f}с: {type(e).__name__}: {e}")
