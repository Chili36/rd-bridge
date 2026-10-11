"""Read value labels from a SAS format catalog (.sas7bcat), standard library only.

EFSA ships the FoodEx2 hierarchies and implicit facets of its FoodEx2 -> food-class algorithm
as SAS formats. readstat rejects EFSA's 1 GB catalog, so this reads the parts we need:

- pages of 4096 bytes after a 1024-byte header; a format's data is a chain of chunks, each
  chunk header giving the next page (1-based), the offset in it, and the chunk length;
- a format block: short name at 8, value and label counts at 42/46, long name at 126,
  value records from 158 (each pointing at its label by index), then the label records.

Only what EFSA's catalog uses is supported: 64-bit little-endian catalogs, character formats
($NAME) and numeric informats (@NAME).
"""
import mmap
import struct

HEADER_SIZE = 1024
PAGE_SIZE = 4096
CHUNK_HEADER = 16
VALUES_AT = 158


class Catalog:
    def __init__(self, path: str):
        self._fh = open(path, "rb")
        self._m = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        if b"SAS FILE" not in self._m[:256]:
            raise ValueError(f"{path}: not a SAS catalog")
        header, page, pages = struct.unpack("<III", self._m[200:212])
        if (header, page) != (HEADER_SIZE, PAGE_SIZE) or HEADER_SIZE + pages * PAGE_SIZE != len(self._m):
            raise ValueError(f"{path}: unexpected catalog layout")

    def close(self):
        self._m.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _block(self, name: str) -> bytes:
        """Concatenate the chunk chain of the format called `name` ($X or @X)."""
        m = self._m
        long_name = name.encode("latin-1").ljust(32)
        at = m.find(long_name)
        if at < 0:
            raise KeyError(name)
        short = name.encode("latin-1")[:8].ljust(8, b"\0")
        start = m.rfind(short, max(0, at - PAGE_SIZE), at) - 8 - CHUNK_HEADER
        page = (start - HEADER_SIZE) // PAGE_SIZE + 1
        pos = (start - HEADER_SIZE) % PAGE_SIZE
        out = bytearray()
        for _ in range(len(m) // PAGE_SIZE):
            at = HEADER_SIZE + (page - 1) * PAGE_SIZE + pos
            page, pos, size = struct.unpack("<IHH", m[at:at + 8])
            out += m[at + CHUNK_HEADER:at + CHUNK_HEADER + size]
            if page == 0 or pos == 0:
                break
        if out[126:158].rstrip() != long_name.rstrip():
            raise ValueError(f"{name}: block does not start with its own header")
        return bytes(out)

    def labels(self, name: str) -> dict:
        """{value: label} for a character format, {value: float} for a numeric informat."""
        data = self._block(name)
        count = struct.unpack("<I", data[42:46])[0]
        informat = name.startswith("@")
        values, p = data[VALUES_AT:], 0
        keys = []
        for _ in range(count):
            size = 6 + values[p + 2]
            record = values[p:p + size]
            index = struct.unpack("<I", record[14:18])[0]
            raw = record[22:] if informat else record[-16:]
            keys.append((index, raw.replace(b"\0", b" ").decode("latin-1").strip()))
            p += size
        labels = []
        while p + 10 <= len(values) and values[p:p + 2] == b"\x05\x00":
            size = 6 + struct.unpack("<H", values[p + 2:p + 4])[0]
            if informat:
                labels.append(struct.unpack("<d", values[p + 8:p + 16])[0])
            else:
                length = struct.unpack("<H", values[p + 8:p + 10])[0]
                labels.append(values[p + 10:p + 10 + length].decode("latin-1"))
            p += size
        if len(labels) <= max(i for i, _ in keys):
            raise ValueError(f"{name}: {len(labels)} labels for label index {max(i for i, _ in keys)}")
        return {key: labels[index] for index, key in keys}
