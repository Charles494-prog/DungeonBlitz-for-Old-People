"""
Minimal SWF reader that extracts enemy placements (a_Cue instances) from the
game's level SWFs.

The original game spawned monsters from a_Cue MovieClips placed inside each
a_Room_* of an a_Level_* symbol. A cue's class is "ac_<EntType>" (see
Level.method_1130 in extra-modules/ActionScripts/Level.txt, entType =
className.slice(3)), and its world position is its transform concatenated
through room -> level (Game.method_234 uses localToGlobal).

Only frame 1 of every sprite is read, because rooms are shown with
gotoAndStop(1).
"""
import lzma
import struct
import zlib


class _Bits:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.byte = pos
        self.bit = 0

    def ub(self, n: int) -> int:
        v = 0
        for _ in range(n):
            b = (self.data[self.byte] >> (7 - self.bit)) & 1
            v = (v << 1) | b
            self.bit += 1
            if self.bit == 8:
                self.bit = 0
                self.byte += 1
        return v

    def sb(self, n: int) -> int:
        if n == 0:
            return 0
        v = self.ub(n)
        if v & (1 << (n - 1)):
            v -= 1 << n
        return v

    def align(self):
        if self.bit:
            self.bit = 0
            self.byte += 1


def _read_matrix(data: bytes, pos: int):
    """Returns ((a, b, c, d, tx, ty), new_pos). Translation is in twips."""
    br = _Bits(data, pos)
    a = d = 1.0
    b = c = 0.0
    if br.ub(1):
        n = br.ub(5)
        a = br.sb(n) / 65536.0
        d = br.sb(n) / 65536.0
    if br.ub(1):
        n = br.ub(5)
        b = br.sb(n) / 65536.0
        c = br.sb(n) / 65536.0
    n = br.ub(5)
    tx = br.sb(n) / 20.0
    ty = br.sb(n) / 20.0
    br.align()
    return (a, b, c, d, tx, ty), br.byte


def _read_cstring(data: bytes, pos: int):
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8", "replace"), end + 1


def _iter_tags(data: bytes, pos: int, end: int):
    while pos < end:
        code_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        code, length = code_len >> 6, code_len & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        yield code, data, pos, length
        pos += length
        if code == 0:
            return


def _parse_place(code: int, data: bytes, pos: int, length: int):
    """Parse PlaceObject2 (26) / PlaceObject3 (70). Returns dict or None."""
    end = pos + length
    flags = data[pos]
    pos += 1
    flags3 = 0
    if code == 70:
        flags3 = data[pos]
        pos += 1
    depth = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    has_class = flags3 & 0x08
    has_image = flags3 & 0x10
    if code == 70 and (has_class or (has_image and flags & 0x02)):
        _, pos = _read_cstring(data, pos)
    place = {"depth": depth, "move": bool(flags & 0x01)}
    if flags & 0x02:
        place["char"] = struct.unpack_from("<H", data, pos)[0]
        pos += 2
    if flags & 0x04:
        place["matrix"], pos = _read_matrix(data, pos)
    if flags & 0x08:
        # Colour transform with alpha; skip it.
        br = _Bits(data, pos)
        has_add, has_mult = br.ub(1), br.ub(1)
        n = br.ub(4)
        br.ub(n * 4 * (has_add + has_mult))
        br.align()
        pos = br.byte
    if flags & 0x10:
        pos += 2  # ratio
    if flags & 0x20:
        place["name"], pos = _read_cstring(data, pos)
    if pos > end:
        return None
    return place


def _mul(m1, m2):
    """m1 applied after m2 (child matrix m2 inside parent m1)."""
    a1, b1, c1, d1, tx1, ty1 = m1
    a2, b2, c2, d2, tx2, ty2 = m2
    return (
        a2 * a1 + b2 * c1,
        a2 * b1 + b2 * d1,
        c2 * a1 + d2 * c1,
        c2 * b1 + d2 * d1,
        tx2 * a1 + ty2 * c1 + tx1,
        tx2 * b1 + ty2 * d1 + ty1,
    )


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


class SwfLevels:
    def __init__(self, path: str):
        raw = open(path, "rb").read()
        sig = raw[:3]
        if sig == b"FWS":
            body = raw[8:]
        elif sig == b"CWS":
            body = zlib.decompress(raw[8:])
        elif sig == b"ZWS":
            # LZMA SWF: 4 bytes compressed length, 5 bytes props, then data.
            props = raw[12:17]
            body = lzma.LZMADecompressor(
                lzma.FORMAT_RAW,
                filters=[lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)],
            ).decompress(raw[17:])
        else:
            raise ValueError(f"{path}: not a SWF")
        nbits = body[0] >> 3
        pos = (5 + nbits * 4 + 7) // 8 + 4  # RECT + frame rate + frame count
        self.sprites = {}   # char id -> list of placements on frame 1
        self.classes = {}   # char id -> class name
        self.shapes = {}    # char id -> (tag code, tag bytes) of DefineShape1-4
        self._scan(body, pos, len(body))
        self.by_class = {name: cid for cid, name in self.classes.items()}

    def _scan(self, data, pos, end):
        for code, d, p, length in _iter_tags(data, pos, end):
            if code == 39:  # DefineSprite
                sprite_id = struct.unpack_from("<H", d, p)[0]
                self.sprites[sprite_id] = self._sprite_frame1(d, p + 4, p + length)
            elif code in SHAPE_TAGS:
                self.shapes[struct.unpack_from("<H", d, p)[0]] = (code, d[p:p + length])
            elif code == 76:  # SymbolClass
                count = struct.unpack_from("<H", d, p)[0]
                q = p + 2
                for _ in range(count):
                    cid = struct.unpack_from("<H", d, q)[0]
                    name, q = _read_cstring(d, q + 2)
                    self.classes[cid] = name

    @staticmethod
    def _sprite_frame1(data, pos, end):
        display = {}
        for code, d, p, length in _iter_tags(data, pos, end):
            if code in (26, 70):
                place = _parse_place(code, d, p, length)
                if not place:
                    continue
                if place["move"] and place["depth"] in display:
                    display[place["depth"]].update({k: v for k, v in place.items() if k != "move"})
                elif "char" in place:
                    display[place["depth"]] = place
            elif code in (5, 28):  # RemoveObject / RemoveObject2
                depth = struct.unpack_from("<H", d, p + (2 if code == 5 else 0))[0]
                display.pop(depth, None)
            elif code == 1:  # ShowFrame: frame 1 done
                break
        return [display[k] for k in sorted(display)]

    def cues(self, level_symbol: str):
        """
        Return (entType, x, y, rotation_deg, room_class, instance_name, group) for a level.
        group is the instance name of the "am_..." clip a cue sits in (a_Group in the
        client, Level.method_1130); cues in "am_Wave..." groups don't spawn on their
        own, a room script spawns them later.
        """
        root = self.by_class.get(level_symbol)
        if root is None:
            raise KeyError(level_symbol)
        out = []
        self._walk(root, IDENTITY, None, None, out, 0)
        return out

    def _walk(self, sprite_id, matrix, room, group, out, depth):
        if depth > 12:
            return
        for place in self.sprites.get(sprite_id, []):
            cid = place["char"]
            m = _mul(matrix, place.get("matrix", IDENTITY))
            cls = self.classes.get(cid, "")
            if cls.startswith("ac_"):
                import math
                rotation = math.degrees(math.atan2(m[1], m[0]))
                out.append((cls[3:], m[4], m[5], rotation, room, place.get("name", ""), group or ""))
            elif cid in self.sprites:
                child_room = cls if cls.startswith("a_Room_") else room
                name = place.get("name", "")
                child_group = name if name.startswith("am_") else (None if child_room != room else group)
                self._walk(cid, m, child_room, child_group, out, depth + 1)


# Collision lines
#####################################################

SHAPE_TAGS = {2: 1, 22: 2, 32: 3, 83: 4}  # DefineShape tag -> version

# Line colours the client turns into floors (DungeonBlitz.as: CollisionManager.method_77):
# red / magenta = soft floor (drop-through platform), cyan / blue = hard floor
FLOOR_COLOURS = {0xFF0000: True, 0xFF00FF: True, 0x00FFFF: False, 0x0000FF: False}


def _skip_rect(data, pos):
    br = _Bits(data, pos)
    n = br.ub(5)
    br.ub(n * 4)
    br.align()
    return br.byte


def _read_fill_styles(data, pos, version):
    count = data[pos]
    pos += 1
    if count == 0xFF and version >= 2:
        count = struct.unpack_from("<H", data, pos)[0]
        pos += 2
    colour = 4 if version >= 3 else 3
    for _ in range(count):
        kind = data[pos]
        pos += 1
        if kind == 0x00:
            pos += colour
        elif kind in (0x10, 0x12, 0x13):
            _, pos = _read_matrix(data, pos)
            n = data[pos] & 0x0F
            pos += 1 + n * (1 + colour)
            if kind == 0x13:
                pos += 2
        elif kind in (0x40, 0x41, 0x42, 0x43):
            _, pos = _read_matrix(data, pos + 2)
        else:
            raise ValueError(f"fill style {kind:#x}")
    return pos


def _read_line_styles(data, pos, version):
    count = data[pos]
    pos += 1
    if count == 0xFF:
        count = struct.unpack_from("<H", data, pos)[0]
        pos += 2
    colours = []
    for _ in range(count):
        pos += 2  # width
        if version == 4:
            flags = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            join = (flags >> 4) & 3
            has_fill = (flags >> 3) & 1
            if join == 2:
                pos += 2
            if has_fill:
                kind = data[pos]
                colours.append(int.from_bytes(data[pos + 1:pos + 4], "big") if kind == 0 else None)
                pos = _read_fill_styles(bytes([1]) + data[pos:], 0, 4) - 1 + pos
            else:
                colours.append(int.from_bytes(data[pos:pos + 3], "big"))
                pos += 4
        else:
            colours.append(int.from_bytes(data[pos:pos + 3], "big"))
            pos += 4 if version >= 3 else 3
    return pos, colours


CURVE_STEPS = 8  # straight pieces per curved edge


def shape_lines(code: int, tag: bytes):
    """[(colour, (x1, y1), (x2, y2))] in pixels; a curve (a quadratic Bezier: curved
    stairs, rounded hills) becomes CURVE_STEPS straight pieces that follow it, not one
    anchor-to-anchor chord, which ran far off a curved floor and dropped monsters."""
    version = SHAPE_TAGS[code]
    pos = _skip_rect(tag, 2)
    if version == 4:
        pos = _skip_rect(tag, pos) + 1
    pos = _read_fill_styles(tag, pos, version)
    pos, colours = _read_line_styles(tag, pos, version)
    br = _Bits(tag, pos)
    fill_bits, line_bits = br.ub(4), br.ub(4)
    x = y = 0
    line = 0
    out = []
    while True:
        if br.ub(1):  # edge
            straight = br.ub(1)
            n = br.ub(4) + 2
            if straight:
                if br.ub(1):
                    dx, dy = br.sb(n), br.sb(n)
                elif br.ub(1):
                    dx, dy = 0, br.sb(n)
                else:
                    dx, dy = br.sb(n), 0
            else:
                cx, cy = br.sb(n), br.sb(n)  # control point, then anchor, relative
                ax, ay = br.sb(n), br.sb(n)
                if line and line <= len(colours) and colours[line - 1] is not None:
                    px, py = x, y
                    for k in range(1, CURVE_STEPS + 1):
                        t = k / CURVE_STEPS
                        qx = x + 2 * (1 - t) * t * cx + t * t * (cx + ax)
                        qy = y + 2 * (1 - t) * t * cy + t * t * (cy + ay)
                        out.append((colours[line - 1], (px / 20.0, py / 20.0), (qx / 20.0, qy / 20.0)))
                        px, py = qx, qy
                x += cx + ax
                y += cy + ay
                continue
            if line and line <= len(colours) and colours[line - 1] is not None:
                out.append((colours[line - 1], (x / 20.0, y / 20.0), ((x + dx) / 20.0, (y + dy) / 20.0)))
            x += dx
            y += dy
            continue
        flags = br.ub(5)
        if not flags:
            break
        if flags & 0x01:
            n = br.ub(5)
            x, y = br.sb(n), br.sb(n)
        if flags & 0x02:
            br.ub(fill_bits)
        if flags & 0x04:
            br.ub(fill_bits)
        if flags & 0x08:
            line = br.ub(line_bits)
        if flags & 0x10:
            br.align()
            p = _read_fill_styles(tag, br.byte, version)
            p, colours = _read_line_styles(tag, p, version)
            br = _Bits(tag, p)
            fill_bits, line_bits = br.ub(4), br.ub(4)
            line = 0
    return out


def _apply(m, point):
    a, b, c, d, tx, ty = m
    x, y = point
    return a * x + c * y + tx, b * x + d * y + ty


def floors(swf: "SwfLevels", level_symbol: str):
    """
    The level's walkable lines in level coordinates: [(x1, y1, x2, y2, soft)], x1 <= x2.
    Like Level.as / class_154.method_444, they are the strokes inside each room's
    am_CollisionObject sprites; named am_ children (DynamicCollision gates, doors,
    triggers) are left out.
    """
    root = swf.by_class.get(level_symbol)
    if root is None:
        raise KeyError(level_symbol)
    out = []

    def walk(sprite_id, matrix, inside, depth):
        if depth > 14:
            return
        for place in swf.sprites.get(sprite_id, []):
            cid = place["char"]
            m = _mul(matrix, place.get("matrix", IDENTITY))
            name = place.get("name", "")
            if cid in swf.shapes:
                if inside:
                    for colour, p1, p2 in shape_lines(*swf.shapes[cid]):
                        if colour in FLOOR_COLOURS:
                            (x1, y1), (x2, y2) = sorted((_apply(m, p1), _apply(m, p2)))
                            if x1 != x2 or y1 != y2:
                                out.append((round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1),
                                            FLOOR_COLOURS[colour]))
            elif cid in swf.sprites:
                if name.startswith("am_CollisionObject"):
                    walk(cid, m, True, depth + 1)
                elif inside and name.startswith("am_"):
                    continue  # gates, doors, triggers
                else:
                    walk(cid, m, inside, depth + 1)

    walk(root, IDENTITY, False, 0)
    return out
