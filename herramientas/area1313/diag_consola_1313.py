# Diagnostico: abre el visor (URL como 1er argumento) en Chrome y vuelca los mensajes de consola / errores durante N segundos.
import sys, os, time, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8066), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = sys.argv[1]; seg = int(sys.argv[2]) if len(sys.argv) > 2 else 60
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False); pg = b.new_page(viewport={'width': 1280, 'height': 720})
    pg.on('pageerror', lambda e: print('PAGEERROR', str(e)[:400], flush=True))
    pg.on('console', lambda m: print('CONSOLA', m.type, m.text[:300], flush=True))
    pg.on('requestfailed', lambda r: print('REQFAIL', r.url[-90:], flush=True))
    pg.on('response', lambda r: print('HTTP', r.status, r.url[-90:], flush=True) if r.status >= 400 else None)
    pg.goto('http://127.0.0.1:8066/' + url)
    for i in range(seg):
        time.sleep(1)
        if pg.evaluate('window.__listo === true'): print('LISTO en', i + 1, 's', flush=True); break
    print('HUD:', pg.evaluate("(document.getElementById('hud')||{}).textContent"), '| carga:', pg.evaluate("(document.getElementById('carga')||document.body).innerText.slice(0,200)"), flush=True)
    b.close()
