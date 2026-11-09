"""
Read and write the client's .swz data files (Game.swz, Login.swz, Init.swz).

Format (ResourceManager.method_654 in the client):
    int32 key, int32 count, then per entry: int32 length + bytes.
    Each byte is XORed with the low byte of the key, and the key rotates right
    by (index & 7) after every byte; the key carries on across entries.
    The unscrambled bytes are zlib data holding one XML document.
"""
import struct
import zlib


def _scramble(data: bytes, key: int):
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ (key & 0xFF)
        shift = i & 7
        key = ((key << (32 - shift)) | (key >> shift)) & 0xFFFFFFFF if shift else key
    return bytes(out), key


def read_swz(path: str):
    """Returns (key, [xml_text, ...])."""
    raw = open(path, "rb").read()
    key, count = struct.unpack_from(">iI", raw, 0)
    key &= 0xFFFFFFFF
    start_key = key
    pos = 8
    docs = []
    for _ in range(count):
        length = struct.unpack_from(">I", raw, pos)[0]
        pos += 4
        plain, key = _scramble(raw[pos:pos + length], key)
        pos += length
        docs.append(zlib.decompress(plain).decode("utf-8"))
    return start_key, docs


def write_swz(path: str, key: int, docs):
    out = bytearray(struct.pack(">II", key, len(docs)))
    for text in docs:
        packed = zlib.compress(text.encode("utf-8"), 9)
        scrambled, key = _scramble(packed, key)
        out += struct.pack(">I", len(scrambled)) + scrambled
    with open(path, "wb") as f:
        f.write(out)
