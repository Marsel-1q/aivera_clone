// Lightweight worker stub: keeps running, sends heartbeats, manages messaging adapters.

const cloneId = process.env.CLONE_ID || "unknown";
const modelId = process.env.MODEL_ID || "";
const adapterDir = process.env.ADAPTER_DIR || "";
const ragIndexDir = process.env.RAG_INDEX_DIR || "";
const integrations = (() => {
  try {
    return JSON.parse(process.env.INTEGRATIONS || "[]");
  } catch {
    return [];
  }
})();

const apiUrl = process.env.CLONE_API_URL || "http://localhost:3000";

console.log(`[worker:${cloneId}] starting. model=${modelId}, adapter=${adapterDir}, rag=${ragIndexDir}`);
console.log(`[worker:${cloneId}] integrations: ${integrations.map((i) => i.platform).join(", ") || "none"}`);

// Store references for graceful shutdown
let telegramBot = null;
let heartbeatInterval = null;
let isShuttingDown = false;

// Chat history storage per Telegram chat_id
const chatHistories = new Map();
const MAX_HISTORY = 20; // Keep last N message pairs

if (process.send) {
  process.send({ type: "ready", cloneId });
}

async function callInference(messageText, history = []) {
  const res = await fetch(`${apiUrl}/api/tests/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cloneId, message: messageText, history }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Inference failed");
  return data.answer || "No answer";
}

async function bootstrapTelegram(token) {
  let Telegraf;
  try {
    Telegraf = require("telegraf").Telegraf;
  } catch (err) {
    console.error(`[worker:${cloneId}] telegraf not installed. Install dependency to enable Telegram.`);
    if (process.send) process.send({ type: "error", cloneId, error: "telegraf not installed" });
    return;
  }

  const bot = new Telegraf(token);
  telegramBot = bot; // Store reference for graceful shutdown

  bot.on("text", async (ctx) => {
    if (isShuttingDown) return;
    try {
      const chatId = ctx.chat.id;
      const userMessage = ctx.message.text;

      // Get existing history for this chat
      const history = chatHistories.get(chatId) || [];

      // Call inference with history
      const answer = await callInference(userMessage, history);
      await ctx.reply(answer);

      // Update history with this exchange
      history.push({ role: "user", content: userMessage });
      history.push({ role: "assistant", content: answer });

      // Trim history if too long (keep last MAX_HISTORY pairs)
      while (history.length > MAX_HISTORY * 2) {
        history.shift();
      }

      chatHistories.set(chatId, history);
    } catch (err) {
      console.error(`[worker:${cloneId}] telegram handler error`, err);
      await ctx.reply("Sorry, bot is unavailable right now.");
    }
  });

  bot.launch()
    .then(() => console.log(`[worker:${cloneId}] Telegram bot launched`))
    .catch((err) => {
      console.error(`[worker:${cloneId}] failed to launch Telegram bot`, err);
      if (process.send) process.send({ type: "error", cloneId, error: err?.message || String(err) });
    });
}

// Start integrations
for (const integ of integrations) {
  if (integ.platform === "telegram" && integ.active && integ.token) {
    bootstrapTelegram(integ.token);
  }
}

// Heartbeat to parent process
heartbeatInterval = setInterval(() => {
  if (process.send && !isShuttingDown) {
    process.send({ type: "heartbeat", cloneId, ts: Date.now() });
  }
}, 5000);

// Graceful shutdown handler
async function gracefulShutdown(signal) {
  if (isShuttingDown) return;
  isShuttingDown = true;

  console.log(`[worker:${cloneId}] received ${signal}, graceful shutdown...`);

  // Clear heartbeat
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }

  // Stop Telegram bot gracefully
  if (telegramBot) {
    try {
      await telegramBot.stop(signal);
      console.log(`[worker:${cloneId}] Telegram bot stopped`);
    } catch (err) {
      console.error(`[worker:${cloneId}] Error stopping Telegram bot:`, err);
    }
  }

  // Give time for cleanup
  setTimeout(() => {
    console.log(`[worker:${cloneId}] shutdown complete`);
    process.exit(0);
  }, 1000);
}

process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => gracefulShutdown("SIGINT"));

process.on("uncaughtException", (err) => {
  console.error(`[worker:${cloneId}] uncaught exception:`, err);
  if (process.send) process.send({ type: "error", cloneId, error: err?.message || String(err) });
  gracefulShutdown("uncaughtException");
});

process.on("unhandledRejection", (reason, promise) => {
  console.error(`[worker:${cloneId}] unhandled rejection at:`, promise, "reason:", reason);
  // Don't exit on unhandled rejection, just log
});

