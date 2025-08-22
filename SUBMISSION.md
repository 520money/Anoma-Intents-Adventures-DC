# Anoma Intents Adventures — Submission Package

## Links
- Repository: https://github.com/520money/Anoma-Intents-Adventures
- Bot Invite (recommended permissions):
  - https://discord.com/api/oauth2/authorize?client_id=1408016619862491217&permissions=117824&scope=bot
- Optional Test Server Invite (read-only channel for reviewers): <YOUR_TEST_SERVER_INVITE>
- Demo Video: <YOUR_DEMO_VIDEO_URL>
- Screenshots: <SCREENSHOT_1_URL>, <SCREENSHOT_2_URL>, <SCREENSHOT_3_URL>

Replace `YOUR_APPLICATION_ID` with your app’s Application ID (Developer Portal → General Information). If you already have an invite link, paste it directly.

---

## Summary
Anoma Intents Adventures is a fully multiplayer, top-down roguelike RPG built entirely around an intent-centric architecture. Players submit intents (move, attack, duel, trade, join dungeon) via Discord commands; a background solver resolves conflicts and deterministically settles world state. The design cleanly separates intent submission from settlement and is ready to integrate with Anoma/Namada for wallet-signed intents, solver sponsorship, on-chain settlement, and privacy extensions.

---

## Feature Compliance (per challenge brief)
- Name: “Anoma Intents Adventures”
- Fully Multiplayer:
  - Free-for-all rumble (join via reaction or command)
  - 1v1 duels (intent-acknowledge-accept/decline/cancel flow)
  - Cooperative roguelike dungeon (multiple players per channel instance)
- Top-down Roguelike RPG:
  - Tick-based grid, melee adjacency attacks
  - Roaming enemies, victory when enemies are cleared
  - On-demand ASCII map (no auto-spam)
- Intents Games Features included:
  - Character creation & full customization references: `p!create <race> <class>`, respec via `p!race` / `p!class` (2500 gold each)
  - Economy & progression: `p!daily`, `p!work`, `p!quest [easy|medium|hard]` (level^3*25 curve, ~60% drop rate), `p!inventory`, `p!shop`, `p!buy`, `p!transfer`, `p!alignment`
  - Leaderboards: `p!leaderboard [level|gold|quests]`

---

## Gameplay (high-level)
- Profile & customization: `p!create`, `p!profile`, `p!race`, `p!class`, `p!inventory`
- Progression & economy: `p!daily`, `p!work`, `p!quest [easy|medium|hard]`, `p!shop`, `p!buy`, `p!transfer`, `p!alignment`, `p!leaderboard`
- Multiplayer PvP: `p!duel`, `p!accept`, `p!decline`, `p!cancel`, `p!rumble`
- Roguelike Dungeon:
  - `p!dungeon create|join|start|leave|status|map`
  - `p!move <up|down|left|right|w|a|s|d>`
  - `p!attack` (melee; only hits if an enemy is in an adjacent tile)

Dungeon help: `p!dungeon help` (rules, rewards, victory, cleanup conditions).

---

## Intent-Centric Architecture (Why it aligns with Anoma)
- Commands are intents → stored in an `IntentStorage` queue
- `solver_loop()` processes intents and performs deterministic settlement:
  - Duel matching/settlement (accept/decline/cancel/timeout)
  - Dungeon tick (batch movement/attacks, collision rules, AI, rewards)
- Conflicts handled via ordered processing and `_processed` flags (replayable/auditable)
- Clean path to on-chain integration:
  - Wallet-signed intents, solver sponsorship, on-chain settlement of results
  - Privacy extensions via Namada/Anoma for sensitive state

---

## How to Run Locally
1) Python 3.10+
2) Install dependencies:
```
pip install -r requirements.txt
```
3) Copy env and set the token:
```
copy .env.example .env  # Windows CMD
# or: Copy-Item .env.example .env  # PowerShell
```
Open `.env` and set:
```
DISCORD_TOKEN=YOUR_BOT_TOKEN
```
4) Enable “Message Content Intent” in Developer Portal → Bot
5) Run:
```
python anoma_intents_bot.py
```

---

## Invite the Bot to a Server
- Developer Portal → OAuth2 → URL Generator:
  - Scopes: `bot`
  - Permissions: View Channels, Send Messages, Read Message History, Add Reactions (optionally Embed Links, Attach Files)
- Or use the invite URL above.

---

## Demo Flow (for reviewers)
- `p!help` and `p!dungeon help` to view features and rules
- Create & customize: `p!create human warrior`, `p!profile`
- Economy: `p!daily`, `p!work`, `p!quest medium`, `p!shop`, `p!buy Potion`, `p!inventory`
- PvP: `p!duel @user`, then `p!accept` or `p!decline`, `p!cancel`
- Multiplayer: `p!rumble`
- Dungeon: `p!dungeon create` → `p!dungeon join` (multiple users) → `p!dungeon start` → `p!move` / `p!attack` → `p!dungeon map`

---

## Evaluation Notes
- Deterministic, intent-driven solver ensures fairness and reproducibility
- Modular: new modes = new intent types + solver rules
- Extensible items/content: structure supports scaling to 750+ items across 9 categories
- Chain-ready: separation of concerns (intent vs. settlement) eases Anoma/Namada integration

---

## Contact
- Author: <YOUR_NAME or DISCORD_HANDLE>
- Timezone / Availability: <OPTIONAL>
