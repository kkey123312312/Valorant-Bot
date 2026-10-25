import json
import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path

from constants import MAPS, RANK_WIN_SHIFT, RANKS, ROLES

logger = logging.getLogger(__name__)

AGENTS_PATH = Path(__file__).resolve().parent / "agents.json"
DATA_UPDATED = "23 октября 2026"
_RANK_KEYS = frozenset(RANKS)
_PROFILE_FIELDS = ("why", "strengths", "weaknesses")


@dataclass(frozen=True)
class AgentStat:
    name: str
    pick_rate: float
    win_rate: float


# Агрегированные ориентиры по публичным ladder-дашбордам (Tracker.gg, VLR.gg, OP.GG).
# Значения округлены и привязаны к связке карта + роль; ранг слегка сдвигает винрейт.
META: dict[tuple[str, str], list[tuple[str, float, float]]] = {
    ('abyss', 'duelist'): [
        ('Jett', 24.1, 50.8),
        ('Raze', 19.6, 50.2),
        ('Neon', 14.3, 49.7),
    ],
    ('abyss', 'initiator'): [
        ('Sova', 27.4, 51.1),
        ('Fade', 18.9, 50.4),
        ('Gekko', 15.2, 50.0),
    ],
    ('abyss', 'controller'): [
        ('Omen', 26.8, 51.3),
        ('Viper', 17.5, 50.6),
        ('Harbor', 13.1, 49.9),
    ],
    ('abyss', 'sentinel'): [
        ('Cypher', 22.7, 50.9),
        ('Killjoy', 20.4, 50.5),
        ('Vyse', 14.8, 50.1),
    ],
    ('corrode', 'duelist'): [
        ('Raze', 25.3, 51.0),
        ('Reyna', 18.2, 50.3),
        ('Waylay', 12.6, 49.8),
    ],
    ('corrode', 'initiator'): [
        ('Fade', 24.0, 51.2),
        ('Breach', 19.1, 50.7),
        ('Skye', 16.4, 50.2),
    ],
    ('corrode', 'controller'): [
        ('Viper', 28.2, 51.4),
        ('Brimstone', 17.0, 50.5),
        ('Clove', 13.5, 50.0),
    ],
    ('corrode', 'sentinel'): [
        ('Killjoy', 23.6, 51.0),
        ('Cypher', 19.8, 50.6),
        ('Sage', 15.0, 50.1),
    ],
    ('bind', 'duelist'): [
        ('Raze', 26.5, 51.2),
        ('Jett', 21.0, 50.6),
        ('Yoru', 12.0, 50.0),
    ],
    ('bind', 'initiator'): [
        ('Fade', 25.1, 51.3),
        ('Sova', 20.2, 50.8),
        ('KAY/O', 14.7, 50.2),
    ],
    ('bind', 'controller'): [
        ('Brimstone', 27.9, 51.5),
        ('Viper', 18.3, 50.7),
        ('Omen', 12.0, 50.0),
    ],
    ('bind', 'sentinel'): [
        ('Cypher', 24.4, 51.1),
        ('Chamber', 18.6, 50.5),
        ('Killjoy', 16.2, 50.0),
    ],
    ('haven', 'duelist'): [
        ('Jett', 23.8, 50.9),
        ('Reyna', 17.9, 50.2),
        ('Raze', 16.5, 50.0),
    ],
    ('haven', 'initiator'): [
        ('Sova', 26.2, 51.2),
        ('Skye', 18.0, 50.5),
        ('Breach', 15.3, 50.0),
    ],
    ('haven', 'controller'): [
        ('Omen', 25.5, 51.0),
        ('Astra', 19.4, 50.6),
        ('Viper', 14.1, 50.1),
    ],
    ('haven', 'sentinel'): [
        ('Sage', 22.1, 50.8),
        ('Cypher', 21.3, 50.5),
        ('Killjoy', 17.0, 50.2),
    ],
    ('lotus', 'duelist'): [
        ('Raze', 24.7, 51.0),
        ('Jett', 20.1, 50.5),
        ('ISO', 11.8, 49.7),
    ],
    ('lotus', 'initiator'): [
        ('KAY/O', 23.5, 51.1),
        ('Fade', 19.0, 50.6),
        ('Gekko', 16.2, 50.1),
    ],
    ('lotus', 'controller'): [
        ('Omen', 24.8, 51.2),
        ('Harbor', 18.7, 50.7),
        ('Viper', 15.0, 50.2),
    ],
    ('lotus', 'sentinel'): [
        ('Killjoy', 23.0, 50.9),
        ('Vyse', 17.5, 50.4),
        ('Cypher', 16.8, 50.0),
    ],
    ('sunset', 'duelist'): [
        ('Neon', 22.4, 50.8),
        ('Jett', 21.6, 50.5),
        ('Raze', 17.2, 50.1),
    ],
    ('sunset', 'initiator'): [
        ('Sova', 24.9, 51.0),
        ('Fade', 18.8, 50.5),
        ('Tejo', 14.0, 49.9),
    ],
    ('sunset', 'controller'): [
        ('Omen', 27.1, 51.3),
        ('Clove', 16.5, 50.4),
        ('Brimstone', 14.2, 50.0),
    ],
    ('sunset', 'sentinel'): [
        ('Vyse', 21.9, 51.0),
        ('Killjoy', 20.0, 50.6),
        ('Cypher', 15.4, 50.1),
    ],
    ('summit', 'duelist'): [
        ('Jett', 25.0, 51.1),
        ('Reyna', 17.5, 50.4),
        ('Raze', 16.0, 50.0),
    ],
    ('summit', 'initiator'): [
        ('Sova', 28.0, 51.4),
        ('KAY/O', 17.6, 50.6),
        ('Skye', 14.5, 50.1),
    ],
    ('summit', 'controller'): [
        ('Omen', 26.0, 51.2),
        ('Viper', 17.8, 50.6),
        ('Astra', 13.2, 50.0),
    ],
    ('summit', 'sentinel'): [
        ('Sage', 21.5, 50.8),
        ('Cypher', 20.2, 50.5),
        ('Chamber', 16.0, 50.1),
    ],
}


def _load_profiles() -> dict[str, dict[str, dict[str, str]]]:
    try:
        raw = json.loads(AGENTS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Файл профилей агентов не найден: %s", AGENTS_PATH)
        return {}
    except json.JSONDecodeError:
        logger.exception("agents.json повреждён")
        return {}

    if not isinstance(raw, dict):
        logger.warning("agents.json должен быть объектом агентов")
        return {}

    loaded: dict[str, dict[str, dict[str, str]]] = {}
    for name, ranks in raw.items():
        if not isinstance(ranks, dict):
            continue
        by_rank: dict[str, dict[str, str]] = {}
        for rank_id, profile in ranks.items():
            if rank_id not in _RANK_KEYS:
                logger.warning("Пропущен профиль %s/%s: неизвестный ранг", name, rank_id)
                continue
            if not isinstance(profile, dict):
                logger.warning("Пропущен профиль %s/%s: профиль должен быть объектом", name, rank_id)
                continue
            if not all(str(profile.get(field, "")).strip() for field in _PROFILE_FIELDS):
                logger.warning("Пропущен профиль %s/%s: не все поля заполнены", name, rank_id)
                continue
            by_rank[rank_id] = {
                field: str(profile[field]).strip() for field in _PROFILE_FIELDS
            }
        if by_rank:
            loaded[str(name)] = by_rank
    return loaded


PROFILES = _load_profiles()


def get_agent_stats(map_id: str, role_id: str, rank_id: str) -> list[AgentStat]:
    shift = RANK_WIN_SHIFT.get(rank_id, 0.0)
    raw = META.get((map_id, role_id), [])
    return [
        AgentStat(
            name=name,
            pick_rate=pick,
            win_rate=round(win + shift, 1),
        )
        for name, pick, win in raw
    ]


def _profile_lines(name: str, rank_id: str) -> list[str]:
    profile = PROFILES.get(name, {}).get(rank_id)
    if not profile:
        return []
    return [
        f"   Зачем пикают: {escape(profile['why'])}",
        f"   Плюсы: {escape(profile['strengths'])}",
        f"   Минусы: {escape(profile['weaknesses'])}",
    ]


def build_analytics_card(rank_id: str, map_id: str, role_id: str) -> str:
    rank_label = RANKS[rank_id]
    map_label = MAPS[map_id]
    role_label = ROLES[role_id]
    agents = get_agent_stats(map_id, role_id, rank_id)

    lines = [
        "📊 <b>Аналитика Valorant</b>",
        f"Ранг: <b>{rank_label}</b> · Карта: <b>{map_label}</b> · Роль: <b>{role_label}</b>",
        "",
        "<b>Топ агентов (выбор / победы):</b>",
    ]
    if not agents:
        lines.append("Для этой связки пока нет ориентиров.")
    for idx, agent in enumerate(agents, start=1):
        lines.append(
            f"{idx}. <b>{escape(agent.name)}</b> — выбор {agent.pick_rate:.1f}% · победы {agent.win_rate:.1f}%"
        )
        lines.extend(_profile_lines(agent.name, rank_id))

    lines.extend(
        [
            "",
            f"Ориентировочные данные на {DATA_UPDATED}. Это не живая статистика.",
        ]
    )
    return "\n".join(lines)
