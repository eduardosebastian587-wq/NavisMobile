# Genera el MP4 final del recorrido continuo de 50 s con el propio botón del visor (Edge, GPU real, calidad alta, 1920x1080).
import os, sys, time, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
RES = sys.argv[1] if len(sys.argv) > 1 else '1920x1080'
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8062), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=False, args=['--ignore-gpu-blocklist', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion'])
    pg = b.new_page(viewport={'width': 1280, 'height': 720}, accept_downloads=True)
    pg.set_default_timeout(0)
    pg.on('pageerror', lambda e: print('ERROR pagina:', e, flush=True))
    print('abriendo visor', flush=True)
    pg.goto('http://127.0.0.1:8062/index_hito.html?modelo=convertidos_blender/hito_web.glb&calidad=alta')
    pg.wait_for_function('window.__listo === true', timeout=0, polling=1000)
    print('visor cargado', flush=True)
    pg.evaluate("window.__api.activar('continuo_50s')")
    pg.evaluate("r => { const e = document.getElementById('selRes'); e.value = r; e.dispatchEvent(new Event('change')); }", RES)
    t0 = time.time(); print('grabando', RES, pg.evaluate("document.getElementById('selRes').value"), flush=True)
    with pg.expect_download(timeout=0) as d:
        pg.evaluate("document.getElementById('bVideo').click()")
    dl = d.value; destino = os.path.join(raiz, 'videos', 'Hito_M33-1_recorrido_continuo_50s_' + RES + '_alta.mp4')
    dl.save_as(destino); print('listo', destino, round(os.path.getsize(destino) / 1e6, 1), 'MB', round(time.time() - t0), 's', flush=True)
    b.close()
