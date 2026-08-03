import os
import io
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from rembg import remove
from PIL import Image

TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")

app = FastAPI()
telegram_app = Application.builder().token(TOKEN).concurrent_updates(True).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Sou o seu bot de remoção de fundo.\n\n"
        "Envie o **link direto** de uma imagem e eu te devolvo ela sem fundo, em alta qualidade (PNG)!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if not text or not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("⚠️ Por favor, envie um **link válido** de imagem (começando com http:// ou https://).")
        return

    processing_msg = await update.message.reply_text("🔄 Baixando e processando a imagem com IA...")

    try:
        response = requests.get(text, timeout=15)
        if response.status_code != 200:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id,
                text="❌ Erro ao baixar a imagem. Verifique se o link está acessível."
            )
            return

        input_image = Image.open(io.BytesIO(response.content))
        output_image = remove(input_image)

        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)

        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id
        )

        await update.message.reply_document(
            document=output_buffer,
            filename="removido_fundo.png",
            caption="✨ Aqui está sua imagem sem fundo em alta qualidade!"
        )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"❌ Ocorreu um erro ao processar a imagem: {str(e)}"
        )

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    if WEBHOOK_URL:
        await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("Bot inicializado com sucesso!")

@app.on_event("shutdown")
async def shutdown():
    await telegram_app.shutdown()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "Bot REMOVEBG está rodando perfeitamente!"}
