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
}

EMPTY_ROLE_LINEUPS_TEXT = "Лайн-апы для этой роли пока в процессе добавления"


@dataclass(frozen=True)
class Lineup:
    lineup_id: str
    stable_id: str
    title: str
    side: str
    site: str
    description: str
    photo_url: str
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


def agents_for_role(role_id: str) -> list[tuple[str, str]]:
    return [
        (agent_id, AGENTS[agent_id])
        for agent_id, agent_role in AGENT_ROLES.items()
        if agent_role == role_id
    ]


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


def _load() -> dict[str, dict[str, list[Lineup]]]:
    try:
        raw = json.loads(LINEUPS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Файл лайн-апов не найден: %s", LINEUPS_PATH)
        return {}
    except json.JSONDecodeError:
        logger.exception("lineups.json повреждён")
        return {}

    if not isinstance(raw, dict):
        logger.warning("lineups.json должен быть объектом карт")
        return {}

    loaded: dict[str, dict[str, list[Lineup]]] = {}
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
                title = str(item["title"]).strip()
                description = str(item["description"]).strip()
                site_raw = str(item.get("site", "")).strip().upper()
                site = site_raw if site_raw in KNOWN_SITES else _infer_site(title, description)
                stable_id = str(item.get("id", "")).strip()
                if not stable_id:
                    stable_id = f"legacy_{map_id}_{_normalize(str(agent_name))}_{index}"
                lineups.append(
                    Lineup(
                        lineup_id=str(index),
                        stable_id=stable_id,
                        title=title,
                        side=str(item["side"]).strip(),
                        site=site,
                        description=description,
                        photo_url=str(item.get("photo_url", "")).strip(),
                        video_url=str(item.get("video_url", "")).strip(),
                        target=str(item.get("target", "")).strip(),
                        source=str(item.get("source", "")).strip(),
                        page=str(item.get("page", "")).strip(),
                        limited=item.get("limited") is True,
                    )
                )
            if lineups:
                by_agent[_normalize(str(agent_name))] = lineups
        if by_agent:
            loaded[map_id] = by_agent
    return loaded


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
