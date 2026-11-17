# Prueba automática del visor del Hito en Edge: carga, recorrido 50 s, verificación de holgura, FPS y capturas.
import sys, os, time, json, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8061), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
sal = os.path.join(raiz, 'capturas_prueba'); os.makedirs(sal, exist_ok=True)
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=False, args=['--ignore-gpu-blocklist'])
    pg = b.new_page(viewport={'width': 1280, 'height': 720})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    t0 = time.time()
    pg.goto('http://127.0.0.1:8061/index_hito.html?modelo=convertidos_blender/hito_web.glb&calidad=media&prueba=1&panel=0')
    pg.wait_for_function('window.__listo === true', timeout=300000); res['carga_s'] = round(time.time() - t0, 1)
    res['recorridos'] = pg.evaluate("window.__api.RECS.map(r => [r.id, r.nombre, +r.dur.toFixed(2)])")
    pg.evaluate("window.__api.activar('continuo_50s')")
    res['verificacion'] = pg.evaluate("window.__api.verificar(3).then(v => ({min: +v.min.toFixed(2), tmin: +v.tmin.toFixed(1), tramos: v.tramos}))")
    for s in (0, 12, 25, 26, 38, 45, 50):
        pg.evaluate(f"window.irA({s})"); pg.screenshot(path=os.path.join(sal, f'v50_{s:02d}s.png'))
    pg.goto('http://127.0.0.1:8061/index_hito.html?modelo=convertidos_blender/hito_web.glb&calidad=media&panel=0')
    pg.wait_for_function('window.__listo === true', timeout=300000); pg.evaluate("window.__api.activar('continuo_50s')"); time.sleep(8)
    res['fps_aprox'] = pg.evaluate("new Promise(r => { let n = 0, t = performance.now(); const f = () => { n++; if (performance.now() - t > 4000) r(+(n / ((performance.now() - t) / 1000)).toFixed(1)); else requestAnimationFrame(f); }; f(); })")
    res['soporta_VideoEncoder'] = pg.evaluate("'VideoEncoder' in window")
    res['errores'] = errs[:8]; b.close()
print(json.dumps(res, ensure_ascii=False, indent=1))
open(os.path.join(sal, 'prueba_50s.json'), 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
