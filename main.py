import os
import io
import requests
from fastapi import FastAPI, Request
from telegram import Bot, Update
from rembg import remove
from PIL import Image

TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")

app = FastAPI()
bot = Bot(token=TOKEN)

@app.get("/")
async def root():
    return {"status": "Bot REMOVEBG está rodando perfeitamente!"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text.startswith("/start"):
            await bot.send_message(
                chat_id=chat_id,
                text="👋 Olá! Sou o seu bot de remoção de fundo.\n\nEnvie o **link direto** de uma imagem e eu te devolvo ela sem fundo em alta qualidade (PNG)!"
            )
        elif text.startswith("http://") or text.startswith("https://"):
            sent_msg = await bot.send_message(chat_id=chat_id, text="🔄 Baixando e processando a imagem com IA...")
            
            try:
                response = requests.get(text, timeout=15)
                if response.status_code != 200:
                    await bot.edit_message_text(chat_id=chat_id, message_id=sent_msg.message_id, text="❌ Erro ao baixar a imagem. Verifique o link.")
                    return

                input_image = Image.open(io.BytesIO(response.content))
                output_image = remove(input_image)

                output_buffer = io.BytesIO()
                output_image.save(output_buffer, format="PNG")
                output_buffer.seek(0)

                await bot.delete_message(chat_id=chat_id, message_id=sent_msg.message_id)
                await bot.send_document(
                    chat_id=chat_id,
                    document=output_buffer,
                    filename="removido_fundo.png",
                    caption="✨ Aqui está sua imagem sem fundo em alta qualidade!"
                )
            except Exception as e:
                await bot.edit_message_text(chat_id=chat_id, message_id=sent_msg.message_id, text=f"❌ Erro ao processar: {str(e)}")
        else:
            await bot.send_message(chat_id=chat_id, text="⚠️ Por favor, envie um **link válido** começando com http:// ou https://")

    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    if WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("Webhook configurado com sucesso!")
