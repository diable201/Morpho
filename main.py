import logging
import os
import openai
import telebot
import time
import pymongo
import json
import sys
from telebot import types
from typing import Callable
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

file_handler = logging.FileHandler('logs.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)


logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

load_dotenv(find_dotenv())
# Constants
openai.api_key = os.getenv("OPEN_AI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEMPERATURE = float(os.getenv("TEMPERATURE"))
MONGO_LINK = os.getenv("MONGO_LINK")
MONGO_DB = os.getenv("MONGO_DB")
ALLOWED_USERS = os.getenv("ALLOWED_USERS")


db = pymongo.MongoClient(MONGO_LINK)[MONGO_DB]
morpho_collection = db["morpho"]
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


def restricted_access(func: Callable):
    def wrapper(message: types.Message):
        username = message.from_user.username
        if username in ALLOWED_USERS:
            return func(message)
        else:
            bot.send_message(message.chat.id, "У вас нет доступа к Morpho")
    return wrapper


def get_previous_dialogue(user_id: int):
    previous_dialogue = morpho_collection.find_one({"user_id": user_id})
    if previous_dialogue:
        return json.loads(previous_dialogue["dialogue"])
    return None


def save_current_dialogue(user_id: int, dialogue):
    print(type(dialogue))
    morpho_collection.replace_one(
        {"user_id": user_id},
        {"user_id": user_id, "dialogue": dialogue},
        upsert=True
    )


def log_message(user: str, message: types.Message):
    if user == "user":
        logging.info(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{message.from_user.first_name} "
            f"{message.from_user.last_name}: "
            f"{message.text}"
        )
    elif user == "bot":
        logging.info(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] chatGPT-3:{message}"
        )


@bot.message_handler(commands=["start"])
@restricted_access
def start_message(message: types.Message):
    log_message(user="user", message=message)
    bot.send_message(
        message.chat.id,
        "Здравствуйте! Я ваш персональный помощник Morpho 🦋, как я могу помочь вам?"
    )


@bot.message_handler(commands=["reset"])
@restricted_access
def reset_message(message: types.Message):
    log_message(user="user", message=message)
    user_id = message.from_user.id
    previous_dialogue = get_previous_dialogue(user_id)
    if previous_dialogue:
        morpho_collection.delete_one({"user_id": user_id})
    bot.send_message(
        message.chat.id,
        "История очищена!"
    )


def main():
    @bot.message_handler(commands=["ask"])
    def handle(message: types.Message):
        user_id = message.from_user.id
        previous_dialogue = get_previous_dialogue(user_id)
        prompt = "User: " + message.text + "\nBot: "
        if previous_dialogue:
            prompt = previous_dialogue + prompt
        log_message(user="user", message=message)

        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=1024,
                n=1,
                stop=None,
                temperature=TEMPERATURE
            ).get("choices")[0].text
            dialogue = prompt + response
            dialogue = json.dumps(dialogue[-1000:])
            save_current_dialogue(user_id=user_id, dialogue=dialogue)
            log_message(user="bot", message=response)
            bot.send_message(message.chat.id, response)
        except Exception as e:
            logging.error("Service unavailable", e)
            bot.send_message(message.chat.id, "Сервер перегружен 🥵. Попробуйте через несколько минут")

    logging.info(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bot started!")
    bot.polling(none_stop=True)


if __name__ == "__main__":
    print("Init App")
    main()
    print("Close App")
