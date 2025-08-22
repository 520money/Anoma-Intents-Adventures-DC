#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anoma Intents Adventures - Discord Bot (Discord-only, intent-centric)
- Prefix commands: p! / P!
- Basics: help, create, profile, daily, work, quest, leaderboard, rumble
- Customization & economy: race, class, inventory, shop, buy, transfer, alignment
- PvP & multiplayer: duel, accept, decline, cancel, rumble
- Roguelike dungeon (minimal): dungeon create/join/start/leave/status/map, move, attack
- Storage: data/players.json (players) + data/intents.json (intent queue) + data/dungeons.json (dungeons)
- Solver: background loop to process intents (intent -> solver -> settlement)
"""

import os
import json
import time
import random
import asyncio
from typing import Dict, Any, List, Optional, Tuple

import discord
from discord.ext import commands
from dotenv import load_dotenv

BOT_PREFIXES = ["p!", "P!"]
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PLAYERS_JSON_PATH = os.path.join(DATA_DIR, "players.json")
INTENTS_JSON_PATH = os.path.join(DATA_DIR, "intents.json")
DUNGEONS_JSON_PATH = os.path.join(DATA_DIR, "dungeons.json")

# ----------------------- Config -----------------------
CHANGE_COST = 2500  # race/class change cost (v2.1)
DAILY_COOLDOWN_SEC = 23 * 3600
WORK_COOLDOWN_SEC = 3600
DUEL_TIMEOUT_SEC = 120
DUNGEON_TICK_MS = 2000

# Level curve: level^3 * 25 (v2.1)

def get_level_exp_requirement(level: int) -> int:
    if level <= 0:
        return 0
    return (level ** 3) * 25

ALLOWED_RACES = [
    # Base
    "human", "elf", "dwarf", "orc", "halfling", "dragonborn", "tiefling", "gnome", "half-elf", "half-orc",
    # Underdark
    "drow", "duergar", "svirfneblin", "derro", "quaggoth",
    # Astral Plane
    "aasimar", "kalashtar", "githzerai", "sylph", "starborn",
    # Other Planes
    "githyanki",
]

ALLOWED_CLASSES = [
    # Base
    "warrior", "mage", "rogue", "cleric", "ranger", "paladin", "warlock", "bard", "monk", "druid",
    # Underdark
    "shadowmancer", "voidpriest", "gloomhunter", "crystalsmith", "mindflayer",
    # Astral Plane
    "astral monk", "planar mage", "dream walker", "star weaver", "mind sage",
]

QUEST_DIFFICULTIES = {
    "easy": {"xp": (10, 20), "gold": (5, 10), "drop_rate": 0.60},
    "medium": {"xp": (18, 32), "gold": (8, 16), "drop_rate": 0.60},
    "hard": {"xp": (28, 50), "gold": (12, 24), "drop_rate": 0.60},
}

SHOP_ITEMS: Dict[str, int] = {
    "Potion": 25,
    "Rune": 40,
    "Gem": 60,
    "Scroll": 30,
    "Herb": 15,
    "Ring": 80,
    "Amulet": 100,
    "Cloak": 90,
    "Boots": 70,
}

# Regions for adventures/explore
REGIONS = ["forest", "mountain", "desert"]

# Pet species (minimal set)
PET_SPECIES = ["wolf", "cat", "hawk", "golem"]

# Dungeon balance (simple)
PLAYER_BASE_HP = 10
ENEMY_BASE_HP = 4
BOSS_HP = 12
OBSTACLE_DENSITY = 0.06  # ~6% of inner tiles become obstacles
DROP_TABLE = [
    ("Potion", 0.30),  # heal +5 hp
    ("Bomb", 0.15),    # deal 3 dmg to adjacent enemies when used
]

# ----------------------- Storage (JSON + Lock) -----------------------
class JsonStorage:
    def __init__(self, json_path: str, default_factory):
        self.json_path = json_path
        self._lock = asyncio.Lock()
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        if not os.path.exists(self.json_path):
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(default_factory(), f, ensure_ascii=False, indent=2)

    async def _read(self) -> Dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._read_sync)

    def _read_sync(self) -> Dict[str, Any]:
        if not os.path.exists(self.json_path):
            return {}
        with open(self.json_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    async def _write(self, data: Dict[str, Any]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._write_sync, data)

    def _write_sync(self, data: Dict[str, Any]) -> None:
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class PlayerStorage(JsonStorage):
    def __init__(self, json_path: str):
        super().__init__(json_path, default_factory=lambda: {"players": {}})

    async def get_player(self, user_id: int) -> Optional[Dict[str, Any]]:
        data = await self._read()
        return data.get("players", {}).get(str(user_id))

    async def upsert_player(self, user_id: int, player: Dict[str, Any]) -> None:
        data = await self._read()
        if "players" not in data:
            data["players"] = {}
        data["players"][str(user_id)] = player
        await self._write(data)

    async def all_players(self) -> Dict[str, Dict[str, Any]]:
        data = await self._read()
        return data.get("players", {})


class IntentStorage(JsonStorage):
    def __init__(self, json_path: str):
        super().__init__(json_path, default_factory=lambda: {"intents": []})

    async def enqueue(self, intent: Dict[str, Any]) -> None:
        data = await self._read()
        intents = data.get("intents", [])
        intents.append(intent)
        data["intents"] = intents
        await self._write(data)

    async def list_all(self) -> List[Dict[str, Any]]:
        data = await self._read()
        return data.get("intents", [])

    async def replace_all(self, intents: List[Dict[str, Any]]) -> None:
        await self._write({"intents": intents})


class DungeonStorage(JsonStorage):
    def __init__(self, json_path: str):
        super().__init__(json_path, default_factory=lambda: {"dungeons": {}})

    async def get(self, channel_id: int) -> Optional[Dict[str, Any]]:
        data = await self._read()
        return data.get("dungeons", {}).get(str(channel_id))

    async def upsert(self, channel_id: int, dungeon: Dict[str, Any]) -> None:
        data = await self._read()
        if "dungeons" not in data:
            data["dungeons"] = {}
        data["dungeons"][str(channel_id)] = dungeon
        await self._write(data)

    async def remove(self, channel_id: int) -> None:
        data = await self._read()
        if data.get("dungeons") and str(channel_id) in data["dungeons"]:
            del data["dungeons"][str(channel_id)]
            await self._write(data)

    async def all(self) -> Dict[str, Dict[str, Any]]:
        data = await self._read()
        return data.get("dungeons", {})


# ----------------------- Utils -----------------------

def now() -> int:
    return int(time.time())

async def ensure_player(storage: PlayerStorage, user: discord.User) -> Dict[str, Any]:
    existing = await storage.get_player(user.id)
    if existing:
        return existing
    profile = {
        "user_id": user.id,
        "name": user.name,
        "race": None,
        "clazz": None,
        "gold": 0,
        "xp": 0,
        "level": 1,
        "quests_completed": 0,
        "alignment": 0,  # -100 ~ 100
        "inventory": [],
        "last_daily": 0,
        "last_work": 0,
        "created_at": now(),
    }
    await player_storage.upsert_player(user.id, profile)
    return profile


def _new_dungeon(width: int = 10, height: int = 10) -> Dict[str, Any]:
    return {
        "state": "lobby",  # lobby/running
        "created_at": now(),
        "width": width,
        "height": height,
        "floor": 1,
        "players": {},  # user_id -> {x,y,hp,dead}
        "enemies": [],  # list of {x,y,hp,boss}
        "obstacles": [],  # list of {x,y}
        "end_at": 0,  # ms timestamp; 0 = no timer
        "next_tick": int(time.time() * 1000) + DUNGEON_TICK_MS,
    }


def _rand_empty_cell(dg: Dict[str, Any]) -> Tuple[int, int]:
    width, height = dg["width"], dg["height"]
    occupied = {(p["x"], p["y"]) for p in dg["players"].values()} | {(e["x"], e["y"]) for e in dg["enemies"]} | {(o["x"], o["y"]) for o in dg.get("obstacles", [])}
    while True:
        x = random.randint(1, width - 2)
        y = random.randint(1, height - 2)
        if (x, y) not in occupied:
            return x, y


def _render_map(dg: Dict[str, Any]) -> str:
    width, height = dg["width"], dg["height"]
    grid = [["#" if x in (0, width - 1) or y in (0, height - 1) else "." for x in range(width)] for y in range(height)]
    for o in dg.get("obstacles", []):
        grid[o["y"]][o["x"]] = "X"
    for e in dg["enemies"]:
        grid[e["y"]][e["x"]] = "B" if e.get("boss") else "E"
    for uid, p in dg["players"].items():
        if p.get("dead"):
            grid[p["y"]][p["x"]] = "✖"
        else:
            grid[p["y"]][p["x"]] = "P"
    lines = ["".join(row) for row in grid]
    banner = f"Floor {dg.get('floor',1)}"
    return banner + "\n" + "\n".join(lines)


def _dir_to_vec(direction: str) -> Tuple[int, int]:
    d = direction.lower()
    if d in ("up", "w"):
        return (0, -1)
    if d in ("down", "s"):
        return (0, 1)
    if d in ("left", "a"):
        return (-1, 0)
    if d in ("right", "d"):
        return (1, 0)
    return (0, 0)


def _in_bounds(dg: Dict[str, Any], x: int, y: int) -> bool:
    return 0 < x < dg["width"] - 1 and 0 < y < dg["height"] - 1


# ----------------------- Bot init -----------------------
load_dotenv()
intents = discord.Intents.default()
authority_intents = intents
authority_intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIXES, intents=authority_intents, help_command=None)

player_storage = PlayerStorage(PLAYERS_JSON_PATH)
intent_storage = IntentStorage(INTENTS_JSON_PATH)
dungeon_storage = DungeonStorage(DUNGEONS_JSON_PATH)
_solver_task: Optional[asyncio.Task] = None

# ----------------------- Solver loop -----------------------
async def solver_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            intents_list = await intent_storage.list_all()
            changed = False

            changed |= await _solve_duel_cancels(intents_list)
            changed |= await _solve_duels(intents_list)
            changed |= await _solve_dungeons(intents_list)
            changed |= await _solve_region(intents_list)
            changed |= await _solve_pets(intents_list)

            if changed:
                intents_list = [it for it in intents_list if not it.get("_processed", False)]
                await intent_storage.replace_all(intents_list)
        except Exception as e:
            print(f"[solver] error: {e}")
        await asyncio.sleep(1.0)


async def _solve_duel_cancels(intents_list: List[Dict[str, Any]]) -> bool:
    changed = False
    for cancel in intents_list:
        if cancel.get("type") != "duel_cancel" or cancel.get("_processed"):
            continue
        latest_req = None
        for req in intents_list:
            if req.get("type") == "duel_request" and not req.get("_processed") and req.get("channel_id") == cancel.get("channel_id") and req.get("challenger_id") == cancel.get("challenger_id"):
                if latest_req is None or req.get("created_at", 0) > latest_req.get("created_at", 0):
                    latest_req = req
        if latest_req:
            latest_req["_processed"], cancel["_processed"], changed = True, True, True
            await _notify_channel(cancel["channel_id"], f"🛑 Duel canceled by <@{cancel['challenger_id']}>")
        else:
            cancel["_processed"], changed = True, True
    return changed


async def _solve_duels(intents_list: List[Dict[str, Any]]) -> bool:
    now_ts = now()
    changed = False
    for it in intents_list:
        if it.get("type") == "duel_request" and not it.get("_processed"):
            created = it.get("created_at", 0)
            if now_ts - created > DUEL_TIMEOUT_SEC:
                it["_processed"], changed = True, True
                await _notify_channel(it["channel_id"], f"⏳ Duel timed out: <@{it['target_id']}> did not respond")
    for req in intents_list:
        if req.get("type") != "duel_request" or req.get("_processed"):
            continue
        challenger_id = req["challenger_id"]
        target_id = req["target_id"]
        decision: Optional[Dict[str, Any]] = None
        for it in intents_list:
            if it.get("type") in ("duel_accept", "duel_decline") and not it.get("_processed") and it.get("target_id") == target_id and it.get("challenger_id") == challenger_id:
                decision = it
                break
        if decision is None:
            continue
        req["_processed"], decision["_processed"], changed = True, True, True
        if decision["type"] == "duel_decline":
            await _notify_channel(req["channel_id"], f"🙅 Duel declined: <@{target_id}> refused <@{challenger_id}>")
            continue
        challenger_profile = await ensure_player(player_storage, await _fetch_user(challenger_id))
        target_profile = await ensure_player(player_storage, await _fetch_user(target_id))
        c_roll = random.randint(1, 20) + challenger_profile.get("level", 1)
        t_roll = random.randint(1, 20) + target_profile.get("level", 1)
        if c_roll > t_roll:
            winner_id, loser_id, w, l = challenger_id, target_id, c_roll, t_roll
        elif t_roll > c_roll:
            winner_id, loser_id, w, l = target_id, challenger_id, t_roll, c_roll
        else:
            await _notify_channel(req["channel_id"], f"🤝 Duel draw: <@{challenger_id}>({c_roll}) vs <@{target_id}>({t_roll})")
            continue
        reward_gold = random.randint(15, 30)
        winner_profile = await ensure_player(player_storage, await _fetch_user(winner_id))
        winner_profile["gold"] = winner_profile.get("gold", 0) + reward_gold
        await player_storage.upsert_player(winner_id, winner_profile)
        await _notify_channel(req["channel_id"], f"🏆 Duel result: <@{winner_id}>({w}) beat <@{loser_id}>({l}), +{reward_gold} gold")
    return changed


async def _solve_dungeons(intents_list: List[Dict[str, Any]]) -> bool:
    changed = False
    all_dg = await dungeon_storage.all()

    # Manage intents (create/join/leave/start)
    for it in intents_list:
        if it.get("_processed"):
            continue
        if it.get("type") not in ("dg_create", "dg_join", "dg_leave", "dg_start", "dg_move", "dg_attack", "dg_use", "dg_revive"):
            continue
        channel_id = it.get("channel_id")
        dungeon = all_dg.get(str(channel_id))

        if it["type"] == "dg_create":
            if dungeon is None:
                dungeon = _new_dungeon(12, 12)
                all_dg[str(channel_id)] = dungeon
                await _notify_channel(channel_id, "🗺️ Dungeon created. Use p!dungeon join, then p!dungeon start.")
                changed = True
            it["_processed"] = True

        elif it["type"] == "dg_join":
            if dungeon is None:
                await _notify_channel(channel_id, "❌ Please run p!dungeon create first.")
                it["_processed"], changed = True, True
                continue
            if dungeon["state"] != "lobby":
                await _notify_channel(channel_id, "❌ Dungeon already started, cannot join.")
                it["_processed"], changed = True, True
                continue
            uid = str(it["user_id"])
            if uid not in dungeon["players"]:
                x, y = _rand_empty_cell(dungeon)
                dungeon["players"][uid] = {"x": x, "y": y, "hp": PLAYER_BASE_HP, "dead": False}
                await _notify_channel(channel_id, f"✅ <@{it['user_id']}> joined the dungeon")
                changed = True
            it["_processed"] = True

        elif it["type"] == "dg_leave":
            if dungeon is not None:
                uid = str(it["user_id"])
                if uid in dungeon["players"]:
                    del dungeon["players"][uid]
                    await _notify_channel(channel_id, f"🚪 <@{it['user_id']}> left the dungeon")
                    changed = True
                if not dungeon["players"]:
                    await _notify_channel(channel_id, "🧹 No players left. Dungeon cleaned up.")
                    del all_dg[str(channel_id)]
                    changed = True
            it["_processed"] = True

        elif it["type"] == "dg_start":
            if dungeon is None:
                await _notify_channel(channel_id, "❌ Please p!dungeon create + join first.")
                it["_processed"], changed = True, True
                continue
            if dungeon["state"] == "running":
                it["_processed"] = True
                continue
            # Spawn a few enemies
            dungeon["enemies"] = []
            dungeon["obstacles"] = []
            # generate obstacles
            total_inner = (dungeon["width"] - 2) * (dungeon["height"] - 2)
            num_obs = max(0, int(total_inner * OBSTACLE_DENSITY))
            while len(dungeon["obstacles"]) < num_obs:
                x, y = _rand_empty_cell(dungeon)
                dungeon["obstacles"].append({"x": x, "y": y})
            enemy_count = max(1, len(dungeon["players"]) + dungeon["floor"] // 1)
            for i in range(enemy_count):
                x, y = _rand_empty_cell(dungeon)
                dungeon["enemies"].append({"x": x, "y": y, "hp": ENEMY_BASE_HP + dungeon["floor"] - 1, "boss": False})
            if dungeon["floor"] % 3 == 0:
                x, y = _rand_empty_cell(dungeon)
                dungeon["enemies"].append({"x": x, "y": y, "hp": BOSS_HP + dungeon["floor"], "boss": True})
            dungeon["state"] = "running"
            dungeon["next_tick"] = int(time.time() * 1000) + DUNGEON_TICK_MS
            await _notify_channel(channel_id, "▶️ Dungeon started! Use p!move and p!attack.")
            changed = True
            it["_processed"] = True

    # Tick process (move/attack/AI/broadcast)
    now_ms = int(time.time() * 1000)
    for chan_id_str, dg in list(all_dg.items()):
        # handle end timer
        if dg.get("end_at", 0) and now_ms >= dg["end_at"]:
            await _notify_channel(int(chan_id_str), "⏱️ Dungeon time is up. Instance closed.")
            del all_dg[chan_id_str]
            changed = True
            continue
        if dg.get("state") != "running":
            continue
        if now_ms < dg.get("next_tick", 0):
            continue
        dg["next_tick"] = now_ms + DUNGEON_TICK_MS

        channel_id = int(chan_id_str)
        # 收集本 tick 的移动/攻击/使用/复活意图
        moves: List[Dict[str, Any]] = []
        attacks: List[Dict[str, Any]] = []
        uses: List[Dict[str, Any]] = []
        revives: List[Dict[str, Any]] = []
        for it in intents_list:
            if it.get("_processed"):
                continue
            if it.get("channel_id") != channel_id:
                continue
            if it.get("type") == "dg_move":
                moves.append(it)
            elif it.get("type") == "dg_attack":
                attacks.append(it)
            elif it.get("type") == "dg_use":
                uses.append(it)
            elif it.get("type") == "dg_revive":
                revives.append(it)
        # 先处理复活
        for rv in revives:
            uid = str(rv["user_id"])
            p = dg["players"].get(uid)
            if p and p.get("dead"):
                # pay 5 gold
                prof = await ensure_player(player_storage, await _fetch_user(int(uid)))
                if prof.get("gold", 0) >= 5:
                    prof["gold"] -= 5
                    await player_storage.upsert_player(int(uid), prof)
                    p["dead"] = False
                    p["hp"] = PLAYER_BASE_HP
                    # respawn at a safe random cell
                    rx, ry = _rand_empty_cell(dg)
                    p["x"], p["y"] = rx, ry
                    await _notify_channel(channel_id, f"❤️ <@{uid}> revived (-5 gold).")
            rv["_processed"] = True
        # 先处理移动
        random.shuffle(moves)
        for mv in moves:
            uid = str(mv["user_id"])
            if uid not in dg["players"]:
                mv["_processed"] = True
                continue
            if dg["players"][uid].get("dead"):
                mv["_processed"] = True
                continue
            dx, dy = _dir_to_vec(mv.get("direction", ""))
            px = dg["players"][uid]["x"] + dx
            py = dg["players"][uid]["y"] + dy
            if _in_bounds(dg, px, py) and {"x": px, "y": py} not in dg["enemies"] and {"x": px, "y": py} not in dg.get("obstacles", []):
                occupied_players = {(p["x"], p["y"]) for p in dg["players"].values() if p is not dg["players"][uid]}
                if (px, py) not in occupied_players:
                    dg["players"][uid]["x"] = px
                    dg["players"][uid]["y"] = py
            mv["_processed"] = True
        # 物品使用（如炸弹）
        for us in uses:
            uid = str(us["user_id"])
            profile = await ensure_player(player_storage, await _fetch_user(int(uid)))
            item = us.get("item", "").title()
            inv = profile.get("inventory", [])
            if item in inv:
                if item == "Potion":
                    p = dg["players"].get(uid)
                    if p:
                        p["hp"] = min(PLAYER_BASE_HP, p.get("hp", PLAYER_BASE_HP) + 5)
                        inv.remove(item)
                        profile["inventory"] = inv
                        await player_storage.upsert_player(int(uid), profile)
                        await _notify_channel(channel_id, f"🧪 <@{uid}> used Potion (+5 HP)")
                elif item == "Bomb":
                    p = dg["players"].get(uid)
                    if p:
                        px, py = p["x"], p["y"]
                        for ex, ey in [(px+1,py),(px-1,py),(px,py+1),(px,py-1)]:
                            for e in dg["enemies"]:
                                if e["x"] == ex and e["y"] == ey:
                                    e["hp"] = e.get("hp", ENEMY_BASE_HP) - 3
                        inv.remove(item)
                        profile["inventory"] = inv
                        await player_storage.upsert_player(int(uid), profile)
                        await _notify_channel(channel_id, f"💣 <@{uid}> used Bomb (-3 HP to adjacent enemies)")
            us["_processed"] = True
        # 攻击
        for at in attacks:
            uid = str(at["user_id"])
            if uid not in dg["players"]:
                at["_processed"] = True
                continue
            if dg["players"][uid].get("dead"):
                at["_processed"] = True
                continue
            px, py = dg["players"][uid]["x"], dg["players"][uid]["y"]
            killed = False
            hit = False
            remaining = None
            for ex, ey in [(px+1,py), (px-1,py), (px,py+1), (px,py-1)]:
                # find enemy by coords
                target = None
                for e in dg["enemies"]:
                    if e["x"] == ex and e["y"] == ey:
                        target = e
                        break
                if target:
                    target["hp"] = target.get("hp", ENEMY_BASE_HP) - 2  # player damage
                    if target["hp"] <= 0:
                        dg["enemies"].remove(target)
                        killed = True
                        user = await _fetch_user(int(uid))
                        prof = await ensure_player(player_storage, user)
                        prof["xp"] += 5
                        prof["gold"] += 3
                        # drop
                        for name, prob in DROP_TABLE:
                            if random.random() < prob:
                                prof.setdefault("inventory", []).append(name)
                        while prof["xp"] >= get_level_exp_requirement(prof["level"]):
                            prof["xp"] -= get_level_exp_requirement(prof["level"])
                            prof["level"] += 1
                        await player_storage.upsert_player(int(uid), prof)
                    else:
                        hit = True
                        remaining = target["hp"]
                    break
            at["_processed"] = True
            if killed:
                await _notify_channel(channel_id, f"⚔️ <@{uid}> defeated an enemy!")
            elif hit:
                await _notify_channel(channel_id, f"🗡️ <@{uid}> hit an enemy (-2 HP, {remaining} HP left)")
            else:
                await _notify_channel(channel_id, "🗡️ No enemy adjacent")
        # 敌人行动：相邻则攻击，否则尝试移动
        for e in dg["enemies"]:
            dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1),(0,0)])
            nx, ny = e["x"] + dx, e["y"] + dy
            # if adjacent to a player, attack instead of move
            did_attack = False
            for uid, p in dg["players"].items():
                if p.get("dead"):
                    continue
                if abs(p["x"] - e["x"]) + abs(p["y"] - e["y"]) == 1:
                    dmg = 2 if e.get("boss") else 1
                    p["hp"] = p.get("hp", PLAYER_BASE_HP) - dmg
                    if p["hp"] <= 0:
                        p["dead"] = True
                        await _notify_channel(channel_id, f"💀 <@{uid}> has fallen!")
                    did_attack = True
                    break
            if not did_attack and _in_bounds(dg, nx, ny):
                if all(not (other["x"] == nx and other["y"] == ny) for other in dg["enemies"]) and all(not (p["x"] == nx and p["y"] == ny) for p in dg["players"].values()) and {"x": nx, "y": ny} not in dg.get("obstacles", []):
                    e["x"], e["y"] = nx, ny
        if not dg["enemies"]:
            await _notify_channel(channel_id, "🎉 Floor cleared. Use p!dungeon next to descend, or instance will close if abandoned.")
        else:
            pass
        changed = True

    for chan_id_str, dg in list(all_dg.items()):
        await dungeon_storage.upsert(int(chan_id_str), dg)

    return changed


# ---- Region adventures & explore ----
async def _solve_region(intents_list: List[Dict[str, Any]]) -> bool:
    changed = False
    # Region Adventure state is stored per player in their profile under key 'region_adv'
    for it in intents_list:
        if it.get("_processed"):
            continue
        t = it.get("type")
        if t not in ("region_start", "region_continue", "region_claim", "region_abandon", "region_explore"):
            continue
        user_id = it.get("user_id")
        user = await _fetch_user(user_id)
        profile = await ensure_player(player_storage, user)
        adv = profile.get("region_adv") or {"active": False}

        if t == "region_start":
            region = it.get("region")
            if region not in REGIONS:
                await _notify_channel(it["channel_id"], f"❌ Unknown region. Available: {', '.join(REGIONS)}")
            else:
                adv = {"active": True, "region": region, "step": 1, "completed": False, "pending_reward": 0}
                profile["region_adv"] = adv
                await player_storage.upsert_player(user_id, profile)
                await _notify_channel(it["channel_id"], f"🗺️ Adventure started in {region}. Use p!region adventure continue.")
            it["_processed"], changed = True, True
            continue

        if t == "region_continue":
            if not adv.get("active"):
                await _notify_channel(it["channel_id"], "❗ No active adventure. Use p!region adventure start <region>.")
            else:
                adv["step"] = adv.get("step", 1) + 1
                # simple branching: after 3 steps, complete and set pending reward
                if adv["step"] >= 3:
                    adv["completed"] = True
                    adv["active"] = False
                    adv["pending_reward"] = random.randint(10, 25)
                    await _notify_channel(it["channel_id"], "✅ Adventure completed. Use p!region adventure claim to receive rewards.")
                else:
                    await _notify_channel(it["channel_id"], f"➡️ Progressed to step {adv['step']}. Keep going with continue.")
                profile["region_adv"] = adv
                await player_storage.upsert_player(user_id, profile)
            it["_processed"], changed = True, True
            continue

        if t == "region_claim":
            reward = adv.get("pending_reward", 0)
            if reward > 0:
                profile["gold"] = profile.get("gold", 0) + reward
                adv["pending_reward"] = 0
                profile["region_adv"] = adv
                await player_storage.upsert_player(user_id, profile)
                await _notify_channel(it["channel_id"], f"💰 Adventure reward claimed: +{reward} gold.")
            else:
                await _notify_channel(it["channel_id"], "❗ No reward to claim.")
            it["_processed"], changed = True, True
            continue

        if t == "region_abandon":
            profile["region_adv"] = {"active": False}
            await player_storage.upsert_player(user_id, profile)
            await _notify_channel(it["channel_id"], "🛑 Adventure abandoned.")
            it["_processed"], changed = True, True
            continue

        if t == "region_explore":
            # quick explore with moral choice and small reward/penalty
            choice = it.get("choice", "help")
            delta_align = 1 if choice == "help" else (-1 if choice == "plunder" else 0)
            gold_gain = random.randint(2, 6) if choice == "plunder" else random.randint(1, 4)
            profile["alignment"] = max(-100, min(100, profile.get("alignment", 0) + delta_align))
            profile["gold"] = profile.get("gold", 0) + gold_gain
            await player_storage.upsert_player(user_id, profile)
            await _notify_channel(it["channel_id"], f"🌄 Explore result: alignment {delta_align:+d}, gold +{gold_gain}.")
            it["_processed"], changed = True, True

    return changed


# ---- Pets ----
async def _solve_pets(intents_list: List[Dict[str, Any]]) -> bool:
    changed = False
    for it in intents_list:
        if it.get("_processed"):
            continue
        t = it.get("type")
        if t not in ("pet_adopt", "pet_rename", "pet_feed", "pet_train"):
            continue
        user_id = it.get("user_id")
        user = await _fetch_user(user_id)
        profile = await ensure_player(player_storage, user)
        pet = profile.get("pet")

        if t == "pet_adopt":
            species = it.get("species")
            if pet:
                await _notify_channel(it["channel_id"], "❗ You already have a pet.")
            elif species not in PET_SPECIES:
                await _notify_channel(it["channel_id"], f"❌ Unknown species. Available: {', '.join(PET_SPECIES)}")
            else:
                profile["pet"] = {"species": species, "name": species.title(), "level": 1, "xp": 0, "hunger": 0}
                await player_storage.upsert_player(user_id, profile)
                await _notify_channel(it["channel_id"], f"🐾 Adopted a {species}!")
            it["_processed"], changed = True, True
            continue

        if not pet:
            await _notify_channel(it["channel_id"], "❗ You have no pet. Use p!petadopt <species>.")
            it["_processed"], changed = True, True
            continue

        if t == "pet_rename":
            new_name = it.get("name", pet.get("name", "Pet"))
            pet["name"] = new_name
            profile["pet"] = pet
            await player_storage.upsert_player(user_id, profile)
            await _notify_channel(it["channel_id"], f"✏️ Pet renamed to {new_name}.")
            it["_processed"], changed = True, True
        elif t == "pet_feed":
            pet["hunger"] = max(0, pet.get("hunger", 0) - 1)
            profile["pet"] = pet
            await player_storage.upsert_player(user_id, profile)
            await _notify_channel(it["channel_id"], "🍖 Pet fed.")
            it["_processed"], changed = True, True
        elif t == "pet_train":
            pet["xp"] = pet.get("xp", 0) + 5
            # level up every 20 xp
            while pet["xp"] >= 20:
                pet["xp"] -= 20
                pet["level"] = pet.get("level", 1) + 1
            profile["pet"] = pet
            await player_storage.upsert_player(user_id, profile)
            await _notify_channel(it["channel_id"], f"🏋️ Pet trained. Lv {pet['level']} (XP {pet['xp']}/20)")
            it["_processed"], changed = True, True

    return changed


async def _fetch_user(user_id: int) -> discord.User:
    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except Exception:
            class P:
                id = user_id
                name = f"User {user_id}"
            return P()  # type: ignore
    return user

async def _notify_channel(channel_id: int, content: str) -> None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return
    try:
        await channel.send(content)
    except Exception:
        pass

# ----------------------- Commands -----------------------
load_dotenv()

@bot.event
async def on_ready():
    global _solver_task
    if _solver_task is None or _solver_task.done():
        _solver_task = asyncio.create_task(solver_loop())
    print(f"✅ Logged in as {bot.user} (id={bot.user.id})")


@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    text = (
        "🌟 Anoma Intents Adventures v2.1 (Discord-only)\n"
        "Prefix: p! or P!\n\n"
        "Basics:\n"
        "p!create <race> <class> - create character\n"
        "p!profile - view profile\n"
        "p!daily - claim daily gold\n"
        "p!work - work to earn gold (cooldown)\n"
        "p!quest [easy|medium|hard] - quest (level^3*25 curve, ~60% drops)\n"
        "p!leaderboard [level|gold|quests] - leaderboard\n\n"
        "Customization & Economy:\n"
        f"p!race <race> - change race ({CHANGE_COST} gold)\n"
        f"p!class <class> - change class ({CHANGE_COST} gold)\n"
        "p!inventory - view inventory\n"
        "p!shop - view shop\n"
        "p!buy <item> - buy item\n"
        "p!transfer <@user> <amount> - transfer gold\n"
        "p!alignment - view alignment\n\n"
        "Multiplayer PvP:\n"
        "p!duel <@user> - challenge to a duel\n"
        "p!accept / p!decline - (target) accept/decline\n"
        "p!cancel - (challenger) cancel latest pending duel\n"
        "p!rumble - start free-for-all rumble\n\n"
        "Multiplayer Roguelike Dungeon (full):\n"
        "p!dungeon create|join|start|leave|status|map|help|next|reset\n"
        "p!move <up|down|left|right|w|a|s|d> | p!attack | p!use <item> | p!revive\n"
        "map is on-demand via p!dungeon map (no auto-broadcast).\n\n"
        "Region & Pets:\n"
        "p!region adventure start <forest|mountain|desert> | continue | status | claim | abandon\n"
        "p!region explore <help|plunder>\n"
        "p!pet | p!petadopt <species> | p!petname <name> | p!petfeed | p!pettrain\n\n"
        " races: " + ", ".join(ALLOWED_RACES) + "\n"
        " classes: " + ", ".join(ALLOWED_CLASSES) + "\n"
    )
    await ctx.send(text)


@bot.command(name="create")
async def create_cmd(ctx: commands.Context, *, args: str = ""):
    args = args.strip()
    if not args:
        await ctx.send("Usage: p!create <race> <class>")
        return
    parts = args.split()
    if len(parts) < 2:
        await ctx.send("Provide both race and class: p!create <race> <class>")
        return
    race = parts[0].lower()
    clazz = " ".join(parts[1:]).lower()
    if race not in ALLOWED_RACES:
        await ctx.send(f"Invalid race: {race}")
        return
    if clazz not in ALLOWED_CLASSES:
        await ctx.send(f"Invalid class: {clazz}")
        return
    profile = await ensure_player(player_storage, ctx.author)
    profile["race"], profile["clazz"] = race, clazz
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"🎉 Created: {ctx.author.mention} | {race} {clazz}")


@bot.command(name="profile")
async def profile_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    race = profile.get("race") or "unset"
    clazz = profile.get("clazz") or "unset"
    await ctx.send("\n".join([
        f"👤 {ctx.author.display_name} Profile",
        f"Race: {race}",
        f"Class: {clazz}",
        f"Level: {profile['level']}  (XP: {profile['xp']}/{get_level_exp_requirement(profile['level'])})",
        f"Gold: {profile['gold']}",
        f"Quests Completed: {profile['quests_completed']}",
        f"Alignment: {profile['alignment']}",
    ]))


@bot.command(name="daily")
async def daily_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    now_ts = now()
    if now_ts - profile.get("last_daily", 0) < DAILY_COOLDOWN_SEC:
        remaining = DAILY_COOLDOWN_SEC - (now_ts - profile.get("last_daily", 0))
        await ctx.send(f"⏳ On cooldown. {remaining // 3600}h {remaining % 3600 // 60}m left")
        return
    reward = random.randint(10, 20)
    profile["gold"] += reward
    profile["last_daily"] = now_ts
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"💰 Daily reward: +{reward} gold. Current: {profile['gold']}")


@bot.command(name="work")
async def work_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    now_ts = now()
    if now_ts - profile.get("last_work", 0) < WORK_COOLDOWN_SEC:
        remaining = WORK_COOLDOWN_SEC - (now_ts - profile.get("last_work", 0))
        await ctx.send(f"⏳ On cooldown. {remaining // 60}m left")
        return
    reward = random.randint(5, 12)
    profile["gold"] += reward
    profile["last_work"] = now_ts
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"🔨 Work complete: +{reward} gold. Current: {profile['gold']}")


@bot.command(name="quest")
async def quest_cmd(ctx: commands.Context, difficulty: str = "medium"):
    difficulty = difficulty.lower()
    if difficulty not in QUEST_DIFFICULTIES:
        await ctx.send("Usage: p!quest [easy|medium|hard]")
        return
    profile = await ensure_player(player_storage, ctx.author)
    conf = QUEST_DIFFICULTIES[difficulty]
    xp_gain = random.randint(*conf["xp"])
    gold_gain = random.randint(*conf["gold"])  # scarce gold
    drop = random.random() < conf["drop_rate"]
    alignment_shift = random.choice([-1, 0, 1])
    profile["xp"] += xp_gain
    profile["gold"] += gold_gain
    profile["quests_completed"] += 1
    profile["alignment"] = max(-100, min(100, profile.get("alignment", 0) + alignment_shift))
    while profile["xp"] >= get_level_exp_requirement(profile["level"]):
        profile["xp"] -= get_level_exp_requirement(profile["level"])
        profile["level"] += 1
    if drop:
        item = random.choice(list(SHOP_ITEMS.keys()))
        profile["inventory"].append(item)
    await player_storage.upsert_player(ctx.author.id, profile)
    lines = [
        f"🗺️ Quest ({difficulty}) complete: +{xp_gain} XP, +{gold_gain} gold",
        f"Level: {profile['level']}  (XP: {profile['xp']}/{get_level_exp_requirement(profile['level'])})",
        f"Alignment change: {alignment_shift:+d} (current: {profile['alignment']})",
    ]
    if drop:
        lines.append(f"🎁 Drop: {item}")
    await ctx.send("\n".join(lines))


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard_cmd(ctx: commands.Context, category: str = "level"):
    category = category.lower()
    if category not in ["level", "gold", "quests"]:
        await ctx.send("Usage: p!leaderboard [level|gold|quests]")
        return
    players = await player_storage.all_players()
    records: List[Dict[str, Any]] = list(players.values())
    if category == "level":
        key_fn = lambda p: (p.get("level", 1), p.get("xp", 0))
    elif category == "gold":
        key_fn = lambda p: p.get("gold", 0)
    else:
        key_fn = lambda p: p.get("quests_completed", 0)
    records.sort(key=key_fn, reverse=True)
    top_n = records[:10]
    lines = [f"📊 Leaderboard - {category}"]
    for idx, rec in enumerate(top_n, 1):
        name = rec.get("name") or f"User {rec.get('user_id')}"
        lines.append(f"{idx}. {name} | lvl {rec.get('level', 1)} | gold {rec.get('gold', 0)} | quests {rec.get('quests_completed', 0)}")
    await ctx.send("\n".join(lines) if len(lines) > 1 else "No data yet")


@bot.command(name="race")
async def race_cmd(ctx: commands.Context, *, race: str = ""):
    race = race.strip().lower()
    if not race:
        await ctx.send("Usage: p!race <race>")
        return
    if race not in ALLOWED_RACES:
        await ctx.send("Invalid race")
        return
    profile = await ensure_player(player_storage, ctx.author)
    if profile.get("gold", 0) < CHANGE_COST:
        await ctx.send(f"Not enough gold ({CHANGE_COST} required)")
        return
    profile["gold"] -= CHANGE_COST
    profile["race"] = race
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"🔁 Race changed to {race}. -{CHANGE_COST} gold")


@bot.command(name="class")
async def class_cmd(ctx: commands.Context, *, clazz: str = ""):
    clazz = clazz.strip().lower()
    if not clazz:
        await ctx.send("Usage: p!class <class>")
        return
    if clazz not in ALLOWED_CLASSES:
        await ctx.send("Invalid class")
        return
    profile = await ensure_player(player_storage, ctx.author)
    if profile.get("gold", 0) < CHANGE_COST:
        await ctx.send(f"Not enough gold ({CHANGE_COST} required)")
        return
    profile["gold"] -= CHANGE_COST
    profile["clazz"] = clazz
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"🔁 Class changed to {clazz}. -{CHANGE_COST} gold")


@bot.command(name="inventory")
async def inventory_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    inv = profile.get("inventory", [])
    if not inv:
        await ctx.send("👜 Inventory is empty")
        return
    counts: Dict[str, int] = {}
    for it in inv:
        counts[it] = counts.get(it, 0) + 1
    lines = ["👜 Inventory:"] + [f"- {name} x{qty}" for name, qty in counts.items()]
    await ctx.send("\n".join(lines))


@bot.command(name="shop")
async def shop_cmd(ctx: commands.Context):
    lines = ["🏪 Shop:"]
    for name, price in SHOP_ITEMS.items():
        lines.append(f"- {name}: {price} gold")
    await ctx.send("\n".join(lines))


@bot.command(name="buy")
async def buy_cmd(ctx: commands.Context, *, item: str = ""):
    item = item.strip()
    if not item:
        await ctx.send("Usage: p!buy <item>")
        return
    matched: Optional[Tuple[str, int]] = None
    for name, price in SHOP_ITEMS.items():
        if name.lower() == item.lower():
            matched = (name, price)
            break
    if not matched:
        await ctx.send("Item not found in shop")
        return
    name, price = matched
    profile = await ensure_player(player_storage, ctx.author)
    if profile.get("gold", 0) < price:
        await ctx.send("Not enough gold")
        return
    profile["gold"] -= price
    profile.setdefault("inventory", []).append(name)
    await player_storage.upsert_player(ctx.author.id, profile)
    await ctx.send(f"✅ Purchased {name} for {price} gold. Current: {profile['gold']}")


@bot.command(name="transfer")
async def transfer_cmd(ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
    if member is None or amount is None or amount <= 0:
        await ctx.send("Usage: p!transfer <@user> <amount>")
        return
    if member.id == ctx.author.id:
        await ctx.send("Cannot transfer to yourself")
        return
    sender = await ensure_player(player_storage, ctx.author)
    if sender.get("gold", 0) < amount:
        await ctx.send("You don't have enough gold")
        return
    receiver = await ensure_player(player_storage, member)
    sender["gold"] -= amount
    receiver["gold"] = receiver.get("gold", 0) + amount
    await player_storage.upsert_player(ctx.author.id, sender)
    await player_storage.upsert_player(member.id, receiver)
    await ctx.send(f"💸 Transfer: {ctx.author.mention} → {member.mention} {amount} gold")


@bot.command(name="alignment")
async def alignment_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    val = profile.get("alignment", 0)
    label = _alignment_label(val)
    await ctx.send(f"⚖️ Alignment: {val} ({label})")


def _alignment_label(value: int) -> str:
    if value >= 60:
        return "Lawful Good"
    if value >= 20:
        return "Neutral Good"
    if value > -20:
        return "True Neutral"
    if value > -60:
        return "Neutral Evil"
    return "Chaotic Evil"


@bot.command(name="duel")
@commands.guild_only()
async def duel_cmd(ctx: commands.Context, target: Optional[discord.Member] = None):
    if target is None:
        await ctx.send("Usage: p!duel <@user>")
        return
    if target.bot or target.id == ctx.author.id:
        await ctx.send("Cannot duel yourself or a bot")
        return
    await intent_storage.enqueue({
        "type": "duel_request",
        "guild_id": ctx.guild.id if ctx.guild else 0,
        "channel_id": ctx.channel.id,
        "challenger_id": ctx.author.id,
        "target_id": target.id,
        "created_at": now(),
    })
    await ctx.send(f"⚔️ <@{ctx.author.id}> challenged <@{target.id}>! Respond within {DUEL_TIMEOUT_SEC}s: p!accept or p!decline")


@bot.command(name="accept")
@commands.guild_only()
async def accept_cmd(ctx: commands.Context):
    latest = await _find_latest_incoming_duel(ctx.author.id, ctx.channel.id)
    if latest is None:
        await ctx.send("No pending duel request for you")
        return
    await intent_storage.enqueue({
        "type": "duel_accept",
        "guild_id": latest["guild_id"],
        "channel_id": latest["channel_id"],
        "challenger_id": latest["challenger_id"],
        "target_id": latest["target_id"],
        "created_at": now(),
    })
    await ctx.send("👌 Accepted. Settling…")


@bot.command(name="decline")
@commands.guild_only()
async def decline_cmd(ctx: commands.Context):
    latest = await _find_latest_incoming_duel(ctx.author.id, ctx.channel.id)
    if latest is None:
        await ctx.send("No pending duel request for you")
        return
    await intent_storage.enqueue({
        "type": "duel_decline",
        "guild_id": latest["guild_id"],
        "channel_id": latest["channel_id"],
        "challenger_id": latest["challenger_id"],
        "target_id": latest["target_id"],
        "created_at": now(),
    })
    await ctx.send("🙅 Declined.")


@bot.command(name="cancel")
@commands.guild_only()
async def cancel_cmd(ctx: commands.Context):
    latest = await _find_latest_outgoing_duel(ctx.author.id, ctx.channel.id)
    if latest is None:
        await ctx.send("No pending duel you initiated in this channel")
        return
    await intent_storage.enqueue({
        "type": "duel_cancel",
        "guild_id": latest["guild_id"],
        "channel_id": latest["channel_id"],
        "challenger_id": latest["challenger_id"],
        "target_id": latest["target_id"],
        "created_at": now(),
    })
    await ctx.send("🛑 Cancel requested. Settling…")


async def _find_latest_incoming_duel(user_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
    intents_list = await intent_storage.list_all()
    candidates = [
        it for it in intents_list
        if it.get("type") == "duel_request" and not it.get("_processed") and it.get("target_id") == user_id and it.get("channel_id") == channel_id
    ]
    candidates.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return candidates[0] if candidates else None


async def _find_latest_outgoing_duel(user_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
    intents_list = await intent_storage.list_all()
    candidates = [
        it for it in intents_list
        if it.get("type") == "duel_request" and not it.get("_processed") and it.get("challenger_id") == user_id and it.get("channel_id") == channel_id
    ]
    candidates.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return candidates[0] if candidates else None


RUMBLE_JOIN_EMOJI = "⚔️"

@bot.command(name="rumble")
@commands.guild_only()
async def rumble_cmd(ctx: commands.Context, seconds: int = 20):
    seconds = max(10, min(120, seconds))
    msg = await ctx.send(f"🏟️ Rumble started! React {RUMBLE_JOIN_EMOJI} or type p!join to participate ({seconds}s)")
    try:
        await msg.add_reaction(RUMBLE_JOIN_EMOJI)
    except discord.Forbidden:
        pass

    participants: Dict[int, discord.Member] = {}

    def ensure_member(user: discord.User) -> Optional[discord.Member]:
        if isinstance(user, discord.Member):
            return user
        if ctx.guild is None:
            return None
        return ctx.guild.get_member(user.id)

    @bot.command(name="join")
    async def join_cmd(inner_ctx: commands.Context):
        if inner_ctx.message.reference and inner_ctx.message.reference.message_id == msg.id:
            member = ensure_member(inner_ctx.author)
            if member:
                participants[member.id] = member
                await inner_ctx.message.add_reaction("✅")
        elif inner_ctx.channel.id == ctx.channel.id:
            member = ensure_member(inner_ctx.author)
            if member:
                participants[member.id] = member
                await inner_ctx.message.add_reaction("✅")

    def reaction_check(reaction: discord.Reaction, user: discord.User):
        return reaction.message.id == msg.id and str(reaction.emoji) == RUMBLE_JOIN_EMOJI and not user.bot

    end_at = time.time() + seconds
    while time.time() < end_at:
        timeout = max(0.0, end_at - time.time())
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=timeout, check=reaction_check)
            member = ensure_member(user)
            if member:
                participants[member.id] = member
        except asyncio.TimeoutError:
            break

    if not participants:
        await ctx.send("🙃 No participants. Canceled.")
        return

    winner = random.choice(list(participants.values()))
    reward = random.randint(15, 30)
    profile = await ensure_player(player_storage, winner)
    profile["gold"] += reward
    await player_storage.upsert_player(winner.id, profile)

    await ctx.send(f"🎉 Rumble finished! Winner: {winner.mention} +{reward} gold | Participants: {len(participants)}")


# ---------- Dungeon commands ----------
@bot.command(name="dungeon")
@commands.guild_only()
async def dungeon_cmd(ctx: commands.Context, action: Optional[str] = None):
    if action is None:
        await ctx.send("Usage: p!dungeon create|join|start|leave|status|map|help|next|reset|timer <minutes>")
        return
    action = action.lower()
    if action == "create":
        await intent_storage.enqueue({"type": "dg_create", "channel_id": ctx.channel.id, "created_at": now()})
        await ctx.send("🛠️ Create intent submitted")
    elif action == "join":
        await intent_storage.enqueue({"type": "dg_join", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
        await ctx.send("➕ Join intent submitted")
    elif action == "leave":
        await intent_storage.enqueue({"type": "dg_leave", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
        await ctx.send("🚪 Leave intent submitted")
    elif action == "start":
        await intent_storage.enqueue({"type": "dg_start", "channel_id": ctx.channel.id, "created_at": now()})
        await ctx.send("▶️ Start intent submitted")
    elif action == "status":
        dg = await dungeon_storage.get(ctx.channel.id)
        if dg is None:
            await ctx.send("❌ No dungeon yet. p!dungeon create")
            return
        # show each player's HP/dead
        players_info = []
        for uid, p in dg["players"].items():
            players_info.append(f"<@{uid}> HP {p.get('hp',PLAYER_BASE_HP)}{' DEAD' if p.get('dead') else ''}")
        await ctx.send(f"Status: {dg['state']} | Floor {dg.get('floor',1)} | Players: {len(dg['players'])} | Enemies: {len(dg['enemies'])}\n" + " | ".join(players_info))
    elif action == "map":
        dg = await dungeon_storage.get(ctx.channel.id)
        if dg is None:
            await ctx.send("❌ No dungeon yet. p!dungeon create")
            return
        if dg["state"] != "running":
            await ctx.send("❗ Not started. p!dungeon start")
            return
        await ctx.send(f"```\n{_render_map(dg)}\n```")
    elif action == "next":
        dg = await dungeon_storage.get(ctx.channel.id)
        if dg is None:
            await ctx.send("❌ No dungeon yet. p!dungeon create")
            return
        if dg.get("state") != "running" or dg.get("enemies"):
            await ctx.send("❗ You can only go next when the floor is cleared.")
            return
        # increase floor, respawn enemies stronger, rebuild obstacles
        dg["floor"] = dg.get("floor", 1) + 1
        dg["enemies"] = []
        dg["obstacles"] = []
        # generate obstacles
        total_inner = (dg["width"] - 2) * (dg["height"] - 2)
        num_obs = max(0, int(total_inner * OBSTACLE_DENSITY))
        while len(dg["obstacles"]) < num_obs:
            x, y = _rand_empty_cell(dg)
            dg["obstacles"].append({"x": x, "y": y})
        enemy_count = max(1, len(dg["players"]) + dg["floor"] // 1)
        for i in range(enemy_count):
            x, y = _rand_empty_cell(dg)
            dg["enemies"].append({"x": x, "y": y, "hp": ENEMY_BASE_HP + dg["floor"] - 1, "boss": False})
        if dg["floor"] % 3 == 0:
            x, y = _rand_empty_cell(dg)
            dg["enemies"].append({"x": x, "y": y, "hp": BOSS_HP + dg["floor"], "boss": True})
        await dungeon_storage.upsert(ctx.channel.id, dg)
        await ctx.send(f"⬇️ Descended to Floor {dg['floor']}! Enemies strengthened.")
    elif action == "help":
        rules = (
            "📘 Dungeon Help (Roguelike, intent-centric)\n\n"
            "How to play:\n"
            "- Create & join: p!dungeon create → p!dungeon join (multiple players)\n"
            "- Start: p!dungeon start (spawns enemies, begins ticks)\n"
            "- Move: p!move up/down/left/right (w/a/s/d). Walls are the outer border.\n"
            "- Attack: p!attack (melee). Only hits when an enemy is in an adjacent tile.\n"
            "- Use item: p!use <item> (Potion heals +5; Bomb damages adjacent enemies).\n"
            "- Revive: p!revive (costs 5 gold).\n"
            "- Map: p!dungeon map (ASCII). No auto-broadcast; check on demand.\n"
            "- Status: p!dungeon status | Next floor: p!dungeon next | Leave: p!dungeon leave\n"
            "- Admin: p!dungeon reset (force clear current channel instance)\n\n"
            "Rewards:\n"
            "- Defeating an enemy: +5 XP, +3 gold; chance to drop Potion/Bomb.\n\n"
            "End conditions:\n"
            "- Victory when all enemies are defeated (instance closes).\n"
            "- Cleanup when no players remain.\n"
            "Timer:\n"
            "- p!dungeon timer <minutes> — auto close after N minutes.\n"
        )
        await ctx.send(rules)
    elif action == "reset":
        await dungeon_storage.remove(ctx.channel.id)
        await ctx.send("🧹 Dungeon reset for this channel. You can now p!dungeon create → join → start.")
    elif action.startswith("timer"):
        parts = action.split()
        minutes = None
        if len(parts) == 2 and parts[1].isdigit():
            minutes = int(parts[1])
        # if user typed "timer" as separate token, parse from message content tail
        if minutes is None:
            await ctx.send("Usage: p!dungeon timer <minutes>")
            return
        dg = await dungeon_storage.get(ctx.channel.id)
        if dg is None:
            await ctx.send("❌ No dungeon yet. p!dungeon create")
            return
        end_at = int(time.time() * 1000) + minutes * 60 * 1000
        dg["end_at"] = end_at
        await dungeon_storage.upsert(ctx.channel.id, dg)
        await ctx.send(f"⏱️ Timer set: this instance will end in {minutes} minutes.")
    else:
        await ctx.send("Usage: p!dungeon create|join|start|leave|status|map|help|next|reset|timer <minutes>")


# ---------- Use & Revive commands ----------
@bot.command(name="use")
@commands.guild_only()
async def use_cmd(ctx: commands.Context, *, item: Optional[str] = None):
    if not item:
        await ctx.send("Usage: p!use <item> (Potion|Bomb)")
        return
    await intent_storage.enqueue({
        "type": "dg_use",
        "channel_id": ctx.channel.id,
        "user_id": ctx.author.id,
        "item": item,
        "created_at": now(),
    })
    await ctx.send("🧰 Use intent submitted")


@bot.command(name="revive")
@commands.guild_only()
async def revive_cmd(ctx: commands.Context):
    await intent_storage.enqueue({
        "type": "dg_revive",
        "channel_id": ctx.channel.id,
        "user_id": ctx.author.id,
        "created_at": now(),
    })
    await ctx.send("❤️ Revive intent submitted (costs 5 gold)")


# ---------- Region commands ----------
@bot.command(name="region")
@commands.guild_only()
async def region_cmd(ctx: commands.Context, *, args: Optional[str] = None):
    if not args:
        await ctx.send("Usage: p!region adventure <start|continue|status|claim|abandon> [region] | explore <help|plunder>")
        return
    parts = args.strip().split()
    if parts[0].lower() == "adventure":
        if len(parts) < 2:
            await ctx.send("Usage: p!region adventure <start|continue|status|claim|abandon> [region]")
            return
        sub = parts[1].lower()
        if sub == "start":
            region = parts[2].lower() if len(parts) > 2 else None
            await intent_storage.enqueue({"type": "region_start", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "region": region, "created_at": now()})
            await ctx.send("🧭 Adventure start intent submitted")
        elif sub == "continue":
            await intent_storage.enqueue({"type": "region_continue", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
            await ctx.send("➡️ Continue intent submitted")
        elif sub == "status":
            profile = await ensure_player(player_storage, ctx.author)
            adv = profile.get("region_adv") or {"active": False}
            await ctx.send(f"Adventure status: {adv}")
        elif sub == "claim":
            await intent_storage.enqueue({"type": "region_claim", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
            await ctx.send("💰 Claim intent submitted")
        elif sub == "abandon":
            await intent_storage.enqueue({"type": "region_abandon", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
            await ctx.send("🛑 Abandon intent submitted")
        else:
            await ctx.send("Usage: p!region adventure <start|continue|status|claim|abandon> [region]")
    elif parts[0].lower() == "explore":
        choice = parts[1].lower() if len(parts) > 1 else "help"
        await intent_storage.enqueue({"type": "region_explore", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "choice": choice, "created_at": now()})
        await ctx.send("🌄 Explore intent submitted")
    else:
        await ctx.send("Usage: p!region adventure <start|continue|status|claim|abandon> [region] | explore <help|plunder>")


# ---------- Pet commands ----------
@bot.command(name="pet")
async def pet_cmd(ctx: commands.Context):
    profile = await ensure_player(player_storage, ctx.author)
    pet = profile.get("pet")
    if not pet:
        await ctx.send("You have no pet. Adopt one with p!petadopt <species> (wolf|cat|hawk|golem)")
    else:
        await ctx.send(f"🐾 Pet: {pet.get('name')} the {pet.get('species')} | Lv {pet.get('level',1)} XP {pet.get('xp',0)}/20 Hunger {pet.get('hunger',0)}")


@bot.command(name="petadopt")
async def petadopt_cmd(ctx: commands.Context, species: Optional[str] = None):
    if not species:
        await ctx.send("Usage: p!petadopt <species> (wolf|cat|hawk|golem)")
        return
    await intent_storage.enqueue({"type": "pet_adopt", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "species": species.lower(), "created_at": now()})
    await ctx.send("🐾 Adopt intent submitted")


@bot.command(name="petname")
async def petname_cmd(ctx: commands.Context, *, name: Optional[str] = None):
    if not name:
        await ctx.send("Usage: p!petname <name>")
        return
    await intent_storage.enqueue({"type": "pet_rename", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "name": name, "created_at": now()})
    await ctx.send("✏️ Rename intent submitted")


@bot.command(name="petfeed")
async def petfeed_cmd(ctx: commands.Context):
    await intent_storage.enqueue({"type": "pet_feed", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
    await ctx.send("🍖 Feed intent submitted")


@bot.command(name="pettrain")
async def pettrain_cmd(ctx: commands.Context):
    await intent_storage.enqueue({"type": "pet_train", "channel_id": ctx.channel.id, "user_id": ctx.author.id, "created_at": now()})
    await ctx.send("🏋️ Train intent submitted")


# ----------------------- Run -----------------------

def main():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        print("❌ DISCORD_TOKEN not found. Create .env with DISCORD_TOKEN=<YourBotToken>")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
