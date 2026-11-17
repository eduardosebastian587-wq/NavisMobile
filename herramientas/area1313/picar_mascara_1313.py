# Picado en el visor SOLO en pixeles candidatos (oscuros o muy saturados = restos/piezas sueltas) dentro de elipses, en uno o varios instantes.
# Uso: py -I picar_mascara_1313.py "<url relativa>" <WxH> <trabajos.json> <salida.json> [max_rayos_por_elipse=1200]
#   trabajos.json = [{"t": 90, "elipses": [{"id": 1, "cx":.., "cy":.., "rx":.., "ry":..}, ...]}, ...]  (pixeles del canvas WxH)
import sys, os, io, time, json, threading, http.server, socketserver
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8067), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url, vp, fj, sal = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]; MAXR = int(sys.argv[5]) if len(sys.argv) > 5 else 1200
W, H = [int(x) for x in vp.split('x')]; jobs = json.load(open(fj, encoding='utf-8')); rng = np.random.default_rng(1)
t0 = time.time(); log = lambda *x: print(f'[{time.time()-t0:6.1f} s]', *x, flush=True)
JS = r'''(P) => {
 const {scene, cam, THREE} = window.__api; const rc = new THREE.Raycaster(); const W = innerWidth, H = innerHeight; cam.updateMatrixWorld(); const out = [];
 const raiz = o => { while (o.parent && o.parent !== scene) o = o.parent; return o; };
 const vis = o => { while (o) { if (!o.visible) return false; o = o.parent; } return true; };
 for (const [x, y, e] of P) { rc.setFromCamera(new THREE.Vector2(x / W * 2 - 1, -(y / H) * 2 + 1), cam);
  const h = rc.intersectObjects(scene.children, true).find(i => i.object.isMesh && vis(i.object)); if (!h) continue;
  const m = Array.isArray(h.object.material) ? h.object.material[0] : h.object.material; const p = raiz(h.object).worldToLocal(h.point.clone());
  out.push({e, t: 0, x, y, p: [p.x, p.y, p.z].map(v => +v.toFixed(3)), n: h.object.name.slice(0, 40), c: m && m.color ? m.color.getHexString() : ''}); }
 return out; }'''
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': W, 'height': H}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    pg.goto('http://127.0.0.1:8067/' + url + ('&' if '?' in url else '?') + 'prueba=1&panel=0&calidad=media', wait_until='commit', timeout=300000)
    pg.wait_for_function('window.__listo === true', timeout=600000); time.sleep(3); res = []
    for J in jobs:
        pg.evaluate(f"window.irA({J['t']})"); time.sleep(3)
        img = np.array(Image.open(io.BytesIO(pg.screenshot())).convert('RGB')).astype(float); mx, mn = img.max(2), img.min(2); sat = (mx - mn) / np.maximum(mx, 1)
        cand = (mx < 175) | (sat > 0.38)
        for E in J['elipses']:
            yy, xx = np.mgrid[0:H, 0:W]; dentro = (((xx - E['cx']) / E['rx']) ** 2 + ((yy - E['cy']) / E['ry']) ** 2 <= 1) & cand
            ys, xs = np.nonzero(dentro); n = len(xs)
            if n > MAXR: k = rng.choice(n, MAXR, replace=False); xs, ys = xs[k], ys[k]
            r = pg.evaluate(JS, [[int(x), int(y), E['id']] for x, y in zip(xs, ys)])
            for h in r: h['t'] = J['t']
            res += r; log(f"t={J['t']} elipse {E['id']}: candidatos {n}, rayos {len(xs)}, impactos {len(r)}")
    json.dump(res, open(sal, 'w', encoding='utf-8')); log('guardado', sal, len(res), 'errores:', errs[:3]); b.close()
