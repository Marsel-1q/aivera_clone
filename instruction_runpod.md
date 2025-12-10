## Быстрая заливка `ai-clone-bundle` на удалённый сервер через ngrok

Ниже — минимальный «installer» без токенов и флагов. Локально собираем архив, отдаём через `python -m http.server`, пробрасываем порт ngrok’ом. На сервере одной командой качаем и распаковываем.

# 1) установить (если нет)
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | tee /etc/apt/sources.list.d/ngrok.list
apt update && apt install -y ngrok

# 2) добавить токен (получите на ngrok.com)
ngrok config add-authtoken <YOUR_TOKEN>

# 3) запустить прокси порта 3000
ngrok http 3000


### 1) Подготовка архива на вашей машине
```bash
cd /Users/jakhongir/Documents/startup
# Убедитесь, что в ai-clone-bundle есть models/lora и data/rag_index (если нужны)
ls ai-clone-bundle/models/lora
ls ai-clone-bundle/data/rag_index

# Собрать архив без macOS xattrs
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='._*' -czf /tmp/startup.tgz startup
```

### 2) Локальный HTTP-сервер + ngrok
В одном терминале:
```bash
cd /tmp
cat > install_clone.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-./startup}"
ARCHIVE_URL="${ARCHIVE_URL:-http://localhost:8000/startup.tgz}"

echo "Downloading bundle from $ARCHIVE_URL ..."
mkdir -p "$(dirname "$TARGET_DIR")"
curl -L "$ARCHIVE_URL" | tar xz -C "$(dirname "$TARGET_DIR")"
echo "Done. Bundle is in $TARGET_DIR"
EOF
chmod +x install_clone.sh

# Отдаём архив и скрипт
python3 -m http.server 8000
```
В другом терминале:
```bash
ngrok http 8000
# запомните URL вида https://<ngrok>.ngrok-free.dev
```

### 3) Установка на сервере (Linux, ssh)
Пример в `/root/ai-clone-bundle`:
```bash
ARCHIVE_URL="https://<ngrok>.ngrok-free.dev/ai-clone-bundle.tgz" \
bash <(curl -s https://<ngrok>.ngrok-free.dev/install_clone.sh) /root/ai-clone-bundle
#или если startup
ARCHIVE_URL="https://parodistically-indicatory-lesa.ngrok-free.dev/startup.tgz" \
bash <(curl -s https://parodistically-indicatory-lesa.ngrok-free.dev/install_clone.sh) /root/startup

```
Без пробелов внутри `ARCHIVE_URL`.

### 4) Проверка на сервере
```bash
ls /root/ai-clone-bundle/models/lora          # должны быть adapter_model.safetensors и др.
ls /root/ai-clone-bundle/data/rag_index       # embeddings.npy, records.jsonl если включали
```

### 5) Запуск сервера
```bash
cd /root/ai-clone-bundle
chmod +x run.sh
./run.sh
```
Убедитесь, что в логах есть `Loading LoRA adapter from ...` и RAG индекс подхватился.

### Шпаргалка по типичным ошибкам
- `Malformed input to a URL function` — лишний пробел в `ARCHIVE_URL`.
- `Couldn't connect to server` — ngrok или локальный http сервер не поднят/сменился домен.
- Предупреждения `LIBARCHIVE.xattr...` при распаковке — можно игнорировать или собирать архив с `COPYFILE_DISABLE=1` как выше.


### запус сайта 

```bash
cd /path/to/repo
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# зависимости для пайплайна и обучения
pip install -r dataset_pipeline/requirements.txt
# если нужно — добей transformers/peft/bitsandbytes/trl (train_qlora)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers peft datasets bitsandbytes trl accelerate hf_transfer sentence-transformers
```
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

node -v
npm -v

cd website_clone
npm install
```

```bash
cd website_clone
ENABLE_REAL_TRAINING=true npm run dev   # порт 3000
```

```bash
cd /tmp
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update \
  && sudo apt install ngrok
ngrok version   # проверка
ngrok config add-authtoken 34yduy9qaOWzPPWXk3Z3cLEsWIF_47aDGJQwwCQTz1srD8Ny5
```

проверка
curl http://127.0.0.1:3000/api/training/7a588dcc-3220-4f21-a931-65030254e31b