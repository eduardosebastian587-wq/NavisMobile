# Boton MP4 del visor del Area 1313 (Chrome, GPU real). Uso: py grabar_video_1313.py [WxH=1280x720] [calidad=media] [pagina=index_1313.html]
import os, sys, time, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
RES = sys.argv[1] if len(sys.argv) > 1 else '1280x720'; CAL = sys.argv[2] if len(sys.argv) > 2 else 'media'
PAG = sys.argv[3] if len(sys.argv) > 3 else 'index_1313.html'; ETQ = os.path.splitext(PAG.split('?')[0])[0].replace('index_1313', '').strip('_')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8064), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False, args=['--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion'])
    pg = b.new_page(viewport={'width': 1280, 'height': 720}, accept_downloads=True); pg.set_default_timeout(0)
    pg.on('pageerror', lambda e: print('ERROR pagina:', e, flush=True))
    pg.goto('http://127.0.0.1:8064/' + PAG + ('&' if '?' in PAG else '?') + 'calidad=' + CAL + '&panel=0')
    pg.wait_for_function('window.__listo === true', timeout=0, polling=1000); print('visor cargado', flush=True)
    pg.evaluate("r => { const e = document.getElementById('selRes'); e.value = r; e.dispatchEvent(new Event('change')); }", RES)
    t0 = time.time(); print('grabando', RES, flush=True)
    with pg.expect_download(timeout=0) as d:
        pg.evaluate("document.getElementById('bVideo').click()")
    os.makedirs('videos', exist_ok=True); dst = os.path.join(raiz, 'videos', 'Area1313_recorrido_' + (ETQ + '_' if ETQ else '') + RES + '_' + CAL + '.mp4')
    d.value.save_as(dst); print('listo', dst, round(os.path.getsize(dst) / 1e6, 1), 'MB', round(time.time() - t0), 's', flush=True)
    b.close()