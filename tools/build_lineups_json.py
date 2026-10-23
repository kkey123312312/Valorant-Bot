"""Собрать lineups.json из C:\\Project Vlr\\lineups.json и lineups_bind_sentinels.json."""
import json
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "lineups.json"
MAIN = Path(r"C:\Project Vlr\lineups.json")
BIND_SENTINELS = Path(r"C:\Project Vlr\lineups_bind_sentinels.json")

SIDE = {"attack": "\u0410\u0442\u0430\u043a\u0430", "defense": "\u0417\u0430\u0449\u0438\u0442\u0430"}
SITE = {"a_site": "A", "b_site": "B", "c_site": "C", "mid": "M"}
AGENTS = {
    "sova": "Sova",
    "fade": "Fade",
    "breach": "Breach",
    "kayo": "Kayo",
    "gekko": "Gekko",
    "viper": "Viper",
    "cypher": "Cypher",
    "killjoy": "Killjoy",
    "vyse": "Vyse",
    "veto": "Veto",
    "deadlock": "Deadlock",
}
MAP_ORDER = ["Haven", "Ascent", "Bind"]
AGENT_ORDER = [
    "Sova",
    "Fade",
    "Breach",
    "Kayo",
    "Gekko",
    "Viper",
    "Cypher",
    "Killjoy",
    "Vyse",
    "Veto",
    "Deadlock",
]


def is_mp4(url: str) -> bool:
    u = (url or "").strip()
    if not u.startswith("http"):
        return False
    path = unquote(u.split("?", 1)[0]).lower()
    return path.endswith(".mp4")


def flatten(raw: dict) -> dict[str, dict[str, list]]:
    by_key: dict[tuple[str, str], list] = {}
    for map_key, agents in raw.items():
        map_name = map_key.strip().title()
        if map_name == "Haven":
            map_name = "Haven"
        elif map_name == "Ascent":
            map_name = "Ascent"
        elif map_name == "Bind":
            map_name = "Bind"
        for agent_key, sides in agents.items():
            agent_name = AGENTS.get(agent_key.lower(), agent_key.title())
            bucket = by_key.setdefault((map_name, agent_name), [])
            for side_key, sites in sides.items():
                if not isinstance(sites, dict):
                    continue
                limited = sites.get("note") == "limited_data"
                for site_key, items in sites.items():
                    if site_key == "note" or not isinstance(items, list):
                        continue
                    for it in items:
                        video = str(it.get("video_url", "")).strip()
                        if not is_mp4(video):
                            continue
                        row = {
                            "id": it["id"],
                            "title": it["title"],
                            "side": SIDE[side_key],
                            "site": SITE[site_key],
                            "target": it.get("target", ""),
                            "description": it["description"],
                            "video_url": video,
                            "source": it.get("source", ""),
                        }
                        page = str(it.get("page") or "").strip()
                        if page:
                            row["page"] = page
                        if limited:
                            row["limited"] = True
                        bucket.append(row)

    merged: dict[str, dict[str, list]] = {}
    for map_name in MAP_ORDER:
        merged[map_name] = {}
        for agent_name in AGENT_ORDER:
            items = by_key.get((map_name, agent_name), [])
            if items:
                merged[map_name][agent_name] = items
    return merged


def main() -> None:
    main_raw = json.loads(MAIN.read_text(encoding="utf-8"))
    bind_raw = json.loads(BIND_SENTINELS.read_text(encoding="utf-8"))
    nested = {**main_raw}
    nested.setdefault("bind", {})
    for agent, sides in bind_raw["bind"].items():
        nested["bind"][agent] = sides

    merged = flatten(nested)
    flat = [it for agents in merged.values() for items in agents.values() for it in items]
    ids = [it["id"] for it in flat]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids")
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(flat)} lineups to {OUT}")


if __name__ == "__main__":
    main()
