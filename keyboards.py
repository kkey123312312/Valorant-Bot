from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
from constants import MAP_SITES, MAPS, RANKS, ROLES
from lineups import SIDE_KEYS, Lineup, agents_for_role


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
    role_agents = agents_for_role(role_id)
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


def site_pick_keyboard(
    rank_id: str, map_id: str, role_id: str, agent_id: str, side_key: str
) -> InlineKeyboardMarkup:
    sites = MAP_SITES.get(map_id, ("A", "B"))
    rows = [
        [
            InlineKeyboardButton(
                text=f"Сайт {site}",
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                text=lineup.title[:64],
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lineup_view_keyboard(
    rank_id: str,
    map_id: str,
    role_id: str,
    agent_id: str,
    side_key: str,
    site: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ К лайн-апам",
                    callback_data=NavCb(
                        action="lineup_list",
                        rank_id=rank_id,
                        map_id=map_id,
                        role_id=role_id,
                        agent_id=agent_id,
                        side_key=side_key,
                        site=site,
                    ).pack(),
                )
            ]
        ]
    )
