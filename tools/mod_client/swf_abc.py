"""
Read a_Cue property assignments out of a level SWF's ActionScript (DoABC).

Flash compiles the cue settings made in the editor into generated methods
named __setProp_<instance>_<room>_<layer>_<frame>, which look like:

    __id351_.bHoldSpawn = true;
    __id351_.characterName = "CH_Mayor01";
    __id351_.team = "neutral";

This module decodes just enough AVM2 bytecode to recover those
(instance, property, value) triples. Values are str/bool/number, or a list
for array literals (params).
"""
import struct
import zlib

from swf_cues import _iter_tags


class _Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def u30(self):
        result = shift = 0
        while True:
            b = self.d[self.p]
            self.p += 1
            result |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80 or shift >= 35:
                return result

    def s24(self):
        b = self.d[self.p:self.p + 3]
        self.p += 3
        v = b[0] | (b[1] << 8) | (b[2] << 16)
        return v - (1 << 24) if v & 0x800000 else v

    def bytes(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


class Abc:
    def __init__(self, data: bytes):
        r = _Reader(data)
        r.u16(); r.u16()
        n = r.u30()
        self.ints = [0] + [self._s32(r) for _ in range(max(0, n - 1))]
        n = r.u30()
        self.uints = [0] + [r.u30() for _ in range(max(0, n - 1))]
        n = r.u30()
        self.doubles = [0.0] + [struct.unpack("<d", r.bytes(8))[0] for _ in range(max(0, n - 1))]
        n = r.u30()
        self.strings = [""]
        for _ in range(max(0, n - 1)):
            length = r.u30()
            self.strings.append(r.bytes(length).decode("utf-8", "replace"))
        n = r.u30()
        for _ in range(max(0, n - 1)):
            r.u8(); r.u30()
        n = r.u30()
        for _ in range(max(0, n - 1)):
            for _ in range(r.u30()):
                r.u30()
        n = r.u30()
        self.multinames = [""]
        for _ in range(max(0, n - 1)):
            self.multinames.append(self._multiname(r))
        self.method_count = r.u30()
        for _ in range(self.method_count):
            pc = r.u30(); r.u30()
            for _ in range(pc):
                r.u30()
            r.u30()
            flags = r.u8()
            if flags & 0x08:
                for _ in range(r.u30()):
                    r.u30(); r.u8()
            if flags & 0x80:
                for _ in range(pc):
                    r.u30()
        for _ in range(r.u30()):
            r.u30()
            for _ in range(r.u30()):
                r.u30(); r.u30()
        class_count = r.u30()
        self.method_names = {}
        self.method_class = {}  # method index -> class name (instance methods)
        self.slot_defaults = []  # (slot name, byte offset of its value index, index, value kind)
        for _ in range(class_count):
            class_name = self.multinames[r.u30()]
            r.u30()
            flags = r.u8()
            if flags & 0x08:
                r.u30()
            for _ in range(r.u30()):
                r.u30()
            r.u30()
            before = set(self.method_names)
            self._traits(r)
            for method in set(self.method_names) - before:
                self.method_class[method] = class_name
        for _ in range(class_count):
            r.u30()
            self._traits(r)
        for _ in range(r.u30()):
            r.u30()
            self._traits(r)
        self.bodies = {}
        self.body_spans = {}  # method -> (body start, code start, code end, exception count)
        for _ in range(r.u30()):
            start = r.p
            method = r.u30()
            r.u30(); r.u30(); r.u30(); r.u30()
            code_len = r.u30()
            code_at = r.p
            code = r.bytes(code_len)
            exceptions = r.u30()
            for _ in range(exceptions):
                r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
            self._traits(r)
            self.bodies[method] = code
            self.body_spans[method] = (start, code_at, code_at + code_len, exceptions)

    @staticmethod
    def _s32(r):
        v = r.u30()
        return v - (1 << 32) if v & 0x80000000 else v

    def _multiname(self, r):
        kind = r.u8()
        if kind in (0x07, 0x0D):
            r.u30()
            return self.strings[r.u30()]
        if kind in (0x0F, 0x10):
            return self.strings[r.u30()]
        if kind in (0x11, 0x12):
            return ""
        if kind in (0x09, 0x0E):
            name = self.strings[r.u30()]
            r.u30()
            return name
        if kind in (0x1B, 0x1C):
            r.u30()
            return ""
        if kind == 0x1D:
            r.u30()
            for _ in range(r.u30()):
                r.u30()
            return ""
        raise ValueError(f"unknown multiname kind {kind:#x}")

    def _traits(self, r):
        for _ in range(r.u30()):
            name = self.multinames[r.u30()]
            kind = r.u8()
            k = kind & 0x0F
            if k in (0, 6):
                r.u30(); r.u30()
                at = r.p
                vindex = r.u30()
                if vindex:
                    self.slot_defaults.append((name, at, vindex, r.u8()))
            elif k in (1, 2, 3):
                r.u30()
                self.method_names[r.u30()] = name
            elif k in (4, 5):
                r.u30(); r.u30()
            if kind & 0x40:
                for _ in range(r.u30()):
                    r.u30()

    # Bytecode
    #####################################################

    _U30_1 = {0x04, 0x05, 0x06, 0x08, 0x2C, 0x2D, 0x2E, 0x2F, 0x31, 0x40, 0x41, 0x42, 0x49, 0x53, 0x55,
              0x56, 0x58, 0x59, 0x5A, 0x5D, 0x5E, 0x5F, 0x60, 0x61, 0x62, 0x63, 0x66, 0x68, 0x6A, 0x6C,
              0x6D, 0x6E, 0x6F, 0x80, 0x86, 0x92, 0x94, 0xB2, 0xC2, 0xC3, 0xF0, 0xF1, 0x25}
    _U30_2 = {0x32, 0x43, 0x44, 0x45, 0x46, 0x4A, 0x4C, 0x4E, 0x4F}

    def instructions(self, code: bytes):
        """[(start, opcode, end, [(s24 operand offset, base, target)])] for every instruction."""
        r = _Reader(code)
        out = []
        while r.p < len(code):
            start = r.p
            op = r.u8()
            branches = []
            if op in (0x24, 0x65):               # pushbyte, getscopeobject
                r.u8()
            elif op in self._U30_1:
                r.u30()
            elif op in self._U30_2:
                r.u30(); r.u30()
            elif 0x0C <= op <= 0x1A:             # branches: relative to the next instruction
                at = r.p
                offset = r.s24()
                branches.append((at, r.p, r.p + offset))
            elif op == 0x1B:                     # lookupswitch: relative to its own start
                at = r.p
                branches.append((at, start, start + r.s24()))
                for _ in range(r.u30() + 1):
                    at = r.p
                    branches.append((at, start, start + r.s24()))
            elif op == 0xEF:                     # debug
                r.u8(); r.u30(); r.u8(); r.u30()
            out.append((start, op, r.p, branches))
        return out

    def setprops(self, code: bytes):
        """Yield (instance, property, value) for `instance.property = literal` in a method."""
        r = _Reader(code)
        last_get = None   # last getproperty/getlex name: the object being set
        stack = []        # pushed literals
        while r.p < len(code):
            op = r.u8()
            if op == 0x24:                       # pushbyte
                b = r.u8()
                stack.append(b - 256 if b > 127 else b)
            elif op == 0x25:                     # pushshort
                stack.append(r.u30())
            elif op == 0x2C:
                stack.append(self.strings[r.u30()])
            elif op == 0x2D:
                stack.append(self.ints[r.u30()])
            elif op == 0x2E:
                stack.append(self.uints[r.u30()])
            elif op == 0x2F:
                stack.append(self.doubles[r.u30()])
            elif op == 0x26:
                stack.append(True)
            elif op == 0x27:
                stack.append(False)
            elif op == 0x20:
                stack.append(None)
            elif op == 0x56:                     # newarray
                n = r.u30()
                items = stack[-n:] if n else []
                del stack[len(stack) - n:]
                stack.append(list(items))
            elif op in (0x66, 0x60):             # getproperty / getlex
                last_get = self.multinames[r.u30()]
                stack.clear()
            elif op in (0x61, 0x68):             # setproperty / initproperty
                prop = self.multinames[r.u30()]
                if last_get and stack and prop:
                    yield last_get, prop, stack[-1]
                stack.clear()
            elif op in self._U30_1:
                r.u30()
            elif op in self._U30_2:
                r.u30(); r.u30()
            elif op == 0x65:                     # getscopeobject
                r.u8()
            elif 0x0C <= op <= 0x1A:             # branches
                r.s24()
            elif op == 0x1B:                     # lookupswitch
                r.s24()
                for _ in range(r.u30() + 1):
                    r.s24()
            elif op == 0xEF:                     # debug
                r.u8(); r.u30(); r.u8(); r.u30()

    def literal_pushes(self, code: bytes):
        """[(offset, length, value, kind)] for every numeric literal push in a method."""
        r = _Reader(code)
        out = []
        while r.p < len(code):
            start = r.p
            op = r.u8()
            if op == 0x24:
                b = r.u8()
                out.append((start, 2, b - 256 if b > 127 else b, "byte"))
            elif op == 0x25:
                out.append((start, None, r.u30(), "short"))
            elif op == 0x2D:
                out.append((start, None, self.ints[r.u30()], "int"))
            elif op == 0x2E:
                out.append((start, None, self.uints[r.u30()], "uint"))
            elif op == 0x2F:
                out.append((start, None, self.doubles[r.u30()], "double"))
            elif op in self._U30_1:
                r.u30()
            elif op in self._U30_2:
                r.u30(); r.u30()
            elif op == 0x65:
                r.u8()
            elif 0x0C <= op <= 0x1A:
                r.s24()
            elif op == 0x1B:
                r.s24()
                for _ in range(r.u30() + 1):
                    r.s24()
            elif op == 0xEF:
                r.u8(); r.u30(); r.u8(); r.u30()
            if out and out[-1][0] == start and out[-1][1] is None:
                out[-1] = (start, r.p - start) + out[-1][2:]
        return out

    def cue_properties(self):
        """{(instance, room_class): {property: value}} from all __setProp_ methods."""
        out = {}
        for method, name in self.method_names.items():
            if not name.startswith("__setProp_") or method not in self.bodies:
                continue
            room = ""
            if "_a_Room_" in name:
                room = "a_Room_" + name.split("_a_Room_", 1)[1].rsplit("_", 2)[0]
            for inst, prop, value in self.setprops(self.bodies[method]):
                if prop == "componentInspectorSetting":
                    continue
                out.setdefault((inst, room), {})[prop] = value
        return out


def read_abcs(path: str):
    raw = open(path, "rb").read()
    body = zlib.decompress(raw[8:]) if raw[:3] == b"CWS" else raw[8:]
    nbits = body[0] >> 3
    pos = (5 + nbits * 4 + 7) // 8 + 4
    abcs = []
    for code, d, p, length in _iter_tags(body, pos, len(body)):
        if code == 82:
            start = d.index(b"\x00", p + 4) + 1
            abcs.append(Abc(d[start:p + length]))
        elif code == 72:
            abcs.append(Abc(d[p:p + length]))
    return abcs


def cue_properties(path: str):
    props = {}
    for abc in read_abcs(path):
        props.update(abc.cue_properties())
    return props
