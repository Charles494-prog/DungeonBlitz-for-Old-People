/**
 * The mod's chat commands and the Mount Merchant (the old server's chat_commands.py and
 * mount_merchant.py). Commands start with "!" and arrive as public chat; the patched
 * client (tools/mod_client) sends them from its chat menu rows and from the Mount
 * Merchant window:
 *
 *   !mounts / !mmopen      open the Mount Merchant window (every mount)
 *   !mmbuy <id>            the window's Buy button
 *   !buymount <id>         buy a mount by id
 *   !buygold <idols>       Mammoth Idols for gold
 *   !buysigils <idols>     Mammoth Idols for Royal Sigils
 *   !gearfind              your Gear Find and what it does
 *   !widescreen            switch the 16:9 / 3:2 view
 *
 * The window opens on a chat status message (0x44) the patched client catches:
 *   "\x01MM|0|<idols>|<sigils>|<gold>|<id>:<G|I|S>:<price>:<owned>,..."
 */
import * as fs from 'fs';
import * as path from 'path';
import { Client } from './Client';
import { BitBuffer } from '../network/protocol/bitBuffer';
import { ModConfig } from './ModConfig';
import { getEquippedCharmBonuses } from '../utils/CharmBonuses';
import { getActivePotionBonuses } from '../utils/ConsumableState';
import { PetHandler } from '../handlers/PetHandler';

const MM_MARK = '\u0001MM|';
const WS_MARK = '\u0001WS|';
const SIGIL_PRICE: Record<string, number> = { R: 640, L: 1200 };
const SANE_IDOL_COST = 1000;       // MountTypes IdolCost 999999999 marks event / lockbox mounts
const EVENT_MOUNT_IDOLS = 500;     // what those cost here when they are Magic
const CURRENCY_NAMES: Record<string, string> = { G: 'gold', I: 'Mammoth Idols', S: 'Royal Sigils' };

type Mount = { MountID: number; DisplayName: string; IdolCost: number; Rarity: string };

let mounts: Mount[] | null = null;

function allMounts(): Mount[] {
    if (!mounts) {
        // the same table the client's Game.swz MountTypes has (tools/mod_client/data/MountTypes.json)
        const file = path.join(__dirname, '..', '..', '..', 'tools', 'mod_client', 'data', 'MountTypes.json');
        try {
            mounts = (JSON.parse(fs.readFileSync(file, 'utf8')) as Mount[]).filter((m) => Number(m.MountID) > 0);
        } catch (err) {
            console.error('[ModCommands] MountTypes.json not readable:', err);
            mounts = [];
        }
    }
    return mounts;
}

/** [mount id, currency, price]: every mount, Magic first (Idols), then Rare and Legendary (Sigils). */
export function mountStock(): Array<[number, 'G' | 'I' | 'S', number]> {
    return [...allMounts()]
        .sort((a, b) => 'MRL'.indexOf(a.Rarity) - 'MRL'.indexOf(b.Rarity) || a.MountID - b.MountID)
        .map((m) => SIGIL_PRICE[m.Rarity]
            ? [m.MountID, 'S', SIGIL_PRICE[m.Rarity]]
            : [m.MountID, 'I', m.IdolCost > 0 && m.IdolCost < SANE_IDOL_COST ? m.IdolCost : EVENT_MOUNT_IDOLS]);
}

function status(client: Client, text: string): void {
    const bb = new BitBuffer(false);
    bb.writeMethod13(text);
    client.sendBitBuffer(0x44, bb);
}

function save(client: Client): void {
    if (typeof client.scheduleCharacterSave === 'function') {
        client.scheduleCharacterSave('mod command');
    }
}

function sendIdols(client: Client): void {
    const character: any = client.character;
    const bb = new BitBuffer(false);
    bb.writeMethod4(Number(character.mammothIdols ?? 0));
    bb.writeMethod4(0);
    bb.writeMethod11(character.showHigher ? 1 : 0, 1);
    client.sendBitBuffer(0xA1, bb);
}

function wallet(character: any): Record<string, number> {
    return {
        G: Number(character.gold ?? 0),
        I: Number(character.mammothIdols ?? 0),
        S: Number(character.SilverSigils ?? 0)
    };
}

export function openMountMerchant(client: Client): void {
    const character: any = client.character;
    if (!character) {
        return;
    }
    const owned = new Set<number>((character.mounts ?? []).map(Number));
    const w = wallet(character);
    const items = mountStock().map(([id, cur, price]) => `${id}:${cur}:${price}:${owned.has(id) ? 1 : 0}`).join(',');
    status(client, `${MM_MARK}0|${w.I}|${w.S}|${w.G}|${items}`);
}

function charge(client: Client, currency: string, price: number): void {
    const character: any = client.character;
    const bb = new BitBuffer(false);
    if (currency === 'G') {
        character.gold = Number(character.gold ?? 0) - price;
        bb.writeMethod4(price);
        client.sendBitBuffer(0xB4, bb);   // PKTTYPE_MONEY_LOSS
    } else if (currency === 'I') {
        character.mammothIdols = Number(character.mammothIdols ?? 0) - price;
        sendIdols(client);
    } else {
        character.SilverSigils = Number(character.SilverSigils ?? 0) - price;
        bb.writeMethod4(price);
        client.sendBitBuffer(0x10F, bb);  // PKTTYPE_SPEND_ROYAL_SIGILS
    }
}

function buyMount(client: Client, args: string[]): void {
    const character: any = client.character;
    const mountId = Number(args[0] ?? 0);
    const offer = mountStock().find(([id]) => id === mountId);
    const mount = allMounts().find((m) => m.MountID === mountId);
    if (!character) {
        return;
    }
    if (!offer || !mount) {
        status(client, "The Mount Merchant doesn't sell that mount.");
    } else if ((character.mounts ?? []).map(Number).includes(mountId)) {
        status(client, `You already own the ${mount.DisplayName}.`);
    } else {
        const [, currency, price] = offer;
        const have = wallet(character)[currency];
        if (have < price) {
            status(client, `The ${mount.DisplayName} costs ${price.toLocaleString()} ${CURRENCY_NAMES[currency]}; you have ${have.toLocaleString()}.`);
        } else {
            charge(client, currency, price);
            character.mounts = [...(character.mounts ?? []), mountId];
            const bb = new BitBuffer(false);
            bb.writeMethod4(mountId);
            bb.writeMethod15(false);  // PKTTYPE_GAIN_MOUNT, with the "new mount" notice
            client.sendBitBuffer(0x36, bb);
            save(client);
            status(client, `You bought the ${mount.DisplayName} for ${price.toLocaleString()} ${CURRENCY_NAMES[currency]}!`);
            console.log(`[MountMerchant] ${character.name} bought ${mount.DisplayName} for ${price} ${currency}`);
        }
    }
    openMountMerchant(client);  // the window refreshes (and its Buy button frees up)
}

function spendIdols(client: Client, idols: number): boolean {
    const character: any = client.character;
    const have = Number(character.mammothIdols ?? 0);
    if (!Number.isFinite(idols) || idols <= 0) {
        return false;
    }
    if (idols > have) {
        status(client, `That costs ${idols.toLocaleString()} Mammoth Idols; you have ${have.toLocaleString()}.`);
        return false;
    }
    character.mammothIdols = have - idols;
    sendIdols(client);
    return true;
}

function buyGold(client: Client, args: string[]): void {
    const idols = Math.floor(Number(String(args[0] ?? '').replace(/,/g, '')));
    if (!(idols > 0)) {
        status(client, `Usage: !buygold <idols>  (1 Mammoth Idol = ${ModConfig.GOLD_PER_IDOL.toLocaleString()} gold)`);
        return;
    }
    if (!spendIdols(client, idols)) {
        return;
    }
    const gold = idols * ModConfig.GOLD_PER_IDOL;
    const character: any = client.character;
    character.gold = Number(character.gold ?? 0) + gold;
    const bb = new BitBuffer(false);
    bb.writeMethod4(gold);
    bb.writeMethod15(false);
    client.sendBitBuffer(0x35, bb);
    save(client);
    status(client, `Traded ${idols.toLocaleString()} Mammoth Idols for ${gold.toLocaleString()} gold.`);
}

function buySigils(client: Client, args: string[]): void {
    const idols = Math.floor(Number(String(args[0] ?? '').replace(/,/g, '')));
    if (!(idols > 0)) {
        status(client, `Usage: !buysigils <idols>  (1 Mammoth Idol = ${ModConfig.SIGILS_PER_IDOL} Royal Sigils)`);
        return;
    }
    if (!spendIdols(client, idols)) {
        return;
    }
    const sigils = idols * ModConfig.SIGILS_PER_IDOL;
    const character: any = client.character;
    character.SilverSigils = Number(character.SilverSigils ?? 0) + sigils;
    const bb = new BitBuffer(false);
    bb.writeMethod4(sigils);
    client.sendBitBuffer(0x112, bb);  // PKTTYPE_GAIN_ROYAL_SIGILS
    save(client);
    status(client, `Traded ${idols.toLocaleString()} Mammoth Idols for ${sigils.toLocaleString()} Royal Sigils.`);
}

export function gearFind(client: Client): number {
    const pets = PetHandler.getEquippedPetBonusRates(client.character);
    const charms = getEquippedCharmBonuses(client.character);
    const potions = getActivePotionBonuses(client.character, client.currentLevel);
    return pets.itemFind + charms.itemFind + potions.itemFind;
}

function showGearFind(client: Client): void {
    const find = gearFind(client);
    status(client, `Gear Find: +${Math.round(find * 100)}% (charms in your worn gear, finder pets, Gear Find potion)`);
    status(client, `  gear drops x${(1 + find * ModConfig.GEAR_FIND_DROP_EFFECT).toFixed(2)} as often; `
        + `Rare and Legendary chances x${(1 + find * ModConfig.GEAR_FIND_RARITY_EFFECT).toFixed(2)}`);
}

export function sendView(client: Client): void {
    const character: any = client.character;
    if (character) {
        status(client, `${WS_MARK}${character.widescreen ? 1 : 0}`);
    }
}

function toggleWidescreen(client: Client): void {
    const character: any = client.character;
    if (!character) {
        return;
    }
    character.widescreen = !character.widescreen;
    save(client);
    sendView(client);
}

const COMMANDS: Record<string, (client: Client, args: string[]) => void> = {
    mounts: (client) => openMountMerchant(client),
    mmopen: (client) => openMountMerchant(client),
    mmbuy: buyMount,
    buymount: buyMount,
    buygold: buyGold,
    buysigils: buySigils,
    gearfind: (client) => showGearFind(client),
    widescreen: (client) => toggleWidescreen(client)
};

/** A "!command" from chat: handled here (and not shown to other players) when it is ours. */
export function handleModCommand(client: Client, message: string): boolean {
    if (!client.character || !message.startsWith('!')) {
        return false;
    }
    const [name, ...args] = message.slice(1).trim().split(/\s+/);
    const command = COMMANDS[String(name ?? '').toLowerCase()];
    if (!command) {
        return false;
    }
    command(client, args);
    return true;
}

// The Mammoth Idol window's packages (client class_63.const_116 / const_103; the 4th and
// 5th are patched to 1000 and 10000 by tools/mod_client)
const IDOL_PACKAGES: Record<string, number> = {
    '9QQNJJH7RGZTQ': 50, '34D5DGPVPKNDW': 105, 'YQJR84UHXP6P2': 180, 'BMDSGRY5C4FEL': 1000,
    'YAPMVT7PBQGJE': 10000, 'YAGXMFQJEZR5J': 2050, 'WUPTFRTXUZL24': 220, '5TWEH5VL9H82Y': 480
};

/** /buyidols: the idol window's Buy button (its PayPal address is patched to this server).
 *  Grants the package to the buyer's logged-in character; returns a message. */
export function buyIdols(fields: Record<string, string>, sessions: Iterable<Client>): string {
    const amount = IDOL_PACKAGES[String(fields.hosted_button_id ?? '')];
    if (!amount) {
        return 'Unknown Mammoth Idol package.';
    }
    const userId = Number(String(fields.custom ?? '').split(':')[0]);
    const client = [...sessions].find((s: any) => Number(s.userId) === userId && s.character && s.playerSpawned);
    if (!client) {
        return 'Log in with a character first, then buy again.';
    }
    const character: any = client.character;
    character.mammothIdols = Number(character.mammothIdols ?? 0) + amount;
    sendIdols(client);
    save(client);
    console.log(`[Store] ${character.name} got ${amount} Mammoth Idols`);
    return `${amount} Mammoth Idols added to ${character.name}.`;
}

/** NPCs that open the Mount Merchant when talked to (the Wolf's End stable girl). */
export const MOUNT_SHOP_NPCS = new Set(['NR_IntroVillager']);
