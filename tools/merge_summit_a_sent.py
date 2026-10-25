"""Дописать готовые file_id-лайн-апы Summit A (сентинелы) в lineups.json.

Порядок: attack, defense; a_site, b_site, c_site, mid.
Дубль по id или source/video_src пропускается. TODO_REPLACE_WITH_MP4 не берётся.
Поля type (setup/retake) и upload_date сохраняются.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "incoming" / "lineups_summit_a_sent.json"
OUT = ROOT / "lineups.json"

SIDE_ORDER = ("attack", "defense")
SITE_ORDER = ("a_site", "b_site", "c_site", "mid")
SIDE = {"attack": "Атака", "defense": "Защита"}
SITE = {"a_site": "A", "b_site": "B", "c_site": "C", "mid": "M"}
TYPES = {"setup", "retake"}
AGENTS = {
    "cypher": "Cypher",
    "killjoy": "Killjoy",
    "vyse": "Vyse",
    "veto": "Veto",
    "deadlock": "Deadlock",
}


def _refs(item: dict) -> set[str]:
    return {str(item.get(key) or "").strip() for key in ("source", "video_src")} - {""}


def _known(db: dict) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    refs: set[str] = set()
    for agents in db.values():
        if not isinstance(agents, dict):
            continue
        for items in agents.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "").strip()
                if item_id:
                    ids.add(item_id)
                refs.update(_refs(item))
    return ids, refs


def _rows(fragment: dict):
    summit = fragment.get("summit")
    if not isinstance(summit, dict):
        raise SystemExit("во фрагменте нет объекта summit")
    for agent_key, sides in summit.items():
        agent_name = AGENTS.get(str(agent_key).lower())
        if agent_name is None or not isinstance(sides, dict):
            continue
        for side_key in SIDE_ORDER:
            sites = sides.get(side_key)
            if not isinstance(sites, dict):
                continue
            for site_key in SITE_ORDER:
                items = sites.get(site_key)
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    yield agent_name, SIDE[side_key], SITE[site_key], item


def main() -> None:
    fragment = json.loads(SRC.read_text(encoding="utf-8"))
    db = json.loads(OUT.read_text(encoding="utf-8"))
    summit = db.setdefault("Summit", {})
    ids, refs = _known(db)
    added = skipped = 0
    for agent_name, side, site, item in _rows(fragment):
        video = str(item.get("video_url") or "").strip()
        item_id = str(item.get("id") or "").strip()
        item_refs = _refs(item)
        if not video.startswith("file_id:") or not item_id:
            skipped += 1
            continue
        if item_id in ids or item_refs & refs:
            skipped += 1
            continue
        row = {
            "id": item_id,
            "title": item.get("title", ""),
            "side": side,
            "site": site,
            "target": item.get("target", ""),
            "description": item.get("description", ""),
            "video_url": video,
            "source": item.get("source", ""),
        }
        video_src = str(item.get("video_src") or "").strip()
        if video_src:
            row["video_src"] = video_src
        lineup_type = str(item.get("type") or "").strip()
        if lineup_type in TYPES:
            row["type"] = lineup_type
        upload_date = str(item.get("upload_date") or "").strip()
        if upload_date:
            row["upload_date"] = upload_date
        summit.setdefault(agent_name, []).append(row)
        ids.add(item_id)
        refs.update(item_refs)
        added += 1
    OUT.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"добавлено {added}, пропущено {skipped}")


if __name__ == "__main__":
    sys.exit(main())
