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
