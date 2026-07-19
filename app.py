import streamlit as st
import threading
import asyncio
import os
from openai import OpenAI

# ══════════════════════════════════════
#  КОНФИГ
# ══════════════════════════════════════

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", st.secrets.get("NVIDIA_API_KEY", ""))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
MODEL = "thinkingmachines/inkling"
BASE_URL = "https://integrate.api.nvidia.com/v1"

client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)

SYSTEM = "You are OpenClaw, an autonomous AI agent. Think step by step."


# ══════════════════════════════════════
#  ЯДРО: вызов LLM
# ══════════════════════════════════════

def chat(message, history=None):
    msgs = [{"role": "system", "content": SYSTEM}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": message})
    r = client.chat.completions.create(
        model=MODEL, messages=msgs,
        temperature=1, top_p=0.95, max_tokens=8192, stream=False,
    )
    return r.choices[0].message.content


def chat_stream(message, history=None):
    msgs = [{"role": "system", "content": SYSTEM}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": message})
    stream = client.chat.completions.create(
        model=MODEL, messages=msgs,
        temperature=1, top_p=0.95, max_tokens=8192, stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ══════════════════════════════════════
#  TELEGRAM-БОТ (фоновый поток)
# ══════════════════════════════════════

_bot_started = False

def _run_bot():
    global _bot_started
    if _bot_started or not TELEGRAM_TOKEN:
        return
    _bot_started = True

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from telegram import Update
    from telegram.ext import (
        Application, CommandHandler,
        MessageHandler, ContextTypes, filters,
    )

    tg_histories = {}

    async def cmd_start(update: Update, ctx):
        await update.message.reply_text(
            f"🦞 OpenClaw\nМодель: {MODEL}\n\nПишите — отвечу.\n/clear — сброс"
        )

    async def cmd_clear(update: Update, ctx):
        tg_histories.pop(update.effective_user.id, None)
        await update.message.reply_text("🗑️ Очищено.")

    async def on_msg(update: Update, ctx):
        uid = update.effective_user.id
        text = update.message.text
        if not text:
            return
        h = tg_histories.get(uid, [])
        await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
        try:
            resp = chat(text, h)
            h.append({"role": "user", "content": text})
            h.append({"role": "assistant", "content": resp})
            if len(h) > 40:
                h = h[-40:]
            tg_histories[uid] = h
            for i in range(0, len(resp), 4096):
                await update.message.reply_text(resp[i:i + 4096])
        except Exception as e:
            await update.message.reply_text(f"⚠️ {e}")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    app.run_polling(drop_pending_updates=True)


# Запускаем бота ОДИН РАЗ при старте приложения
_bot_thread = threading.Thread(target=_run_bot, daemon=True)
_bot_thread.start()


# ══════════════════════════════════════
#  STREAMLIT DASHBOARD
# ══════════════════════════════════════

st.set_page_config(page_title="OpenClaw", page_icon="🦞", layout="wide")

# --- Сайдбар: статус и настройки ---
with st.sidebar:
    st.title("🦞 OpenClaw")
    st.success("Agent: Online")
    st.info(f"Модель: `{MODEL}`")
    st.info(f"API: NVIDIA NIM")

    bot_status = "🟢 Запущен" if TELEGRAM_TOKEN else "🔴 Токен не задан"
    st.info(f"Telegram-бот: {bot_status}")

    st.divider()

    if st.button("🗑️ Очистить чат"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Streamlit Cloud · Free · 24/7")

# --- Основная область: чат ---
st.title("💬 Чат с OpenClaw")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Спросите OpenClaw..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]
        response = st.write_stream(chat_stream(prompt, history))

    st.session_state.messages.append({"role": "assistant", "content": response})
