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
