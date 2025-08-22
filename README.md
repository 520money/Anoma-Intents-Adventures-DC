# Anoma Intents Adventures (Discord Bot)

A fully multiplayer, top‑down roguelike RPG designed around Anoma’s intent‑centric philosophy. Players submit intents (commands) and an authoritative solver resolves conflicts and deterministically settles state.

## Overview
- Modes: Free‑for‑all Rumble, 1v1 Duels, and a cooperative Roguelike Dungeon (grid movement, adjacency melee, roaming enemies, victory on enemy clear, on‑demand ASCII map)
- Intents Games features: character creation and respec, daily/work/quests (level^3*25), inventory/shop/buy, transfer, alignment, leaderboards
- Intent‑centric: commands → intent queue → solver loop → settlement

## Quickstart
```bash
# Python 3.10+
pip install -r requirements.txt

# copy env template and set your bot token locally (do NOT commit the real token)
copy .env.example .env  # Windows CMD
# or: Copy-Item .env.example .env  # PowerShell
# then edit .env and set:
# DISCORD_TOKEN=YOUR_BOT_TOKEN

# enable “Message Content Intent” in Developer Portal -> Bot
python anoma_intents_bot.py
```

## Prefix
- Use `p!` or `P!`, e.g. `p!help`

## Core Commands
- Help: `p!help`
- Create/Profile: `p!create <race> <class>`, `p!profile`
- Respec: `p!race <race>`, `p!class <class>` (2500 gold each)
- Economy: `p!daily`, `p!work`, `p!quest [easy|medium|hard]`
- Inventory/Shop: `p!inventory`, `p!shop`, `p!buy <item>`, `p!transfer <@user> <amount>`
- Alignment/Leaderboard: `p!alignment`, `p!leaderboard [level|gold|quests]`
- PvP/Multiplayer: `p!duel / p!accept / p!decline / p!cancel`, `p!rumble`
- Dungeon (co‑op): `p!dungeon create|join|start|leave|status|map|help|next`, `p!move <up|down|left|right|w|a|s|d>`, `p!attack`, `p!use <item>`, `p!revive`

## Dungeon Gameplay (quick guide)
- Start a run: `p!dungeon create` → `p!dungeon join` (multiple players) → `p!dungeon start`
- Move/Attack: `p!move up/down/left/right` (or `w/a/s/d`) → `p!attack` (melee, must be adjacent)
- Items: `p!use Potion` (+5 HP), `p!use Bomb` (damage adjacent enemies)
- Status/Map: `p!dungeon status` (HP, floor, enemy count), `p!dungeon map` (ASCII map, on‑demand)
- Revive: `p!revive` (costs 5 gold)
- Next floor: clear all enemies then `p!dungeon next` (boss every 3 floors)

Legend (ASCII map):
- `P` = player, `✖` = downed player, `E` = enemy, `B` = boss, `X` = obstacle, `#` = wall, `.` = ground

## Storage
- Lightweight JSON: `data/players.json`, `data/intents.json`, `data/dungeons.json`

## Reviewer flow
1) `p!help` and `p!dungeon help`
2) `p!create human warrior` → `p!daily` → `p!quest medium` → `p!shop` / `p!buy Potion`
3) `p!duel @user` → `p!accept`
4) `p!dungeon create` → `join` → `start` → `move/attack` → `use potion/bomb` → `next` → `revive` → `map/status`

## Links
- Repository (submission): https://github.com/520money/Anoma-Intents-Adventures-DC
- Bot invite: https://discord.com/oauth2/authorize?client_id=1408016619862491217&permissions=67584&integration_type=0&scope=bot

## Security
- Never commit your real Discord bot token. Keep it only in your local `.env`.
