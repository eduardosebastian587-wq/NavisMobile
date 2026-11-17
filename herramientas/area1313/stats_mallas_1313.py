import os, sys, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8066), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
JS = """() => { const A = window.__api, L = []; let vt = 0, tt = 0;
 A.scene.traverse(o => { if (!o.isMesh || !o.geometry) return; const g = o.geometry, pos = g.attributes.position, ix = g.index;
   const nt = ix ? ix.count / 3 : pos.count / 3; let deg = 0; const P = pos.array;
   const v = k => ix ? ix.array[k] : k;
   for (let i = 0; i < nt; i++) { const a = v(3*i)*3, b = v(3*i+1)*3, c = v(3*i+2)*3;
     const ux=P[b]-P[a], uy=P[b+1]-P[a+1], uz=P[b+2]-P[a+2], wx=P[c]-P[a], wy=P[c+1]-P[a+1], wz=P[c+2]-P[a+2];
     const cx=uy*wz-uz*wy, cy=uz*wx-ux*wz, cz=ux*wy-uy*wx; if (cx*cx+cy*cy+cz*cz < 1e-12) deg++; }
   vt += pos.count; tt += nt; L.push([o.name, Math.round(nt), pos.count, !!ix, o.material && o.material.side, deg, o.visible]); });
 return {mallas: L.sort((a, b) => b[1] - a[1]).slice(0, 14), total_tri: tt, total_vert: vt}; }"""
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': 1280, 'height': 720}); pg.set_default_timeout(0)
    pg.goto('http://127.0.0.1:8066/index_1313.html?calidad=baja&prueba=1&panel=0&auto=0')
    pg.wait_for_function('window.__listo === true', timeout=0, polling=1000)
    r = pg.evaluate(JS); print('tri', r['total_tri'], 'vert', r['total_vert'])
    for m in r['mallas']: print(m)
    b.close()