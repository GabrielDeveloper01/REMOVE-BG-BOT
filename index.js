require("dotenv").config();

const TelegramBot = require("node-telegram-bot-api");
const axios = require("axios");
const express = require("express");

const app = express();

const PORT = process.env.PORT || 3000;

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;

const REMOVE_BG_API = process.env.REMOVE_BG_API;

const bot = new TelegramBot(BOT_TOKEN, {
    polling: true
});

app.get("/", (req, res) => {

    res.send("🤖 Remove BG Bot Online!");

});

app.listen(PORT, () => {

    console.log(`Servidor rodando na porta ${PORT}`);

});

console.log("========================================");
console.log("🤖 REMOVE BG BOT INICIADO");
console.log("========================================");

bot.onText(/\/start/, async (msg) => {

    await bot.sendMessage(

        msg.chat.id,

        "👋 Olá!\n\n" +
        "Envie o link direto de uma imagem.\n\n" +
        "Eu vou:\n" +
        "✅ Baixar a imagem\n" +
        "✅ Remover o fundo\n" +
        "✅ Enviar a imagem em PNG."

    );

});

bot.on("message", async (msg) => {

    if (!msg.text) return;

    if (msg.text.startsWith("/")) return;

    const chatId = msg.chat.id;

    const link = msg.text.trim();

    if (!link.startsWith("http://") && !link.startsWith("https://")) {

        return bot.sendMessage(

            chatId,

            "❌ Envie um link válido de uma imagem."

        );

    }

    await bot.sendMessage(

        chatId,

        "✅ Link recebido!\n\n" +
        "🔗 " + link

    );

});
