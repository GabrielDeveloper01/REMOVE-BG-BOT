"""Bot do Telegram para remoção de fundo de imagens via webhook (FastAPI + rembg)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response, status
from PIL import Image, UnidentifiedImageError
from rembg import remove as rembg_remove
from telegram import InputFile, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("bg-remover-bot")

# --------------------------------------------------------------------------
# Configuração / variáveis de ambiente
# --------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Variável de ambiente TELEGRAM_BOT_TOKEN não definida.")
if not RENDER_EXTERNAL_URL:
    raise RuntimeError("Variável de ambiente RENDER_EXTERNAL_URL não definida.")

WEBHOOK_PATH = "/webhook"
# Token do Telegram contém ":" e não pode ser usado como secret_token do Telegram.
# Por isso derivamos um segredo válido (regex: ^[A-Za-z0-9_-]{1,256}$) a partir dele.
WEBHOOK_SECRET = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).hexdigest()
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL.rstrip('/')}{WEBHOOK_PATH}"

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
DOWNLOAD_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
URL_PATTERN = re.compile(r"https?://\S+")

http_client: Optional[httpx.AsyncClient] = None


# --------------------------------------------------------------------------
# Download e validação de imagens
# --------------------------------------------------------------------------

class ImageDownloadError(Exception):
    """Erro amigável a ser exibido ao usuário."""


def _looks_like_supported_image(data: bytes) -> bool:
    """Fallback quando o Content-Type não é confiável: verifica o conteúdo real."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            return img.format in {"JPEG", "PNG", "WEBP"}
    except (UnidentifiedImageError, OSError):
        return False


async def download_image(url: str) -> bytes:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ImageDownloadError("O link precisa começar com http:// ou https://.")

    assert http_client is not None
    chunks = bytearray()

    try:
        async with http_client.stream("GET", url, timeout=DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()

            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            declared_length = response.headers.get("content-length")
            if declared_length and int(declared_length) > MAX_IMAGE_SIZE_BYTES:
                raise ImageDownloadError("A imagem excede o limite de 20 MB.")

            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_IMAGE_SIZE_BYTES:
                    raise ImageDownloadError("A imagem excede o limite de 20 MB.")

    except httpx.ConnectTimeout as exc:
        raise ImageDownloadError("Tempo esgotado ao conectar ao servidor da imagem.") from exc
    except httpx.ReadTimeout as exc:
        raise ImageDownloadError("Tempo esgotado ao baixar a imagem.") from exc
    except httpx.ConnectError as exc:
        raise ImageDownloadError("Não foi possível conectar ao servidor. Verifique o link.") from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            raise ImageDownloadError("Imagem não encontrada (HTTP 404).") from exc
        raise ImageDownloadError(f"O servidor retornou um erro (HTTP {code}).") from exc
    except httpx.HTTPError as exc:
        raise ImageDownloadError(f"Falha de rede ao baixar a imagem: {exc}") from exc

    image_bytes = bytes(chunks)

    if content_type not in ALLOWED_CONTENT_TYPES and not _looks_like_supported_image(image_bytes):
        raise ImageDownloadError(
            "Formato não suportado. Envie um link para JPG, JPEG, PNG ou WEBP."
        )

    return image_bytes


# --------------------------------------------------------------------------
# Remoção de fundo (rembg é bloqueante -> roda em thread separada)
# --------------------------------------------------------------------------

def _remove_background_sync(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as original:
        original.load()
        source = original.convert("RGBA")

    result = rembg_remove(source)

    buffer = io.BytesIO()
    result.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def remove_background(image_bytes: bytes) -> bytes:
    return await asyncio.to_thread(_remove_background_sync, image_bytes)


# --------------------------------------------------------------------------
# Handlers do Telegram
# --------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Olá! Envie o link direto de uma imagem (JPG, JPEG, PNG ou WEBP) e eu "
        "removo o fundo automaticamente, devolvendo um PNG transparente."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.text:
        return

    match = URL_PATTERN.search(message.text)
    if not match:
        await message.reply_text(
            "Não encontrei nenhum link na sua mensagem. Envie o link direto de uma imagem."
        )
        return

    url = match.group(0)
    chat_id = message.chat_id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    status_message = await message.reply_text("Baixando e processando a imagem, aguarde...")

    try:
        image_bytes = await download_image(url)
        result_bytes = await remove_background(image_bytes)
    except ImageDownloadError as exc:
        await status_message.edit_text(f"Não foi possível processar o link: {exc}")
        return
    except Exception:
        logger.exception("Erro inesperado ao processar imagem do chat %s", chat_id)
        await status_message.edit_text(
            "Ocorreu um erro interno ao processar a imagem. Tente novamente em instantes."
        )
        return

    try:
        await context.bot.send_document(
            chat_id=chat_id,
            document=InputFile(result_bytes, filename="sem-fundo.png"),
            caption="Pronto! Fundo removido.",
        )
    except Exception:
        logger.exception("Falha ao enviar resultado para o chat %s", chat_id)
        await status_message.edit_text(
            "A imagem foi processada, mas houve um erro ao enviá-la. Tente novamente."
        )
        return

    await status_message.delete()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exceção não tratada: %s", update, exc_info=context.error)


telegram_app: Application = (
    Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
)
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", start_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_error_handler(error_handler)


# --------------------------------------------------------------------------
# FastAPI: ciclo de vida e rotas
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client

    http_client = httpx.AsyncClient(follow_redirects=True, timeout=DOWNLOAD_TIMEOUT)

    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    await telegram_app.start()
    logger.info("Webhook configurado em %s", WEBHOOK_URL)

    yield

    logger.info("Encerrando aplicação...")
    await telegram_app.stop()
    await telegram_app.shutdown()
    await http_client.aclose()


app = FastAPI(title="Telegram Background Remover Bot", lifespan=lifespan)


@app.get("/")
@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_header != WEBHOOK_SECRET:
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    payload = await request.json()
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
