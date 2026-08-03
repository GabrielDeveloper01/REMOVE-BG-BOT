import os
import io
import requests
from PIL import Image
from rembg import remove
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TOKEN = os.environ.get("TOKEN")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or not text.startswith("http"):
        await update.message.reply_text("Envie um link direto de uma imagem (começando com http).")
        return

    try:
        await update.message.reply_text("Baixando e removendo o fundo...")
        response = requests.get(text)
        input_image = Image.open(io.BytesIO(response.content))
        
        output_image = remove(input_image)
        output_byte_arr = io.BytesIO()
        output_image.save(output_byte_arr, format='PNG')
        output_byte_arr.seek(0)
        
        await update.message.reply_document(document=output_byte_arr, filename="sem_fundo.png")
    except Exception as e:
        await update.message.reply_text(f"Erro ao processar a imagem: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
