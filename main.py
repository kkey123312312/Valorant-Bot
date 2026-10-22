import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from gigachat_client import close_client
from handlers import router

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Задайте {name} в файле .env")
    return value


async def main() -> None:
    bot_token = _require_env("BOT_TOKEN")
    _require_env("GIGACHAT_CREDENTIALS")

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        close_client()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
