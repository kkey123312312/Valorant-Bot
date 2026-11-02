import asyncio
import logging
import os
import threading

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from analytics import get_agent_stats
from constants import MAPS, RANKS, ROLES

logger = logging.getLogger(__name__)

_client: GigaChat | None = None
_chat_lock = threading.Lock()


def _credentials() -> str:
    creds = os.getenv("GIGACHAT_CREDENTIALS", "").strip()
    if not creds:
        raise RuntimeError("GIGACHAT_CREDENTIALS не задан в .env")
    return creds


def get_client() -> GigaChat:
    global _client
    if _client is None:
        _client = GigaChat(
            credentials=_credentials(),
            verify_ssl_certs=False,
            model=os.getenv("GIGACHAT_MODEL", "GigaChat-2").strip() or "GigaChat-2",
        )
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


_HISTORY_ROLES = {
    "system": MessagesRole.SYSTEM,
    "user": MessagesRole.USER,
    "assistant": MessagesRole.ASSISTANT,
}


def _chat_sync(history: list[dict[str, str]]) -> str:
    messages: list[Messages] = []
    for item in history:
        role = _HISTORY_ROLES.get(item.get("role", ""))
        content = (item.get("content") or "").strip()
        if role is None or not content:
            continue
        messages.append(Messages(role=role, content=content))
    if not messages:
        raise RuntimeError("Пустая история для GigaChat")
    chat = Chat(messages=messages)
    with _chat_lock:
        response = get_client().chat(chat)
    content = response.choices[0].message.content.strip()
    if not content:
        raise RuntimeError("GigaChat вернул пустой ответ")
    return content


async def continue_ai_chat(history: list[dict[str, str]]) -> str:
    try:
        return await asyncio.to_thread(_chat_sync, history)
    except Exception:
        logger.exception("GigaChat request failed")
        raise


def _ask_sync(prompt: str) -> str:
    chat = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=(
                    "Ты Valorant-коуч. Ответь на русском обычным текстом, без HTML и markdown. "
                    "3 коротких пункта: кого взять, как играть роль на карте, "
                    "типичная ошибка на этом ранге."
                ),
            ),
            Messages(role=MessagesRole.USER, content=prompt),
        ]
    )
    with _chat_lock:
        response = get_client().chat(chat)
    content = response.choices[0].message.content.strip()
    if not content:
        raise RuntimeError("GigaChat вернул пустой ответ")
    return content


async def generate_ai_advice(rank_id: str, map_id: str, role_id: str) -> str:
    agents = get_agent_stats(map_id, role_id, rank_id)
    agent_lines = "\n".join(
        f"- {agent.name}: pick {agent.pick_rate}%, win {agent.win_rate}%"
        for agent in agents
    )
    prompt = (
        f"Ранг: {RANKS[rank_id]}. Карта: {MAPS[map_id]}. Роль: {ROLES[role_id]}.\n"
        f"Ориентиры по агентам:\n{agent_lines or 'нет данных'}"
    )
    try:
        return await asyncio.to_thread(_ask_sync, prompt)
    except Exception:
        logger.exception("GigaChat request failed")
        raise
