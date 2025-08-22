# Anoma Intents Adventures (Discord Bot)

一个基于 Discord 文本消息交互的最小可运行版本，包含基础命令：help、create、profile、daily、work、quest、leaderboard、rumble。

## 快速开始

1) 安装 Python 3.10+
2) 安装依赖：
```bash
pip install -r requirements.txt
```
3) 复制 `.env.example` 为 `.env`，并填入你的 Discord 机器人 Token：
```
DISCORD_TOKEN=xxxxxxxxxxxxxxxxxxxx
```
4) 在 Discord 开发者后台为该 Bot 开启 Message Content Intent
5) 运行机器人：
```bash
python anoma_intents_bot.py
```

## 使用前缀
- 使用 `p!` 或 `P!` 作为命令前缀，例如：`p!help`

## 基础命令
- p!help：查看帮助
- p!create <race> <class>：创建角色
- p!profile：查看角色
- p!daily：领取每日金币（冷却）
- p!work：工作赚金币（冷却）
- p!quest [easy|medium|hard]：进行任务，获得 XP/金币/可能的掉落
- p!leaderboard [level|gold|quests]：排行榜
- p!rumble：发起多人“乱斗”，成员反应或输入 `p!join` 参与

## 数据存储
- 默认使用 `data/players.json` 作为轻量级存储（可后续切换 SQLite）

## 说明
- 该版本旨在尽快跑通最小闭环，便于参赛演示；可按需求继续覆盖 intents-games 全量功能。
