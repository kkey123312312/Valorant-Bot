import re

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

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
from constants import LINEUP_BUTTON_EMOJI, MAP_SITES, MAPS, RANKS, ROLES
from lineups import SIDE_KEYS, Lineup, agents_for_role

_LINEUP_BUTTON_LIMIT = 64
_DEFAULT_LINEUP_EMOJI = "🎯"
LAUNCH_BUTTON_TEXT = "Запустить"


def launch_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=LAUNCH_BUTTON_TEXT)]],
        resize_keyboard=True,
        input_field_placeholder="Нажми «Запустить»",
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
# Короткие латинские и «тп» — только с границы слова, иначе Default содержит ult.
_WORD_START_KEYWORDS = frozenset({"ult", "tp", "тп"})


def _rows(buttons: list[InlineKeyboardButton], columns: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + columns] for i in range(0, len(buttons), columns)]


def rank_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=label, callback_data=RankCb(rank_id=rank_id).pack())
        for rank_id, label in RANKS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, columns=1))


def map_keyboard(rank_id: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=MapCb(rank_id=rank_id, map_id=map_id).pack(),
        )
        for map_id, label in MAPS.items()
    ]
    rows = _rows(buttons, columns=2)
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К рангам",
                callback_data=NavCb(
                    action="ranks", rank_id="-", map_id="-", role_id="-", agent_id="-"
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def role_keyboard(rank_id: str, map_id: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=RoleCb(rank_id=rank_id, map_id=map_id, role_id=role_id).pack(),
        )
        for role_id, label in ROLES.items()
    ]
    rows = _rows(buttons, columns=2)
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К картам",
                callback_data=NavCb(
                    action="maps", rank_id=rank_id, map_id="-", role_id="-", agent_id="-"
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def analytics_keyboard(rank_id: str, map_id: str, role_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Спросить совет у ИИ",
                    callback_data=AiAdviceCb(
                        rank_id=rank_id,
                        map_id=map_id,
                        role_id=role_id,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Лайн-апы",
                    callback_data=NavCb(
                        action="agents",
                        rank_id=rank_id,
                        map_id=map_id,
                        role_id=role_id,
                        agent_id="-",
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="◀️ К ролям",
                    callback_data=NavCb(
                        action="roles",
                        rank_id=rank_id,
                        map_id=map_id,
                        role_id="-",
                        agent_id="-",
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🔄 Заново",
                    callback_data=NavCb(
                        action="ranks", rank_id="-", map_id="-", role_id="-", agent_id="-"
                    ).pack(),
                ),
            ],
        ]
    )


def agent_keyboard(rank_id: str, map_id: str, role_id: str) -> InlineKeyboardMarkup:
    role_agents = agents_for_role(role_id, map_id)
    buttons = [
        InlineKeyboardButton(
            text=name,
            callback_data=AgentCb(
                rank_id=rank_id,
                map_id=map_id,
                role_id=role_id,
                agent_id=agent_id,
            ).pack(),
        )
        for agent_id, name in role_agents
    ]
    rows = _rows(buttons, columns=2) if buttons else []
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К карточке",
                callback_data=NavCb(
                    action="card",
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id="-",
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def side_pick_keyboard(
    rank_id: str, map_id: str, role_id: str, agent_id: str
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=SidePickCb(
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id=agent_id,
                    side_key=side_key,
                ).pack(),
            )
        ]
        for side_key, label in SIDE_KEYS.items()
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К агентам",
                callback_data=NavCb(
                    action="agents",
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id="-",
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lineup_jump_callbacks(rank_id: str, map_id: str, role_id: str) -> tuple[str, str]:
    """callback_data «К агентам» и «К картам»: агент, сторона и сайт сброшены."""
    agents_cb = NavCb(
        action="agents",
        rank_id=rank_id,
        map_id=map_id,
        role_id=role_id,
        agent_id="-",
    ).pack()
    maps_cb = NavCb(
        action="maps",
        rank_id=rank_id,
        map_id="-",
        role_id="-",
        agent_id="-",
    ).pack()
    return agents_cb, maps_cb


def _lineup_jump_row(rank_id: str, map_id: str, role_id: str) -> list[InlineKeyboardButton]:
    agents_cb, maps_cb = lineup_jump_callbacks(rank_id, map_id, role_id)
    return [
        InlineKeyboardButton(text="🕵️ К агентам", callback_data=agents_cb),
        InlineKeyboardButton(text="🗺 К картам", callback_data=maps_cb),
    ]


def site_pick_keyboard(
    rank_id: str, map_id: str, role_id: str, agent_id: str, side_key: str
) -> InlineKeyboardMarkup:
    sites = MAP_SITES.get(map_id, ("A", "B"))
    rows = [
        [
            InlineKeyboardButton(
                text="Mid" if site == "M" else f"Сайт {site}",
                callback_data=SitePickCb(
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id=agent_id,
                    side_key=side_key,
                    site=site,
                ).pack(),
            )
        ]
        for site in sites
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К стороне",
                callback_data=NavCb(
                    action="lineup_side",
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id=agent_id,
                ).pack(),
            )
        ]
    )
    rows.append(_lineup_jump_row(rank_id, map_id, role_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _is_emoji_base(ch: str) -> bool:
    code = ord(ch)
    return (
        0x1F1E6 <= code <= 0x1F1FF
        or 0x1F300 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x2B00 <= code <= 0x2BFF
        or 0x23E9 <= code <= 0x23FA
        or 0x25AA <= code <= 0x25FE
        or code in {0x231A, 0x231B, 0x2934, 0x2935, 0x3030, 0x303D, 0x3297, 0x3299}
    )


def _strip_leading_emoji(title: str) -> str:
    """Снимает один ведущий эмодзи и следующий пробел, если название с него начинается."""
    if not title or not _is_emoji_base(title[0]):
        return title
    index = 1
    while index < len(title):
        ch = title[index]
        if ch in "\ufe0e\ufe0f\u20e3" or "\U0001F3FB" <= ch <= "\U0001F3FF":
            index += 1
            continue
        if ch == "\u200d" and index + 1 < len(title) and _is_emoji_base(title[index + 1]):
            index += 2
            continue
        break
    if index < len(title) and title[index] == " ":
        index += 1
    return title[index:]


def _keyword_matches(keyword: str, folded_title: str) -> bool:
    needle = keyword.casefold()
    if needle in _WORD_START_KEYWORDS:
        return re.search(rf"(?<!\w){re.escape(needle)}", folded_title) is not None
    return needle in folded_title


def _lineup_button_text(agent_id: str, title: str) -> str:
    rules = LINEUP_BUTTON_EMOJI.get(agent_id)
    if not rules:
        return title[:_LINEUP_BUTTON_LIMIT]
    body = _strip_leading_emoji(title).strip()
    folded = body.casefold()
    emoji = _DEFAULT_LINEUP_EMOJI
    for keywords, icon in rules:
        if any(_keyword_matches(word, folded) for word in keywords):
            emoji = icon
            break
    return f"{emoji} {body}".strip()[:_LINEUP_BUTTON_LIMIT]


def lineup_keyboard(
    rank_id: str,
    map_id: str,
    role_id: str,
    agent_id: str,
    side_key: str,
    site: str,
    lineups: list[Lineup],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_lineup_button_text(agent_id, lineup.title),
                callback_data=LineupCb(
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id=agent_id,
                    side_key=side_key,
                    site=site,
                    lineup_id=lineup.lineup_id,
                ).pack(),
            )
        ]
        for lineup in lineups
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ К сайтам",
                callback_data=NavCb(
                    action="lineup_sites",
                    rank_id=rank_id,
                    map_id=map_id,
                    role_id=role_id,
                    agent_id=agent_id,
                    side_key=side_key,
                ).pack(),
            )
        ]
    )
    rows.append(_lineup_jump_row(rank_id, map_id, role_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)
