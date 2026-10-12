import struct, sys
def tables(path):
    f = open(path, 'rb')
    hdr = f.read(0x20)
    assert hdr[:9] == b'scimitar\0'
    ver, fdh = struct.unpack_from('<IQ', hdr, 9)
    f.seek(fdh); total = struct.unpack('<I', f.read(4))[0]
    t = fdh + 0x2c  # first table header
    out = []
    while t != -1 and t != 0xffffffffffffffff:
        f.seek(t)
        cnt, unk, idx, nxt, s, e, nm, raw = struct.unpack('<IIQqIIQQ', f.read(48))
        f.seek(idx); ib = f.read(cnt*20)
        f.seek(nm); nb = f.read(cnt*192)
        for i in range(cnt):
            off, fid, sz = struct.unpack_from('<QQI', ib, i*20)
            n = nb[i*192:(i+1)*192]
            typ = struct.unpack_from('<I', n, 0x10)[0]
            name = n[0x2c:0x2c+128].split(b'\0')[0].decode('latin1')
            out.append((idx + i*20, off, sz, fid, typ, name, nm + i*192))
        t = nxt
    return out
if __name__ == '__main__':
    for r in tables(sys.argv[1]):
        print('%d\t%d\t%d\t%016x\t%08x\t%s' % r[:6])
