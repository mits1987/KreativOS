"""
KreativOS — Telegram Bot (from AionUi inspiration)
Lets you send tasks to KreativOS from your phone via Telegram.

Setup:
1. Talk to @BotFather on Telegram → /newbot → copy token
2. Set TELEGRAM_BOT_TOKEN env var
3. Get your chat ID: message @userinfobot

Then set TELEGRAM_CHAT_ID to whitelist your own chat.
"""
import asyncio, json, os, logging
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_IDS = set(os.getenv("TELEGRAM_CHAT_ID", "").split(","))  # comma-separated chat IDs

class TelegramBot:
    def __init__(self):
        self.token   = BOT_TOKEN
        self.enabled = bool(self.token)
        self._app    = None
        self._task_cb: Optional[Callable] = None   # async fn(task, model, agent) -> str
        self._chat_cb: Optional[Callable] = None   # async fn(msg, model, agent) -> AsyncGenerator

    def set_task_callback(self, cb): self._task_cb = cb
    def set_chat_callback(self, cb): self._chat_cb = cb

    async def start(self):
        if not self.enabled:
            logger.info("Telegram bot disabled — set TELEGRAM_BOT_TOKEN to enable")
            return
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

            app = Application.builder().token(self.token).build()

            async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                uid = str(update.effective_chat.id)
                if ALLOWED_IDS and uid not in ALLOWED_IDS:
                    await update.message.reply_text("❌ Unauthorized. Add your chat ID to TELEGRAM_CHAT_ID.")
                    return
                await update.message.reply_text(
                    "🧠 *KreativOS Bot* — Commands:\n"
                    "/task <prompt> — run autonomous task\n"
                    "/agent <name> — set agent (coder/researcher/architect/devops)\n"
                    "/status — system status\n"
                    "/help — show this\n\n"
                    "Or just send a message to chat with the General agent.",
                    parse_mode="Markdown"
                )

            async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if ALLOWED_IDS and str(update.effective_chat.id) not in ALLOWED_IDS: return
                await update.message.reply_text("✅ KreativOS is running. Backend connected.")

            async def task_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if ALLOWED_IDS and str(update.effective_chat.id) not in ALLOWED_IDS: return
                task = " ".join(ctx.args) if ctx.args else ""
                if not task:
                    await update.message.reply_text("Usage: /task <your task here>"); return
                agent = ctx.bot_data.get("agent", "coder")
                model = ctx.bot_data.get("model", "")
                await update.message.reply_text(f"⚡ Running task with {agent} agent…")
                if self._task_cb and model:
                    try:
                        result = await self._task_cb(task, model, agent)
                        text = result[:3800] + "\n…(truncated)" if len(result) > 3800 else result
                        await update.message.reply_text(f"✅ *Done:*\n{text}", parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Error: {e}")
                else:
                    await update.message.reply_text("⚠️ No model selected. Configure in KreativOS settings.")

            async def agent_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if ALLOWED_IDS and str(update.effective_chat.id) not in ALLOWED_IDS: return
                agents = ["general","coder","researcher","architect","devops","orchestrator"]
                if not ctx.args or ctx.args[0] not in agents:
                    await update.message.reply_text(f"Available agents: {', '.join(agents)}"); return
                ctx.bot_data["agent"] = ctx.args[0]
                await update.message.reply_text(f"✅ Agent set to: {ctx.args[0]}")

            async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if ALLOWED_IDS and str(update.effective_chat.id) not in ALLOWED_IDS: return
                msg   = update.message.text or ""
                agent = ctx.bot_data.get("agent", "general")
                model = ctx.bot_data.get("model", "")
                if not model:
                    await update.message.reply_text("⚠️ No model loaded. Please check KreativOS Settings."); return
                await update.message.reply_text(f"💭 {agent} is thinking…")
                if self._chat_cb:
                    try:
                        result = ""
                        async for chunk in self._chat_cb([{"role":"user","content":msg}], model, agent):
                            result += chunk
                        text = result[:3800] + "\n…" if len(result) > 3800 else result
                        await update.message.reply_text(text)
                    except Exception as e:
                        await update.message.reply_text(f"❌ {e}")

            app.add_handler(CommandHandler("start",  start_cmd))
            app.add_handler(CommandHandler("help",   start_cmd))
            app.add_handler(CommandHandler("status", status_cmd))
            app.add_handler(CommandHandler("task",   task_cmd))
            app.add_handler(CommandHandler("agent",  agent_cmd))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

            self._app = app
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot started")
        except ImportError:
            logger.warning("python-telegram-bot not installed — Telegram disabled")
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")

    async def stop(self):
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception: pass

    def update_model(self, model: str):
        if self._app: self._app.bot_data["model"] = model

# Global bot instance
bot = TelegramBot()
