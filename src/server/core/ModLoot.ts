/**
 * The mod's loot rules (numbers: core/ModConfig.ts), called from handlers/RewardHandler.ts:
 *
 *  - gear: a drop chance per rank (Minions too), Gear Find counts, Legendary only in Dread,
 *    a collection bonus for areas nearly complete, Dread bosses roll twice. Owned items are
 *    already left out by GameData.getGearIdForEntity: a drop is always new or an upgrade.
 *  - materials on every dungeon kill, Legendary ones far more often
 *  - dyes from every rank, always one the player lacks (a rarity with none left gives way)
 *  - Mammoth Idols from every boss by its level, Treasure Troves and Dragon Keys
 */
import { Client } from './Client';
import { GameData } from './GameData';
import { LevelConfig } from './LevelConfig';
import { BitBuffer } from '../network/protocol/bitBuffer';
import { ModConfig, Rank, Rarity } from './ModConfig';

const RANKS: Rank[] = ['Minion', 'Lieutenant', 'MiniBoss', 'Boss'];

function rankOf(entType: any): Rank {
    const rank = String(entType?.EntRank ?? 'Minion') as Rank;
    return RANKS.includes(rank) ? rank : 'Minion';
}

function isBossRank(rank: Rank): boolean {
    return rank === 'Boss' || rank === 'MiniBoss';
}

export function isDread(levelName: string | null | undefined): boolean {
    return /Hard$/i.test(String(levelName ?? '').trim());
}

function pickWeighted<T extends string>(weights: Record<T, number>): T | null {
    const entries = (Object.entries(weights) as Array<[T, number]>).filter(([, w]) => w > 0);
    const total = entries.reduce((sum, [, w]) => sum + w, 0);
    if (total <= 0) {
        return null;
    }
    let roll = Math.random() * total;
    for (const [value, weight] of entries) {
        roll -= weight;
        if (roll < 0) {
            return value;
        }
    }
    return entries[entries.length - 1]![0];
}

// --- Paragon ----------------------------------------------------------------------------

export function paragonLevel(client: Client): number {
    return Math.max(0, Number((client.character as any)?.paragonLevel ?? 0));
}

export function lootMultiplier(client: Client): number {
    return 1 + paragonLevel(client) * ModConfig.PARAGON_LOOT_BONUS_PER_LEVEL;
}

export function healMultiplier(client: Client): number {
    return 1 + paragonLevel(client) * ModConfig.PARAGON_HEAL_BONUS_PER_LEVEL;
}

/** The Paragon level for the patched client (tools/mod_client a_LocalText: gear stats). */
export function sendParagon(client: Client): void {
    sendStatus(client, PG_MARK + String(paragonLevel(client)));
}

const PG_MARK = String.fromCharCode(1) + 'PG|';

/** XP earned at level 50 fills Paragon levels; a level-up is announced. */
export function addParagonXp(client: Client, xp: number): void {
    const character: any = client.character;
    if (!character || xp <= 0) {
        return;
    }
    character.paragonXP = Number(character.paragonXP ?? 0) + xp;
    let gained = 0;
    while (character.paragonXP >= ModConfig.PARAGON_XP_PER_LEVEL) {
        character.paragonXP -= ModConfig.PARAGON_XP_PER_LEVEL;
        character.paragonLevel = Number(character.paragonLevel ?? 0) + 1;
        gained += 1;
    }
    if (gained) {
        const level = paragonLevel(client);
        sendParagon(client);
        sendStatus(client, `Paragon level up! Paragon ${level}: `
            + `+${Math.round(level * ModConfig.PARAGON_STAT_BONUS_PER_LEVEL * 100)}% gear stats, `
            + `+${Math.round(level * ModConfig.PARAGON_HEAL_BONUS_PER_LEVEL * 100)}% healing, `
            + `+${Math.round(level * ModConfig.PARAGON_LOOT_BONUS_PER_LEVEL * 100)}% loot and gold`);
    }
}

// --- gear ------------------------------------------------------------------------

export function gearDropChance(client: Client, entType: any, itemFind: number): number {
    let chance = ModConfig.GEAR_DROP_CHANCE_BY_RANK[rankOf(entType)];
    if (isDread(client.currentLevel)) {
        chance *= ModConfig.DREAD_DROP_MULTIPLIER;
    }
    chance *= 1 + Math.max(0, itemFind) * ModConfig.GEAR_FIND_DROP_EFFECT;
    return Math.max(0, Math.min(1, chance * lootMultiplier(client)));
}

/** Owned gear: id -> best tier (bag and worn). */
function ownedTiers(client: Client): Map<number, number> {
    const owned = new Map<number, number>();
    const character: any = client.character;
    for (const gear of [...(character?.inventoryGears ?? []), ...(character?.equippedGears ?? [])]) {
        const id = Number(gear?.gearID ?? 0);
        if (id > 0) {
            owned.set(id, Math.max(owned.get(id) ?? -1, Number(gear?.tier ?? 0)));
        }
    }
    return owned;
}

/** (extra Rare, extra Legendary) for an area the player has (nearly) collected. */
function collectionBonus(client: Client, entName: string): { rare: number; legendary: number } {
    const pool = GameData.getGearPoolForEntity(entName, String(client.character?.class ?? ''), client.currentLevel);
    if (!pool.length) {
        return { rare: 0, legendary: 0 };
    }
    const owned = ownedTiers(client);
    if (!pool.every((id) => (owned.get(id) ?? -1) >= 0)) {
        return { rare: 0, legendary: 0 };
    }
    const bonus = { ...ModConfig.GEAR_COLLECTED_BONUS };
    if (pool.every((id) => (owned.get(id) ?? -1) >= 1)) {
        bonus.legendary += ModConfig.GEAR_COLLECTED_RARE_BONUS;
    }
    return bonus;
}

/** The rarity (tier 0 Magic, 1 Rare, 2 Legendary) of a gear drop. */
export function gearTier(client: Client, entType: any, entName: string, itemFind: number): number {
    const rank = rankOf(entType);
    let rare: number;
    let legendary: number;
    if (isDread(client.currentLevel)) {
        if (rank === 'Boss') {
            rare = ModConfig.DREAD_BOSS_RARE_CHANCE;
            legendary = ModConfig.DREAD_BOSS_LEGENDARY_CHANCE;
        } else if (rank === 'MiniBoss') {
            rare = ModConfig.DREAD_MINIBOSS_RARE_CHANCE;
            legendary = ModConfig.DREAD_MINIBOSS_LEGENDARY_CHANCE;
        } else {
            rare = ModConfig.DREAD_RARE_CHANCE;
            legendary = ModConfig.DREAD_LEGENDARY_CHANCE;
        }
    } else {
        rare = ModConfig.GEAR_RARE_CHANCE;
        legendary = 0;  // Legendary gear drops in Dread only
    }
    const find = 1 + Math.max(0, itemFind) * ModConfig.GEAR_FIND_RARITY_EFFECT;
    legendary = Math.min(ModConfig.GEAR_FIND_MAX_LEGENDARY, legendary * find);
    rare = Math.min(rare * find, Math.max(0, ModConfig.GEAR_FIND_MAX_RARE_OR_BETTER - legendary));
    const bonus = collectionBonus(client, entName);
    rare += bonus.rare;
    if (isDread(client.currentLevel)) {
        legendary += bonus.legendary;
    }
    const roll = Math.random();
    if (roll < legendary) {
        return 2;
    }
    return roll < legendary + rare ? 1 : 0;
}

export function gearRolls(client: Client, entType: any): number {
    return isDread(client.currentLevel) && rankOf(entType) === 'Boss' ? ModConfig.DREAD_BOSS_GEAR_DROPS : 1;
}

// --- materials -----------------------------------------------------------------------

export function materialDropChance(): number {
    return ModConfig.MATERIAL_DROP_CHANCE;
}

/** The rarities to try for a material drop, best first (a realm without one gives way). */
export function materialRarities(client: Client, entType: any): Rarity[] {
    const dread = isDread(client.currentLevel);
    let mult = isBossRank(rankOf(entType)) ? ModConfig.MATERIAL_BOSS_RARITY_MULTIPLIER : 1;
    if (dread) {
        mult *= ModConfig.MATERIAL_DREAD_RARITY_MULTIPLIER;
    }
    const baseLegendary = dread ? ModConfig.MATERIAL_LEGENDARY_CHANCE : ModConfig.MATERIAL_LEGENDARY_CHANCE_NORMAL;
    const legendary = Math.min(1, baseLegendary * mult);
    const rare = Math.min(1 - legendary, ModConfig.MATERIAL_RARE_CHANCE * mult);
    const roll = Math.random();
    if (roll < legendary) {
        return ['L', 'R', 'M'];
    }
    return roll < legendary + rare ? ['R', 'M'] : ['M', 'R'];
}

// --- dyes ----------------------------------------------------------------------------

/** A dye the player lacks, or 0. */
export function rollDye(client: Client, entType: any, ownedDyes: Set<number>): number {
    const rank = rankOf(entType);
    const dread = isDread(client.currentLevel);
    let chance = ModConfig.DYE_DROP_CHANCE_BY_RANK[rank];
    if (dread) {
        chance *= ModConfig.DREAD_DROP_MULTIPLIER;
    }
    if (Math.random() >= chance * lootMultiplier(client)) {
        return 0;
    }
    const table = ModConfig.DYE_RARITY[(dread ? 'dread' : '') + (isBossRank(rank) ? (dread ? 'Boss' : 'boss') : (dread ? 'Monster' : 'monster'))];
    const weights = { ...table } as Record<Rarity, number>;
    for (const rarity of Object.keys(weights) as Rarity[]) {
        if (GameData.getRandomDyeId([rarity], ownedDyes) <= 0) {
            weights[rarity] = 0;  // all of this rarity collected: the others share its chance
        }
    }
    const rarity = pickWeighted(weights);
    return rarity ? GameData.getRandomDyeId([rarity], ownedDyes) : 0;
}

// --- health orbs and sigils ------------------------------------------------------------

export function healthOrbAmount(client: Client): number {
    if (Math.random() >= ModConfig.HEALTH_ORB_DROP_CHANCE) {
        return 0;
    }
    const maxHp = Math.max(100, Number((client as any).authoritativeMaxHp ?? 100));
    return Math.max(1, Math.floor(maxHp * ModConfig.HEALTH_ORB_HEAL_FRACTION * healMultiplier(client)));
}

export function maybeGrantSigils(client: Client): void {
    const character: any = client.character;
    if (!character || Math.random() >= ModConfig.SIGIL_DROP_CHANCE) {
        return;
    }
    const sigils = ModConfig.SIGIL_DROP_MIN
        + Math.floor(Math.random() * (ModConfig.SIGIL_DROP_MAX - ModConfig.SIGIL_DROP_MIN + 1));
    character.SilverSigils = Number(character.SilverSigils ?? 0) + sigils;
    const bb = new BitBuffer(false);
    bb.writeMethod4(sigils);
    client.sendBitBuffer(0x112, bb);  // PKTTYPE_GAIN_ROYAL_SIGILS
}

// --- idols, troves and keys -------------------------------------------------------------

function monsterLevel(entType: any, levelName: string | null | undefined): number {
    const spec: any = levelName && LevelConfig.has(levelName) ? LevelConfig.get(levelName) : null;
    const own = Number(entType?.Level ?? spec?.mapId ?? 1);
    const extra = spec ? Math.max(0, Number(spec.mapId ?? 0) - Number(spec.baseId ?? 0)) : 0;
    return Math.max(1, own + extra);
}

export function bossIdols(entType: any, levelName: string | null | undefined): number {
    const share = Math.min(1, monsterLevel(entType, levelName) / ModConfig.BOSS_IDOLS_TOP_LEVEL);
    return Math.max(ModConfig.BOSS_IDOLS_MIN, Math.round(ModConfig.BOSS_IDOLS_TOP * share * share));
}

export function rollIdols(client: Client, entType: any): number {
    const rank = rankOf(entType);
    if (rank === 'Boss') {
        return bossIdols(entType, client.currentLevel);
    }
    if (rank === 'MiniBoss' && Math.random() < ModConfig.MINIBOSS_IDOL_CHANCE) {
        const high = Math.max(2, Math.round(bossIdols(entType, client.currentLevel) * ModConfig.MINIBOSS_IDOL_SHARE));
        return 1 + Math.floor(Math.random() * high);
    }
    return 0;
}

function sendStatus(client: Client, text: string): void {
    const bb = new BitBuffer(false);
    bb.writeMethod13(text);
    client.sendBitBuffer(0x44, bb);
}

/** Idols, a trove and a key for a dungeon kill; true if the character changed. */
export function grantExtras(client: Client, entType: any): boolean {
    const character: any = client.character;
    if (!character) {
        return false;
    }
    const rank = rankOf(entType);
    const mult = (isDread(client.currentLevel) ? ModConfig.DREAD_DROP_MULTIPLIER : 1) * lootMultiplier(client);
    let changed = false;

    const idols = rollIdols(client, entType);
    if (idols > 0) {
        character.mammothIdols = Number(character.mammothIdols ?? 0) + idols;
        const bb = new BitBuffer(false);  // CharacterHandler.sendMammothIdolUpdate
        bb.writeMethod4(Number(character.mammothIdols));
        bb.writeMethod4(0);
        bb.writeMethod11(character.showHigher ? 1 : 0, 1);
        client.sendBitBuffer(0xA1, bb);
        sendStatus(client, `+${idols} Mammoth Idols`);
        changed = true;
    }
    if (Math.random() < ModConfig.TROVE_DROP_CHANCE_BY_RANK[rank] * mult) {
        const lockboxes: any[] = Array.isArray(character.lockboxes) ? character.lockboxes : (character.lockboxes = []);
        const entry = lockboxes.find((box) => Number(box?.lockboxID) === ModConfig.TROVE_LOCKBOX_ID);
        if (entry) {
            entry.count = Number(entry.count ?? 0) + 1;
        } else {
            lockboxes.push({ lockboxID: ModConfig.TROVE_LOCKBOX_ID, count: 1 });
        }
        const bb = new BitBuffer(false);  // LockboxHandler.sendLockboxInventoryDelta, with its notice
        bb.writeMethod6(ModConfig.TROVE_LOCKBOX_ID, 2);
        bb.writeMethod4(1);
        bb.writeMethod15(false);
        client.sendBitBuffer(0x104, bb);
        changed = true;
    }
    if (Math.random() < ModConfig.KEY_DROP_CHANCE_BY_RANK[rank] * mult) {
        character.DragonKeys = Number(character.DragonKeys ?? 0) + 1;
        sendStatus(client, '\u0001KY|1');  // the patched client adds it and says "You found 1 Dragon Key!"
        changed = true;
    }
    return changed;
}
