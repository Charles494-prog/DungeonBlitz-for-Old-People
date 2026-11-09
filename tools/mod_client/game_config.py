import math

"""
Local single-player tuning. Edit these values and restart server.py.

TIME_MULTIPLIER  : how long timed operations take compared to the original game
                   (skill training, building upgrades, talent research, forge,
                   pet training, egg hatching). Scaled building timers cap at
                   2 hours; other timers range from 30 minutes to 1 hour.
XP_MULTIPLIER    : experience gained from killing monsters. 1.0 = original.
GOLD_MULTIPLIER  : gold dropped by monsters. 1.0 = original.
FRESH_START      : new characters start at level 1 with starter gear only,
                   instead of the developer template (level 20, everything unlocked).
FRESH_START_GOLD : gold a fresh character starts with.
FRESH_START_IDOLS: mammoth idols a fresh character starts with.
SKIP_BOAT        : skip the "Lost at Sea" boat. New characters start in NewbieRoad
                   with the boat mission (DefendTheShip) already done, so Captain Fink
                   offers the next story quest. Characters still on the boat are moved
                   ashore when selected. False plays the scripted boat (boat_script.py).
SKIP_GOBLIN_CAVE : skip the Goblin Kidnappers cave (TutorialDungeon): accepting the
                   Mayor's quest tells the rescue in chat and Anna's follow-up is ready to
                   hand in (see quests.SKIPPED_DUNGEON_STORY). False plays the cave: its
                   gates open as rooms are cleared (room_gates.py) and the Goblin Boss
                   scene plays (boss_cutscenes.py).

ENEMY_AI_ENABLED        : enemies chase and attack players (see ai_logic.py).
ENEMY_AGGRO_RANGE       : enemies notice a player this close (pixels, horizontal).
ENEMY_AGGRO_HEIGHT      : ...and at most this far above/below them.
ENEMY_LEASH_RANGE       : enemies give up and walk home once this far from their spawn.
ENEMY_DAMAGE_MULTIPLIER : damage enemies deal to players. 1.0 = original formula.
OUT_OF_COMBAT_REGEN_DELAY : seconds without dealing or taking damage before healing starts.
OUT_OF_COMBAT_REGEN_RATE  : fraction of maximum HP restored per second after the delay.
HEALTH_ORB_DROP_CHANCE    : chance an enemy drops a health orb.
HEALTH_ORB_HEAL_FRACTION  : fraction of maximum HP restored by a health orb.
SIGIL_DROP_CHANCE         : chance a gold pickup also grants Silver/Royal Sigils.
MAMMOTH_*_DROP_CHANCE     : Mammoth Idol drop chance for strong enemies.

Loot follows the original client's rules (Entity.txt reward code): only monsters with a
Kingdom, Realm and GroupLevel and an item-giving RewardClass drop gear or materials.
GEAR_DROP_CHANCE_BY_RANK: gear chance per kill by EntRank (EntType.const_247 in the
                          client); a monster's own ItemDropChance is used if higher.
GEAR_DROP_MULTIPLIER    : multiplies every gear chance. 1.0 = original.
OVERWORLD_LOOT_MULTIPLIER : gear and material chance outside dungeons. 0.25 = original.
MATERIAL_DROP_CHANCE    : crafting material chance per kill in dungeons. 1.0 = original
                          (every kill). Materials match the monster's Kingdom and Realm.
MATERIAL_RARE_CHANCE / MATERIAL_LEGENDARY_CHANCE : rarity of a material drop (the
                          original server's rates are lost; these are our own).
GEAR_RARE_CHANCE       : chance a gear drop is Rare (tier 1).
GEAR_LEGENDARY_CHANCE   : chance a gear drop is Legendary (tier 2). The rest are Magic.
BOSS_RARITY_MULTIPLIER  : bosses multiply the Rare/Legendary material chances by this.
BOSS_GEAR_RARITY_MULTIPLIER : ... and the Rare/Legendary gear chances (normal maps).
GEAR_LEVEL_RANGE        : drops are gear up to this many levels below the map level.
LEGENDARY_ONLY_IN_DREAD : Legendary gear only drops in Dread maps (the "...Hard" levels);
                          on normal maps a Legendary roll becomes Rare instead.
DREAD_GEAR_DROP_MULTIPLIER : Dread monsters drop gear (and materials) this many times more often.
DREAD_RARE_CHANCE / DREAD_LEGENDARY_CHANCE : Dread rarity per gear drop for monsters.
DREAD_BOSS_RARE_CHANCE / DREAD_BOSS_LEGENDARY_CHANCE : the same for Dread bosses.
DREAD_MINIBOSS_RARE_CHANCE / DREAD_MINIBOSS_LEGENDARY_CHANCE : ... and Dread minibosses.
DREAD_BOSS_GEAR_DROPS      : number of gear items a Dread boss/miniboss drops.

DREAD_UNLOCK_MISSIONS : Dread maps stay locked until every one of these missions is
                        turned in. Default: the end of the normal story (Castle finale
                        IntoTheDepths, then Valhaven's Intervention, TheWestWing,
                        TheEastWing and TacticalStrike). Use [] to unlock Dread at once.
"""

TIME_MULTIPLIER   = 0.05
XP_MULTIPLIER     = 12.5
QUEST_XP_MULTIPLIER   = 2.0   # quests: this on top of XP_MULTIPLIER
QUEST_GOLD_MULTIPLIER = 5.0   # quests: this on top of GOLD_MULTIPLIER
GOLD_MULTIPLIER  = 1.0
FRESH_START      = True
FRESH_START_GOLD  = 500
FRESH_START_IDOLS = 0
SKIP_BOAT        = False
SKIP_GOBLIN_CAVE = True
# Mammoth Idols never run out: the balance is refilled to this amount on entering
# the world and after every idol purchase. False keeps idols as normal currency
# (the "Buy" buttons in the Purchase Mammoth Idols window add them for free).
UNLIMITED_IDOLS  = False
# Test characters: when selected they are raised to level 50 and topped up to at
# least MAXED_GOLD gold and MAXED_IDOLS Mammoth Idols. Names are case-insensitive.
# Trade Mammoth Idols for gold by typing "!buygold <idols>" in chat (chat_commands.py)
GOLD_PER_IDOL    = 1_000
# "!buysigils <idols>" in chat: Royal Sigils for the gem merchant's Royal Sigil Store.
# The store also pays a shortfall in idols at this rate when you buy something.
SIGILS_PER_IDOL  = 10
# Talking to these NPCs (their character name, as the server log's "TalkToNPC ...
# entType=" shows it) opens the Mount Merchant window (mount_merchant.py): six mounts
# a day for gold, idols or Royal Sigils. Without the patched client (FFDec missing)
# the stable is listed in chat instead.
MOUNT_SHOP_NPCS  = ["NR_IntroVillager"]
# Client patches (applied by running "python tools/patch_client_timers.py", then
# reload the game page):
#   WIDESCREEN : a 16:9 view (1366x768) instead of the original 3:2 (1152x768), so a
#                widescreen window has no black bars. The HUD keeps its original
#                layout; set False and re-run the patcher to go back.
#   FFDEC_JAR  : JPEXS FFDec, used to compile the Mount Merchant window into the client.
#   DREAD_REVIVE_SECONDS : how long you lie dead in a Dread map before reviving
#                (original 20; normal maps are 8). At least 3.
WIDESCREEN       = False
FFDEC_JAR        = r"%LOCALAPPDATA%\Temp\db-preservation-ffdec\ffdec-cli.jar"
DREAD_REVIVE_SECONDS = 8  # the same as normal maps (class_95.const_826 = 8 s); the original Dread wait was 20
MAXED_CHARACTERS = ["andrei"]
MAXED_GOLD       = 10_000_000
MAXED_IDOLS      = 10_000
MAXED_PET_LEVEL  = 20      # every pet of a maxed character is raised to this rank (20 = max)
MAXED_COMPLETE_QUESTS = True  # also complete every normal quest (opens the Dread maps)
MAXED_COMPLETE_DREAD_QUESTS = True  # ... and every Dread quest (every dungeon open, for testing)
MAXED_ALL_LEGENDARY_GEAR    = True  # every gear item of the class, Legendary
UNLIMITED_IDOLS_BALANCE = 99999

# EXPERIMENT. Master-client mode (what classic-dungeon-blitz does): the game itself runs every
# room script, monster brain, buff and boss phase, as the original's master client did
# (devSettings.xml DEVFLAG_MASTER_CLIENT -> Level.const_919). The server then sends no
# monsters, runs no monster AI / scenes / gates / dungeon progress of its own, and only
# keeps score: damage, kills, loot, quests. Off: the server runs the monsters (the setup so far).
MASTER_CLIENT           = False
ENEMY_AI_ENABLED        = True
ENEMY_AGGRO_RANGE       = 400
ENEMY_AGGRO_HEIGHT      = 300
ENEMY_LEASH_RANGE       = 1200
ENEMY_AGGRO_DELAY       = 2.0   # s a player stays in range before a monster attacks (pass by in time)
ENEMY_DEAGGRO_DELAY     = 4.0   # s without being hit before a monster that lost its target goes home
ENEMY_ROAM_RADIUS       = 1200  # monsters chase at most this far from their spawn
ENEMY_DAMAGE_MULTIPLIER = 1.0
OUT_OF_COMBAT_REGEN_DELAY = 3.0
OUT_OF_COMBAT_REGEN_RATE = 0.10
CLIENT_PROJECTILE_HITS = True  # enemy shots hit only when the game sees them hit you (False: server timer)
RANGED_DODGE_RADIUS = 70  # px: a player this far from where an enemy shot was aimed dodges it
HEALTH_ORB_DROP_CHANCE = 1.0
HEALTH_ORB_HEAL_FRACTION = 0.25
SIGIL_DROP_CHANCE = 0.15
SIGIL_DROP_MIN = 1
SIGIL_DROP_MAX = 2
MAMMOTH_LIEUTENANT_DROP_CHANCE = 0.15
MAMMOTH_MINIBOSS_DROP_CHANCE = 0.50
MAMMOTH_BOSS_DROP_CHANCE = 1.0
MAMMOTH_STRONG_DROP_MIN = 1
MAMMOTH_STRONG_DROP_MAX = 2
MAMMOTH_BOSS_DROP_MIN = 3
MAMMOTH_BOSS_DROP_MAX = 5
# Every boss drops Mammoth Idols by its level: MAMMOTH_BOSS_IDOLS_TOP x (level / TOP_LEVEL)^2,
# so the hardest Dread bosses (level 45, Valhaven) give 500 and the first bosses a few.
# A MiniBoss (MAMMOTH_MINIBOSS_DROP_CHANCE) gives up to MAMMOTH_MINIBOSS_SHARE of that.
MAMMOTH_BOSS_IDOLS_TOP = 500
MAMMOTH_BOSS_TOP_LEVEL = 45
MAMMOTH_MINIBOSS_SHARE = 0.2

# Timer caps: buildings at most 2 hours; skills, talents, forge, pet training and
# egg hatching between 30 minutes and 1 hour; the hatchery offers new eggs hourly
# (the original was 20 hours). Timers already running are shortened at startup.
BUILDING_MAX_DURATION = 2 * 60 * 60
OTHER_TIMER_MIN_DURATION = 30 * 60
OTHER_TIMER_MAX_DURATION = 60 * 60
EGG_REFRESH_SECONDS = 60 * 60

GEAR_DROP_CHANCE_BY_RANK = {"Minion": 0.06, "Lieutenant": 0.2, "MiniBoss": 0.45, "Boss": 1.0}  # tuned after gear was added to every dungeon
GEAR_DROP_MULTIPLIER    = 1.0
OVERWORLD_LOOT_MULTIPLIER = 0.25
MATERIAL_DROP_CHANCE    = 1.0
MATERIAL_RARE_CHANCE    = 0.35
MATERIAL_LEGENDARY_CHANCE = 0.15
DREAD_MATERIAL_RARITY_MULTIPLIER = 1.5  # Dread x this on the Rare/Legendary material chances (bosses x both)
GEAR_RARE_CHANCE       = 0.15  # tuned (originally 0.10)
GEAR_LEGENDARY_CHANCE   = 0.04  # doubled (was 0.02)
BOSS_RARITY_MULTIPLIER  = 2.0   # materials
BOSS_GEAR_RARITY_MULTIPLIER = 1.0  # gear: bosses keep 24% Rare now that the base chances doubled
GEAR_LEVEL_RANGE        = 5
LEGENDARY_ONLY_IN_DREAD = True
DREAD_GEAR_DROP_MULTIPLIER = 2.0
# Dread gear rarity per drop (the rest is Magic): monsters 30% Rare / 8% Legendary,
# bosses and minibosses 80% Rare / 16% Legendary
DREAD_RARE_CHANCE           = 0.60  # doubled (was 0.30)
DREAD_LEGENDARY_CHANCE      = 0.16  # doubled (was 0.08)
DREAD_BOSS_RARE_CHANCE      = 0.60  # Legendary doubled per kill (16% per item was ~29% per kill, now ~59%)
DREAD_BOSS_LEGENDARY_CHANCE = 0.36
DREAD_MINIBOSS_RARE_CHANCE      = 0.80
DREAD_MINIBOSS_LEGENDARY_CHANCE = 0.16
# Completing an area's gear (every item a monster can drop for your class: a boss's own
# items, else the area's): owning all of them, any rarity, adds (Rare, Legendary) chance;
# owning all at Rare or better adds GEAR_COLLECTED_RARE_BONUS more Legendary.
# Dyes (DyeTypes, 185 of them): a chance per kill by EntRank (Dread x DREAD_GEAR_DROP_MULTIPLIER,
# open maps x OVERWORLD_LOOT_MULTIPLIER), only ones the player doesn't own yet; their rarity
# by where they drop (Legendary dyes only in Dread).
# Treasure Troves and Dragon Keys from dungeon monsters (a bit rarer than gear: 8/20/40/100%),
# each rolled on its own per kill; Dread x DREAD_GEAR_DROP_MULTIPLIER
TROVE_DROP_CHANCE_BY_RANK = {"Minion": 0.03, "Lieutenant": 0.08, "MiniBoss": 0.20, "Boss": 0.60}
KEY_DROP_CHANCE_BY_RANK   = {"Minion": 0.03, "Lieutenant": 0.08, "MiniBoss": 0.20, "Boss": 0.60}
# Gear stats in the client (tools/patch_client_timers.py, rebuilt with the client): Magic is
# the base, Rare x GEAR_RARE_STAT_MULTIPLIER, Legendary x GEAR_LEGENDARY_STAT_MULTIPLIER, and a
# Legendary also gets the stats its item leaves out (GEAR_LEGENDARY_EXTRA_STAT of a standard
# item's, before the multiplier): Attack, Expertise and Armor on every Legendary.
# Gear stat ranges by rarity (every gear stat, at any level): the game's own value (about
# 125 at level 1 up to 1300+ at 50) picks the place in the range, so higher-level items
# land higher. Paragon's bonus applies on top.
GEAR_STAT_RANGES = {"M": (60, 250), "R": (250, 650), "L": (651, 2000)}
GEAR_RARE_STAT_MULTIPLIER      = 3.5
GEAR_LEGENDARY_STAT_MULTIPLIER = 10.0
GEAR_LEGENDARY_EXTRA_STAT      = 0.5
# Mounts: everyone walks at speed 11 and every mount runs at 14; Legendary mounts at this
# (18 = about +60% over walking). MOUNT_KEEPS_SPEED_IN_COMBAT: no slowdown while attacking.
LEGENDARY_MOUNT_SPEED       = 0  # off: a mount's EntType Speed isn't used for riding
# Riding bonus (every mount's "Mounted" buff is +40%): Rare and Legendary mounts get these
RARE_MOUNT_SPEED_BONUS      = 0.40
LEGENDARY_MOUNT_SPEED_BONUS = 0.70
# Paragon (levels after 50): every gear stat +this per Paragon level
PARAGON_STAT_BONUS_PER_LEVEL = 0.02
MOUNT_KEEPS_SPEED_IN_COMBAT = True
# A story dungeon opens only once you have its quest (or cleared it before), in order,
# Dread too; a side dungeon once the quests before it are done.
DUNGEONS_NEED_THEIR_QUEST = True
DYE_DROP_CHANCE_BY_RANK = {"Minion": 0.075, "Lieutenant": 0.15, "MiniBoss": 0.30, "Boss": 0.5}  # halved: a dye is always one you lack
DYE_RARITY = {
    "monster":       {"M": 0.85, "R": 0.15},
    "boss":          {"M": 0.50, "R": 0.50},
    "dread monster": {"M": 0.60, "R": 0.30, "L": 0.10},
    "dread boss":    {"M": 0.20, "R": 0.50, "L": 0.30},
}
GEAR_COLLECTED_BONUS      = (0.10, 0.05)
GEAR_COLLECTED_RARE_BONUS = 0.10
# Gear Find (charms in worn gear, finder pets, a Gear Find potion; "!gearfind" in chat
# shows yours): the gear drop chance is x (1 + Gear Find x GEAR_FIND_DROP_EFFECT), and the
# Rare / Legendary chances x (1 + Gear Find x GEAR_FIND_RARITY_EFFECT), capped so a drop
# is at most GEAR_FIND_MAX_LEGENDARY Legendary and GEAR_FIND_MAX_RARE_OR_BETTER Rare or better.
GEAR_FIND_DROP_EFFECT   = 1.0
GEAR_FIND_RARITY_EFFECT = 0.5
GEAR_FIND_MAX_LEGENDARY = 0.75
GEAR_FIND_MAX_RARE_OR_BETTER = 0.96
# Treasure Troves bought from the trove window (packs of 1 / 10 / 25) cost Mammoth
# Idols instead of the gold shown in the window; same prices as the Dragon Key packs
TROVE_IDOL_COST = [22, 210, 470]
# Royal (Silver) Sigils earned with every trove opened, shown on the trove's prize screen
TROVE_SIGILS = 25
# Magic Forge: chance per Tempering artisan point (max 10 points) that a charm gets
# a Rare / Legendary gem. Original 0.9 / 0.4 (9% / 4% at max). The forge window shows
# the same numbers: tools/patch_client_timers.py writes them into the client, and
# only values already in the client's number pool work (e.g. 0.9, 1.0, 1.5, 1.8, 2.0).
FORGE_RARE_PER_TEMPERING      = 1.8
FORGE_LEGENDARY_PER_TEMPERING = 1.0
DREAD_BOSS_GEAR_DROPS      = 2

DREAD_UNLOCK_MISSIONS = [100, 232, 234, 235, 236]

# A dungeon run completes when its bosses and minibosses are dead; a dungeon with no
# boss completes at this much cleared (its room gates are scripted on the client and
# may stay shut, so 100% isn't always reachable)
DUNGEON_CLEAR_PERCENT = 80

# Paragon levels (paragon.py): the client caps characters at level 50, so XP after
# that fills Paragon levels, each costing the XP of the last level (49 -> 50).
# Bonuses per Paragon level: less damage taken from monsters (capped), more healing,
# better loot and gold.
PARAGON_ENABLED = True
PARAGON_XP_PER_LEVEL = 4_367_860
PARAGON_DAMAGE_REDUCTION_PER_LEVEL = 0.01
PARAGON_MAX_DAMAGE_REDUCTION = 0.60
PARAGON_HEAL_BONUS_PER_LEVEL = 0.02
PARAGON_LOOT_BONUS_PER_LEVEL = 0.02


_client_timers = None


def client_timer(table: str, index: int, original: int) -> int:
    """
    A timer that is built into the client's code (talent research, pet training,
    charm crafting). tools/patch_client_timers.py rewrites those tables in the client
    and saves them to data/client_timers.json; using the same values keeps the
    client's countdown and the server's timer equal. Falls back to scale_duration.
    """
    global _client_timers
    if _client_timers is None:
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "client_timers.json")
        try:
            with open(path, encoding="utf-8") as f:
                _client_timers = json.load(f)
        except (OSError, ValueError):
            _client_timers = {}
    values = _client_timers.get(table)
    if values and 0 <= index < len(values):
        return int(values[index])
    return scale_duration(original)


def scale_duration(seconds: int) -> int:
    seconds = int(seconds)
    if seconds <= 0:
        return seconds
    scaled = max(1, math.ceil(seconds * TIME_MULTIPLIER))
    # never make a timer longer than the original (a 1 second upgrade stays 1 second)
    return min(seconds, OTHER_TIMER_MAX_DURATION, max(OTHER_TIMER_MIN_DURATION, scaled))


def scale_building_duration(seconds: int) -> int:
    seconds = int(seconds)
    if seconds <= 0:
        return seconds
    scaled = max(1, math.ceil(seconds * TIME_MULTIPLIER))
    return min(BUILDING_MAX_DURATION, scaled)

# Gear on the ground: outline colour by rarity (Magic green, Rare blue, Legendary gold),
# drawn thicker and brighter than the game's faint default (blur 6, strength 2)
LOOT_GLOW_BLUR = 12
LOOT_GLOW_STRENGTH = 4
