from openai import OpenAI

# Подключаемся к локальному прокси
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # прокси обрабатывает аутентификацию
)

print("Отправляю запрос через прокси...")
completion = client.chat.completions.create(
    model="Qwen/Qwen3-32B-FP8",
    messages=[{"role": "user", "content": "Привет, как дела?"
    ""}]
)

print("\nОтвет:")
print(completion.choices[0].message.content)
