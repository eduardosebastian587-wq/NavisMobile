# Capturas del recorrido con las piezas candidatas resaltadas (cajas de color) para aprobacion.
# Uso: py -I marcar_visor_1313.py "<url relativa>" <sueltos.json> <D> <ext_min> t1,t2,... prefijo
import sys, os, time, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8067), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url, fs, D, X, inst, pref = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), [float(x) for x in sys.argv[5].split(',')], sys.argv[6]
R = json.load(open(fs, encoding='utf-8')); PZ = R['piezas']
cajas = [PZ[i]['caja'] + [0 if PZ[i]['cad'][0] == 'Piping' else 1] for c in R['D'][D] if c['ext'] >= X for i in c['m']]
JS = r'''(C) => { const {scene, THREE} = window.__api;
 let raiz = null, mx = -1; for (const c of scene.children) { let n = 0; c.traverse(() => n++); if (n > mx) { mx = n; raiz = c; } }
 const geo = new THREE.BoxGeometry(1, 1, 1); const cols = [0xff1a1a, 0xff00ff];
 for (const k of [0, 1]) { const L = C.filter(c => c[6] === k); if (!L.length) continue;
  const mat = new THREE.MeshBasicMaterial({color: cols[k], transparent: true, opacity: 0.55, depthTest: true});
  const im = new THREE.InstancedMesh(geo, mat, L.length); const m = new THREE.Matrix4();
  L.forEach((c, i) => { const e = 0.06; m.compose(new THREE.Vector3((c[0]+c[3])/2, (c[1]+c[4])/2, (c[2]+c[5])/2), new THREE.Quaternion(),
    new THREE.Vector3(c[3]-c[0]+e, c[4]-c[1]+e, c[5]-c[2]+e)); im.setMatrixAt(i, m); });
  im.frustumCulled = false; raiz.add(im); }
 return mx; }'''
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': 1280, 'height': 720})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    pg.goto('http://127.0.0.1:8067/' + url + ('&' if '?' in url else '?') + 'prueba=1&panel=0&calidad=media', wait_until='commit', timeout=300000)
    pg.wait_for_function('window.__listo === true', timeout=600000); time.sleep(3)
    print('nodos raiz', pg.evaluate(JS, cajas), 'cajas', len(cajas), flush=True)
    for s in inst:
        pg.evaluate(f'window.irA({s})'); time.sleep(2.5); f = os.path.join('capturas_prueba', f'{pref}_{s:05.1f}s.jpg')
        pg.screenshot(path=f, type='jpeg', quality=80); print('captura', f, flush=True)
    print('errores de pagina:', errs[:5], flush=True); b.close()
