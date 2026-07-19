"""
OpenClaw: API + Telegram-бот в одном процессе.
Один сервис на Koyeb — всё работает.
"""

import os
import threading
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent import chat, chat_stream, MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  FASTAPI (для iOS-приложения OpenClaw)
# ═══════════════════════════════════════════

app = FastAPI(title="OpenClaw API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "agent": "openclaw"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL, "object": "model", "owned_by": "openclaw"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    try:
        result = chat(req.message, req.history)
        return {
            "id": "openclaw-1",
            "object": "chat.completion",
            "model": MODEL,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def simple_chat(req: ChatRequest):
    try:
        return {"response": chat(req.message, req.history), "model": MODEL}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════
#  TELEGRAM-БОТ (фоновый поток)
# ═══════════════════════════════════════════

def run_bot():
    """Запускает Telegram-бота в отдельном потоке."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN не задан — бот не запущен")
        return

    from telegram import Update
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        ContextTypes, filters,
    )

    user_histories: dict[int, list[dict]] = {}

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"🦞 *OpenClaw Agent*\nМодель: `{MODEL}`\n\nПросто пишите — я отвечу.\n/clear — сброс",
            parse_mode="Markdown",
        )

    async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_histories.pop(update.effective_user.id, None)
        await update.message.reply_text("🗑️ Очищено.")

    async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        text = update.message.text
        if not text:
            return

        history = user_histories.get(uid, [])
        await ctx.bot.send_chat_action(update.effective_chat.id, "typing")

        try:
            response = chat(text, history)
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": response})
            if len(history) > 40:
                history = history[-40:]
            user_histories[uid] = history

            # Telegram лимит 4096 символов
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
        except Exception as e:
            await update.message.reply_text(f"⚠️ Ошибка: {e}")

    bot_app = Application.builder().token(token).build()
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("clear", cmd_clear))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

    logger.info("🤖 Telegram bot started!")
    bot_app.run_polling(drop_pending_updates=True)


# ═══════════════════════════════════════════
#  ЗАПУСК ВСЕГО
# ═══════════════════════════════════════════

if __name__ == "__main__":
    # Бот — в фоновом потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # API — основной процесс
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
