"""
Make the game client show the same (shortened) timers the server uses.

The client computes countdowns from its own data, and no packet can change a
running timer, so with only the server scaled the client showed the original
times (a 10 day egg, a 4 hour Tome) until relog. This rewrites:
  - Game.swz: AbilityTypes and BuildingTypes <UpgradeTime>, using the same
    game_config functions as skills.py and buildings.py
  - DungeonBlitz-Local.swf: the egg hatch constants (class_16 const_993/1093/907,
    3/6/10 days) in the ActionScript constant pool, scaled like pets.py does

Originals are kept next to the files ("... - Original timers.swz/.swf") and
every run starts from them, so the patch can be re-run after changing game_config.

Usage (from the server folder): python tools/patch_client_timers.py
"""
import os
import re
import shutil
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = HERE  # this folder holds the patcher's data (data/, client_ui/) and game_config.py
PROJECT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, SERVER)

import game_config  # noqa: E402
from swz import read_swz, write_swz  # noqa: E402

CONTENT = os.path.join(PROJECT, "src", "client", "content", "localhost", "p")
GAME_SWZ = os.path.join(CONTENT, "cbq", "Game.swz")
# the server sends Game.<locale>.swz when there is one (StaticServer.getGameSwzPathForLocale)
GAME_SWZ_VARIANTS = [os.path.join(CONTENT, "cbq", name) for name in ("Game.swz", "Game.en.swz", "Game.tr.swz")]
CLIENT_SWF = os.path.join(CONTENT, "cbp", "DungeonBlitz.swf")
EGG_TIMES = [259200, 518400, 864000]  # class_16.const_993, const_1093, const_907


def original_of(path: str) -> str:
    base, ext = os.path.splitext(path)
    original = f"{base} - Original timers{ext}"
    if not os.path.exists(original):
        shutil.copy2(path, original)
    return original


ROYAL_STORE_JSON = os.path.join(SERVER, "data", "RoyalStoreTypes.json")


def _sync_royal_store(doc: str) -> str:
    """
    Make the client's Royal Sigil Store slots match data/RoyalStoreTypes.json (what
    royal_store.py sells). A Mount slot draws the mount's own icon, looked up by its
    RoyalStoreName (class_107 OnRefreshScreen), so a mount needs no IconName.
    """
    import json
    with open(ROYAL_STORE_JSON, encoding="utf-8") as f:
        items = {i["RoyalStoreID"]: i for i in json.load(f)}

    def repl(m):
        block = m.group(0)
        item = items.get(int(re.search(r"<RoyalStoreID>(\d+)<", block).group(1)))
        if not item or item["Type"] != "Mount" or f'RoyalStoreName="{item["Name"]}"' in block:
            return block
        indent = re.match(r"[ \t]*", block).group(0)
        fields = [("RoyalStoreID", item["RoyalStoreID"]), ("DisplayName", item["DisplayName"]),
                  ("IconName", ""), ("Quantity", 1), ("SigilCost", item["SigilCost"]),
                  ("Description", "Temp"), ("Category", "Special"), ("Type", "Mount"),
                  # an AfterOwned slot stays clickable once the mount is owned (class_107
                  # method_723 shows OWNED only with DisallowDupes): it sells that item then
                  ("DisallowDupes", "False" if item.get("AfterOwned") else "True")]
        body = "".join(f"\n{indent}\t<{k}>{v}</{k}>" for k, v in fields)
        return f'{indent}<RoyalStoreType RoyalStoreName="{item["Name"]}">{body}\n{indent}</RoyalStoreType>'

    return re.sub(r"[ \t]*<RoyalStoreType RoyalStoreName=.*?</RoyalStoreType>", repl, doc, flags=re.S)


LOGIN_SWZ = os.path.join(CONTENT, "cbp", "Login.swz")


def patch_login_swz():
    """
    Login.swz holds EntTypes: every mount runs at Speed 14 (a player walks at 11). The
    Legendary mounts (MountTypes DisplayRarity L) get game_config.LEGENDARY_MOUNT_SPEED.
    """
    import json
    key, docs = read_swz(original_of(LOGIN_SWZ))
    if not game_config.LEGENDARY_MOUNT_SPEED:
        write_swz(LOGIN_SWZ, key, docs)  # unchanged (riding speed: _patch_mount_buff_speed)
        print("Login.swz: unchanged")
        return
    with open(os.path.join(SERVER, "data", "MountTypes.json"), encoding="utf-8") as f:
        legendary = [m["Name"] for m in json.load(f) if m.get("Rarity") == "L"]
    changed = 0
    for i, doc in enumerate(docs):
        if "<EntTypes" not in doc[:300]:
            continue
        for name in legendary:
            pattern = re.compile(r'(<EntType EntName="%s"[^>]*>(?:(?!</EntType>).)*?<Speed>)[^<]*(</Speed>)' % re.escape(name), re.S)
            doc, n = pattern.subn(lambda m: f"{m.group(1)}{game_config.LEGENDARY_MOUNT_SPEED:g}{m.group(2)}", doc, count=1)
            changed += n
        docs[i] = doc
    write_swz(LOGIN_SWZ, key, docs)
    print(f"Login.swz: {changed} Legendary mount(s) at speed {game_config.LEGENDARY_MOUNT_SPEED:g} (others 14)")


def patch_game_swz():
    for path in GAME_SWZ_VARIANTS:
        if os.path.exists(path):
            _patch_one_game_swz(path)


def _patch_one_game_swz(game_swz: str):
    key, docs = read_swz(original_of(game_swz))
    scalers = {"AbilityTypes": game_config.scale_duration, "BuildingTypes": game_config.scale_building_duration}
    changed = 0
    for i, doc in enumerate(docs):
        root = re.match(r"\s*(?:<\?[^>]*>\s*)?<(\w+)", doc).group(1)
        if root == "RoyalStoreTypes":
            continue  # this server keeps its own Royal Sigil Store
        scale = scalers.get(root)
        if not scale:
            continue

        def repl(m):
            nonlocal changed
            new = scale(int(m.group(1)))
            changed += new != int(m.group(1))
            return f"<UpgradeTime>{new}</UpgradeTime>"

        docs[i] = re.sub(r"<UpgradeTime>(\d+)</UpgradeTime>", repl, doc)
    write_swz(game_swz, key, docs)
    print(f"{os.path.basename(game_swz)}: {changed} upgrade times shortened")


# --- client SWF: patch uint/int constant pool values -------------------------

def _u30(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return r, i


def _enc_u30(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


# Text constants replaced in the client. The Mammoth Idol "Buy" buttons post to
# PayPal (class_63.method_1131); send them to this server instead, which grants the
# idols (static_server.py, /buyidols).
STRING_PATCHES = {
    "https://www.paypal.com/cgi-bin/webscr": "http://localhost:8000/buyidols",
    # the trove window's prices are drawn in gold; its header tells the idol prices
    "BUY TREASURE TROVE?": "TROVES: {} / {} / {} IDOLS".format(*game_config.TROVE_IDOL_COST),
    "YOU RAN OUT OF TREASURE TROVES!": "OUT OF TROVES: {} / {} / {} IDOLS".format(*game_config.TROVE_IDOL_COST),
}


# Bytecode edits inside one named method: (method name, old bytes, new bytes).
# class_63.method_1131 (the idol "Buy" button) sets URLRequest.method = POST
# (getlex URLRequestMethod, getproperty POST, setproperty method). Browsers opening a
# new tab from Flash drop POST data, so the package was lost. Replace it with "pop"
# and nops: the request stays GET and the package travels in the query string.
CODE_PATCHES = [
    ("method_1131", bytes.fromhex("608a4666b83f61c93c"), bytes.fromhex("29") + bytes.fromhex("02") * 8),
    # Royal Sigil Store: "mRoyalSigils < cost -> do nothing" in the item click
    # (class_107.method_1212) and the Buy button (class_115.method_994). The sigil
    # count (getproperty mRoyalSigils) becomes pop + pushint 1000000000 (int pool
    # index 44), so the request reaches the server, which pays a shortfall in idols.
    ("method_1212", bytes.fromhex("66b20a6204ad"), bytes.fromhex("292d2c6204ad")),
    ("method_994", bytes.fromhex("66b20ad066d305669310ad"), bytes.fromhex("292d2cd066d305669310ad")),
    # Trove window (class_85): troves cost idols here, so "currGold < price" no longer
    # greys out the buttons (OnRefreshScreen) or blocks the click (method_994)
    ("OnRefreshScreen", bytes.fromhex("d166e80460fb23"), bytes.fromhex("d1292d2c60fb23")),
    ("method_994", bytes.fromhex("d366e80462050c"), bytes.fromhex("d3292d2c62050c")),
]


# Bytecode sequences that must occur exactly once in the whole ABC: (old, new).
# The Mammoth Idol store's packages (class_63 static init, const_103[i] = amount as
# getlex const_103, pushbyte i, pushshort amount). The window has five buttons, so
# the 375 pack becomes 1000 and the 1000 "Best Buy" pack becomes 10000. The server's
# static_server.IDOL_PACKAGES must match.
UNIQUE_PATCHES = [
    (bytes.fromhex("60d40a240325f702"), bytes.fromhex("60d40a240325e807")),  # [3] 375 -> 1000
    (bytes.fromhex("60d40a240425e807"), bytes.fromhex("60d40a2404259" "04e")),  # [4] 1000 -> 10000
]


# Static Number constants set to another value already in the double pool (the slot's
# value index is a single byte, so the new index must be < 128): the forge window's
# Rare / Legendary chance per Tempering point (class_8.const_968 / const_1072).
SLOT_PATCHES = {
    "const_968": game_config.FORGE_RARE_PER_TEMPERING,
    "const_1072": game_config.FORGE_LEGENDARY_PER_TEMPERING,
}


def _patch_slots(parsed, out: bytearray):
    hits = 0
    for name, at, vindex, vkind in parsed.slot_defaults:
        if name not in SLOT_PATCHES or vkind != 0x06 or vindex >= 128:
            continue
        wanted = float(SLOT_PATCHES[name])
        options = [i for i, v in enumerate(parsed.doubles[:128]) if i and v == wanted]
        if not options:
            raise SystemExit(f"{name}: {wanted} is not in the client's number pool; pick another value")
        out[at] = options[0]
        hits += 1
    return hits


# Timer tables built into the client's code as array literals (static initializers):
# (save name, values as the server knows them, first index that is a plain literal).
# Each element is rewritten in place with the same byte length; the resulting tables
# are saved to data/client_timers.json and the server uses exactly those values, so
# the client's countdown and the server's timer always agree.
def _timer_tables():
    from constants import class_66, class_7, class_8
    return [
        ("talent_research", list(class_66.RESEARCH_DURATIONS), 2),  # [1] is Game.const_181
        ("pet_training", list(class_7.const_797), 2),
        ("forge_charm", list(class_8.const_1055), 0),
    ]


CLIENT_TIMERS_JSON = os.path.join(SERVER, "data", "client_timers.json")


def _encode_timer(parsed, value: int, new: int, length: int):
    """Bytes of exactly `length` that push a value close to `new` (never above `value`)."""
    if new == value:
        return None, value
    if length >= 3 and 128 <= new < 16384:
        enc = bytes([0x25]) + _enc_u30(new)
        return enc + bytes([0x02]) * (length - len(enc)), new  # pushshort (+ nops)
    if length == 2:
        # pushint with a one-byte index: use the closest small-index pool value
        options = [(i, v) for i, v in enumerate(parsed.ints[:128])
                   if i and game_config.OTHER_TIMER_MIN_DURATION <= v <= min(value, game_config.OTHER_TIMER_MAX_DURATION)]
        if options:
            idx, v = min(options, key=lambda o: abs(o[1] - new))
            return bytes([0x2D, idx]), v
    return None, value


def _patch_timer_tables(parsed, abc: bytes, out: bytearray):
    tables = {}
    for name, values, start in _timer_tables():
        tail = values[start:]
        hits = []
        for method, code in parsed.bodies.items():
            pushes = parsed.literal_pushes(code)
            seq = [p[2] for p in pushes]
            for i in range(len(seq) - len(tail) + 1):
                if seq[i:i + len(tail)] == tail:
                    hits.append((code, pushes[i:i + len(tail)]))
        if len(hits) != 1 or abc.count(hits[0][0]) != 1:
            print(f"  {name}: not found exactly once, left unchanged")
            continue
        code, pushes = hits[0]
        base = abc.index(code)
        new_values = values[:start]
        for (offset, length, value, _kind) in pushes:
            enc, used = _encode_timer(parsed, int(value), game_config.scale_duration(int(value)), length)
            if enc:
                out[base + offset:base + offset + length] = enc
            new_values.append(used)
        tables[name] = new_values
        print(f"  {name}: longest {max(values)}s -> {max(new_values)}s")
    return tables


def _patch_code(abc: bytes):
    from swf_abc import Abc
    parsed = Abc(abc)
    if parsed.ints[44] != 1_000_000_000:
        raise SystemExit("int pool index 44 moved; fix the Royal Sigil Store patches")
    out = bytearray(abc)
    hits = 0
    tables = _patch_timer_tables(parsed, abc, out)
    if tables:
        import json
        with open(CLIENT_TIMERS_JSON, "w", encoding="utf-8") as f:
            json.dump(tables, f, indent=1)
        hits += len(tables)
    hits += _patch_slots(parsed, out)
    for old, new in UNIQUE_PATCHES:
        assert len(old) == len(new)
        if abc.count(old) != 1:
            raise SystemExit(f"pattern {old.hex()} found {abc.count(old)} times, expected 1")
        pos = abc.index(old)
        out[pos:pos + len(old)] = new
        hits += 1
    for name, old, new in CODE_PATCHES:
        assert len(old) == len(new)
        for method, mname in parsed.method_names.items():
            code = parsed.bodies.get(method)
            if mname != name or not code or old not in code:
                continue
            at = abc.find(code)
            if at < 0 or abc.find(code, at + 1) >= 0:
                raise SystemExit(f"can't locate {name} uniquely")
            pos = at + code.index(old)
            out[pos:pos + len(old)] = new
            hits += 1
    return bytes(out), hits


def _patch_strings(abc: bytes, replace: dict):
    """Rewrite the ABC string pool (lengths change, so the pool is re-encoded)."""
    i = 4
    for _pool in range(2):  # ints, uints
        n, i = _u30(abc, i)
        for _ in range(max(0, n - 1)):
            _, i = _u30(abc, i)
    n, i = _u30(abc, i)
    i += 8 * max(0, n - 1)  # doubles
    out = bytearray(abc[:i])
    n, i = _u30(abc, i)
    out += _enc_u30(n)
    hits = 0
    for _ in range(max(0, n - 1)):
        length, i = _u30(abc, i)
        text = abc[i:i + length]
        i += length
        new = replace.get(text.decode("utf-8", "replace"))
        if new is not None:
            text = new.encode("utf-8")
            hits += 1
        out += _enc_u30(len(text)) + text
    out += abc[i:]
    return bytes(out), hits


def _patch_abc(abc: bytes, replace: dict):
    """
    Replace values in the ABC double pool. class_16's egg constants are
    "uint = 3600 * 24 * N", which the compiler folds into Number (double) slot
    defaults; no code pushes those doubles, while the int pool's 259200/518400
    are other code, so only the doubles are touched. Doubles are fixed size, so
    this is an in-place edit.
    """
    i = 4
    for _pool in range(2):  # skip ints and uints
        n, i = _u30(abc, i)
        for _ in range(max(0, n - 1)):
            _, i = _u30(abc, i)
    n, i = _u30(abc, i)
    out = bytearray(abc)
    hits = 0
    for k in range(max(0, n - 1)):
        at = i + 8 * k
        value = struct.unpack_from("<d", abc, at)[0]
        if value in replace:
            struct.pack_into("<d", out, at, float(replace[value]))
            hits += 1
    return bytes(out), hits


# Rows added to the bottom of the chat options menu (the speech bubble button next to
# the chat box; class_127.method_1237 builds it): (text, keys shown, cmd, send, tip).
# send=True sends cmd as chat at once, False puts it in the chat box to finish typing.
# "!" commands are the server's (chat_commands.py).
CHAT_MENU_ROWS = [
    ("Mount shop", "!mounts", "!mounts", True, "List the mounts you can buy with Mammoth Idols"),
    ("Buy mount...", "!buymount <#>", "!buymount ", False, "Buy a mount by its # number in the Mount shop list"),
    ("Buy gold...", "!buygold <idols>", "!buygold ", False,
     f"Trade Mammoth Idols for gold (1 idol = {game_config.GOLD_PER_IDOL:,} gold)"),
    ("Buy sigils...", "!buysigils <idols>", "!buysigils ", False,
     f"Trade Mammoth Idols for Royal Sigils (1 idol = {game_config.SIGILS_PER_IDOL} sigils)"),
    ("Widescreen 16:9", "!widescreen", "!widescreen", True, "Switch between the 16:9 and the original 3:2 view"),
]


def _add_strings(abc: bytes, strings):
    """Append strings missing from the ABC string pool: (abc, {string: pool index})."""
    i = 4
    for _pool in range(2):  # ints, uints
        n, i = _u30(abc, i)
        for _ in range(max(0, n - 1)):
            _, i = _u30(abc, i)
    n, i = _u30(abc, i)
    i += 8 * max(0, n - 1)  # doubles
    count_at = i
    n, i = _u30(abc, i)
    index = {}
    for k in range(1, n):
        length, i = _u30(abc, i)
        index.setdefault(abc[i:i + length].decode("utf-8", "replace"), k)
        i += length
    added = bytearray()
    for s in strings:
        if s not in index:
            index[s] = n
            n += 1
            data = s.encode("utf-8")
            added += _enc_u30(len(data)) + data
    old_count = _u30(abc, count_at)[1]
    return abc[:count_at] + _enc_u30(n) + abc[old_count:i] + bytes(added) + abc[i:], index


def _insert_code(parsed, code: bytes, at: int, new: bytes) -> bytes:
    """Insert `new` before the instruction at `at`; branches that went to `at` now run it."""
    n = len(new)
    out = bytearray(code[:at] + new + code[at:])
    for start, _op, _end, branches in parsed.instructions(code):
        shift = n if start >= at else 0
        for operand, base, target in branches:
            offset = (target + (n if target > at else 0)) - (base + shift)
            if not -(1 << 23) <= offset < (1 << 23):
                raise SystemExit("chat menu: branch out of range")
            out[operand + shift:operand + shift + 3] = struct.pack("<i", offset)[:3]
    return bytes(out)


def _replace_instruction(parsed, code: bytes, at: int, end: int, new: bytes) -> bytes:
    """Swap the instruction code[at:end] for `new` (any length), fixing every branch."""
    delta = len(new) - (end - at)
    out = bytearray(code[:at] + new + code[end:])

    def moved(pos):
        return pos + delta if pos >= end else pos

    for start, _op, _end, branches in parsed.instructions(code):
        if start == at:
            continue
        shift = delta if start >= end else 0
        for operand, base, target in branches:
            if at < target < end:
                raise SystemExit("replace: a branch lands inside the replaced instruction")
            offset = moved(target) - moved(base)
            out[operand + shift:operand + shift + 3] = struct.pack("<i", offset)[:3]
    return bytes(out)


def _patch_chat_menu(abc: bytes):
    from swf_abc import Abc
    abc, index = _add_strings(abc, [s for row in CHAT_MENU_ROWS for s in row if isinstance(s, str)])
    parsed = Abc(abc)
    ignore = b"\x2c" + _enc_u30(index["Ignore..."])
    found = [m for m, c in parsed.bodies.items() if ignore in c]
    if len(found) != 1:
        raise SystemExit("chat menu: method_1237 not found")
    method = found[0]
    start, code_at, code_end, exceptions = parsed.body_spans[method]
    if exceptions:
        raise SystemExit("chat menu: method_1237 has exception handlers")
    code = parsed.bodies[method]
    ops = parsed.instructions(code)
    if ops[-1][2] != len(code):
        raise SystemExit("chat menu: could not decode method_1237")

    # this.var_325.push(...), with the operands the method's own rows use
    menu = push = None
    for s, op, e, _ in ops:
        name = parsed.multinames[_u30(code, s + 1)[0]] if op in (0x66, 0x4F) else None
        if op == 0x66 and name == "var_325":
            menu = code[s + 1:e]
        elif op == 0x4F and name == "push" and code[e - 1] == 1:
            push = code[s + 1:e]
    if not menu or not push:
        raise SystemExit("chat menu: var_325.push not found")

    def pushstring(s):
        return b"\x2c" + _enc_u30(index[s])

    rows = b""
    for text, keys, cmd, send, tip in CHAT_MENU_ROWS:
        rows += b"\xd0\x66" + menu  # getlocal0, getproperty var_325
        for key, value in (("text", text), ("keys", keys), ("cmd", cmd), ("send", send), ("tip", tip)):
            rows += pushstring(key) + ((b"\x26" if value else b"\x27") if isinstance(value, bool) else pushstring(value))
        rows += b"\x55\x05\x4f" + push  # newobject 5, callpropvoid push 1

    # Before every reachable returnvoid (the obfuscated method can have dead ones)
    targets = {t for _, _, _, branches in ops for _, _, t in branches}
    returns = [s for k, (s, op, _, _) in enumerate(ops)
               if op == 0x47 and (s in targets or not k or ops[k - 1][1] not in (0x03, 0x10, 0x1B, 0x47, 0x48))]
    for at in sorted(returns, reverse=True):
        code = _insert_code(parsed, code, at, rows)
    # a row needs 12 stack slots (receiver, 5 key/value pairs, the object)
    return _write_body(abc, parsed, method, code, 12), len(returns)


def _write_body(abc: bytes, parsed, method: int, code: bytes, extra_stack: int) -> bytes:
    """Put a method's new code (and a bigger max_stack) back into the ABC."""
    start, code_at, code_end, _exceptions = parsed.body_spans[method]
    header = abc[start:code_at]
    method_index, i = _u30(header, 0)
    max_stack, i = _u30(header, i)
    scopes = header[i:_skip_u30s(header, i, 3)]  # local_count, init / max scope depth
    new_header = _enc_u30(method_index) + _enc_u30(max_stack + extra_stack) + scopes
    return abc[:start] + new_header + _enc_u30(len(code)) + code + abc[code_end:]


def _skip_u30s(b: bytes, i: int, count: int) -> int:
    for _ in range(count):
        _, i = _u30(b, i)
    return i


# 16:9 (game_config.WIDESCREEN): Camera.SCREEN_WIDTH is the width of the game's view;
# Main.method_561 fits SCREEN_WIDTH x SCREEN_HEIGHT (768) into the window, so 1366
# fills a 16:9 window instead of leaving bars beside a 1152-wide (3:2) view.
WIDESCREEN_WIDTH = 1366


def _add_int(abc: bytes, value: int):
    """Append an int to the ABC int pool: (abc, its index)."""
    n, i = _u30(abc, 4)
    end = i
    for _ in range(max(0, n - 1)):
        _, end = _u30(abc, end)
    return abc[:4] + _enc_u30(max(n, 1) + 1) + abc[i:end] + _enc_u30(value & 0xFFFFFFFF) + abc[end:], max(n, 1)


def _add_double(abc: bytes, value: float):
    """Append a double to the ABC double pool: (abc, its index)."""
    i = 4
    for _pool in range(2):  # ints, uints
        n, i = _u30(abc, i)
        for _ in range(max(0, n - 1)):
            _, i = _u30(abc, i)
    count_at = i
    n, i = _u30(abc, i)
    end = i + 8 * max(0, n - 1)
    return (abc[:count_at] + _enc_u30(max(n, 1) + 1) + abc[i:end] + struct.pack("<d", float(value))
            + abc[end:], max(n, 1))


def _set_slot(abc: bytes, name: str, value) -> bytes:
    """Give the one static constant called `name` a new value (int or Number slot)."""
    from swf_abc import Abc
    slots = [s for s in Abc(abc).slot_defaults if s[0] == name and s[3] in (0x03, 0x06)]
    if len(slots) != 1:
        raise SystemExit(f"{name}: found {len(slots)} slots, expected 1")
    abc, index = _add_int(abc, int(value)) if slots[0][3] == 0x03 else _add_double(abc, value)
    _name, at, _vindex, _kind = next(s for s in Abc(abc).slot_defaults if s[0] == name)
    return abc[:at] + _enc_u30(index) + abc[_u30(abc, at)[1]:]


# Dread revive wait (class_95: const_615 = 20 s in Hard mode, const_826 = 8 s normally;
# const_1188 = const_615 - const_400 (3 s) is the same wait for the death screen)
REVIVE_COUNTDOWN_LEAD_MS = 3000


def _patch_revive_timer(abc: bytes) -> bytes:
    wait = max(REVIVE_COUNTDOWN_LEAD_MS, int(game_config.DREAD_REVIVE_SECONDS * 1000))
    abc = _set_slot(abc, "const_615", wait)
    abc = _set_slot(abc, "const_1188", float(wait - REVIVE_COUNTDOWN_LEAD_MS))
    return _patch_revive_init(abc, wait)


def _patch_revive_init(abc: bytes, wait: int) -> bytes:
    """
    class_95's static initializer also assigns const_615 = 20000 (pushshort 20000, then
    initproperty / setproperty const_615), which overrode the slot default patched above:
    Dread deaths kept the 20 s wait. That push now pushes the wait too.
    """
    from swf_abc import Abc, _Reader
    parsed = Abc(abc)
    for method, code in parsed.bodies.items():
        ops = parsed.instructions(code)
        for k in range(len(ops) - 1):
            s, op, e, _b = ops[k]
            s2, op2, _e2, _b2 = ops[k + 1]
            if (op == 0x25 and _Reader(code, s + 1).u30() == 20000 and op2 in (0x61, 0x68)
                    and parsed.multinames[_Reader(code, s2 + 1).u30()] == "const_615"):
                new = _replace_instruction(parsed, code, s, e, b"\x25" + _enc_u30(wait))  # pushshort wait
                return _write_body(abc, parsed, method, new, 0)
    raise SystemExit("revive timer: const_615 = 20000 not found in class_95's initializer")


def _patch_hide_news(abc: bytes) -> bytes:
    """
    The top-left event banner ("Double Pet XP Event": the live game's news, class_132)
    is opened by Game's world setup with this.var_1828.Display(). That call (getlocal0,
    getproperty var_1828, callpropvoid Display 0) becomes nops: no banner at all.
    """
    from swf_abc import Abc, _Reader
    parsed = Abc(abc)
    out = bytearray(abc)
    hits = 0
    for m, code in parsed.bodies.items():
        if parsed.method_class.get(m) != "Game":
            continue
        ops = parsed.instructions(code)
        for k in range(len(ops) - 2):
            (s0, op0, _e0, _b0), (s1, op1, _e1, _b1), (s2, op2, e2, _b2) = ops[k:k + 3]
            if (op0, op1, op2) != (0xD0, 0x66, 0x4F) or code[e2 - 1] != 0:
                continue
            if (parsed.multinames[_Reader(code, s1 + 1).u30()] == "var_1828"
                    and parsed.multinames[_Reader(code, s2 + 1).u30()] == "Display"):
                at = abc.find(code)
                out[at + s0:at + e2] = b"\x02" * (e2 - s0)
                hits += 1
    if hits != 1:
        raise SystemExit(f"news banner: found {hits} Display() calls, expected 1")
    return bytes(out)


def _patch_widescreen(abc: bytes) -> bytes:
    from swf_abc import Abc
    if not game_config.WIDESCREEN:
        return abc
    abc, index = _add_int(abc, WIDESCREEN_WIDTH)
    parsed = Abc(abc)
    slot = next((s for s in parsed.slot_defaults if s[0] == "SCREEN_WIDTH" and s[3] == 0x03), None)
    if slot is None:
        raise SystemExit("widescreen: Camera.SCREEN_WIDTH not found")
    _name, at, vindex, _kind = slot
    old_len = _u30(abc, at)[1] - at
    return abc[:at] + _enc_u30(index) + abc[at + old_len:]


# The Mount Merchant window (tools/client_ui/a_LocalText.as) is compiled into the
# client with FFDec (game_config.FFDEC_JAR), then MathUtil.method_259, which every
# server status message passes through (LinkUpdater.method_1844 ->
# ReadUnsafeStatusText), starts with  text = a_LocalText.mmHook(text):
# mount_merchant.py's "\x01MM|..." message opens the window instead of printing.
CLIENT_UI_DIR = os.path.join(HERE, "client_ui")


def _patch_status_hook(abc: bytes) -> bytes:
    from swf_abc import Abc
    parsed = Abc(abc)
    escape = b"\x2c" + _enc_u30(parsed.strings.index("&lt;"))
    found = [m for m, n in parsed.method_names.items()
             if n == "method_259" and escape in parsed.bodies.get(m, b"")]
    getlex = [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"]
    hook = [i for i, n in enumerate(parsed.multinames) if n == "mmHook"]
    if len(found) != 1 or not getlex or not hook:
        raise SystemExit("client UI: MathUtil.method_259 or a_LocalText.mmHook not found")
    code = parsed.bodies[found[0]]
    if parsed.body_spans[found[0]][3]:
        raise SystemExit("client UI: method_259 has exception handlers")
    # getlex a_LocalText, getlocal1, callproperty mmHook(1), coerce_s, setlocal1
    call = (b"\x60" + _enc_u30(_class_multiname(parsed, getlex)) + b"\xd1\x46"
            + _enc_u30(hook[0]) + b"\x01\x85\xd5")
    abc = _write_body(abc, parsed, found[0], _insert_code(parsed, code, 0, call), 3)
    return _patch_keep_talk_hook(abc)


def _patch_keep_talk_hook(abc: bytes) -> bytes:
    """
    In the keep the client handles NPC clicks itself (Game.method_1916(ent, cue,
    characterName)) and tells the server nothing, so the Stablemaster
    (Special_Stablemaster) had no shop. It now starts with a_LocalText.mmTalk(name).
    """
    from swf_abc import Abc
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "method_1916" and parsed.method_class.get(m) == "Game"]
    getlex = [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"]
    talk = [i for i, n in enumerate(parsed.multinames) if n == "mmTalk"]
    if len(found) != 1 or not talk or parsed.body_spans[found[0]][3]:
        raise SystemExit("client UI: Game.method_1916 or a_LocalText.mmTalk not found")
    # getlex a_LocalText, getlocal3 (characterName), callpropvoid mmTalk(1)
    call = b"\x60" + _enc_u30(_class_multiname(parsed, getlex)) + b"\xd3\x4f" + _enc_u30(talk[0]) + b"\x01"
    code = parsed.bodies[found[0]]
    abc = _write_body(abc, parsed, found[0], _insert_code(parsed, code, 0, call), 2)
    return _patch_mount_buff_speed(_patch_mount_combat_speed(_patch_gear_stats(_patch_gear_sort(_patch_loot_glow(_patch_idol_purchase(abc))))))


def _patch_gear_stats(abc: bytes) -> bytes:
    """
    GearType.method_121(stat, level) is an item's Attack / Expertise / Armor (the real
    stats: Entity.method_1457, powers, the tooltip). Each return now goes through
    a_LocalText.gearStat(this, stat, level, value): Rare and Legendary multiplied
    (game_config.GEAR_RARE / LEGENDARY_STAT_MULTIPLIER), a Legendary's missing stats filled.
    """
    from swf_abc import Abc
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "method_121" and parsed.method_class.get(m) == "GearType"]
    hook = [i for i, n in enumerate(parsed.multinames) if n == "gearStat"]
    if len(found) != 1 or not hook or parsed.body_spans[found[0]][3]:
        raise SystemExit("client UI: GearType.method_121 or a_LocalText.gearStat not found")
    getlex = _class_multiname(parsed, [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"])
    # value on the stack -> [a_LocalText, this, stat, level, value]: push each, swap it under
    # getlex a_LocalText, swap, getlocal0, swap, getlocal1, swap, getlocal2, swap,
    # callproperty gearStat(4), convert_u
    call = (b"\x60" + _enc_u30(getlex) + b"\x2b" + b"\xd0\x2b" + b"\xd1\x2b" + b"\xd2\x2b"
            + b"\x46" + _enc_u30(hook[0]) + b"\x04" + b"\x88")
    code = parsed.bodies[found[0]]
    returns = [s for s, op, _e, _b in parsed.instructions(code) if op == 0x48]
    for at in reversed(returns):  # the later ones first: earlier offsets stay put
        code = _insert_code(parsed, code, at, call)
    return _write_body(abc, parsed, found[0], code, 5)



def _patch_mount_buff_speed(abc: bytes) -> bytes:
    """
    Every mount rides on the same "Mounted" buff (PlayerBuffTypes SpeedChange 0.4: +40%);
    CombatState.method_322 copies its speedChange into var_2405, the riding bonus
    (Entity.RecalculateSpeed). That copy now goes through a_LocalText.mountSpeed(this,
    value): Rare and Legendary mounts ride faster (game_config.*_MOUNT_SPEED_BONUS).
    """
    from swf_abc import Abc, _Reader
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "method_322" and parsed.method_class.get(m) == "CombatState"]
    hook = [i for i, n in enumerate(parsed.multinames) if n == "mountSpeed"]
    if len(found) != 1 or not hook:
        raise SystemExit("client UI: CombatState.method_322 or a_LocalText.mountSpeed not found")
    code = parsed.bodies[found[0]]
    ops = parsed.instructions(code)
    sites = []
    for k in range(1, len(ops)):
        (s0, op0, _e0, _b0), (s1, op1, _e1, _b1) = ops[k - 1], ops[k]
        if (op0 == 0x66 and op1 in (0x61, 0x68)
                and parsed.multinames[_Reader(code, s0 + 1).u30()] == "speedChange"
                and parsed.multinames[_Reader(code, s1 + 1).u30()] == "var_2405"):
            sites.append(s1)
    if len(sites) != 1:
        raise SystemExit(f"client UI: var_2405 = speedChange found {len(sites)} times in method_322, expected 1")
    getlex = _class_multiname(parsed, [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"])
    # [this, value] -> getlex a_LocalText, swap, getlocal0, swap, callproperty mountSpeed(2)
    call = b"\x60" + _enc_u30(getlex) + b"\x2b\xd0\x2b\x46" + _enc_u30(hook[0]) + b"\x02"
    code = _insert_code(parsed, code, sites[0], call)
    return _write_body(abc, parsed, found[0], code, 3)


def _patch_mount_combat_speed(abc: bytes) -> bytes:
    """
    Entity.RecalculateSpeed: a rider keeps the mount's speed only while not attacking
    (combatState.var_2173), so every swing slowed the horse to walking pace. With
    game_config.MOUNT_KEEPS_SPEED_IN_COMBAT the check reads false: full speed while fighting.
    """
    from swf_abc import Abc, _Reader
    if not game_config.MOUNT_KEEPS_SPEED_IN_COMBAT:
        return abc
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "RecalculateSpeed" and parsed.method_class.get(m) == "Entity"]
    if len(found) != 1:
        raise SystemExit("client UI: Entity.RecalculateSpeed not found")
    code = parsed.bodies[found[0]]
    reads = [(s, e) for s, op, e, _b in parsed.instructions(code)
             if op == 0x66 and parsed.multinames[_Reader(code, s + 1).u30()] == "var_2173"]
    if len(reads) != 1:
        raise SystemExit(f"client UI: RecalculateSpeed reads var_2173 {len(reads)} times, expected 1")
    at, end = reads[0]
    code = _replace_instruction(parsed, code, at, end, b"\x29\x27")  # pop combatState, pushfalse
    return _write_body(abc, parsed, found[0], code, 0)


def _patch_gear_sort(abc: bytes) -> bytes:
    """
    The armory's gear list (ScreenArmory.method_2040) is built in the game's gear-table
    order, rarities mixed. Its return now passes the list through a_LocalText.sortGear,
    which puts Legendary first, then Rare, then Magic.
    """
    from swf_abc import Abc
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "method_2040" and parsed.method_class.get(m) == "ScreenArmory"]
    sort = [i for i, n in enumerate(parsed.multinames) if n == "sortGear"]
    if len(found) != 1 or not sort:
        raise SystemExit("client UI: ScreenArmory.method_2040 or a_LocalText.sortGear not found")
    code = parsed.bodies[found[0]]
    returns = [s for s, op, _e, _b in parsed.instructions(code) if op == 0x48]
    if len(returns) != 1:
        raise SystemExit(f"client UI: method_2040 has {len(returns)} returns, expected 1")
    getlex = _class_multiname(parsed, [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"])
    # dup (the list), getlex a_LocalText, swap, callpropvoid sortGear(1), returnvalue
    call = b"\x2a\x60" + _enc_u30(getlex) + b"\x2b\x4f" + _enc_u30(sort[0]) + b"\x01"
    return _write_body(abc, parsed, found[0], _insert_code(parsed, code, returns[0], call), 2)


LOOT_GLOW = 4279367708  # 0xFF11F81C: the green GlowFilter of every gear drop (Loot's constructor)


def _patch_loot_glow(abc: bytes) -> bytes:
    """
    Gear on the ground (Loot) always glowed green: new GlowFilter(0x11F81C). The colour
    becomes a_LocalText.lootGlow(gearType, 0x11F81C): Magic green, Rare blue, Legendary
    gold. The outline is also drawn thicker and brighter than GlowFilter's default
    (blur 6, strength 2): game_config.LOOT_GLOW_BLUR / LOOT_GLOW_STRENGTH.
    gearType is the constructor's 4th parameter (register 4).
    """
    from swf_abc import Abc, _Reader
    parsed = Abc(abc)
    found = []
    for m, code in parsed.bodies.items():
        ops = parsed.instructions(code)
        for k in range(len(ops) - 1):
            s, op, e, _b = ops[k]
            if (op == 0x2F and parsed.doubles[_Reader(code, s + 1).u30()] == float(LOOT_GLOW)
                    and ops[k + 1][1] == 0x4A
                    and parsed.multinames[_Reader(code, e + 1).u30()] == "GlowFilter"):
                found.append((m, s, e, ops[k + 1][2]))
    glow = [i for i, n in enumerate(parsed.multinames) if n == "lootGlow"]
    if len(found) != 1 or not glow:
        raise SystemExit(f"client UI: loot glow found {len(found)} times / a_LocalText.lootGlow missing")
    method, at, end, construct_end = found[0]
    code = parsed.bodies[method]
    targets = {t for _s, _o, _e, branches in parsed.instructions(code) for _a, _b, t in branches}
    if end in targets:
        raise SystemExit("client UI: a branch lands on the loot GlowFilter call")
    getlex = _class_multiname(parsed, [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"])
    construct = code[end:construct_end]  # constructprop <GlowFilter> <argc>
    if construct[-1] != 1:
        raise SystemExit("client UI: the loot GlowFilter isn't built from just a colour")
    # ... getlex a_LocalText, getlocal 4, pushdouble colour, callproperty lootGlow(2),
    # pushbyte 1 (alpha), pushbyte blur, pushbyte blur, pushbyte strength, constructprop GlowFilter(5)
    blur, strength = game_config.LOOT_GLOW_BLUR, game_config.LOOT_GLOW_STRENGTH
    code = _replace_instruction(parsed, code, end, construct_end,
                                b"\x46" + _enc_u30(glow[0]) + b"\x02"
                                + bytes([0x24, 1, 0x24, blur, 0x24, blur, 0x24, strength])
                                + construct[:-1] + b"\x05")
    code = _insert_code(parsed, code, at, b"\x60" + _enc_u30(getlex) + b"\x62\x04")
    return _write_body(abc, parsed, method, code, 4)


def _patch_idol_purchase(abc: bytes) -> bytes:
    """
    The Mammoth Idol window's Buy button (class_63.method_1131) did
    navigateToURL(request, "_blank"): a new browser tab for /buyidols. It now calls
    a_LocalText.mmLoadUrl(request, "_blank"), which sends the same request in the
    background (static_server grants the idols and the game updates the balance).
    """
    from swf_abc import Abc, _Reader
    parsed = Abc(abc)
    found = [m for m, n in parsed.method_names.items()
             if n == "method_1131" and parsed.method_class.get(m) == "class_63"]
    load = [i for i, n in enumerate(parsed.multinames) if n == "mmLoadUrl"]
    if len(found) != 1 or not load:
        raise SystemExit("client UI: class_63.method_1131 or a_LocalText.mmLoadUrl not found")
    code = parsed.bodies[found[0]]
    ops = parsed.instructions(code)
    nav = [(s, op, e) for s, op, e, _b in ops if op in (0x5D, 0x4F)
           and parsed.multinames[_Reader(code, s + 1).u30()] == "navigateToURL"]
    if [op for _s, op, _e in nav] != [0x5D, 0x4F]:
        raise SystemExit("client UI: navigateToURL call not found in method_1131")
    (find_at, _op1, find_end), (call_at, _op2, call_end) = nav
    getlex = _class_multiname(parsed, [i for i, n in enumerate(parsed.multinames) if n == "a_LocalText"])
    code = _replace_instruction(parsed, code, call_at, call_end, b"\x4f" + _enc_u30(load[0]) + b"\x02")
    # the later instruction first, so find_at is still where it was
    code = _replace_instruction(parsed, code, find_at, find_end, b"\x60" + _enc_u30(getlex))
    return _write_body(abc, parsed, found[0], code, 0)


def _class_multiname(parsed, candidates):
    """The a_LocalText multiname the game's own code reads it with (getlex)."""
    from swf_abc import _Reader
    for m, body in parsed.bodies.items():
        for s, op, _e, _b in parsed.instructions(body):
            if op == 0x60 and _Reader(body, s + 1).u30() in candidates:
                return _Reader(body, s + 1).u30()
    return candidates[0]


def _rewrite_abc(src: str, dst: str, fn):
    """Rewrite the DoABC2 tag of a SWF with fn(abc) -> abc."""
    raw = open(src, "rb").read()
    body = zlib.decompress(raw[8:]) if raw[:3] == b"CWS" else raw[8:]
    nbits = body[0] >> 3
    pos = (5 + nbits * 4 + 7) // 8 + 4
    out = bytearray(body[:pos])
    while pos < len(body):
        code_len = struct.unpack_from("<H", body, pos)[0]
        code, length = code_len >> 6, code_len & 0x3F
        header = 2
        if length == 0x3F:
            length = struct.unpack_from("<I", body, pos + 2)[0]
            header = 6
        data = body[pos + header:pos + header + length]
        if code == 82:
            name_end = data.index(b"\x00", 4) + 1
            data = data[:name_end] + fn(data[name_end:])
        out += struct.pack("<HI", (code << 6) | 0x3F, len(data)) + data
        pos += header + length
        if code == 0:
            break
    with open(dst, "wb") as f:
        f.write(b"CWS" + raw[3:4] + struct.pack("<I", len(out) + 8) + zlib.compress(bytes(out), 9))


CLIENT_UI_JSON = os.path.join(SERVER, "data", "client_ui.json")  # mount_merchant.client_has_window


def _write_client_ui(mount_merchant: bool):
    import json
    with open(CLIENT_UI_JSON, "w", encoding="utf-8") as f:
        json.dump({"mount_merchant": mount_merchant}, f)


UI_SETTINGS = {  # placeholders in a_LocalText.as -> game_config values
    "__MAGIC_STAT_MIN__": lambda: game_config.GEAR_STAT_RANGES["M"][0],
    "__MAGIC_STAT_MAX__": lambda: game_config.GEAR_STAT_RANGES["M"][1],
    "__RARE_STAT_MIN__": lambda: game_config.GEAR_STAT_RANGES["R"][0],
    "__RARE_STAT_MAX__": lambda: game_config.GEAR_STAT_RANGES["R"][1],
    "__LEGENDARY_STAT_MIN__": lambda: game_config.GEAR_STAT_RANGES["L"][0],
    "__LEGENDARY_STAT_MAX__": lambda: game_config.GEAR_STAT_RANGES["L"][1],
    "__LEGENDARY_EXTRA_STAT__": lambda: game_config.GEAR_LEGENDARY_EXTRA_STAT,
    "__RARE_MOUNT_SPEED__": lambda: game_config.RARE_MOUNT_SPEED_BONUS,
    "__LEGENDARY_MOUNT_SPEED__": lambda: game_config.LEGENDARY_MOUNT_SPEED_BONUS,
    "__PARAGON_STAT_BONUS__": lambda: game_config.PARAGON_STAT_BONUS_PER_LEVEL,
}


def _client_ui_source() -> str:
    """a_LocalText.as with game_config's numbers written in (a copy in client_ui/build)."""
    with open(os.path.join(CLIENT_UI_DIR, "a_LocalText.as"), encoding="utf-8") as f:
        text = f.read()
    for mark, value in UI_SETTINGS.items():
        text = text.replace(mark, repr(float(value())))
    build = os.path.join(CLIENT_UI_DIR, "build")
    os.makedirs(build, exist_ok=True)
    path = os.path.join(build, "a_LocalText.as")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def patch_client_ui():
    import subprocess
    _write_client_ui(False)  # patch_client_swf just wrote a client without it
    jar = os.path.expandvars(game_config.FFDEC_JAR)
    if not os.path.exists(jar):
        print(f"DungeonBlitz-Local.swf: FFDec not found at {jar}; no Mount Merchant window "
              f"(the stable NPC falls back to the chat list)")
        return
    compiled = CLIENT_SWF + ".ui.swf"
    source = _client_ui_source()
    result = subprocess.run(["java", "-jar", jar, "-replace", CLIENT_SWF, compiled, "a_LocalText", source],
                            capture_output=True, text=True, timeout=900)
    if result.returncode != 0 or not os.path.exists(compiled) or "SEVERE" in result.stderr + result.stdout:
        raise SystemExit("FFDec could not compile tools/client_ui/a_LocalText.as:\n" + result.stdout + result.stderr)
    _rewrite_abc(compiled, CLIENT_SWF, _patch_status_hook)
    os.remove(compiled)
    _write_client_ui(True)
    print("DungeonBlitz-Local.swf: Mount Merchant window compiled in")


def patch_client_swf():
    raw = open(original_of(CLIENT_SWF), "rb").read()
    if raw[:3] != b"CWS":
        raise SystemExit("unexpected SWF compression")
    body = zlib.decompress(raw[8:])
    nbits = body[0] >> 3
    pos = (5 + nbits * 4 + 7) // 8 + 4
    replace = {float(t): game_config.scale_duration(t) for t in EGG_TIMES}
    out = bytearray(body[:pos])
    total_hits = 0
    while pos < len(body):
        code_len = struct.unpack_from("<H", body, pos)[0]
        code, length = code_len >> 6, code_len & 0x3F
        header = 2
        if length == 0x3F:
            length = struct.unpack_from("<I", body, pos + 2)[0]
            header = 6
        data = body[pos + header:pos + header + length]
        if code == 82:  # DoABC2: flags, name, abc
            name_end = data.index(b"\x00", 4) + 1
            abc, code_hits = _patch_code(data[name_end:])
            print(f"DungeonBlitz-Local.swf: {code_hits} code patch(es) applied")
            abc, string_hits = _patch_strings(abc, STRING_PATCHES)
            abc, hits = _patch_abc(abc, replace)
            total_hits += hits
            abc, returns = _patch_chat_menu(abc)
            print(f"DungeonBlitz-Local.swf: chat menu gets {len(CHAT_MENU_ROWS)} shop rows ({returns} return point(s))")
            abc = _patch_widescreen(abc)
            abc = _patch_revive_timer(abc)
            abc = _patch_hide_news(abc)
            print("DungeonBlitz-Local.swf: event news banner hidden")
            print(f"DungeonBlitz-Local.swf: Dread revive wait {game_config.DREAD_REVIVE_SECONDS}s (was 20s)")
            print(f"DungeonBlitz-Local.swf: view {WIDESCREEN_WIDTH if game_config.WIDESCREEN else 1152}x768"
                  f" (game_config.WIDESCREEN = {game_config.WIDESCREEN})")
            print(f"DungeonBlitz-Local.swf: {string_hits} text constant(s) replaced {list(STRING_PATCHES.values())}")
            data = data[:name_end] + abc
        out += struct.pack("<HI", (code << 6) | 0x3F, len(data)) + data
        pos += header + length
        if code == 0:
            break
    swf = b"CWS" + raw[3:4] + struct.pack("<I", len(out) + 8) + zlib.compress(bytes(out), 9)
    with open(CLIENT_SWF, "wb") as f:
        f.write(swf)
    print(f"DungeonBlitz-Local.swf: egg hatch constants {replace} ({total_hits} pool entries)")


if __name__ == "__main__":
    patch_login_swz()
    patch_game_swz()
    patch_client_swf()
    patch_client_ui()
