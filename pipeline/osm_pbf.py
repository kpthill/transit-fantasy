"""Minimal pure-Python OSM PBF reader (no external deps — PyPI is blocked
in this sandbox). Implements just enough of the protobuf wire format for
OSM's fileformat/osmformat schemas: varints, zigzag, packed arrays, zlib
blobs, string tables, DenseNodes and Ways.

API:
    for kind, payload in iter_groups(path):
        kind is "dense" -> (ids, lats, lons, keyvals, strings)
        kind is "ways"  -> list of (way_id, tags_dict, refs_list)

Coordinates come back in degrees. Relations are skipped.
"""
import zlib


def _varint(buf, i):
    result = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _zigzag(n):
    return (n >> 1) ^ -(n & 1)


def _packed_varints(buf):
    out = []
    append = out.append
    i = 0
    n = len(buf)
    while i < n:
        result = 0
        shift = 0
        while True:
            b = buf[i]
            i += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
        append(result)
    return out


def _fields(buf):
    """Yield (field_no, wire_type, value) over a protobuf message."""
    i = 0
    n = len(buf)
    while i < n:
        key, i = _varint(buf, i)
        field, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _varint(buf, i)
        elif wt == 2:
            ln, i = _varint(buf, i)
            val = buf[i:i + ln]
            i += ln
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
        else:
            raise ValueError(f"wire type {wt}")
        yield field, wt, val


def _iter_blobs(path):
    with open(path, "rb") as fh:
        while True:
            head = fh.read(4)
            if len(head) < 4:
                return
            hlen = int.from_bytes(head, "big")
            header = fh.read(hlen)
            btype = None
            dsize = 0
            for field, _, val in _fields(header):
                if field == 1:
                    btype = bytes(val).decode()
                elif field == 3:
                    dsize = val
            blob = fh.read(dsize)
            raw = None
            for field, _, val in _fields(blob):
                if field == 1:
                    raw = bytes(val)
                elif field == 3:
                    raw = zlib.decompress(val)
            yield btype, raw


def _parse_dense(buf, strings, gran, lat_off, lon_off):
    ids = lats = lons = keyvals = None
    for field, _, val in _fields(buf):
        if field == 1:
            ids = [_zigzag(v) for v in _packed_varints(val)]
        elif field == 8:
            lats = [_zigzag(v) for v in _packed_varints(val)]
        elif field == 9:
            lons = [_zigzag(v) for v in _packed_varints(val)]
        elif field == 10:
            keyvals = _packed_varints(val)
    # cumulative deltas -> absolute
    acc = 0
    for k in range(len(ids)):
        acc += ids[k]
        ids[k] = acc
    acc = 0
    for k in range(len(lats)):
        acc += lats[k]
        lats[k] = (lat_off + gran * acc) * 1e-9
    acc = 0
    for k in range(len(lons)):
        acc += lons[k]
        lons[k] = (lon_off + gran * acc) * 1e-9
    return ids, lats, lons, keyvals or [], strings


def _parse_way(buf, strings):
    wid = 0
    keys = vals = ()
    refs = []
    for field, _, val in _fields(buf):
        if field == 1:
            wid = val
        elif field == 2:
            keys = _packed_varints(val)
        elif field == 3:
            vals = _packed_varints(val)
        elif field == 8:
            acc = 0
            for d in _packed_varints(val):
                acc += _zigzag(d)
                refs.append(acc)
    tags = {strings[k]: strings[v] for k, v in zip(keys, vals)}
    return wid, tags, refs


def iter_groups(path, want_dense=True, want_ways=True):
    for btype, raw in _iter_blobs(path):
        if btype != "OSMData":
            continue
        strings = []
        groups = []
        gran, lat_off, lon_off = 100, 0, 0
        for field, _, val in _fields(raw):
            if field == 1:
                for f2, _, v2 in _fields(val):
                    if f2 == 1:
                        strings.append(bytes(v2).decode("utf-8", "replace"))
            elif field == 2:
                groups.append(val)
            elif field == 17:
                gran = val
            elif field == 19:
                lat_off = val
            elif field == 20:
                lon_off = val
        for g in groups:
            dense_buf = None
            way_bufs = []
            for field, _, val in _fields(g):
                if field == 2:
                    dense_buf = val
                elif field == 3:
                    way_bufs.append(val)
            if dense_buf is not None and want_dense:
                yield "dense", _parse_dense(dense_buf, strings, gran, lat_off, lon_off)
            if way_bufs and want_ways:
                yield "ways", [_parse_way(w, strings) for w in way_bufs]
