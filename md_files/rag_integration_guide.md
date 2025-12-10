# RAG Интеграция — пошаговая инструкция

## 1. Построй индекс знаний
```bash
pip install sentence-transformers  # если ещё не установлены эмбеддинги
python -m rag.index_builder \
  --knowledge-file data/processed_dataset/knowledge/knowledge_chunks.jsonl \
  --output-dir data/rag_index \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2
```
- на входе `knowledge_chunks.jsonl` из `dataset_pipeline`;
- на выходе `data/rag_index/embeddings.npy` и `records.jsonl`.

## 2. Запусти RAG-инференс
```bash
python -m rag.rag_inference \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --adapter-path outputs/lora_adapter \
  --index-dir data/rag_index \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --top-k 4 \
  "Где найти резюме Марселя?"
```
- в ответе модель использует стиль LoRA-адаптера и цитирует найденные факты;
- без аргумента `question` запускается интерактивный режим.

## 3. Настрой системный промт (опционально)
- Используй `--system-prompt "..."`, чтобы скорректировать манеру общения;
- помни: RAG-промт уже включает секции `Контекст` и инструкцию не выдумывать факты.

## 4. Обновляй индекс при изменении знаний
- повторяй шаг 1, когда появляются новые документы;
- старые файлы в `data/rag_index/` можно удалить перед пересборкой.

## 5. Советы
- `--load-in-4bit` помогает экономить память на инференсе;
- если хочешь другой эмбеддер, подставь его id в `--embedding-model`;
- проверяй блок «--- Контекст ---» в выводе, чтобы видеть, какие знания использованы.
