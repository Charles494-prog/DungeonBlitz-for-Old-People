# Mod features: port checklist

Every change from the old Python server (`Dungeon-Blitz-preservation-Project-main`), and
where it lives in this project. Status: **done**, **theirs** (this server already does it),
or **n/a** (with the reason).

Settings: `src/server/core/ModConfig.ts`. Client patches: `tools/mod_client/` (run
`python patch_client_timers.py` there after changing a client setting in its
`game_config.py`; it patches `src/client/content/localhost/p/cbp/DungeonBlitz.swf`,
`cbq/Game*.swz` and `cbp/Login.swz`, keeping "- Original timers" copies).

## Launcher and home page
| Feature | Status | Where |
|---|---|---|
| `Play Dungeon Blitz.bat`: installs Node / packages / Flash Browser, starts the server, opens the home page | done | `Play Dungeon Blitz.bat`, `launcher.swf.html` |
| Home page with charts (original vs mod) and Play button | done | `core/HomePage.ts` (`/home`) |

## Loot and rewards (`core/ModLoot.ts`)
| Feature | Status |
|---|---|
| Gear drop chance per rank (Minions too), Dread x2 | done |
| Gear rarity: Rare / Legendary rates, Legendary only in Dread | done |
| Owned gear never drops again (reroll to a missing item) | theirs (`GameData.getGearIdForEntity`) |
| Collection bonus | done |
| Gear Find raises drop chance and rarity; `!gearfind` | done |
| Dread bosses roll gear twice | done |
| Materials on every dungeon kill; Legendary material 4% base in normal dungeons, 15% in Dread (bosses x2, Dread x1.5) | done |
| Dyes from every rank, always unowned, rarity reroll | done |
| Mammoth Idols from every boss by level; mini-bosses sometimes | done |
| Treasure Troves and Dragon Keys from dungeon monsters (keys show live) | done |
| Monster XP x12.5, quest XP x25 / gold x5 | done |
| Health orb from every kill (25% HP) | done |
| Silver Sigils on gold pickups (15%) | done |
| Out-of-combat regeneration after 3 s, 10% a second | done (`CombatHandler` constants) |
| Paragon levels after 50: +2% loot and gold, +2% healing, +2% gear stats per level | done (stats: client patch) |
| Paragon damage reduction | n/a: the game computes damage taken in this setup |

## Time
| Feature | Status |
|---|---|
| Building upgrades at most 2 h; skills at most 1 h (client and server agree) | done |
| Talent research, pet training, forge | theirs (already instant or shortened by their client patches) |
| Eggs at most 1 h | done (client) |
| Dread revive wait 8 s (same as normal) | done (client) |

## Shops and economy
| Feature | Status |
|---|---|
| Mount Merchant window: the Wolf's End stable girl and the keep's Stablemaster sell every mount | done (`core/ModCommands.ts` + client) |
| Chat menu shop rows: `!mounts`, `!buymount`, `!buygold`, `!buysigils`, `!widescreen` | done |
| Buying Mammoth Idols in game, no browser tab (`/buyidols`) | done |
| Troves never give an owned mount / dye / gear | theirs |
| Troves never land on an owned pet (it's out of the draw) | done (`LockboxHandler.buildRewardPool`) |
| Troves never land on an owned mount | theirs |
| New characters start without a mount (was the Buckskin Horse) | done (`data/*_template.json`) |

## Gear and mounts (client)
| Feature | Status |
|---|---|
| Gear stats in fixed ranges by rarity at every level: Magic 60-250, Rare 250-650, Legendary 651-2000 (item level picks the place in the range); Legendaries get every stat | done (`tools/mod_client/game_config.py` GEAR_STAT_RANGES) |
| Legendary mounts ride at +70% (every mount's Mounted buff is +40%) | done (client patch `mountSpeed`) |
| Mounts keep speed while attacking | done |
| Gear on the ground outlined by rarity: Magic green, Rare blue, Legendary gold, thicker than the game's faint glow | done (`LOOT_GLOW_BLUR` / `LOOT_GLOW_STRENGTH`) |
| Gear list sorted Legendary, Rare, Magic | done |
| Event news banner hidden | done |
| Optional 16:9 view (`!widescreen`) | done (the choice isn't re-sent at login yet) |

## Story and dungeons
| Feature | Status |
|---|---|
| Story dungeons open only with their quest | theirs (`LevelHandler.isDungeonEntryUnlocked`) |
| Story areas and the Dreadfold open in story order | theirs |
| Goblin Kidnappers cave | theirs: it works here, so it is no longer skipped |
| Boss scenes, reinforcements, Capstone, Mimic, chest ambushes, room scenes | theirs: the game runs them (master client) |
| Aggro delay 2 s / de-aggro 4 s | n/a for now: monsters run in the game (needs a client patch) |
| Vigils fire straight on a timer | theirs: original game behavior |
| A 100% clear gives full stars on the map; the map keeps your best stars | done (`MissionHandler`, `FULL_STARS_COMPLETION_PERCENT`) |

## Test characters
| Feature | Status |
|---|---|
| Maxed RedKnight (level 50, gold, idols, all quests, all Legendary gear, skills, talents, pets, gems) | done by hand |
