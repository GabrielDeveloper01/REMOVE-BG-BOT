from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá!\n\n"
        "Envie o link direto de uma imagem.\n\n"
        "Eu vou:\n"
        "✅ Baixar a imagem\n"
        "✅ Remover o fundo\n"
        "✅ Enviar a imagem em PNG."
    )


async def receber_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    if texto.startswith("http://") or texto.startswith("https://"):
        await update.message.reply_text(
            f"✅ Link recebido!\n\n🔗 {texto}"
        )
    else:
        await update.message.reply_text(
            "❌ Envie um link válido de uma imagem."
        )


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receber_mensagem)
    )

    print("🤖 Bot iniciado!")

    app.run_polling()


if __name__ == "__main__":
    main()
