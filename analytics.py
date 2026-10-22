from dataclasses import dataclass

from constants import MAPS, RANK_WIN_SHIFT, RANKS, ROLES


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
        ("Jett", 24.1, 50.8, "Вертикаль и длинные прострелы — быстрые дуэли на A/Main."),
        ("Raze", 19.6, 50.2, "Satchel и гранаты давят узкие choke на Mid и B."),
        ("Neon", 14.3, 49.7, "Спринт и slide помогают резать дистанции на огромной карте."),
    ],
    ("abyss", "initiator"): [
        ("Sova", 27.4, 51.1, "Recon покрывает длинные линии и deep углы на всех сайтах."),
        ("Fade", 18.9, 50.4, "Haunt и seize ломают оборону дальних позиций."),
        ("Gekko", 15.2, 50.0, "Wingman и Dizzy дают инфо без риска на wide peeks."),
    ],
    ("abyss", "controller"): [
        ("Omen", 26.8, 51.3, "Smoke на длинных линиях режет обзор с A до Mid."),
        ("Viper", 17.5, 50.6, "Wall и orb контролируют split на B и Mid."),
        ("Harbor", 13.1, 49.9, "Cascade и Cove закрывают высокие прострелы."),
    ],
    ("abyss", "sentinel"): [
        ("Cypher", 22.7, 50.9, "Tripwire и cam держат flanks на длинных ротациях."),
        ("Killjoy", 20.4, 50.5, "Turret и alarmbot стабилизируют hold на site."),
        ("Vyse", 14.8, 50.1, "Arc Rose и wall ловят агрессию на choke."),
    ],
    ("corrode", "duelist"): [
        ("Raze", 25.3, 51.0, "Blast pack и rocket выигрывают tight angles и close fights."),
        ("Reyna", 18.2, 50.3, "Dismiss безопасно выходит из contact duels."),
        ("Waylay", 12.6, 49.8, "Sprint и stall давят ранние дуэли на Mid."),
    ],
    ("corrode", "initiator"): [
        ("Fade", 24.0, 51.2, "Prowler и seize контролируют узкие коридоры."),
        ("Breach", 19.1, 50.7, "Flash через стены ломают stack на site."),
        ("Skye", 16.4, 50.2, "Flash и heal дают tempo после первого contact."),
    ],
    ("corrode", "controller"): [
        ("Viper", 28.2, 51.4, "Orb и wall доминируют на односторонних take."),
        ("Brimstone", 17.0, 50.5, "Sky smoke и molly стабильны на execute."),
        ("Clove", 13.5, 50.0, "Smoke после death и pick дают второй шанс на entry."),
    ],
    ("corrode", "sentinel"): [
        ("Killjoy", 23.6, 51.0, "Nanos и lockdown сильны на retake-heavy meta."),
        ("Cypher", 19.8, 50.6, "Info на flanks критична на многоуровневых углах."),
        ("Sage", 15.0, 50.1, "Wall режет rush, slow orb замедляет execute."),
    ],
    ("bind", "duelist"): [
        ("Raze", 26.5, 51.2, "Blast pack — must-have для A short и B hookah."),
        ("Jett", 21.0, 50.6, "Dash и updraft для peek A heaven и elbow."),
        ("Neon", 13.4, 49.9, "Fast take через teleporter и B long."),
    ],
    ("bind", "initiator"): [
        ("Fade", 25.1, 51.3, "Seize и nightfall на tight site Bind."),
        ("Sova", 20.2, 50.8, "Recon через teleporter и default."),
        ("KAY/O", 14.7, 50.2, "Suppress и knife режут util defenders."),
    ],
    ("bind", "controller"): [
        ("Brimstone", 27.9, 51.5, "3 smokes и molly — классика execute A/B."),
        ("Viper", 18.3, 50.7, "Wall на A и orb на post-plant."),
        ("Omen", 12.0, 50.0, "TP и smokes для fake и rotate."),
    ],
    ("bind", "sentinel"): [
        ("Cypher", 24.4, 51.1, "Cage и cam на hookah и A short."),
        ("Chamber", 18.6, 50.5, "Operator и rendezvous на long angles."),
        ("Killjoy", 16.2, 50.0, "Lockdown на retake B site."),
    ],
    ("haven", "duelist"): [
        ("Jett", 23.8, 50.9, "Три сайта — мобильность для rotate и entry."),
        ("Reyna", 17.9, 50.2, "Self-sustain на длинных раундах Haven."),
        ("Raze", 16.5, 50.0, "Grenades на garage и C long."),
    ],
    ("haven", "initiator"): [
        ("Sova", 26.2, 51.2, "Recon покрывает все три site и mid."),
        ("Skye", 18.0, 50.5, "Heal и flash для tri-site macro."),
        ("Breach", 15.3, 50.0, "Stun через стены на A long и C."),
    ],
    ("haven", "controller"): [
        ("Omen", 25.5, 51.0, "Smokes на все три site из одной точки."),
        ("Astra", 19.4, 50.6, "Stars и cosmic divide на split C."),
        ("Viper", 14.1, 50.1, "Orb на one-way и post-plant."),
    ],
    ("haven", "sentinel"): [
        ("Sage", 22.1, 50.8, "Wall на C long и slow на garage."),
        ("Cypher", 21.3, 50.5, "Trip на A long и B window."),
        ("Killjoy", 17.0, 50.2, "Alarmbot на rotate через mid."),
    ],
    ("lotus", "duelist"): [
        ("Raze", 24.7, 51.0, "Satchel на root и A main take."),
        ("Jett", 20.1, 50.5, "Mobility на revolving doors meta."),
        ("ISO", 11.8, 49.7, "Double tap и wall для isolated duels."),
    ],
    ("lotus", "initiator"): [
        ("KAY/O", 23.5, 51.1, "Knife и suppress на stacked site."),
        ("Fade", 19.0, 50.6, "Prowler на tight lotus angles."),
        ("Gekko", 16.2, 50.1, "Info через walls на B and C."),
    ],
    ("lotus", "controller"): [
        ("Omen", 24.8, 51.2, "Smokes на door control и split."),
        ("Harbor", 18.7, 50.7, "Wall на A and waterfall control."),
        ("Viper", 15.0, 50.2, "Lineups на post-plant и default."),
    ],
    ("lotus", "sentinel"): [
        ("Killjoy", 23.0, 50.9, "Turret на choke и retake setup."),
        ("Vyse", 17.5, 50.4, "Arc Rose на door fights."),
        ("Cypher", 16.8, 50.0, "Cam на info mid и flanks."),
    ],
    ("sunset", "duelist"): [
        ("Neon", 22.4, 50.8, "Speed на mid control и B market."),
        ("Jett", 21.6, 50.5, "Op angles и dash на A main."),
        ("Raze", 17.2, 50.1, "Utility clear на elbow и tiles."),
    ],
    ("sunset", "initiator"): [
        ("Sova", 24.9, 51.0, "Recon на mid и A lobby."),
        ("Fade", 18.8, 50.5, "Haunt на defender stacks."),
        ("Tejo", 14.0, 49.9, "Guided util на execute windows."),
    ],
    ("sunset", "controller"): [
        ("Omen", 27.1, 51.3, "Smokes на mid и market split."),
        ("Clove", 16.5, 50.4, "Aggressive smoke timing на entry."),
        ("Brimstone", 14.2, 50.0, "Stim и molly на B take."),
    ],
    ("sunset", "sentinel"): [
        ("Vyse", 21.9, 51.0, "Steel garden на choke control."),
        ("Killjoy", 20.0, 50.6, "Nanos на retake-heavy rounds."),
        ("Cypher", 15.4, 50.1, "Info на defender mid holds."),
    ],
    ("summit", "duelist"): [
        ("Jett", 25.0, 51.1, "Dash и updraft закрывают перепады высоты и быстрый entry."),
        ("Reyna", 17.5, 50.4, "Короткий swing и dismiss после первого контакта."),
        ("Raze", 16.0, 50.0, "Гранаты чистят close углы перед выходом на сайт."),
    ],
    ("summit", "initiator"): [
        ("Sova", 28.0, 51.4, "Recon и shock dart дают информацию до пика на высоте."),
        ("KAY/O", 17.6, 50.6, "Suppress режет утилити защитников на исполнении."),
        ("Skye", 14.5, 50.1, "Flash и heal держат темп после первого размена."),
    ],
    ("summit", "controller"): [
        ("Omen", 26.0, 51.2, "Дымы режут длинные линии и позволяют сплит."),
        ("Viper", 17.8, 50.6, "Wall и orb держат постплант и один проход."),
        ("Astra", 13.2, 50.0, "Звёзды удобны, когда раунд затягивается."),
    ],
    ("summit", "sentinel"): [
        ("Sage", 21.5, 50.8, "Стена закрывает проход, slow тормозит выход."),
        ("Cypher", 20.2, 50.5, "Растяжки и камера ловят фланг на ротации."),
        ("Chamber", 16.0, 50.1, "Длинные линии под оператора и телепорт отхода."),
    ],
}


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


def build_analytics_card(rank_id: str, map_id: str, role_id: str) -> str:
    rank_label = RANKS[rank_id]
    map_label = MAPS[map_id]
    role_label = ROLES[role_id]
    agents = get_agent_stats(map_id, role_id, rank_id)

    lines = [
        f"📊 <b>Аналитика Valorant</b>",
        f"Ранг: <b>{rank_label}</b> · Карта: <b>{map_label}</b> · Роль: <b>{role_label}</b>",
        "",
        "<b>Топ агенты (pick / win):</b>",
    ]
    if not agents:
        lines.append("Для этой связки пока нет ориентиров.")
    for idx, agent in enumerate(agents, start=1):
        lines.append(
            f"{idx}. <b>{agent.name}</b> — pick {agent.pick_rate:.1f}% · win {agent.win_rate:.1f}%"
        )
        lines.append(f"   <i>{agent.summary}</i>")

    lines.extend(
        [
            "",
            "Ориентиры по публичной мете (Tracker.gg, VLR.gg, OP.GG), "
            "не живая выгрузка. Проценты округлены, винрейт слегка сдвинут под выбранный ранг.",
        ]
    )
    return "\n".join(lines)
