# Capturas del visor (URL = 1er argumento) en Chrome en los instantes dados (2o argumento, separados por coma) + FPS reproduciendo.
# Uso: py capturar_visor_1313.py "<url relativa>" 0,9,15 prefijo
import sys, os, time, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8067), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url, inst, pref = sys.argv[1], [float(x) for x in sys.argv[2].split(',')], sys.argv[3]
sal = os.path.join(raiz, 'capturas_prueba'); os.makedirs(sal, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': 1280, 'height': 720})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    pg.goto('http://127.0.0.1:8067/' + url + ('&' if '?' in url else '?') + 'prueba=1&panel=0&calidad=media', wait_until='commit', timeout=300000)
    pg.wait_for_function('window.__listo === true', timeout=600000); time.sleep(3)
    for s in inst:
        pg.evaluate(f'window.irA({s})'); time.sleep(2.5); f = os.path.join(sal, f'{pref}_{s:05.1f}s.png'); pg.screenshot(path=f); print('captura', f, flush=True)
    print('errores de pagina:', errs[:5], flush=True); b.close()
