RANKS: dict[str, str] = {
    "iron_bronze": "Железо — Бронза",
    "silver_gold": "Серебро — Золото",
    "plat_diamond": "Платина — Алмаз",
    "asc_immortal": "Расцвет — Иммортал",
}

# Сайты на карте. C есть не на всех картах. M — Mid (Haven, Bind).
MAP_SITES: dict[str, tuple[str, ...]] = {
    "abyss": ("A", "B"),
    "corrode": ("A", "B"),
    "bind": ("A", "B", "M"),
    "haven": ("A", "B", "C", "M"),
    "lotus": ("A", "B", "C"),
    "sunset": ("A", "B"),
    "summit": ("A", "B"),
}

MAPS: dict[str, str] = {
    "abyss": "Abyss",
    "corrode": "Corrode",
    "bind": "Bind",
    "haven": "Haven",
    "lotus": "Lotus",
    "sunset": "Sunset",
    "summit": "Summit",
}

ROLES: dict[str, str] = {
    "duelist": "Дуэлянт",
    "initiator": "Инициатор",
    "controller": "Смокер",
    "sentinel": "Сентинел",
}

# Сдвиг винрейта по диапазону ранга. Это поправка к ориентирам, не live-статистика.
RANK_WIN_SHIFT: dict[str, float] = {
    "iron_bronze": -1.2,
    "silver_gold": -0.4,
    "plat_diamond": 0.3,
    "asc_immortal": 0.9,
}

# Значок кнопки списка раскидок: агент → пары (ключевые слова, эмодзи).
# Порядок пар — приоритет, первое совпадение. Агентов вне таблицы не перекрашиваем.
# «ult» и «tp» в подписи ищутся как начало слова, чтобы не задеть Default.
_LINEUP_EMOJI_FIRST: tuple[tuple[tuple[str, ...], str], ...] = (
    (("сетап", "setup"), "🧩"),
    (("общий лайнап", "general lineup"), "🔀"),
)

LINEUP_BUTTON_EMOJI: dict[str, tuple[tuple[tuple[str, ...], str], ...]] = {
    "vyse": _LINEUP_EMOJI_FIRST
    + (
        (("флеш", "flash", "arc rose"), "🌹"),
        (("razorvine",), "🌿"),
    ),
    "killjoy": _LINEUP_EMOJI_FIRST
    + (
        (("ульт", "ult"), "🔒"),
        (("молл", "molly", "гранат", "grenade", "нанорой", "nanoswarm"), "🐝"),
    ),
    "veto": _LINEUP_EMOJI_FIRST
    + (
        (("тп", "tp", "телепорт", "teleport"), "🌀"),
        (("interceptor", "интерцептор"), "🛡"),
    ),
    "deadlock": _LINEUP_EMOJI_FIRST
    + (
        (("ульт", "ult"), "☠️"),
        (("сеть", "сети", "сетью", "сетк", "gravnet"), "🪤"),
        (("барьер", "barrier", "стен", "wall"), "🧱"),
    ),
    "fade": _LINEUP_EMOJI_FIRST + ((("haunt",), "👁"),),
    "gekko": _LINEUP_EMOJI_FIRST
    + (
        (("dizzy", "диззи"), "💫"),
        (("задержк", "delay"), "🧪"),
    ),
    "cypher": _LINEUP_EMOJI_FIRST
    + (
        (("растяжк", "tripwire"), "🧵"),
        (("камер", "camera"), "📷"),
        (("клетк", "cage"), "🧊"),
    ),
}
