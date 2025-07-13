from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import uvicorn
import os

class OmnixBotRender:
    def __init__(self):
        self.bot_token = "AQUI_VA_TU_TOKEN"  # ⬅️ Pon aquí tu token real

    # Comandos del bot
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 ¡Hola! Soy OMNIX, tu asistente de trading. ¿Cómo puedo ayudarte?")

    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("💰 Tu balance actual es de $0.00 (demo).")

    async def comprar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🟢 Has enviado una orden de compra simulada. (No es real)")

    async def voz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🎤 Procesando tu mensaje de voz...")

    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📋 Comandos disponibles:\n/start\n/balance\n/comprar\n/voz\n/ayuda"
        )

    def build(self):
        application = Application.builder().token(self.bot_token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("balance", self.balance))
        application.add_handler(CommandHandler("comprar", self.comprar))
        application.add_handler(CommandHandler("voz", self.voz))
        application.add_handler(CommandHandler("ayuda", self.ayuda))
        return application

omnix = OmnixBotRender()
application = omnix.build()
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    print("🚀 OMNIX se está iniciando...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

@app.on_event("shutdown")
async def on_shutdown():
    print("⛔ Deteniendo OMNIX...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

