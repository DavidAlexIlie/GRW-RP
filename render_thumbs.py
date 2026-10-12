"""Build-time: render a textured front-view thumbnail of every pants item in the holster cache.
Run from the game folder:  python render_thumbs.py <out_dir> [logo_dir]
Uses the ORIGINAL (pre-mod) entry data via the undo files, so holsters are visible in the thumbnail."""
import sys, os, json, struct, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
import anvildata as A, forgelist as FL, pants

W, H, SS = 224, 192, 3                 # output size (2x of the 112x96 card thumb), supersampling
BG = np.array([35, 40, 48], np.float32)  # #232830
TEXMAP = 0xa2b7e917
FALLBACK = np.array([[[52, 52, 54]]], np.uint8)   # dark grey for materials we can't resolve (e.g. the sheath)
# items whose own mesh is only a holster: render it on the outfit's legs so it reads as "pants"
EXTRA_MESHES = {'SPETSNAZ_TACHANKA_Holster': ['CP_SPETSNAZ_TACHANKA_Body_LOD0']}
LEGS_ONLY = {'SPETSNAZ_TACHANKA_Holster'}   # outfit body mesh includes torso/arms: keep the legs
LOGOS = {'FBI_CASTLE_Holster': 'fib.png', 'GIGN_DOC_Holster': 'ging.png'}

# ------------------------------------------------------------------ forge access
class Forges:
    def __init__(self):
        self.rows = {}; self.by_id = {}; self.orig = {}
        for fg in sorted(glob.glob('*.forge') + glob.glob('dlc_*/*.forge'), key=lambda f: ('patch' not in f, f)):
            for up in glob.glob(glob.escape(fg) + '.civmod*undo.json'):
                for pos, hx in json.load(open(up))['patches']:
                    b = bytes.fromhex(hx)
                    if len(b) == 20: self.orig[(fg, pos)] = struct.unpack('<QQI', b)
            for r in FL.tables(fg):
                self.rows.setdefault(r[5], (fg, r))       # patch forges first -> newest version wins
                if r[4] == TEXMAP: self.by_id.setdefault(r[3], (fg, r))
    def read(self, fg, r):
        off, sz = r[1], r[2]
        if (fg, r[0]) in self.orig: off, _, sz = self.orig[(fg, r[0])]
        with open(fg, 'rb') as f: f.seek(off); return f.read(sz)
    def container(self, name):
        fg, r = self.rows[name]; d = self.read(fg, r)
        secs = A.parse_sections(d)
        ids = A.resource_ids(d, secs); u = A.decompress_section(d, secs[1])
        return list(zip(ids, A.iter_resources(u))), u

# ------------------------------------------------------------------ textures (BC7 / BC1, smallest mip >= 128 kept in the TextureMap entry)
_tex_cache = {}
def load_texture(fx, tex_id):
    if tex_id in _tex_cache: return _tex_cache[tex_id]
    img = None
    try:
        fg, r = fx.by_id[tex_id]; d = fx.read(fg, r)
        u = A.decompress_section(d, A.parse_sections(d)[1])
        cls, nm, st, sz = next(A.iter_resources(u)); t = u[st:st + sz]
        # data blob = u32 size + bytes running to the end of the resource
        p = next(p for p in range(12, 400) if struct.unpack_from('<I', t, p)[0] == len(t) - p - 4)
        n = len(t) - p - 4; data = t[p + 4:]
        # header has (w, h, 1) for the full-size texture
        w = h = None
        for q in range(12, p - 12):
            a, b, c = struct.unpack_from('<III', t, q)
            if c == 1 and a in (64, 128, 256, 512, 1024, 2048, 4096) and b in (64, 128, 256, 512, 1024, 2048, 4096):
                w, h = a, b; break
        for bpb, mode in ((16, 7), (8, 1)):
            for k in range(0, 12):
                levels = max(w, h).bit_length()          # down to 1x1 exactly once
                dims = [(max(w >> i, 1), max(h >> i, 1)) for i in range(k, levels)]
                tot = sum(((x + 3) // 4) * ((y + 3) // 4) * bpb for x, y in dims)
                if tot == n:
                    mw, mh = dims[0]
                    img = Image.frombytes('RGBA', (mw, mh), data[:((mw + 3) // 4) * ((mh + 3) // 4) * bpb], 'bcn', mode)
                    break
            if img: break
    except Exception:
        img = None
    arr = np.asarray(img.convert('RGB')) if img else None
    _tex_cache[tex_id] = arr; return arr

def material_texture(fx, mat_bytes):
    """Diffuse texture referenced (by id) from a material resource."""
    # the material lists its own maps plus shared detail tiles (LIB_*) and engine defaults; take its own diffuse
    for p in range(0, len(mat_bytes) - 8):
        i = struct.unpack_from('<Q', mat_bytes, p)[0]
        if i in fx.by_id:
            name = fx.by_id[i][1][5]
            if 'diffuse' in name.lower() and not name.startswith(('LIB_', 'Default')): return i
    return None

# ------------------------------------------------------------------ geometry
def mesh_geometry(m):
    ib, L = A.find_index_buffers(m)[0]
    prims = []; p = m.find(A.PRIM)
    while p != -1:
        minv, _, numv, start, cnt = struct.unpack_from('<5I', m, p + 4)
        if (minv, start) not in [(a, b) for a, b, *_ in prims]: prims.append((minv, start, cnt, numv))
        p = m.find(A.PRIM, p + 4)
    nv = max(a + d for a, b, c, d in prims)
    for stride in range(12, 129, 4):
        vb = ib - 4 - nv * stride
        if vb >= 4 and struct.unpack_from('<I', m, vb - 4)[0] == nv * stride: break
    else:
        raise ValueError('vertex buffer not found')
    raw = np.frombuffer(m, dtype=np.uint8, count=nv * stride, offset=vb).reshape(nv, stride)
    pos = raw[:, 0:6].copy().view('<i2').astype(np.float32)
    uv = raw[:, 20:24].copy().view('<i2').astype(np.float32) / 32768.0
    idx = np.frombuffer(m, dtype='<u2', count=L // 2, offset=ib).reshape(-1, 3).astype(np.int64)
    tri_mat = np.full(len(idx), -1, np.int64)
    subs = A.mesh_submeshes(m)  # (start, count, mat) in submesh-index order == prim order
    for k, (minv, start, cnt, numv) in enumerate(prims):
        idx[start // 3: start // 3 + cnt] += minv
        if k < len(subs): tri_mat[start // 3: start // 3 + cnt] = k
    mats = [s[2] for s in subs]
    # dequantise: the first submesh's bounding box (centre, half-extent) follows the index buffer
    try:
        c = np.array(struct.unpack_from('<3f', m, ib + L + 4)); e = np.array(struct.unpack_from('<3f', m, ib + L + 16))
        minv, _, _, numv = prims[0]; sub = pos[minv:minv + numv]
        rng = sub.max(0) - sub.min(0); ok = rng > 100
        sc = float(np.median((2 * e[ok]) / rng[ok]))
        if np.isfinite(sc) and 1e-7 < sc < 1e-2:
            off = (c - e) - sub.min(0) * sc
            pos = pos * sc + off.astype(np.float32)
    except Exception:
        pass
    return pos, uv, np.clip(idx, 0, nv - 1), tri_mat, mats

# ------------------------------------------------------------------ rasteriser
def render(parts, legs_only=False):
    """parts: list of (pos, uv, idx, tri_tex) where tri_tex[t] is an RGB texture array per triangle."""
    if legs_only:  # keep the legs: below the waist and within the hip width (arms hang beside the hips)
        allp = np.concatenate([p[0] for p in parts]); zs = allp[:, 2]
        z0, z1 = zs.min(), zs.max(); cut = z0 + 0.52 * (z1 - z0)
        low = allp[zs < z0 + 0.35 * (z1 - z0)]; cx = (low[:, 0].min() + low[:, 0].max()) / 2
        half = 0.62 * (low[:, 0].max() - low[:, 0].min())
        def keep(pos, idx):
            t = pos[idx]
            return (t[:, :, 2].max(axis=1) <= cut) & (np.abs(t[:, :, 0] - cx).max(axis=1) <= half)
        # the item's own mesh (parts[0], the holster) is kept whole; only the outfit body gets trimmed
        parts = parts[:1] + [(pos, uv, idx[keep(pos, idx)], [x for x, k in zip(tt, keep(pos, idx)) if k]) for pos, uv, idx, tt in parts[1:]]
    allpos = np.concatenate([p[0][np.unique(p[2])] for p in parts if len(p[2])])
    x, z = allpos[:, 0], allpos[:, 2]
    lo = np.array([x.min(), z.min()]); hi = np.array([x.max(), z.max()])
    Wp, Hp = W * SS, H * SS
    scale = 0.86 * min(Wp / (hi[0] - lo[0]), Hp / (hi[1] - lo[1]))
    ox = (Wp - (hi[0] - lo[0]) * scale) / 2; oy = (Hp - (hi[1] - lo[1]) * scale) / 2
    color = np.tile(BG, (Hp, Wp, 1)); zbuf = np.full((Hp, Wp), np.inf, np.float32)
    light = np.array([0.35, -0.8, 0.5], np.float32); light /= np.linalg.norm(light)
    for pos, uv, idx, tri_tex in parts:
        sx = ox + (pos[:, 0] - lo[0]) * scale
        sy = Hp - (oy + (pos[:, 2] - lo[1]) * scale)
        depth = pos[:, 1]
        fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
        vn = np.zeros_like(pos)
        for k in range(3): np.add.at(vn, idx[:, k], fn)
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9
        shade_v = 0.35 + 0.75 * np.abs(vn @ light)
        for t in range(len(idx)):
            a, b, c = idx[t]
            if a == b or b == c or a == c: continue
            xs = np.array([sx[a], sx[b], sx[c]]); ys = np.array([sy[a], sy[b], sy[c]])
            x0, x1 = int(max(xs.min(), 0)), int(min(xs.max() + 1, Wp)); y0, y1 = int(max(ys.min(), 0)), int(min(ys.max() + 1, Hp))
            if x0 >= x1 or y0 >= y1: continue
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-9: continue
            gx, gy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
            w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any(): continue
            zz = w0 * depth[a] + w1 * depth[b] + w2 * depth[c]
            zb = zbuf[y0:y1, x0:x1]; m = inside & (zz < zb)
            if not m.any(): continue
            tex = tri_tex[t]
            u = (w0 * uv[a, 0] + w1 * uv[b, 0] + w2 * uv[c, 0])[m]
            v = (w0 * uv[a, 1] + w1 * uv[b, 1] + w2 * uv[c, 1])[m]
            th, tw = tex.shape[:2]
            tx = (np.mod(u, 1.0) * tw).astype(int).clip(0, tw - 1); ty = (np.mod(v, 1.0) * th).astype(int).clip(0, th - 1)
            sh = (w0 * shade_v[a] + w1 * shade_v[b] + w2 * shade_v[c])[m]
            col = tex[ty, tx].astype(np.float32) * sh[:, None]
            zb[m] = zz[m]; color[y0:y1, x0:x1][m] = np.clip(col, 0, 255)
    img = Image.fromarray(color.astype(np.uint8), 'RGB')
    return img.resize((W, H), Image.LANCZOS)

def mesh_part(fx, entry_name):
    res, u = fx.container(entry_name)
    by_id = {i: (cls, n, st, sz) for i, (cls, n, st, sz) in res}
    cls, n, st, sz = next(x for _, x in res if x[0] == A.MESH)
    pos, uv, idx, tri_mat, mats = mesh_geometry(u[st:st + sz])
    texs = []
    for mid in mats:
        tex = None
        if mid in by_id:
            _, _, mst, msz = by_id[mid]
            tid = material_texture(fx, u[mst:mst + msz])
            if tid is not None: tex = load_texture(fx, tid)
        texs.append(tex if tex is not None else FALLBACK)
    tri_tex = [texs[k] if 0 <= k < len(texs) else FALLBACK for k in tri_mat]
    return pos, uv, idx, tri_tex

def make_logo(path, box=150):
    """Monochrome stamp in the same grey as the renders, fitted into a fixed box, centred."""
    im = Image.open(path).convert('RGBA'); im.thumbnail((500, 500), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    lum = a[:, :, :3].mean(axis=2)
    if a[:, :, 3].min() == 255:
        # opaque logo on black: background = black region connected to the border -> transparent,
        # inside the badge dark ink becomes opaque, light areas transparent (like the FIB line art)
        h, w = lum.shape; bg = np.zeros((h, w), bool); from collections import deque
        q = deque([(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)])
        dark = lum < 30
        while q:
            y, x = q.popleft()
            if 0 <= y < h and 0 <= x < w and dark[y, x] and not bg[y, x]:
                bg[y, x] = True; q.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
        alpha = np.clip((255 - lum) * 1.4, 0, 255); alpha[bg] = 0
    else:
        alpha = a[:, :, 3] * (lum < 128)
    ink = np.array([200, 204, 210], np.float32)
    out = np.zeros(a.shape, np.uint8); out[:, :, :3] = ink; out[:, :, 3] = alpha.astype(np.uint8)
    im = Image.fromarray(out, 'RGBA'); im = im.crop(im.getbbox()); im.thumbnail((box, box), Image.LANCZOS)
    canvas = Image.new('RGBA', (W, H), tuple(int(c) for c in BG) + (255,))
    canvas.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2))
    return canvas.convert('RGB')

def render_group(fx, g, names, out_path, logo_dir):
    """Render one picker thumbnail to out_path. Returns True on success."""
    if g in LOGOS:
        p = os.path.join(logo_dir, LOGOS[g])
        if not os.path.exists(p): return False
        make_logo(p).save(out_path); return True
    for n in sorted([n for n in names if n.endswith('_LOD0')], key=lambda n: n.startswith('F')):
        if n not in fx.rows: continue
        try:
            parts = [mesh_part(fx, n)] + [mesh_part(fx, e) for e in EXTRA_MESHES.get(g, []) if e in fx.rows]
            render(parts, g in LEGS_ONLY).save(out_path); return True
        except Exception:
            continue
    return False

def main(out_dir, logo_dir='.'):
    os.makedirs(out_dir, exist_ok=True)
    cache = json.load(open(os.path.join(HERE, 'holster_cache.json')))
    groups = pants.groups_from_cache(cache)
    fx = Forges(); done = []
    for g in sorted(groups):
        if g in LOGOS:
            p = os.path.join(logo_dir, LOGOS[g])
            if os.path.exists(p): make_logo(p).save(os.path.join(out_dir, g + '.png')); done.append(g); print('logo', g)
            continue
        lod0 = sorted([n for n in groups[g] if n.endswith('_LOD0')], key=lambda n: n.startswith('F'))
        for n in lod0:
            try:
                parts = [mesh_part(fx, n)] + [mesh_part(fx, e) for e in EXTRA_MESHES.get(g, [])]
                render(parts, g in LEGS_ONLY).save(os.path.join(out_dir, g + '.png')); done.append(g); print('ok  ', g, '<-', n)
                break
            except Exception as e:
                print('FAIL', g, n, repr(e))
    print('%d/%d thumbnails' % (len(done), len(groups)))

if __name__ == '__main__':
    main(*sys.argv[1:])
