# 1‑Minute Demo Script (Voiceover + Actions)

Goal: Show intent‑centric multiplayer, PvP, and the roguelike dungeon in ~60s.

00:00 – Intro (voice)
- “This is Anoma Intents Adventures, a Discord‑native, intent‑centric roguelike. All actions are intents queued and settled by a solver.”
- Action: `p!help`

00:10 – Create & progress (voice)
- “Create a character and show basic progression.”
- Actions:
  - `p!create human warrior`
  - `p!daily`
  - `p!quest medium`
  - `p!shop` → `p!buy Potion` → `p!inventory`

00:25 – PvP demo (voice)
- “Intents settle duels deterministically.”
- Actions:
  - `p!duel @user` (partner runs `p!accept`)
  - (Optional) `p!leaderboard`

00:35 – Dungeon start (voice)
- “Co‑op roguelike: grid movement, adjacency melee, items, floors & bosses.”
- Actions:
  - `p!dungeon create` → `p!dungeon join` (partner joins) → `p!dungeon start`
  - `p!dungeon status`

00:42 – Move / Attack / Map (voice)
- “Intents for move and attack; map is on‑demand.”
- Actions:
  - `p!move up`
  - `p!attack`
  - `p!dungeon map`

00:48 – Items / Revive / Next floor (voice)
- “Use items, revive, and descend after clearing.”
- Actions:
  - `p!use Bomb` or `p!use Potion`
  - (If downed) `p!revive`
  - After enemies cleared: `p!dungeon next`

00:56 – Close (voice)
- “Everything you saw is intent‑centric. The architecture cleanly separates intent submission from settlement and is chain‑ready for Anoma/Namada.”

Notes for recording
- Keep the Discord channel visible; use 125% UI zoom if needed.
- If duel or dungeon needs a partner, have a second account ready.
- If output is too verbose, focus on `p!help`, 1‑2 PvP lines, and core dungeon loop.
- Recommended resolution: 1920×1080 @ 60 FPS. Keep cuts short; avoid dead time.

