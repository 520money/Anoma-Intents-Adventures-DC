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
- Dungeon (co‑op): `p!dungeon create|join|start|leave|status|map`, `p!move <up|down|left|right|w|a|s|d>`, `p!attack`

## Dungeon Notes
- Attack is melee adjacency: move next to an enemy (up/down/left/right) before `p!attack`
- Map is on‑demand via `p!dungeon map` (no auto‑broadcast)

## Storage
- Lightweight JSON: `data/players.json`, `data/intents.json`, `data/dungeons.json`

## Links
- Repository (submission): https://github.com/520money/Anoma-Intents-Adventures-DC
- Bot invite: https://discord.com/oauth2/authorize?client_id=1408016619862491217&permissions=67584&integration_type=0&scope=bot

## Security
- Never commit your real Discord bot token. Keep it only in your local `.env`.
