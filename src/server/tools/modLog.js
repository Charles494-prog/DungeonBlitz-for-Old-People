// Server log for the single-player launcher (Play Dungeon Blitz.bat).
// - Every console line also goes to logs/server.log, written in the background (a
//   WriteStream), so logging never holds up the game. Piping the window through
//   PowerShell's Tee-Object did: Node waited on the slow pipe before answering the game,
//   so drops, quest progress and quest accept / turn-in lagged by many seconds.
// - The multiplayer-sync trace lines (thousands per dungeon, useless with one player)
//   are left out of both. Set MOD_LOG_VERBOSE=true to keep them.

const fs = require('fs');
const path = require('path');
const util = require('util');

const NOISY = [
    '[MultiplayerSync]',
    '[LootSync]',
    '  canonicalId='
];

function installModLog(env = process.env) {
    const file = env.MOD_LOG_FILE || path.resolve(__dirname, '..', '..', '..', 'logs', 'server.log');
    const verbose = String(env.MOD_LOG_VERBOSE || '').toLowerCase() === 'true';
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const out = fs.createWriteStream(file, { flags: 'w', encoding: 'utf8' });

    for (const level of ['log', 'info', 'warn', 'error', 'debug']) {
        const original = console[level].bind(console);
        console[level] = (...args) => {
            const text = util.format(...args);
            if (!verbose && NOISY.some((prefix) => text.startsWith(prefix))) {
                return;
            }
            original(text);
            out.write(text + '\n');
        };
    }
}

module.exports = { installModLog };
