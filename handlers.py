import logging
from html import escape

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
    lineup_view_keyboard,
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
    agent_belongs_to_role,
    agents_for_role,
    get_lineup,
    lineups_for,
    side_label,
)
from states import PickFlow

logger = logging.getLogger(__name__)
router = Router()
_ai_busy: set[int] = set()

WELCOME = (
    "Привет! Подберу агентов под ранг, карту и роль в Valorant.\n\n"
    "Сначала диапазон ранга, потом карта из текущего маппула и роль."
)
ADVICE_LIMIT = 3500
SIDE_MESSAGES = ("photo_id", "video_id", "advice_id")


def _is_direct_file(url: str, suffixes: tuple[str, ...]) -> bool:
    path = url.split("?", 1)[0].lower()
    return path.endswith(suffixes)


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

    if drop_side:
        await _drop(callback.bot, message.chat.id, state, *SIDE_MESSAGES)

    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in exc.message.lower():
            await state.update_data(menu_id=message.message_id)
            return True
        logger.warning("edit_text failed: %s", exc)
        await callback.answer("Не удалось обновить меню. Нажми /start", show_alert=True)
        return False

    await state.update_data(menu_id=message.message_id)
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
    return (
        f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
        f"Сторона: <b>{side_label(side_key)}</b>\n\n"
        "Выбери сайт:"
    )


def _lineup_list_text(
    map_id: str, agent_id: str, side_key: str, site: str
) -> str:
    return (
        f"Карта: <b>{MAPS[map_id]}</b> · {AGENTS[agent_id]}\n"
        f"Сторона: <b>{side_label(side_key)}</b> · сайт <b>{site}</b>\n\n"
        "Лайн-апы:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _drop(message.bot, message.chat.id, state, *SIDE_MESSAGES)
    await _remember(state, step=PickFlow.rank)

    menu_id = data.get("menu_id")
    if menu_id:
        try:
            await message.bot.edit_message_text(
                WELCOME,
                chat_id=message.chat.id,
                message_id=menu_id,
                reply_markup=rank_keyboard(),
            )
            return
        except TelegramBadRequest:
            await _delete(message.bot, message.chat.id, menu_id)

    sent = await message.answer(WELCOME, reply_markup=rank_keyboard())
    await state.update_data(menu_id=sent.message_id)


@router.callback_query(NavCb.filter(F.action == "ranks"))
async def nav_ranks(callback: CallbackQuery, state: FSMContext) -> None:
    await _remember(state, step=PickFlow.rank)
    if await _edit_menu(callback, state, WELCOME, rank_keyboard()):
        await callback.answer()


@router.callback_query(RankCb.filter())
async def on_rank(callback: CallbackQuery, callback_data: RankCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id):
        await callback.answer("Неизвестный ранг", show_alert=True)
        return

    await _remember(state, step=PickFlow.map, rank_id=callback_data.rank_id)
    text = f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n\nВыбери карту:"
    if await _edit_menu(callback, state, text, map_keyboard(callback_data.rank_id)):
        await callback.answer()


@router.callback_query(NavCb.filter(F.action == "maps"))
async def nav_maps(callback: CallbackQuery, callback_data: NavCb, state: FSMContext) -> None:
    if not _known(callback_data.rank_id):
        await callback.answer("Сначала выбери ранг", show_alert=True)
        return

    await _remember(state, step=PickFlow.map, rank_id=callback_data.rank_id)
    text = f"Ранг: <b>{RANKS[callback_data.rank_id]}</b>\n\nВыбери карту:"
    if await _edit_menu(callback, state, text, map_keyboard(callback_data.rank_id)):
        await callback.answer()


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
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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
    if await _edit_menu(
        callback,
        state,
        _card_text(rank_id, map_id, role_id),
        analytics_keyboard(rank_id, map_id, role_id),
    ):
        await callback.answer()


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
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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
        if await _edit_menu(callback, state, text, markup):
            await callback.answer()
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
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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
            f"Сторона: <b>{side_label(side_key)}</b> · сайт <b>{site}</b>\n\n"
            "Лайн-апы для этой стороны и сайта пока не добавлены."
        )
    markup = lineup_keyboard(
        rank_id, map_id, role_id, agent_id, side_key, site, lineups
    )
    if await _edit_menu(callback, state, text, markup):
        await callback.answer()


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

    await _remember(
        state,
        step=PickFlow.lineup,
        rank_id=callback_data.rank_id,
        map_id=callback_data.map_id,
        role_id=callback_data.role_id,
        agent_id=callback_data.agent_id,
    )
    menu_text = lineup.card(AGENTS[callback_data.agent_id], MAPS[callback_data.map_id])
    direct_video = _is_direct_file(lineup.video_url, (".mp4", ".webm", ".gif", ".mov"))
    if not direct_video:
        menu_text += (
            f'\n\n<a href="{escape(lineup.video_url, quote=True)}">Открыть ролик</a>'
        )
    markup = lineup_view_keyboard(
        callback_data.rank_id,
        callback_data.map_id,
        callback_data.role_id,
        callback_data.agent_id,
        callback_data.side_key,
        callback_data.site,
    )
    if not await _edit_menu(callback, state, menu_text, markup):
        return
    await callback.answer()

    message = callback.message
    if not isinstance(message, Message):
        return

    photo_caption = lineup.caption(AGENTS[callback_data.agent_id], MAPS[callback_data.map_id])
    video_caption = f"<b>{escape(lineup.title)}</b>\n{escape(lineup.side)}"
    direct_photo = _is_direct_file(lineup.photo_url, (".png", ".jpg", ".jpeg", ".webp", ".gif"))

    photo_message = None
    video_message = None
    try:
        if direct_photo:
            photo_message = await message.answer_photo(lineup.photo_url, caption=photo_caption)
        if direct_video:
            video_message = await message.answer_video(lineup.video_url, caption=video_caption)
    except TelegramBadRequest:
        logger.exception("Не удалось отправить медиа лайн-апа %s", lineup.lineup_id)
        if photo_message is not None:
            await _delete(callback.bot, message.chat.id, photo_message.message_id)
        note = "\n\nМедиа не загрузилось."
        if not direct_video:
            note += " Ролик можно открыть по ссылке выше."
        await message.edit_text(menu_text + note, reply_markup=markup)
        return

    await state.update_data(
        photo_id=photo_message.message_id if photo_message else None,
        video_id=video_message.message_id if video_message else None,
    )


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
