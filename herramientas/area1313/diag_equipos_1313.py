# Diagnóstico: posición real (ejes Three) de las piezas animadas en el visor y capturas de control con las piezas en rojo.
import os, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8064), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
sal = os.path.join(raiz, 'capturas_prueba')
JS_CAJAS = """(() => { const {THREE, MATS} = window.__api; const out = {}; const s = new Set();
  for (const e of Object.values(MATS)) for (const m of e.mallas) if (/^equipo_/.test(m.name)) s.add(m);
  let raiz = null; for (const m of s) { let p = m; while (p.parent && p.parent.type !== 'Scene') p = p.parent; raiz = p; }
  if (raiz) raiz.traverse(m => { if (m.isMesh) s.add(m); });
  for (const m of s) { const b = new THREE.Box3().setFromObject(m); const k = m.name.replace('equipo_', '');
    const r = out[k] || (out[k] = {min: [1e9,1e9,1e9], max: [-1e9,-1e9,-1e9]});
    for (let i = 0; i < 3; i++) { r.min[i] = Math.min(r.min[i], +b.min.getComponent(i).toFixed(1)); r.max[i] = Math.max(r.max[i], +b.max.getComponent(i).toFixed(1)); }
    if (!m.userData.rojo) { m.userData.rojo = 1; m.material = new THREE.MeshBasicMaterial({color: 0xff0000}); } }
  return out; })()"""
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False)
    pg = b.new_page(viewport={'width': 1280, 'height': 720})
    errs = []; pg.on('response', lambda r: errs.append(r.url) if r.status >= 400 else None)
    pg.goto('http://127.0.0.1:8064/index_1313.html?calidad=media&prueba=1&panel=0&titulo=0')
    pg.wait_for_function('window.__listo === true', timeout=300000)
    out = {}
    for t in (0, 26):
        pg.evaluate(f'window.irA({t})'); out[f't{t}'] = pg.evaluate(JS_CAJAS)
        pg.evaluate("window.__api.vista([30, 140, 40], [30, 0, -45])"); pg.screenshot(path=os.path.join(sal, f'diag_planta_{t:02d}s.png'))
    out['404'] = errs; b.close()
print(json.dumps(out, ensure_ascii=False))
