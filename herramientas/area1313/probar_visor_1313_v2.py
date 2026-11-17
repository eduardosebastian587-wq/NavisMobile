# Prueba automática del visor del Área 1313 en Google Chrome: carga, verificación de holgura del recorrido, capturas en los
# instantes clave del ciclo (lámina de contacto), FPS en calidad media y errores de consola.
import sys, os, time, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8065), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
sal = os.path.join(raiz, 'capturas_prueba'); os.makedirs(sal, exist_ok=True)
INST = [0, 9, 15, 19, 26, 31, 37, 42, 48, 55]
res = {}; fotos = []
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False)
    pg = b.new_page(viewport={'width': 1280, 'height': 720})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type in ('error', 'warning') else None)
    t0 = time.time()
    pg.goto('http://127.0.0.1:8065/index_1313_v2.html?modelo=convertidos_blender/area1313v2_web_v2.glb&calidad=media&prueba=1&panel=0')
    pg.wait_for_function('window.__listo === true', timeout=300000); res['carga_s'] = round(time.time() - t0, 1); time.sleep(2)
    res['recorridos'] = pg.evaluate("window.__api.RECS.map(r => [r.id, r.nombre, +r.dur.toFixed(2)])")
    res['verificacion_visor'] = pg.evaluate("window.__api.verificar(3).then(v => ({min: +v.min.toFixed(2), tmin: +v.tmin.toFixed(1), tramos: v.tramos}))")
    res['hud'] = pg.evaluate("document.getElementById('hud').textContent")
    for s in INST:
        pg.evaluate(f"window.irA({s})"); f = os.path.join(sal, f'a1313v2_{s:02d}s.png'); pg.screenshot(path=f); fotos.append(f)
    pg.goto('http://127.0.0.1:8065/index_1313_v2.html?modelo=convertidos_blender/area1313v2_web_v2.glb&calidad=media&panel=0')
    pg.wait_for_function('window.__listo === true', timeout=300000); time.sleep(8)
    res['fps_media'] = pg.evaluate("new Promise(r => { let n = 0, t = performance.now(); const f = () => { n++; if (performance.now() - t > 4000) r(+(n / ((performance.now() - t) / 1000)).toFixed(1)); else requestAnimationFrame(f); }; f(); })")
    res['hud_reproduciendo'] = pg.evaluate("document.getElementById('hud').textContent")
    res['errores_y_avisos'] = errs[:12]; b.close()
try:                                                       # lámina de contacto 5 x 2 (640 x 360 por cuadro)
    from PIL import Image, ImageDraw
    L = Image.new('RGB', (5 * 640, 2 * 360))
    for i, f in enumerate(fotos):
        im = Image.open(f).resize((640, 360)); ImageDraw.Draw(im).text((10, 10), f'{INST[i]} s', fill=(255, 255, 0)); L.paste(im, ((i % 5) * 640, (i // 5) * 360))
    L.save(os.path.join(sal, 'a1313v2_lamina.jpg'), quality=85); res['lamina'] = 'capturas_prueba/a1313v2_lamina.jpg'
except Exception as e: res['lamina'] = 'sin Pillow: ' + str(e)
print(json.dumps(res, ensure_ascii=False, indent=1))
open(os.path.join(sal, 'prueba_1313_v2.json'), 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
