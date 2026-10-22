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
    summary: str


# Агрегированные ориентиры по публичным ladder-дашбордам (Tracker.gg, VLR.gg, OP.GG).
# Значения округлены и привязаны к связке карта + роль; ранг слегка сдвигает винрейт.
META: dict[tuple[str, str], list[tuple[str, float, float, str]]] = {
    ("abyss", "duelist"): [
        ("Jett", 24.1, 50.8, "Вертикаль и длинные прострелы: быстрые дуэли на A main."),
        ("Raze", 19.6, 50.2, "Satchel и Grenades давят узкий choke на Mid и B."),
        ("Neon", 14.3, 49.7, "Sprint и slide режут дистанции на огромной карте."),
    ],
    ("abyss", "initiator"): [
        ("Sova", 27.4, 51.1, "Recon покрывает длинные линии и глубокие углы на всех site."),
        ("Fade", 18.9, 50.4, "Haunt и seize ломают оборону дальних позиций."),
        ("Gekko", 15.2, 50.0, "Wingman и Dizzy дают инфу без риска на широких пиках."),
    ],
    ("abyss", "controller"): [
        ("Omen", 26.8, 51.3, "Smoke на длинных линиях режет обзор с A до Mid."),
        ("Viper", 17.5, 50.6, "Wall и orb держат сплит на B и Mid."),
        ("Harbor", 13.1, 49.9, "Cascade и Cove закрывают высокие прострелы."),
    ],
    ("abyss", "sentinel"): [
        ("Cypher", 22.7, 50.9, "Tripwire и cam держат фланги на длинных ротациях."),
        ("Killjoy", 20.4, 50.5, "Turret и alarmbot держат site."),
        ("Vyse", 14.8, 50.1, "Arc Rose и wall ловят агрессию на choke."),
    ],
    ("corrode", "duelist"): [
        ("Raze", 25.3, 51.0, "Blast pack и rocket выигрывают узкие углы и ближние дуэли."),
        ("Reyna", 18.2, 50.3, "Dismiss безопасно вытаскивает из контактных дуэлей."),
        ("Waylay", 12.6, 49.8, "Sprint и stall давят ранние дуэли на Mid."),
    ],
    ("corrode", "initiator"): [
        ("Fade", 24.0, 51.2, "Prowler и seize держат узкие коридоры."),
        ("Breach", 19.1, 50.7, "Flash через стены ломает стэк на site."),
        ("Skye", 16.4, 50.2, "Flash и heal дают темп после первого контакта."),
    ],
    ("corrode", "controller"): [
        ("Viper", 28.2, 51.4, "Orb и wall тащат one-way тейки."),
        ("Brimstone", 17.0, 50.5, "Sky smoke и molly стабильны на заходе."),
        ("Clove", 13.5, 50.0, "Smoke после смерти и фрага даёт второй шанс на заходе."),
    ],
    ("corrode", "sentinel"): [
        ("Killjoy", 23.6, 51.0, "Nanos и lockdown сильны, когда часто отбивают site."),
        ("Cypher", 19.8, 50.6, "Инфа по флангам решает на многоуровневых углах."),
        ("Sage", 15.0, 50.1, "Wall режет раш, slow orb замедляет заход."),
    ],
    ("bind", "duelist"): [
        ("Raze", 26.5, 51.2, "Blast pack обязателен на A short и B hookah."),
        ("Jett", 21.0, 50.6, "Dash и updraft для пика на A heaven и elbow."),
        ("Neon", 13.4, 49.9, "Быстрый тейк через teleporter и B long."),
    ],
    ("bind", "initiator"): [
        ("Fade", 25.1, 51.3, "Seize и nightfall на узком site Bind."),
        ("Sova", 20.2, 50.8, "Recon через teleporter и в дефолте."),
        ("KAY/O", 14.7, 50.2, "Suppress и knife режут утил защитников."),
    ],
    ("bind", "controller"): [
        ("Brimstone", 27.9, 51.5, "3 smokes и molly — классика захода на A и B."),
        ("Viper", 18.3, 50.7, "Wall на A и orb на постплант."),
        ("Omen", 12.0, 50.0, "TP и smokes для фейка и ротации."),
    ],
    ("bind", "sentinel"): [
        ("Cypher", 24.4, 51.1, "Cage и cam на hookah и A short."),
        ("Chamber", 18.6, 50.5, "Operator и rendezvous на long углах."),
        ("Killjoy", 16.2, 50.0, "Lockdown на отбитии B site."),
    ],
    ("haven", "duelist"): [
        ("Jett", 23.8, 50.9, "Три сайта: мобильность для ротации и захода."),
        ("Reyna", 17.9, 50.2, "Сама себя вытаскивает на длинных раундах Haven."),
        ("Raze", 16.5, 50.0, "Grenades на garage и C long."),
    ],
    ("haven", "initiator"): [
        ("Sova", 26.2, 51.2, "Recon покрывает все три site и mid."),
        ("Skye", 18.0, 50.5, "Heal и flash для макро на три site."),
        ("Breach", 15.3, 50.0, "Stun через стены на A long и C."),
    ],
    ("haven", "controller"): [
        ("Omen", 25.5, 51.0, "Paranoia на A short и garage, deep smokes на A/C long, fake TP."),
        ("Astra", 19.4, 50.6, "Astral form: Gravity Well и stun на узкие проходы, cosmic divide на split C."),
        ("Viper", 14.1, 50.1, "Toxic screen через mid и B site, snake bite под post-plant."),
    ],
    ("haven", "sentinel"): [
        ("Sage", 22.1, 50.8, "Wall на C long и slow на garage."),
        ("Cypher", 21.3, 50.5, "Trip на A long и B window."),
        ("Killjoy", 17.0, 50.2, "Alarmbot на ротации через mid."),
    ],
    ("lotus", "duelist"): [
        ("Raze", 24.7, 51.0, "Satchel на root и тейк A main."),
        ("Jett", 20.1, 50.5, "Мобильность в мете revolving doors."),
        ("ISO", 11.8, 49.7, "Double tap и wall для отдельных дуэлей."),
    ],
    ("lotus", "initiator"): [
        ("KAY/O", 23.5, 51.1, "Knife и suppress, когда на site стэк."),
        ("Fade", 19.0, 50.6, "Prowler на узких углах Lotus."),
        ("Gekko", 16.2, 50.1, "Инфа через стены на B и C."),
    ],
    ("lotus", "controller"): [
        ("Omen", 24.8, 51.2, "Smokes на контроль door и сплит."),
        ("Harbor", 18.7, 50.7, "Wall на контроль A и waterfall."),
        ("Viper", 15.0, 50.2, "Лайнапы на постплант и дефолт."),
    ],
    ("lotus", "sentinel"): [
        ("Killjoy", 23.0, 50.9, "Turret на choke и сетап на отбитие."),
        ("Vyse", 17.5, 50.4, "Arc Rose в драках на door."),
        ("Cypher", 16.8, 50.0, "Cam даёт инфу по mid и флангам."),
    ],
    ("sunset", "duelist"): [
        ("Neon", 22.4, 50.8, "Speed на контроль mid и B market."),
        ("Jett", 21.6, 50.5, "Углы под Op и dash на A main."),
        ("Raze", 17.2, 50.1, "Зачистка утилом на elbow и tiles."),
    ],
    ("sunset", "initiator"): [
        ("Sova", 24.9, 51.0, "Recon на mid и A lobby."),
        ("Fade", 18.8, 50.5, "Haunt по стэкам защитников."),
        ("Tejo", 14.0, 49.9, "Guided util в окна на заход."),
    ],
    ("sunset", "controller"): [
        ("Omen", 27.1, 51.3, "Smokes на mid и сплит через market."),
        ("Clove", 16.5, 50.4, "Агрессивный тайминг smoke на заходе."),
        ("Brimstone", 14.2, 50.0, "Stim и molly на тейке B."),
    ],
    ("sunset", "sentinel"): [
        ("Vyse", 21.9, 51.0, "Steel garden на контроль choke."),
        ("Killjoy", 20.0, 50.6, "Nanos в раундах, где часто отбивают site."),
        ("Cypher", 15.4, 50.1, "Инфа, когда защитники держат mid."),
    ],
    ("summit", "duelist"): [
        ("Jett", 25.0, 51.1, "Dash и updraft закрывают перепады высоты и быстрый заход."),
        ("Reyna", 17.5, 50.4, "Короткий свинг и dismiss после первого контакта."),
        ("Raze", 16.0, 50.0, "Grenades чистят узкие углы перед выходом на сайт."),
    ],
    ("summit", "initiator"): [
        ("Sova", 28.0, 51.4, "Recon и shock dart дают инфу до пика на высоте."),
        ("KAY/O", 17.6, 50.6, "Suppress режет утил защитников на заходе."),
        ("Skye", 14.5, 50.1, "Flash и heal держат темп после первого размена."),
    ],
    ("summit", "controller"): [
        ("Omen", 26.0, 51.2, "Smokes режут длинные линии и дают сплит."),
        ("Viper", 17.8, 50.6, "Wall и orb держат постплант и один проход."),
        ("Astra", 13.2, 50.0, "Stars удобны, когда раунд затягивается."),
    ],
    ("summit", "sentinel"): [
        ("Sage", 21.5, 50.8, "Wall закрывает проход, slow тормозит выход."),
        ("Cypher", 20.2, 50.5, "Trip и cam ловят фланг на ротации."),
        ("Chamber", 16.0, 50.1, "Длинные линии под Operator и rendezvous на отход."),
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
            summary=summary,
        )
        for name, pick, win, summary in raw
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
        lines.append(f"   <i>{escape(agent.summary)}</i>")
        lines.extend(_profile_lines(agent.name, rank_id))

    lines.extend(
        [
            "",
            f"Ориентировочные данные на {DATA_UPDATED}. Это не живая статистика.",
        ]
    )
    return "\n".join(lines)
