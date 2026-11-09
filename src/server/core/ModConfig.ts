/**
 * Settings of the "Dungeon Blitz for the Older Generation" changes on top of this server
 * (the old Python server's game_config.py). Every number the mod changes is here;
 * core/ModLoot.ts applies them and the launcher's home page (core/HomePage.ts) shows them
 * next to ORIGINAL: this server's own rates before the mod.
 */
export type Rank = 'Minion' | 'Lieutenant' | 'MiniBoss' | 'Boss';
export type Rarity = 'M' | 'R' | 'L';

export const ModConfig = {
    // --- experience and gold ------------------------------------------------------
    XP_MULTIPLIER: 12.5,          // monster experience
    QUEST_XP_MULTIPLIER: 25,      // quest experience (12.5 x 2)
    QUEST_GOLD_MULTIPLIER: 5,
    GOLD_PER_IDOL: 1000,          // !buygold
    SIGILS_PER_IDOL: 10,          // !buysigils

    // --- health -----------------------------------------------------------------------
    HEALTH_ORB_DROP_CHANCE: 1.0,  // a health orb from every dungeon kill
    HEALTH_ORB_HEAL_FRACTION: 0.25,
    REGEN_DELAY_MS: 3_000,        // out of combat this long, the player regenerates
    REGEN_RATE: 0.10,             // of max HP a second
    SIGIL_DROP_CHANCE: 0.15,      // a gold pickup also gives Silver Sigils
    SIGIL_DROP_MIN: 1,
    SIGIL_DROP_MAX: 2,

    // --- Paragon: levels after 50 (XP past the cap) --------------------------------------
    PARAGON_XP_PER_LEVEL: 4_367_860,
    PARAGON_HEAL_BONUS_PER_LEVEL: 0.02,   // health orbs
    PARAGON_STAT_BONUS_PER_LEVEL: 0.02,   // every gear stat (shown by the patched client; keep equal to
                                          // tools/mod_client/game_config.py PARAGON_STAT_BONUS_PER_LEVEL)
    PARAGON_LOOT_BONUS_PER_LEVEL: 0.02,   // gear, dye, trove and key chances, gold
    MAX_LEVEL: 50,

    // playing alone: a monster the game says is dead, with at most this share of its HP
    // left on the server, counts as dead (the boat's Kraken); healthier ones stay alive
    LOCAL_DEATH_HP_TOLERANCE: 0.10,

    // --- gear ----------------------------------------------------------------------
    // a chance per kill in dungeons, by rank; Dread x DREAD_DROP_MULTIPLIER
    GEAR_DROP_CHANCE_BY_RANK: { Minion: 0.06, Lieutenant: 0.20, MiniBoss: 0.45, Boss: 1.0 } as Record<Rank, number>,
    DREAD_DROP_MULTIPLIER: 2.0,
    // rarity of a gear drop: normal dungeons drop Magic and Rare, Legendary only in Dread
    GEAR_RARE_CHANCE: 0.15,
    DREAD_RARE_CHANCE: 0.60,
    DREAD_LEGENDARY_CHANCE: 0.16,
    DREAD_MINIBOSS_RARE_CHANCE: 0.80,
    DREAD_MINIBOSS_LEGENDARY_CHANCE: 0.16,
    DREAD_BOSS_RARE_CHANCE: 0.60,
    DREAD_BOSS_LEGENDARY_CHANCE: 0.36,
    DREAD_BOSS_GEAR_DROPS: 2,     // a Dread boss rolls its gear this many times
    // owning every item an area drops (any rarity): +Rare / +Legendary there; all of them
    // at Rare: another +Legendary. The last pieces come easier.
    GEAR_COLLECTED_BONUS: { rare: 0.10, legendary: 0.05 },
    GEAR_COLLECTED_RARE_BONUS: 0.10,
    // Gear Find (pets, charms, potions): drop chance x (1 + find x DROP), Rare / Legendary
    // chances x (1 + find x RARITY), capped
    GEAR_FIND_DROP_EFFECT: 1.0,
    GEAR_FIND_RARITY_EFFECT: 0.5,
    GEAR_FIND_MAX_LEGENDARY: 0.75,
    GEAR_FIND_MAX_RARE_OR_BETTER: 0.96,

    // --- crafting materials -------------------------------------------------------
    MATERIAL_DROP_CHANCE: 1.0,    // every dungeon kill
    MATERIAL_RARE_CHANCE: 0.35,
    MATERIAL_LEGENDARY_CHANCE: 0.15,         // Dread
    MATERIAL_LEGENDARY_CHANCE_NORMAL: 0.04,  // normal dungeons
    MATERIAL_BOSS_RARITY_MULTIPLIER: 2.0,
    MATERIAL_DREAD_RARITY_MULTIPLIER: 1.5,

    // --- dungeon stars: this completion % (or more) gives full stars on the map ----
    FULL_STARS_COMPLETION_PERCENT: 100,

    // --- dyes (always one the player doesn't own yet) ---------------------------------
    DYE_DROP_CHANCE_BY_RANK: { Minion: 0.075, Lieutenant: 0.15, MiniBoss: 0.30, Boss: 0.5 } as Record<Rank, number>,
    DYE_RARITY: {
        monster: { M: 0.85, R: 0.15, L: 0 },
        boss: { M: 0.50, R: 0.50, L: 0 },
        dreadMonster: { M: 0.60, R: 0.30, L: 0.10 },
        dreadBoss: { M: 0.20, R: 0.50, L: 0.30 }
    } as Record<string, Record<Rarity, number>>,

    // --- Mammoth Idols ---------------------------------------------------------------
    // every boss: IDOLS_TOP x (its level / TOP_LEVEL)^2, the hardest Dread boss 500
    BOSS_IDOLS_TOP: 500,
    BOSS_IDOLS_TOP_LEVEL: 45,
    BOSS_IDOLS_MIN: 3,
    MINIBOSS_IDOL_CHANCE: 0.5,
    MINIBOSS_IDOL_SHARE: 0.2,

    // --- Treasure Troves and Dragon Keys from dungeon monsters --------------------------
    TROVE_DROP_CHANCE_BY_RANK: { Minion: 0.02, Lieutenant: 0.053, MiniBoss: 0.133, Boss: 0.40 } as Record<Rank, number>,  // a third lower
    KEY_DROP_CHANCE_BY_RANK: { Minion: 0.02, Lieutenant: 0.053, MiniBoss: 0.133, Boss: 0.40 } as Record<Rank, number>,  // a third lower
    TROVE_LOCKBOX_ID: 1
};

/** Skills and other upgrades: TIME_MULTIPLIER of the original, between 30 min and 1 h,
 *  never longer than the original (tools/mod_client/game_config.py scale_duration: the
 *  client's Game.swz shows the same times). */
export function scaleDuration(seconds: number): number {
    if (seconds <= 0) return seconds;
    const scaled = Math.max(1, Math.ceil(seconds * TIME.MULTIPLIER));
    return Math.min(seconds, TIME.OTHER_MAX, Math.max(TIME.OTHER_MIN, scaled));
}

/** Building upgrades: TIME_MULTIPLIER of the original, at most 2 h (scale_building_duration). */
export function scaleBuildingDuration(seconds: number): number {
    if (seconds <= 0) return seconds;
    return Math.min(TIME.BUILDING_MAX, Math.max(1, Math.ceil(seconds * TIME.MULTIPLIER)));
}

export const TIME = { MULTIPLIER: 0.05, BUILDING_MAX: 2 * 60 * 60, OTHER_MIN: 30 * 60, OTHER_MAX: 60 * 60 };

/**
 * This server's own rates before the mod (handlers/RewardHandler.ts as released), for
 * the home page's comparison charts. Gear: chance per kill of a Rare / Legendary item.
 */
export const ORIGINAL = {
    XP_MULTIPLIER: 1,
    QUEST_XP_MULTIPLIER: 1,
    QUEST_GOLD_MULTIPLIER: 1,
    GEAR_DROP_CHANCE_BY_RANK: { Minion: 0, Lieutenant: 0.03, MiniBoss: 0.10, Boss: 1 } as Record<Rank, number>,
    GEAR_RARE_PER_KILL: {
        normal: { Lieutenant: 1 / 250, MiniBoss: 1 / 60, Boss: 1 / 15 },
        dread: { Lieutenant: 1 / 100, MiniBoss: 1 / 40, Boss: 1 / 5 }
    },
    GEAR_LEGENDARY_PER_KILL: {
        dread: { Lieutenant: 1 / 333, MiniBoss: 1 / 100, Boss: 1 / 25 }
    },
    MATERIAL_DROP_CHANCE_BY_RANK: { Minion: 0.03, Lieutenant: 0.15, MiniBoss: 0.5, Boss: 1 } as Record<Rank, number>,
    MATERIAL_RARITY: { normal: { M: 0.82, R: 0.15, L: 0.03 }, dread: { M: 0.62, R: 0.32, L: 0.06 } },
    DYE_DROP_CHANCE_BY_RANK: { Minion: 0, Lieutenant: 0.01, MiniBoss: 0.01, Boss: 0.01 } as Record<Rank, number>,
    BOSS_IDOLS: 0,
    TROVE_DROP_CHANCE: 0,
    KEY_DROP_CHANCE: 0
};
