/**
 * The launcher's home page (http://localhost:8000/home): what the mod changes, shown as
 * charts of this server's original rates (ModConfig.ORIGINAL) against the mod's
 * (ModConfig), with a Play button. Rebuilt on every request from the live settings.
 */
import { ModConfig, ORIGINAL, Rank } from './ModConfig';

const RANKS: Rank[] = ['Minion', 'Lieutenant', 'MiniBoss', 'Boss'];
const RANK_LABEL: Record<Rank, string> = { Minion: 'Minion', Lieutenant: 'Lieutenant', MiniBoss: 'Mini-boss', Boss: 'Boss' };

function esc(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function pct(x: number): string {
    const v = x * 100;
    if (v === 0) return '0%';
    if (v < 1) return `${v.toFixed(v < 0.1 ? 2 : 1)}%`;
    return `${Math.round(v * 10) / 10}%`;
}

function atLeastOnce(p: number, rolls: number): number {
    return 1 - Math.pow(1 - Math.min(1, p), rolls);
}

// --- per-kill chances of the mod (no Gear Find or collection bonus) -----------------

function modGearChance(rank: Rank, dread: boolean): number {
    return Math.min(1, ModConfig.GEAR_DROP_CHANCE_BY_RANK[rank] * (dread ? ModConfig.DREAD_DROP_MULTIPLIER : 1));
}

function modDreadLegendaryPerKill(rank: Rank): number {
    const share = rank === 'Boss' ? ModConfig.DREAD_BOSS_LEGENDARY_CHANCE
        : rank === 'MiniBoss' ? ModConfig.DREAD_MINIBOSS_LEGENDARY_CHANCE : ModConfig.DREAD_LEGENDARY_CHANCE;
    const rolls = rank === 'Boss' ? ModConfig.DREAD_BOSS_GEAR_DROPS : 1;
    return atLeastOnce(modGearChance(rank, true) * share, rolls);
}

function modNormalRarePerKill(rank: Rank): number {
    return modGearChance(rank, false) * ModConfig.GEAR_RARE_CHANCE;
}

function modLegendaryMaterial(rank: Rank, dread: boolean): number {
    let mult = rank === 'Boss' || rank === 'MiniBoss' ? ModConfig.MATERIAL_BOSS_RARITY_MULTIPLIER : 1;
    if (dread) mult *= ModConfig.MATERIAL_DREAD_RARITY_MULTIPLIER;
    const base = dread ? ModConfig.MATERIAL_LEGENDARY_CHANCE : ModConfig.MATERIAL_LEGENDARY_CHANCE_NORMAL;
    return ModConfig.MATERIAL_DROP_CHANCE * Math.min(1, base * mult);
}

function origLegendaryMaterial(rank: Rank, dread: boolean): number {
    return ORIGINAL.MATERIAL_DROP_CHANCE_BY_RANK[rank] * (dread ? ORIGINAL.MATERIAL_RARITY.dread.L : ORIGINAL.MATERIAL_RARITY.normal.L);
}

function bossIdols(level: number): number {
    const share = Math.min(1, level / ModConfig.BOSS_IDOLS_TOP_LEVEL);
    return Math.max(ModConfig.BOSS_IDOLS_MIN, Math.round(ModConfig.BOSS_IDOLS_TOP * share * share));
}

// --- chart: horizontal paired bars, original vs mod, one value axis ------------------

type Row = { label: string; original: number; mod: number };

function barChart(title: string, unit: string, rows: Row[], format: (v: number) => string = pct): string {
    const max = Math.max(...rows.map((r) => Math.max(r.original, r.mod)), 1e-9);
    const labelW = 104, plotW = 300, valueW = 64, barH = 12, gap = 2, rowGap = 14;
    const rowH = barH * 2 + gap;
    const height = rows.length * (rowH + rowGap) + 6;
    const width = labelW + plotW + valueW;
    const bar = (y: number, value: number, series: 'original' | 'mod', row: Row) => {
        const w = Math.max(value > 0 ? 3 : 0, (value / max) * plotW);
        const name = series === 'original' ? 'Original' : 'This mod';
        const tip = `${row.label} · ${name}: ${format(value)}`;
        return `<g class="mark"><title>${esc(tip)}</title>`
            + `<rect class="hit" x="${labelW}" y="${y - 2}" width="${plotW + valueW}" height="${barH + 4}"/>`
            + (w > 0 ? `<rect class="bar ${series}" x="${labelW}" y="${y}" width="${w.toFixed(1)}" height="${barH}" rx="4"/>` : '')
            + `<text class="value" x="${labelW + w + 6}" y="${y + barH - 2}">${esc(format(value))}</text></g>`;
    };
    let body = `<line class="baseline" x1="${labelW}" y1="0" x2="${labelW}" y2="${height - 4}"/>`;
    rows.forEach((row, i) => {
        const y = 4 + i * (rowH + rowGap);
        body += `<text class="label" x="${labelW - 8}" y="${y + rowH / 2 + 4}" text-anchor="end">${esc(row.label)}</text>`;
        body += bar(y, row.original, 'original', row);
        body += bar(y + barH + gap, row.mod, 'mod', row);
    });
    const table = '<table><thead><tr><th></th><th>Original</th><th>This mod</th></tr></thead><tbody>'
        + rows.map((r) => `<tr><td>${esc(r.label)}</td><td>${esc(format(r.original))}</td><td>${esc(format(r.mod))}</td></tr>`).join('')
        + '</tbody></table>';
    return `<figure class="chart"><figcaption>${esc(title)}<span>${esc(unit)}</span></figcaption>`
        + `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}">${body}</svg>`
        + `<details><summary>Show as a table</summary>${table}</details></figure>`;
}

function card(title: string, tag: string, body: string, wide = false): string {
    return `<section class="card${wide ? ' wide' : ''}"><h3>${esc(title)}<span class="tag">${esc(tag)}</span></h3>${body}</section>`;
}

function list(items: string[]): string {
    return '<ul>' + items.filter(Boolean).map((i) => `<li>${i}</li>`).join('') + '</ul>';
}

function stat(value: string, label: string, was: string): string {
    return `<div class="stat"><b>${value}</b><span>${esc(label)}</span><em>was ${esc(was)}</em></div>`;
}

export function renderHomePage(gameUrl: string): string {
    const c = ModConfig;
    const legendaryRows: Row[] = (['Lieutenant', 'MiniBoss', 'Boss'] as Rank[]).map((r) => ({
        label: RANK_LABEL[r],
        original: (ORIGINAL.GEAR_LEGENDARY_PER_KILL.dread as Record<string, number>)[r] ?? 0,
        mod: modDreadLegendaryPerKill(r)
    }));
    legendaryRows.unshift({ label: 'Minion', original: 0, mod: modDreadLegendaryPerKill('Minion') });
    const rareRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r],
        original: (ORIGINAL.GEAR_RARE_PER_KILL.normal as Record<string, number>)[r] ?? 0,
        mod: modNormalRarePerKill(r)
    }));
    const gearRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r], original: ORIGINAL.GEAR_DROP_CHANCE_BY_RANK[r], mod: modGearChance(r, false)
    }));
    const matRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r], original: origLegendaryMaterial(r, true), mod: modLegendaryMaterial(r, true)
    }));
    const matNormalRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r], original: origLegendaryMaterial(r, false), mod: modLegendaryMaterial(r, false)
    }));
    const dyeRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r], original: ORIGINAL.DYE_DROP_CHANCE_BY_RANK[r], mod: c.DYE_DROP_CHANCE_BY_RANK[r]
    }));
    const troveRows: Row[] = RANKS.map((r) => ({
        label: RANK_LABEL[r], original: ORIGINAL.TROVE_DROP_CHANCE, mod: c.TROVE_DROP_CHANCE_BY_RANK[r]
    }));
    const idolRows: Row[] = [
        ['Cemetery Hill', 11], ['Dread Cemetery Hill', 26], ['Valhaven', 30],
        ['Dread Emerald Glades', 35], ['Dread Shazari', 40], ['Hardest Dread', c.BOSS_IDOLS_TOP_LEVEL]
    ].map(([label, level]) => ({ label: String(label), original: ORIGINAL.BOSS_IDOLS, mod: bossIdols(Number(level)) }));

    const bonusL = c.GEAR_COLLECTED_BONUS.legendary + c.GEAR_COLLECTED_RARE_BONUS;
    const bossL = modDreadLegendaryPerKill('Boss');
    const hunt = barChart('Legendary gear, chance per kill in Dread', 'per kill', legendaryRows)
        + list([
            '<b>No wasted Legendaries.</b> A drop never picks an item you already own at that rarity: it rerolls '
            + 'to one you are still missing, so every Legendary fills your collection.',
            `<b>Collection bonus:</b> own every item of an area and its drops get +${pct(c.GEAR_COLLECTED_BONUS.rare)} Rare `
            + `and +${pct(c.GEAR_COLLECTED_BONUS.legendary)} Legendary; own them all at Rare and Legendary gets another `
            + `+${pct(c.GEAR_COLLECTED_RARE_BONUS)} (a Dread boss: ${pct(bossL)} → up to ${pct(atLeastOnce(Math.min(1, modGearChance('Boss', true)) * (c.DREAD_BOSS_LEGENDARY_CHANCE + bonusL), c.DREAD_BOSS_GEAR_DROPS))} per kill).`,
            `<b>Gear Find</b> (pets, charms, potions) counts twice: +100% Gear Find doubles how often gear drops and lifts `
            + `Rare and Legendary by ${pct(c.GEAR_FIND_RARITY_EFFECT)} of itself (Legendary up to ${pct(c.GEAR_FIND_MAX_LEGENDARY)}).`,
            `Dread bosses roll their gear <b>${c.DREAD_BOSS_GEAR_DROPS} times</b>.`
        ]);

    const cards = [
        card('The Legendary hunt', 'Gear', hunt, true),
        card('Gear drops', 'Gear', barChart('Any gear item, chance per kill (normal dungeons)', 'per kill', gearRows)
            + barChart('A Rare item, chance per kill (normal dungeons)', 'per kill', rareRows)
            + `<p class="note">Dread doubles the drop chance.</p>`),
        card('Legendary crafting materials', 'Materials', barChart('Legendary material, chance per kill in Dread', 'per kill', matRows)
            + barChart('Legendary material, chance per kill (normal dungeons)', 'per kill', matNormalRows)
            + `<p class="note">A material drops from every dungeon kill now (was ${pct(ORIGINAL.MATERIAL_DROP_CHANCE_BY_RANK.Minion)} for a minion). They stack: farm as many as you like.</p>`),
        card('Mammoth Idols from every boss', 'Idols', barChart('Mammoth Idols per boss', 'idols', idolRows, (v) => String(Math.round(v)))
            + `<p class="note">Every boss always drops idols; the tougher the boss, the more. Mini-bosses: ${pct(c.MINIBOSS_IDOL_CHANCE)} of the time.</p>`),
        card('Dyes', 'Dyes', barChart('A dye, chance per kill', 'per kill', dyeRows)
            + `<p class="note">Always a dye you don't own yet. Dread doubles the chance and adds Legendary dyes.</p>`),
        card('Treasure Troves and Dragon Keys', 'Loot', barChart('A Treasure Trove, chance per dungeon kill', 'per kill', troveRows)
            + `<p class="note">Dragon Keys drop at the same rates, rolled separately. Dread doubles both.</p>`)
    ].join('');

    const stats = [
        stat(`${c.XP_MULTIPLIER}×`, 'experience from monsters', '1×'),
        stat(`${c.QUEST_XP_MULTIPLIER}×`, 'experience from quests', '1×'),
        stat(`${c.QUEST_GOLD_MULTIPLIER}×`, 'gold from quests', '1×'),
        stat(`${c.BOSS_IDOLS_TOP}`, 'idols from the hardest boss', '0')
    ].join('');

    return PAGE.replace('{{GAME_URL}}', gameUrl).replace('{{STATS}}', stats).replace('{{CARDS}}', cards);
}

const PAGE = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dungeon Blitz</title>
<style>
:root {
  --bg: #17110b; --panel: #2b1d0e; --line: #5a4420;
  --gold: #e8c45a; --cream: #f5e6c8; --muted: #c7b48f;
  --series-original: #3987e5; --series-mod: #d95926;
}
* { box-sizing: border-box; }
body { margin: 0; color: var(--cream); background: var(--bg); font: 16px/1.55 "Segoe UI", Tahoma, sans-serif; }
.hero { text-align: center; padding: 52px 16px 40px; border-bottom: 3px solid var(--line);
  background: linear-gradient(rgba(23,17,11,.55), var(--bg)), url("/background.webp") center/cover; }
.hero h1 { margin: 0; font-size: clamp(34px, 7vw, 64px); letter-spacing: 2px; color: var(--gold);
  text-shadow: 0 3px 0 #5a3a08, 0 6px 18px #000; }
.hero .sub { margin: 6px 0 22px; color: var(--muted); font-size: 18px; }
.play { display: inline-block; padding: 14px 54px; border-radius: 30px; font-size: 24px; font-weight: 700;
  color: #2b1600; text-decoration: none; letter-spacing: 1px; background: linear-gradient(#ffd96a, #d08a10);
  border: 3px solid #f0e0a0; box-shadow: 0 6px 0 #6b4a1a, 0 10px 24px rgba(0,0,0,.6); }
.play:hover { filter: brightness(1.1); }
.stats { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 28px; }
.stat { background: rgba(43,29,14,.88); border: 2px solid var(--line); border-radius: 12px; padding: 10px 18px; min-width: 150px; }
.stat b { display: block; font-size: 26px; color: var(--gold); font-variant-numeric: tabular-nums; }
.stat span { display: block; color: var(--cream); font-size: 14px; }
.stat em { color: var(--muted); font-size: 12px; font-style: normal; }
.intro { max-width: 820px; margin: 0 auto; padding: 34px 16px 0; text-align: center; }
.intro h2 { color: var(--gold); margin: 0 0 12px; font-size: 28px; }
.intro p { font-size: 17px; margin: 10px 0; }
main { max-width: 1100px; margin: 0 auto; padding: 30px 16px 50px; }
main > h2 { color: var(--gold); text-align: center; margin: 0 0 8px; }
.legend { display: flex; gap: 22px; justify-content: center; margin: 0 0 20px; color: var(--muted); font-size: 14px; }
.legend i { display: inline-block; width: 14px; height: 14px; border-radius: 4px; margin-right: 6px; vertical-align: -2px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr)); gap: 18px; }
.card { background: var(--panel); border: 2px solid var(--line); border-radius: 14px; padding: 18px 20px; min-width: 0; }
.card.wide { grid-column: 1 / -1; }
.card h3 { margin: 0 0 8px; color: var(--gold); display: flex; align-items: center; gap: 10px; }
.tag { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--panel); background: var(--gold); border-radius: 10px; padding: 1px 8px; }
.chart { margin: 10px 0 14px; }
.chart figcaption { font-size: 14px; color: var(--cream); margin-bottom: 6px; }
.chart figcaption span { color: var(--muted); margin-left: 8px; font-size: 12px; }
.chart svg { width: 100%; height: auto; max-width: 520px; display: block; overflow: visible; }
.chart .bar.original { fill: var(--series-original); }
.chart .bar.mod { fill: var(--series-mod); }
.chart .hit { fill: transparent; }
.chart .mark:hover .hit { fill: rgba(245,230,200,.06); }
.chart .label { fill: var(--muted); font-size: 12px; }
.chart .value { fill: var(--cream); font-size: 11px; font-variant-numeric: tabular-nums; }
.chart .baseline { stroke: var(--line); stroke-width: 1; }
details { font-size: 13px; color: var(--muted); }
details table { border-collapse: collapse; margin-top: 6px; }
details td, details th { padding: 3px 10px; border-bottom: 1px solid var(--line); text-align: right; }
details td:first-child, details th:first-child { text-align: left; }
.note { color: var(--muted); font-size: 14px; margin: 6px 0 0; }
ul { margin: 6px 0 0; padding-left: 20px; } li { margin: 6px 0; }
footer { text-align: center; color: var(--muted); font-size: 13px; padding: 0 16px 30px; }
</style>
</head>
<body>
<header class="hero">
  <h1>DUNGEON BLITZ</h1>
  <p class="sub">For the Older Generation: a modded, fan-preserved version of the game</p>
  <a class="play" href="{{GAME_URL}}">PLAY</a>
  <div class="stats">{{STATS}}</div>
</header>
<section class="intro">
  <h2>Dungeon Blitz for the Older Generation</h2>
  <p>We grew up with Dungeon Blitz. We are older now: jobs, families, less time.</p>
  <p>Dungeon Blitz is an amazing game, but it was built around waiting and grinding: Legendary drops so rare
  most of us never finished a set. This version keeps the adventure (every dungeon, every boss, every
  story beat) and makes the progression fit the time we actually have.</p>
</section>
<main>
  <h2>How much better the loot is</h2>
  <div class="legend"><span><i style="background:var(--series-original)"></i>Original</span><span><i style="background:var(--series-mod)"></i>This mod</span></div>
  <div class="grid">{{CARDS}}</div>
</main>
<footer>A non-commercial fan preservation project. Close the "Dungeon Blitz Server" window to stop the server.</footer>
</body>
</html>
`;
