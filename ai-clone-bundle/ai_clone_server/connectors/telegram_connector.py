import asyncio
import threading
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelegramConnector:
    def __init__(self, token: str, model_engine, rag_engine=None):
        self.token = token
        self.model_engine = model_engine
        self.rag_engine = rag_engine
        self.application = None
        self.loop = None
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"Telegram Bot started with token {self.token[:5]}...")

    def stop(self):
        if not self.thread:
            return
        
        print("Stopping Telegram Bot...")
        self.stop_event.set()
        # In a real robust implementation, we'd need to properly cancel the asyncio loop
        # For MVP, we let the daemon thread die or try to stop the app if accessible
        if self.application:
            # This is tricky from another thread, but let's try
            asyncio.run_coroutine_threadsafe(self.application.stop(), self.loop)
            asyncio.run_coroutine_threadsafe(self.application.shutdown(), self.loop)
        # Wait for thread to finish to avoid zombie bot still replying
        if self.thread.is_alive():
            self.thread.join(timeout=5)
        self.application = None
        self.loop = None
        self.thread = None

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run_bot())

    async def _run_bot(self):
        self.application = ApplicationBuilder().token(self.token).build()
        
        start_handler = CommandHandler('start', self.start_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        
        self.application.add_handler(start_handler)
        self.application.add_handler(message_handler)
        
        # Run polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Keep running until stopped
        while not self.stop_event.is_set():
            await asyncio.sleep(1)
            
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I am your AI Clone.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        chat_id = update.effective_chat.id
        
        # RAG Context
        rag_context = ""
        if self.rag_engine and self.rag_engine.enabled:
            results = self.rag_engine.search(user_text, top_k=3)
            if results:
                rag_context = "\n\nContext:\n" + "\n".join(results)
        
        full_prompt = user_text + rag_context
        
        # Generate response (blocking call, so run in executor)
        # ModelEngine is synchronous, so we wrap it
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self.model_engine.generate, full_prompt)
        
        await context.bot.send_message(chat_id=chat_id, text=response)
