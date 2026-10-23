import logging
from html import escape
from urllib.parse import unquote

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from analytics import build_analytics_card
from callbacks import (
    AgentCb,
    AiAdviceCb,
    LineupCb,
    MapCb,
    NavCb,
    RankCb,
    RoleCb,
    SidePickCb,
    SitePickCb,
)
from constants import MAPS, RANKS, ROLES
from gigachat_client import generate_ai_advice
from keyboards import (
    agent_keyboard,
    analytics_keyboard,
    lineup_keyboard,
    map_keyboard,
    rank_keyboard,
    role_keyboard,
    side_pick_keyboard,
    site_pick_keyboard,
)
from lineups import (
    AGENTS,
    EMPTY_LINEUPS_TEXT,
    EMPTY_ROLE_LINEUPS_TEXT,
    SIDE_KEYS,
    Lineup,
    agent_belongs_to_role,
    agents_for_role,
    get_lineup,
    lineups_for,
    side_has_limited,
    side_label,
)
from lineups_view import send_lineup
from states import PickFlow

logger = logging.getLogger(__name__)
router = Router()
_ai_busy: set[int] = set()
_lineup_busy: set[int] = set()

WELCOME = (
    "Привет! Подберу агентов под ранг, карту и роль в Valorant.\n\n"
    "Сначала диапазон ранга, потом карта из текущего маппула и роль."
)
ADVICE_LIMIT = 3500
SIDE_MESSAGES = ("photo_id", "video_id", "advice_id")


def _is_direct_file(url: str, suffixes: tuple[str, ...]) -> bool:
    path = unquote(url.split("?", 1)[0]).lower()
    return path.endswith(suffixes)


def _site_place(site: str) -> str:
    site = site.upper()
    return "Mid" if site == "M" else site


def _lineup_payload(lineup: Lineup, agent_name: str, map_name: str) -> dict:
    """Словарь для send_lineup: HTML новых записей как в файле, у старых текст экранируется."""
    description = lineup.description
    if "<" not in description:
        place = "Mid" if lineup.site == "M" else f"сайт {lineup.site}"
        description = (
            f"{escape(agent_name)} · {escape(map_name)} · {escape(lineup.side)} · {place}\n\n"
            f"{escape(description)}"
        )
    video_url = lineup.video_url.strip()
    source = lineup.source.strip()
    if not source and video_url.startswith("http") and not _is_direct_file(
        video_url, (".mp4", ".webm", ".gif", ".mov")
    ):
        source = video_url
    return {
        "id": lineup.stable_id,
        "title": escape(lineup.title),
        "description": description,
        "video_url": video_url if video_url.startswith("http") else "",
        "source": source,
        "page": lineup.page,
    }


def _known(
    rank_id: str,
    map_id: str | None = None,
    role_id: str | None = None,
    agent_id: str | None = None,
) -> bool:
    if rank_id not in RANKS:
        return False
    if map_id is not None and map_id not in MAPS:
        return False
    if role_id is not None and role_id not in ROLES:
        return False
    if agent_id is not None and agent_id not in AGENTS:
        return False
    if agent_id is not None and role_id is not None and not agent_belongs_to_role(agent_id, role_id):
        return False
    return True


async def _remember(
    state: FSMContext,
    *,
    step: State,
    rank_id: str | None = None,
    map_id: str | None = None,
    role_id: str | None = None,
    agent_id: str | None = None,
) -> None:
    await state.set_state(step)
    await state.update_data(
        rank_id=rank_id,
        map_id=map_id,
        role_id=role_id,
        agent_id=agent_id,
    )


async def _delete(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        logger.debug("Не удалось удалить сообщение %s", message_id)


async def _drop(bot, chat_id: int, state: FSMContext, *keys: str) -> None:
    data = await state.get_data()
    for key in keys:
        await _delete(bot, chat_id, data.get(key))
    if keys:
        await state.update_data(**{key: None for key in keys})


async def _drop_lineup_media(bot, chat_id: int, state: FSMContext) -> None:
    await _drop(bot, chat_id, state, "photo_id", "video_id")


async def _clear_ui(bot, chat_id: int, state: FSMContext) -> None:
    """Удалить все сообщения бота в чате (меню, ролик, совет)."""
    data = await state.get_data()
    for key in ("menu_id", *SIDE_MESSAGES):
        await _delete(bot, chat_id, data.get(key))
    await state.update_data(menu_id=None, photo_id=None, video_id=None, advice_id=None)


async def _reuse_advice_message(
    callback: CallbackQuery,
    state: FSMContext,
    message: Message,
) -> int:
    """Оставляет в чате одно сообщение совета: правит его или шлёт заново, если старое уже удалено."""
    data = await state.get_data()
    advice_id = data.get("advice_id")
    placeholder = "GigaChat готовит совет…"
    if advice_id:
        try:
            await callback.bot.edit_message_text(
                placeholder,
                chat_id=message.chat.id,
                message_id=advice_id,
            )
            return advice_id
        except TelegramBadRequest as exc:
            if "message is not modified" in exc.message.lower():
                return advice_id
            await _delete(callback.bot, message.chat.id, advice_id)
    sent = await message.answer(placeholder)
    await state.update_data(advice_id=sent.message_id)
    return sent.message_id


async def _edit_menu(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup,
    *,
    drop_side: bool = True,
) -> bool:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Меню устарело. Нажми /start", show_alert=True)
        return False

    await callback.answer()

    chat_id = message.chat.id
    bot = callback.bot

    if drop_side:
        await _drop_lineup_media(bot, chat_id, state)
        await _drop(bot, chat_id, state, "advice_id")

    data = await state.get_data()
    menu_id = data.get("menu_id")

    if menu_id and message.message_id != menu_id:
        await _delete(bot, chat_id, message.message_id)
    elif not menu_id and message.message_id:
        await _delete(bot, chat_id, message.message_id)

    if menu_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=menu_id,
                reply_markup=markup,
            )
            await state.update_data(menu_id=menu_id, video_id=None, photo_id=None)
            return True
        except TelegramBadRequest as exc:
            if "message is not modified" in exc.message.lower():
                await state.update_data(menu_id=menu_id, video_id=None, photo_id=None)
                return True
            await _delete(bot, chat_id, menu_id)

    sent = await bot.send_message(
        chat_id, text, reply_markup=markup, parse_mode="HTML"
    )
    await state.update_data(menu_id=sent.message_id, video_id=None, photo_id=None)
    return True


def _card_text(rank_id: str, map_id: str, role_id: str) -> str:
    return build_analytics_card(rank_id, map_id, role_id)


def _agents_text(rank_id: str, map_id: str, role_id: str) -> str:
    role_agents = agents_for_role(role_id)
    header = (
        f"Ранг: <b>{RANKS[rank_id]}</b>\n"
        f"Карта: <b>{MAPS[map_id]}</b>\n"
        f"Роль: <b>{ROLES[role_id]}</b>\n\n"
    )
    if not role_agents:
        return header + EMPTY_ROLE_LINEUPS_TEXT
    names = ", ".join(name for _, name in role_agents)
    return header + f"🎯 Выбери агента ({ROLES[role_id]}): {names}."


def _side_pick_text(rank_id: str, map_id: str, role_id: str, agent_id: str) -> str:
    return (
        f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
        f"Роль: <b>{ROLES[role_id]}</b>\n\n"
        "Выбери сторону:"
    )


def _site_pick_text(
    rank_id: str, map_id: str, role_id: str, agent_id: str, side_key: str
) -> str:
    text = (
        f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
        f"Сторона: <b>{side_label(side_key)}</b>\n\n"
        "Выбери сайт:"
    )
    if side_has_limited(map_id, agent_id, side_key):
        text += "\n\nМало данных в источниках"
    return text


def _lineup_list_text(
    map_id: str, agent_id: str, side_key: str, site: str
) -> str:
    return (
        f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
        f"Сторона: <b>{side_label(side_key)}</b> · сайт <b>{_site_place(site)}</b>\n\n"
        "Лайн-апы:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await _clear_ui(message.bot, message.chat.id, state)
    await _remember(state, step=PickFlow.rank)

    sent = await message.answer(WELCOME, reply_markup=rank_keyboard())
    await state.update_data(menu_id=sent.message_id)


@router.callback_query(NavCb.filter(F.action == "ranks"))
async def nav_ranks(callback: CallbackQuery, state: FSMContext) -> None:
    await _remember(state, step=PickFlow.rank)
    await _edit_menu(callback, state, WELCOME, rank_keyboard())


@router.callback_query(RankCb.filter())
async def on_rank(callback: CallbackQuery, callback_data: RankCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id):
        await callback.answer("Неизвестный ранг", show_alert=True)
        return

    await _remember(state, step=PickFlow.map, rank_id=callback_data.rank_id)
    text = f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n\nВыбери карту:"
    await _edit_menu(callback, state, text, map_keyboard(callback_data.rank_id))


@router.callback_query(NavCb.filter(F.action == "maps"))
async def nav_maps(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id):
        await callback.answer("Сначала выбери ранг", show_alert=True)
        return

    await _remember(state, step=PickFlow.map, rank_id=callback_data.rank_id)
    text = f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n\nВыбери карту:"
    await _edit_menu(callback, state, text, map_keyboard(callback_data.rank_id))


@router.callback_query(MapCb.filter())
async def on_map(callback: CallbackQuery, callback_data: MapCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id):
        await callback.answer("Неизвестная карта", show_alert=True)
        return

    await _remember(
        state,
        step=PickFlow.role,
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
    )
    text = (
        f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n"
        f"Карта: <b>{MAPS[callback_data.map_id]}</b>\n\n"
        "Выбери роль:"
    )
    markup = role_keyboard(callback_data.rank_id, callback_data.map_id)
    await _edit_menu(callback, state, text, markup)


@router.callback_query(NavCb.filter(F.action == "roles"))
async def nav_roles(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id):
        await callback.answer("Сначала выбери ранг и карту", show_alert=True)
        return

    await _remember(
        state,
        step=PickFlow.role,
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
    )
    text = (
        f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n"
        f"Карта: <b>{MAPS[callback_data.map_id]}</b>\n\n"
        "Выбери роль:"
    )
    markup = role_keyboard(callback_data.rank_id, callback_data.map_id)
    await _edit_menu(callback, state, text, markup)


@router.callback_query(RoleCb.filter())
async def on_role(callback: CallbackQuery, callback_data: RoleCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id, callback_data.role_id):
        await callback.answer("Неизвестная роль", show_alert=True)
        return

    await _show_card(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
    )


@router.callback_query(NavCb.filter(F.action == "card"))
async def nav_card(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id, callback_data.role_id):
        await callback.answer("Сначала выбери ранг, карту и роль", show_alert=True)
        return
    await _show_card(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
    )


async def _show_card(
    callback: CallbackQuery,
    state: FSMContext,
    rank_id: str,
    map_id: str,
    role_id: str,
) -> None:
    await _remember(state, step=PickFlow.ready, rank_id=rank_id, map_id=map_id, role_id=role_id)
    await _edit_menu(
        callback,
        state,
        _card_text(rank_id, map_id, role_id),
        analytics_keyboard(rank_id, map_id, role_id),
    )


@router.callback_query(NavCb.filter(F.action == "agents"))
async def nav_agents(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id, callback_data.role_id):
        await callback.answer("Сначала выбери ранг, карту и роль", show_alert=True)
        return

    await _remember(
        state,
        step=PickFlow.agent,
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
        role_id=callback_data.role_id,
    )
    text = _agents_text(callback_data.rank_id, callback_data.map_id, callback_data.role_id)
    markup = agent_keyboard(callback_data.rank_id, callback_data.map_id, callback_data.role_id)
    await _edit_menu(callback, state, text, markup)


@router.callback_query(AgentCb.filter())
async def on_agent(callback: CallbackQuery, callback_data: AgentCb, state: FSMContext) -> None:
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Неизвестный агент", show_alert=True)
        return
    await _show_side_pick(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    )


@router.callback_query(NavCb.filter(F.action == "lineup_side"))
async def nav_lineup_side(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Сначала выбери агента", show_alert=True)
        return
    await _show_side_pick(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    )


@router.callback_query(SidePickCb.filter())
async def on_side_pick(callback: CallbackQuery, callback_data: SidePickCb, state: FSMContext) -> None:
    if callback_data.side_key not in SIDE_KEYS:
        await callback.answer("Неизвестная сторона", show_alert=True)
        return
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Эта кнопка устарела. Нажми /start", show_alert=True)
        return
    await _show_site_pick(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
        callback_data.side_key,
    )


@router.callback_query(NavCb.filter(F.action == "lineup_sites"))
async def nav_lineup_sites(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if callback_data.side_key not in SIDE_KEYS:
        await callback.answer("Сначала выбери сторону", show_alert=True)
        return
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Сначала выбери агента", show_alert=True)
        return
    await _show_site_pick(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
        callback_data.side_key,
    )


@router.callback_query(SitePickCb.filter())
async def on_site_pick(callback: CallbackQuery, callback_data: SitePickCb, state: FSMContext) -> None:
    if callback_data.side_key not in SIDE_KEYS:
        await callback.answer("Неизвестная сторона", show_alert=True)
        return
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Эта кнопка устарела. Нажми /start", show_alert=True)
        return
    await _show_lineup_list(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
        callback_data.side_key,
        callback_data.site,
    )


@router.callback_query(NavCb.filter(F.action == "lineup_list"))
async def nav_lineup_list(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if callback_data.side_key not in SIDE_KEYS or callback_data.site == "-":
        await callback.answer("Сначала выбери сторону и сайт", show_alert=True)
        return
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Сначала выбери агента", show_alert=True)
        return
    await _show_lineup_list(
        callback,
        state,
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
        callback_data.side_key,
        callback_data.site,
    )


async def _show_side_pick(
    callback: CallbackQuery,
    state: FSMContext,
    rank_id: str,
    map_id: str,
    role_id: str,
    agent_id: str,
) -> None:
    if not lineups_for(map_id, agent_id):
        await _remember(
            state,
            step=PickFlow.agent,
            rank_id=rank_id,
            map_id=map_id,
            role_id=role_id,
            agent_id=agent_id,
        )
        text = (
            f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n\n"
            f"{EMPTY_LINEUPS_TEXT}"
        )
        markup = agent_keyboard(rank_id, map_id, role_id)
        await _edit_menu(callback, state, text, markup)
        return

    await _remember(
        state,
        step=PickFlow.lineup,
        rank_id=rank_id,
        map_id=map_id,
        role_id=role_id,
        agent_id=agent_id,
    )
    text = _side_pick_text(rank_id, map_id, role_id, agent_id)
    markup = side_pick_keyboard(rank_id, map_id, role_id, agent_id)
    await _edit_menu(callback, state, text, markup)


async def _show_site_pick(
    callback: CallbackQuery,
    state: FSMContext,
    rank_id: str,
    map_id: str,
    role_id: str,
    agent_id: str,
    side_key: str,
) -> None:
    await _remember(
        state,
        step=PickFlow.lineup,
        rank_id=rank_id,
        map_id=map_id,
        role_id=role_id,
        agent_id=agent_id,
    )
    text = _site_pick_text(rank_id, map_id, role_id, agent_id, side_key)
    markup = site_pick_keyboard(rank_id, map_id, role_id, agent_id, side_key)
    await _edit_menu(callback, state, text, markup)


async def _show_lineup_list(
    callback: CallbackQuery,
    state: FSMContext,
    rank_id: str,
    map_id: str,
    role_id: str,
    agent_id: str,
    side_key: str,
    site: str,
) -> None:
    lineups = lineups_for(map_id, agent_id, side_key=side_key, site=site.upper())
    await _remember(
        state,
        step=PickFlow.lineup,
        rank_id=rank_id,
        map_id=map_id,
        role_id=role_id,
        agent_id=agent_id,
    )
    site = site.upper()
    if lineups:
        text = _lineup_list_text(map_id, agent_id, side_key, site)
    else:
        text = (
            f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
            f"Сторона: <b>{side_label(side_key)}</b> · сайт <b>{_site_place(site)}</b>\n\n"
            "Лайн-апы для этой стороны и сайта пока не добавлены."
        )
    markup = lineup_keyboard(
        rank_id, map_id, role_id, agent_id, side_key, site, lineups
    )
    await _edit_menu(callback, state, text, markup)


@router.callback_query(LineupCb.filter())
async def on_lineup(callback: CallbackQuery, callback_data: LineupCb, state: FSMContext) -> None:
    if not _known(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
    ):
        await callback.answer("Эта кнопка устарела. Нажми /start", show_alert=True)
        return

    lineup = get_lineup(
        callback_data.map_id,
        callback_data.agent_id,
        callback_data.lineup_id,
        side_key=callback_data.side_key,
        site=callback_data.site,
    )
    if lineup is None:
        await callback.answer("Нет такого лайн-апа", show_alert=True)
        return

    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Меню устарело. Нажми /start", show_alert=True)
        return

    user_id = callback.from_user.id
    if user_id in _lineup_busy:
        await callback.answer("Ролик уже открывается", show_alert=True)
        return

    await callback.answer()

    await _remember(
        state,
        step=PickFlow.lineup,
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
        role_id=callback_data.role_id,
        agent_id=callback_data.agent_id,
    )
    chat_id = message.chat.id
    await _clear_ui(callback.bot, chat_id, state)

    back_cb = NavCb(
        action="lineup_list",
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
        role_id=callback_data.role_id,
        agent_id=callback_data.agent_id,
        side_key=callback_data.side_key,
        site=callback_data.site,
    ).pack()
    payload = _lineup_payload(
        lineup, AGENTS[callback_data.agent_id], MAPS[callback_data.map_id]
    )
    _lineup_busy.add(user_id)
    try:
        sent = await send_lineup(callback.bot, chat_id, payload, back_cb)
    except Exception:
        logger.exception("Не удалось показать лайн-ап %s", lineup.stable_id)
        return
    finally:
        _lineup_busy.discard(user_id)
    if sent.video:
        await state.update_data(menu_id=None, photo_id=None, video_id=sent.message_id)
    else:
        await state.update_data(menu_id=sent.message_id, photo_id=None, video_id=None)


@router.callback_query(AiAdviceCb.filter())
async def on_ai_advice(callback: CallbackQuery, callback_data: AiAdviceCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id, callback_data.map_id, callback_data.role_id):
        await callback.answer("Эта кнопка устарела. Нажми /start", show_alert=True)
        return

    user_id = callback.from_user.id
    if user_id in _ai_busy:
        await callback.answer("Совет уже готовится", show_alert=True)
        return

    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Меню устарело. Нажми /start", show_alert=True)
        return

    _ai_busy.add(user_id)
    await callback.answer()
    try:
        advice_id = await _reuse_advice_message(callback, state, message)
        try:
            advice = await generate_ai_advice(
                callback_data.rank_id,
                callback_data.map_id,
                callback_data.role_id,
            )
            text = f"<b>Совет ИИ</b>\n\n{escape(advice[:ADVICE_LIMIT])}"
        except Exception:
            logger.exception("AI advice failed for user %s", user_id)
            text = "Не удалось получить совет. Проверь ключ GigaChat и интернет."

        try:
            await callback.bot.edit_message_text(
                text, chat_id=message.chat.id, message_id=advice_id
            )
        except TelegramBadRequest:
            await _delete(callback.bot, message.chat.id, advice_id)
            sent = await message.answer(text)
            await state.update_data(advice_id=sent.message_id)
    finally:
        _ai_busy.discard(user_id)
