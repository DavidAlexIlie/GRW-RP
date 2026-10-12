import struct, zlib
MAGIC = bytes.fromhex('33aafb5799fa0410')

def lzo1x_decompress(src, out_len):
    dst = bytearray(); ip = 0; n = len(src)
    def lit(k):
        nonlocal ip
        dst.extend(src[ip:ip+k]); ip += k
    def copy_match(dist, length):
        p = len(dst) - dist
        if p < 0: raise ValueError('bad dist')
        for _ in range(length): dst.append(dst[p]); p += 1
    t = src[ip]
    state = 0
    if t > 17:
        ip += 1; lit(t - 17); state = 4 if t - 17 >= 4 else (t - 17)
    while True:
        t = src[ip]; ip += 1
        if t < 16:
            if state == 0:
                if t == 0:
                    while src[ip] == 0: t += 255; ip += 1
                    t += 15 + src[ip]; ip += 1
                lit(t + 3); state = 4; continue
            elif state == 4:
                dist = 1 + 0x800 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 3); s = t & 3
            else:
                dist = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 2); s = t & 3
        elif t >= 64:
            dist = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
            copy_match(dist, (t >> 5) + 1); s = t & 3
        elif t >= 32:
            ln = t & 31
            if ln == 0:
                while src[ip] == 0: ln += 255; ip += 1
                ln += 31 + src[ip]; ip += 1
            ln += 2
            v = src[ip] | (src[ip+1] << 8); ip += 2
            copy_match(1 + (v >> 2), ln); s = v & 3
        else:
            ln = t & 7
            if ln == 0:
                while src[ip] == 0: ln += 255; ip += 1
                ln += 7 + src[ip]; ip += 1
            ln += 2
            v = src[ip] | (src[ip+1] << 8); ip += 2
            dist = ((t & 8) << 11) + (v >> 2)
            if dist == 0: break  # EOS
            copy_match(dist + 0x4000, ln); s = v & 3
        if s: lit(s)
        state = s if s else 0
        if s == 0: state = 0
    if len(dst) != out_len: raise ValueError('len %d != %d' % (len(dst), out_len))
    return bytes(dst)

def parse_sections(d):
    """Return list of sections: dict(pos, end, comp, chunks=[(usz, csz, cksum, cdata_off)])"""
    secs = []; p = 0
    while p < len(d):
        assert d[p:p+8] == MAGIC, 'no magic at %d' % p
        ver, comp, mx1, mx2, cnt = struct.unpack_from('<HBHHI', d, p+8)
        q = p + 8 + 2 + 1 + 4 + 4
        hdr = [struct.unpack_from('<HH', d, q + 4*i) for i in range(cnt)]
        q += 4*cnt
        chunks = []
        for usz, csz in hdr:
            ck = struct.unpack_from('<I', d, q)[0]
            chunks.append((usz, csz, ck, q + 4)); q += 4 + csz
        secs.append(dict(pos=p, end=q, ver=ver, comp=comp, mx1=mx1, mx2=mx2, chunks=chunks))
        p = q
    return secs

def decompress_section(d, s):
    out = bytearray()
    for usz, csz, ck, off in s['chunks']:
        c = d[off:off+csz]
        out += c if usz == csz else lzo1x_decompress(c, usz)
    return bytes(out)

def build_section_stored(data, comp=1, mx=0x8000):
    """Build a section whose chunks are stored uncompressed (usz == csz)."""
    chunks = [data[i:i+mx] for i in range(0, len(data), mx)] or [b'']
    h = MAGIC + struct.pack('<HBHHI', 1, comp, mx, mx, len(chunks))
    h += b''.join(struct.pack('<HH', len(c) & 0xffff, len(c) & 0xffff) for c in chunks)
    body = b''.join(struct.pack('<I', checksum(c)) + c for c in chunks)
    return h + body

def checksum(c):
    return zlib.adler32(c, 0)

MESH = 0x415d9568
PRIM = bytes.fromhex('ef8773a5')  # MeshPrimitive class hash

def iter_resources(u):
    p = 0
    while p + 12 <= len(u):
        cls, sz, nl = struct.unpack_from('<III', u, p)
        name = u[p+12:p+12+nl].decode('latin1')
        start = p + 12 + nl + 1
        yield cls, name, start, sz
        p = start + sz

def find_index_buffers(m):
    """The index buffer is the last length-prefixed u16 blob before the first
    MeshPrimitive record (class PRIM) and is followed by it within ~1KB."""
    first_prim = m.find(PRIM)
    if first_prim == -1: return []
    best = None
    for p in range(max(0, first_prim - 4*1024*1024), first_prim - 4):
        L = struct.unpack_from('<I', m, p)[0]
        end = p + 4 + L
        if L >= 36 and L % 6 == 0 and end <= first_prim and first_prim - end < 1024:
            idx = struct.unpack_from('<%dH' % (L // 2), m, p + 4)
            tris = [set(idx[i:i+3]) for i in range(0, len(idx), 3)]
            # real triangle lists share vertices with the previous triangle most of the time
            share = sum(1 for a, b in zip(tris, tris[1:]) if a & b) / max(1, len(tris) - 1)
            after = struct.unpack_from('<I', m, end)[0]
            if after % 0x24 == 0 and first_prim - end == after + 31 and share > 0.5 and (best is None or end > best[0] + best[1]):  # closest to the primitives
                best = (p + 4, L)
    return [best] if best else []

def hide_meshes(d, log=print):
    """Decompress every section, collapse all mesh triangles to degenerate ones, rebuild."""
    secs = parse_sections(d)
    out = b''; hidden = 0
    for s in secs:
        u = bytearray(decompress_section(d, s))
        changed = False
        if s is not secs[0]:
            for cls, name, start, sz in iter_resources(bytes(u)):
                if cls != MESH: continue
                m = bytes(u[start:start+sz])
                for off, L in find_index_buffers(m):
                    u[start+off:start+off+L] = bytes(L)
                    log('  %s: zeroed %d indices (%d tris) at +0x%x' % (name, L // 2, L // 6, off))
                    hidden += 1; changed = True
        if changed:
            out += build_section_stored(bytes(u), s['comp'], s['mx1'])
        else:
            out += d[s['pos']:s['end']]
    return out, hidden

SUBMESH = bytes.fromhex('c1341d0b')  # submesh record class hash: +5 u16 index, +10 u64 material id

def resource_ids(d, secs):
    t = decompress_section(d, secs[0])
    cnt = struct.unpack_from('<H', t, 0)[0]
    return [struct.unpack_from('<Q', t, 2 + i*14)[0] for i in range(cnt)]

def mesh_submeshes(m):
    """[(start_index, index_count, material_id)] for each submesh of a Mesh payload."""
    prims = []; p = m.find(PRIM)
    while p != -1:
        minv, _, numv, start, cnt = struct.unpack_from('<5I', m, p + 4)
        prims.append((start, cnt * 3)); p = m.find(PRIM, p + 4)
    subs = []; p = m.find(SUBMESH)
    while p != -1:
        idx = struct.unpack_from('<H', m, p + 4 + 5)[0]
        mat = struct.unpack_from('<Q', m, p + 4 + 10)[0]
        subs.append((idx, mat)); p = m.find(SUBMESH, p + 4)
    out = []
    for idx, mat in subs:
        if idx < len(prims): out.append(prims[idx] + (mat,))
    return out

def hide_submeshes(d, want, log=print):
    """Degenerate only the triangles of submeshes for which want(material_id, material_name) is true."""
    secs = parse_sections(d)
    ids = resource_ids(d, secs)
    u = bytearray(decompress_section(d, secs[1]))
    res = list(iter_resources(bytes(u)))
    names = {i: r[1] for i, r in zip(ids, res)}
    hidden = 0
    for cls, name, start, sz in res:
        if cls != MESH: continue
        m = bytes(u[start:start+sz]); ibs = find_index_buffers(m)
        if not ibs: continue
        ib, L = ibs[0]
        for s0, n, mat in mesh_submeshes(m):
            mname = names.get(mat, '')
            if want(mat, mname) and (s0 + n) * 2 <= L:
                a = start + ib + s0 * 2
                u[a:a + n * 2] = bytes(n * 2)
                log('  %s: hid submesh %s (%d tris)' % (name, mname or hex(mat), n // 3)); hidden += 1
    if not hidden: return d, 0
    out = d[secs[0]['pos']:secs[0]['end']] + build_section_stored(bytes(u), secs[1]['comp'], secs[1]['mx1'])
    for s in secs[2:]: out += d[s['pos']:s['end']]
    return out, hidden
