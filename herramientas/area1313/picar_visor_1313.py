# Raycast en el visor (Chrome) dentro de elipses de pantalla en un instante del recorrido -> puntos 3D visibles (marco local del GLB).
# Uso: py picar_visor_1313.py "<url relativa>" <t> <ancho>x<alto> <elipses.json> <salida.json>
#   elipses.json = [{"id":1,"cx":..,"cy":..,"rx":..,"ry":..}, ...] en pixeles del canvas; paso de muestreo "paso" opcional (px, def. 8)
import sys, os, time, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8067), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url, t, vp, fe, sal = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
W, H = [int(x) for x in vp.split('x')]; elipses = json.load(open(fe, encoding='utf-8'))
t0 = time.time(); log = lambda *x: print(f'[{time.time()-t0:6.1f} s]', *x, flush=True)
JS = r'''([E, paso]) => {
 const {scene, cam, THREE} = window.__api; const rc = new THREE.Raycaster(); const W = innerWidth, H = innerHeight;
 cam.updateMatrixWorld(); const out = [];
 const raiz = o => { while (o.parent && o.parent !== scene) o = o.parent; return o; };
 const vis = o => { while (o) { if (!o.visible) return false; o = o.parent; } return true; };
 for (let y = E.cy - E.ry; y <= E.cy + E.ry; y += paso) for (let x = E.cx - E.rx; x <= E.cx + E.rx; x += paso) {
  if (((x - E.cx) / E.rx) ** 2 + ((y - E.cy) / E.ry) ** 2 > 1 || x < 0 || x >= W || y < 0 || y >= H) continue;
  rc.setFromCamera(new THREE.Vector2(x / W * 2 - 1, -(y / H) * 2 + 1), cam);
  const h = rc.intersectObjects(scene.children, true).find(i => i.object.isMesh && vis(i.object));
  if (!h) continue; const m = Array.isArray(h.object.material) ? h.object.material[0] : h.object.material;
  const p = raiz(h.object).worldToLocal(h.point.clone());
  out.push({e: E.id, x, y, p: [p.x, p.y, p.z].map(v => +v.toFixed(3)), d: +h.distance.toFixed(2), n: h.object.name.slice(0, 40), c: m && m.color ? m.color.getHexString() : ''});
 }
 return out; }'''
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': W, 'height': H})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    pg.goto('http://127.0.0.1:8067/' + url + ('&' if '?' in url else '?') + 'prueba=1&panel=0&calidad=media', wait_until='commit', timeout=300000)
    pg.wait_for_function('window.__listo === true', timeout=600000); time.sleep(3)
    pg.evaluate(f'window.irA({t})'); time.sleep(3)
    pg.screenshot(path=os.path.join(raiz, 'capturas_prueba', f'pick_{t:05.1f}s.png')); log('captura lista')
    res = []
    for E in elipses:
        r = pg.evaluate(JS, [E, E.get('paso', 8)]); res += r; log('elipse', E['id'], 'impactos', len(r))
    cam = pg.evaluate('''() => { const {scene, cam} = window.__api; let raiz = null, mx = -1; for (const c of scene.children) { let n = 0; c.traverse(() => n++); if (n > mx) { mx = n; raiz = c; } } cam.updateMatrixWorld(); raiz.updateMatrixWorld(); return {P: cam.projectionMatrix.elements, V: cam.matrixWorldInverse.elements, R: raiz.matrixWorld.elements, W: innerWidth, H: innerHeight}; }''')
    json.dump(cam, open(os.path.splitext(sal)[0] + '_cam.json', 'w'))
    json.dump(res, open(sal, 'w', encoding='utf-8')); log('guardado', sal, len(res), 'errores:', errs[:3]); b.close()
