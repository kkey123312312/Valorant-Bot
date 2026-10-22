from aiogram.filters.callback_data import CallbackData


class RankCb(CallbackData, prefix="rank"):
    rank_id: str


class MapCb(CallbackData, prefix="map"):
    rank_id: str
    map_id: str


class RoleCb(CallbackData, prefix="role"):
    rank_id: str
    map_id: str
    role_id: str


class AiAdviceCb(CallbackData, prefix="ai"):
    rank_id: str
    map_id: str
    role_id: str


class AgentCb(CallbackData, prefix="ag"):
    rank_id: str
    map_id: str
    role_id: str
    agent_id: str


class SidePickCb(CallbackData, prefix="sd"):
    rank_id: str
    map_id: str
    role_id: str
    agent_id: str
    side_key: str


class SitePickCb(CallbackData, prefix="st"):
    rank_id: str
    map_id: str
    role_id: str
    agent_id: str
    side_key: str
    site: str


class LineupCb(CallbackData, prefix="ln"):
    rank_id: str
    map_id: str
    role_id: str
    agent_id: str
    side_key: str
    site: str
    lineup_id: str


class NavCb(CallbackData, prefix="nav"):
    action: str
    rank_id: str
    map_id: str
    role_id: str
    agent_id: str
    side_key: str = "-"
    site: str = "-"
