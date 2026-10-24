"""Перезаписать description: компактный формат и «Зачем» из названия, если заглушка."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lineups import compact_lineup_description  # noqa: E402


def walk(obj, side_hint: str = "") -> int:
    changed = 0
    if isinstance(obj, dict):
        if "description" in obj and "title" in obj and isinstance(obj["description"], str):
            if "<b>" in obj["description"]:
                side = str(obj.get("side") or side_hint)
                new = compact_lineup_description(
                    obj["description"],
                    side=side,
                    target=str(obj.get("target", "")),
                    title=str(obj.get("title", "")),
                )
                if new != obj["description"]:
                    obj["description"] = new
                    changed += 1
        for key, val in obj.items():
            hint = side_hint
            if key == "attack":
                hint = "Атака"
            elif key == "defense":
                hint = "Защита"
            changed += walk(val, hint)
    elif isinstance(obj, list):
        for val in obj:
            changed += walk(val, side_hint)
    return changed


def main() -> None:
    paths = [ROOT / "lineups.json", ROOT / "incoming" / "lineups_haven_a_test.json"]
    for path in paths:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        n = walk(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: обновлено {n}")


if __name__ == "__main__":
    main()
