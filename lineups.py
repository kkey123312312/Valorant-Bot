import json
import logging
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

LINEUPS_PATH = Path(__file__).resolve().parent / "lineups.json"
EMPTY_LINEUPS_TEXT = "Лайн-апы для этого агента пока в процессе добавления"
REQUIRED_FIELDS = ("title", "side", "description")
KNOWN_SITES = {"A", "B", "C", "M"}

SIDE_KEYS: dict[str, str] = {
    "atk": "Атака",
    "def": "Защита",
}

AGENTS: dict[str, str] = {
    "sova": "Sova",
    "fade": "Fade",
    "breach": "Breach",
    "kayo": "KAY/O",
    "gekko": "Gekko",
    "viper": "Viper",
    "cypher": "Сайфер",
    "killjoy": "Killjoy",
    "vyse": "Vyse",
    "veto": "Veto",
    "deadlock": "Deadlock",
    "yoru": "Yoru",
}

AGENT_ROLES: dict[str, str] = {
    "sova": "initiator",
    "fade": "initiator",
    "breach": "initiator",
    "kayo": "initiator",
    "gekko": "initiator",
    "viper": "controller",
    "cypher": "sentinel",
    "killjoy": "sentinel",
    "vyse": "sentinel",
    "veto": "sentinel",
    "deadlock": "sentinel",
    "yoru": "duelist",
}

EMPTY_ROLE_LINEUPS_TEXT = "Лайн-апы для этой роли пока в процессе добавления"

_DESC_FIELD_RE = re.compile(r"<b>([^<]+):</b>\s*(.*?)(?=\n<b>|$)", re.DOTALL)
_PLACEHOLDER_WHY = re.compile(
    r"подробного описания.*?(нет|не\s+описан)|только название|только подпись",
    re.I | re.DOTALL,
)


def _clean_lineup_title(title: str) -> str:
    s = title.strip()
    while s and not (s[0].isalnum() or s[0] in "(«"):
        s = s[1:].lstrip()
    return s


def _lineup_focus_area(target: str, title: str) -> str:
    target = (target or "").strip()
    if target and target.lower() not in {"см. видео", "-"}:
        return target
    tl = title.lower()
    for pattern, label in (
        (r"дефолт[- ]?плант\s*a", "дефолт-плант A"),
        (r"a heaven", "A Heaven"),
        (r"a long", "A Long"),
        (r"a short", "A Short"),
        (r"a lobby", "A Lobby"),
        (r"a backsite|дальн\w+ часть a", "A Backsite"),
        (r"фланг a", "фланг A"),
        (r"hell", "Hell"),
        (r"a site|плент a|\bна a\b|\bна a\+", "A Site"),
    ):
        if re.search(pattern, tl):
            return label
    return title.strip(" .") or "зону с видео"


def _is_placeholder_why(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if _PLACEHOLDER_WHY.search(text):
        return True
    low = text.lower()
    return low.startswith("подпись:") and "подробного описания" in low


def infer_lineup_purpose(title: str, *, target: str = "", side: str = "") -> str:
    """Краткий «Зачем», если в источнике нет нормального описания."""
    clean = _clean_lineup_title(title)
    tl = clean.lower()
    area = _lineup_focus_area(target, clean)
    area_l = area.lower()

    if "камера" in tl:
        if area_l in {"a site", "a"} or re.search(r"\bна a\b", tl):
            return "Видит плент A и зоны пост-планта."
        if "hell" in tl or "hell" in area_l:
            return "Камера для ретейка: видит Hell и входы на A."
        if "short" in tl or "short" in area_l:
            return "Видит A Short и подходы к пленту."
        if "heaven" in tl or "heaven" in area_l:
            return "Видит A Heaven и обзор сверху на A."
        return f"Камера даёт обзор на {area}."

    if "растяж" in tl:
        if "пост-план" in tl:
            return f"Пост-плант: растяжка на {area} ловит зачистку."
        return f"Растяжка сигнализирует о заходе на {area}."

    if "клетк" in tl or "односторон" in tl:
        return f"Клетка режет обзор и мешает выйти на {area}."

    if "молли" in tl or "гранат" in tl:
        if "пост-план" in tl or "дефолт" in area_l:
            return f"Граната задерживает зачистку и дефьюз на {area}."
        if "ретейк" in tl:
            return f"Граната помогает вернуть {area}."
        return f"Граната выжигает или задерживает игроков на {area}."

    if "ульт" in tl or "lockdown" in tl:
        return f"Ульта помогает удержать или вернуть {area}."

    if "флеш" in tl:
        return f"Флешка ослепляет игроков на {area} перед выходом."

    if "сеть" in tl or "gravnet" in tl:
        return f"Сеть замедляет атакующих на {area}."

    if "razorvine" in tl or re.search(r"\bvyse\b", tl):
        if "комбо" in tl:
            return f"Комбо шипов для выхода или зачистки {area}."
        return f"Шипы бьют или режут выход на {area}."

    if "сетап" in tl:
        return f"Сетап утилиты для контроля {area}."

    if "ретейк" in tl:
        return f"Помогает вернуть контроль над {area}."

    if "общий лайнап" in tl:
        return f"Утилита в составе общего лайнапа на {area}."

    if "комбо" in tl:
        return f"Комбо способностей для {area}."

    if "пост-план" in tl:
        return f"Утилита для пост-планта на {area}."

    if area and area != clean:
        return f"Лайн-ап на {area} — детали на видео."
    return f"{clean} — детали на видео."


def compact_lineup_description(
    description: str,
    *,
    side: str = "",
    target: str = "",
    title: str = "",
) -> str:
    """Подпись ролика: только цель, сторона и зачем (без позиции, установки, броска и т.п.)."""
    if "<b>" not in description:
        return description
    fields = {
        match.group(1).strip(): match.group(2).strip()
        for match in _DESC_FIELD_RE.finditer(description)
    }
    parts: list[str] = []
    goal = fields.get("Цель") or target.strip()
    if goal:
        parts.append(f"<b>Цель:</b> {goal}")
    side_val = side.strip() or fields.get("Сторона")
    if side_val:
        parts.append(f"<b>Сторона:</b> {side_val}")
    why = fields.get("Зачем", "").strip()
    goal_for_infer = goal or target.strip()
    if _is_placeholder_why(why):
        why = infer_lineup_purpose(title, target=goal_for_infer, side=side_val or side)
    elif not why and title:
        why = infer_lineup_purpose(title, target=goal_for_infer, side=side_val or side)
    if why:
        parts.append(f"<b>Зачем:</b> {why}")
    return "\n".join(parts) if parts else description


@dataclass(frozen=True)
class Lineup:
    lineup_id: str
    stable_id: str
    title: str
    side: str
    site: str
    description: str
    video_url: str
    target: str = ""
    source: str = ""
    page: str = ""
    limited: bool = False

    def card(self, agent_name: str, map_name: str) -> str:
        place = "Mid" if self.site == "M" else f"сайт {self.site}"
        return (
            f"🎯 <b>{escape(self.title)}</b>\n"
            f"{escape(agent_name)} · {escape(map_name)} · {escape(self.side)} · {place}\n\n"
            f"{escape(self.description)}"
        )

    def caption(self, agent_name: str, map_name: str) -> str:
        text = self.card(agent_name, map_name)
        if len(text) <= 1000:
            return text
        return text[:997] + "..."


def side_label(side_key: str) -> str:
    return SIDE_KEYS.get(side_key, side_key)


def side_key_for_label(side: str) -> str | None:
    side = side.strip()
    for key, label in SIDE_KEYS.items():
        if side == label:
            return key
    return None


def _side_from_item(item: dict, *, stable_id: str) -> str:
    side = str(item.get("side", "")).strip()
    if side in SIDE_KEYS.values():
        return side
    parts = stable_id.split("_")
    if len(parts) >= 3:
        label = SIDE_KEYS.get(parts[2])
        if label:
            return label
    return side


def agents_for_role(role_id: str, map_id: str | None = None) -> list[tuple[str, str]]:
    agents = [
        (agent_id, AGENTS[agent_id])
        for agent_id, agent_role in AGENT_ROLES.items()
        if agent_role == role_id
    ]
    if not map_id:
        return agents
    return [(agent_id, name) for agent_id, name in agents if lineups_for(map_id, agent_id)]


def agent_belongs_to_role(agent_id: str, role_id: str) -> bool:
    return AGENT_ROLES.get(agent_id) == role_id


def _normalize(key: str) -> str:
    return key.strip().lower()


def _infer_site(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    if re.search(
        r"c site|c long|c main|garage|post[- ]?plant c|haven c| c site|site c|entry cage|cypher post plant - c",
        text,
    ):
        return "C"
    if re.search(r"b site|b link|b cam|b main|hookah| b site", text):
        return "B"
    if re.search(r"a site|a long|a short|heaven| ct |a main", text):
        return "A"
    if "mid" in text:
        return "B"
    return "A"


_catalog_cache: dict[str, dict[str, list[Lineup]]] | None = None
_catalog_mtime: float = 0.0
_limited_sides: set[tuple[str, str, str]] = set()


def _load() -> dict[str, dict[str, list[Lineup]]]:
    global _catalog_cache, _catalog_mtime, _limited_sides
    try:
        mtime = LINEUPS_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _catalog_cache is not None and mtime == _catalog_mtime:
        return _catalog_cache

    try:
        raw = json.loads(LINEUPS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Файл лайн-апов не найден: %s", LINEUPS_PATH)
        _catalog_cache = {}
        _catalog_mtime = mtime
        _limited_sides = set()
        return _catalog_cache
    except json.JSONDecodeError:
        logger.exception("lineups.json повреждён")
        _catalog_cache = {}
        _catalog_mtime = mtime
        _limited_sides = set()
        return _catalog_cache

    if not isinstance(raw, dict):
        logger.warning("lineups.json должен быть объектом карт")
        _catalog_cache = {}
        _catalog_mtime = mtime
        _limited_sides = set()
        return _catalog_cache

    loaded: dict[str, dict[str, list[Lineup]]] = {}
    limited_sides: set[tuple[str, str, str]] = set()
    for map_name, agents in raw.items():
        if not isinstance(agents, dict):
            continue
        map_id = _normalize(str(map_name))
        by_agent: dict[str, list[Lineup]] = {}
        for agent_name, items in agents.items():
            if not isinstance(items, list):
                continue
            lineups: list[Lineup] = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if not all(str(item.get(field, "")).strip() for field in REQUIRED_FIELDS):
                    logger.warning(
                        "Пропущен лайн-ап %s/%s #%s: не все поля заполнены",
                        map_id,
                        agent_name,
                        index,
                    )
                    continue
                video_url = str(item.get("video_url", "")).strip()
                if video_url == "TODO_REPLACE_WITH_MP4":
                    continue
                title = str(item["title"]).strip()
                target = str(item.get("target", "")).strip()
                description = str(item["description"]).strip()
                site_raw = str(item.get("site", "")).strip().upper()
                site = site_raw if site_raw in KNOWN_SITES else _infer_site(title, description)
                stable_id = str(item.get("id", "")).strip()
                if not stable_id:
                    stable_id = f"legacy_{map_id}_{_normalize(str(agent_name))}_{index}"
                side = _side_from_item(item, stable_id=stable_id)
                if "<" in description:
                    description = compact_lineup_description(
                        description, side=side, target=target, title=title
                    )
                if item.get("limited") is True:
                    sk = side_key_for_label(side)
                    if sk:
                        limited_sides.add((map_id, _normalize(str(agent_name)), sk))
                lineups.append(
                    Lineup(
                        lineup_id=str(index),
                        stable_id=stable_id,
                        title=title,
                        side=side,
                        site=site,
                        description=description,
                        video_url=video_url,
                        target=target,
                        source=str(item.get("source", "")).strip(),
                        page=str(item.get("page", "")).strip(),
                        limited=item.get("limited") is True,
                    )
                )
            if lineups:
                by_agent[_normalize(str(agent_name))] = lineups
        if by_agent:
            loaded[map_id] = by_agent
    _catalog_cache = loaded
    _catalog_mtime = mtime
    _limited_sides = limited_sides
    return loaded


def side_has_limited(map_id: str, agent_id: str, side_key: str) -> bool:
    _load()
    return (_normalize(map_id), _normalize(agent_id), side_key) in _limited_sides


def lineups_for(
    map_id: str,
    agent_id: str,
    *,
    side_key: str | None = None,
    site: str | None = None,
) -> list[Lineup]:
    catalog = _load()
    items = list(catalog.get(_normalize(map_id), {}).get(_normalize(agent_id), []))
    if side_key:
        label = side_label(side_key)
        items = [item for item in items if item.side == label]
    if site:
        site = site.upper()
        items = [item for item in items if item.site == site]
    return items


def get_lineup(
    map_id: str,
    agent_id: str,
    lineup_id: str,
    *,
    side_key: str | None = None,
    site: str | None = None,
) -> Lineup | None:
    for lineup in lineups_for(map_id, agent_id, side_key=side_key, site=site):
        if lineup.lineup_id == lineup_id:
            return lineup
    return None
