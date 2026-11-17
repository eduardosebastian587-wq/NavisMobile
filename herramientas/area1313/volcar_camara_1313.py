# Vuelca, para varios instantes del recorrido, la camara real del visor (matrices P, V, raiz) y la mascara de pixeles candidatos
# (oscuros o muy saturados) de la captura. Uso: py -I volcar_camara_1313.py "<url relativa>" <WxH> <t1,t2,..> <prefijo>
import sys, os, io, time, json, threading, http.server, socketserver
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8067), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url, vp, ts, pref = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3].split(',')], sys.argv[4]
W, H = [int(x) for x in vp.split('x')]
JS = '''() => { const {scene, cam} = window.__api; let raiz = null, mx = -1; for (const c of scene.children) { let n = 0; c.traverse(() => n++); if (n > mx) { mx = n; raiz = c; } }
 cam.updateMatrixWorld(); raiz.updateMatrixWorld(); return {P: cam.projectionMatrix.elements, V: cam.matrixWorldInverse.elements, R: raiz.matrixWorld.elements, W: innerWidth, H: innerHeight}; }'''
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': W, 'height': H})
    pg.goto('http://127.0.0.1:8067/' + url + ('&' if '?' in url else '?') + 'prueba=1&panel=0&calidad=media', wait_until='commit', timeout=300000)
    pg.wait_for_function('window.__listo === true', timeout=600000); time.sleep(3)
    for t in ts:
        pg.evaluate(f'window.irA({t})'); time.sleep(3)
        img = np.array(Image.open(io.BytesIO(pg.screenshot())).convert('RGB')).astype(float); mx, mn = img.max(2), img.min(2)
        cand = (mx < 175) | ((mx - mn) / np.maximum(mx, 1) > 0.38)
        np.save(f'{pref}_{t:g}_cand.npy', cand); json.dump(pg.evaluate(JS), open(f'{pref}_{t:g}_cam.json', 'w')); print('t', t, 'candidatos', int(cand.sum()), flush=True)
    b.close()
