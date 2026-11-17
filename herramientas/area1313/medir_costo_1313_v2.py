# Medicion de costo de dibujo por cuadro (ms) en instantes del recorrido; variantes para ubicar el cuello de botella.
import os, sys, json, threading, http.server, socketserver
from playwright.sync_api import sync_playwright
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(raiz)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 8065), Q); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = sys.argv[1] if len(sys.argv) > 1 else 'index_1313.html'
JS = """async (instantes) => {
  const A = window.__api, out = {};
  A.ao(false);
  const medir = () => { const t0 = performance.now(); for (let i = 0; i < 6; i++) { A.composer.render(0); const g = A.renderer.getContext(); g.readPixels(0, 0, 1, 1, g.RGBA, g.UNSIGNED_BYTE, new Uint8Array(4)); } return +((performance.now() - t0) / 6).toFixed(1); };
  for (const s of instantes) {
    window.irA(s); A.ao(false); const r = {};
    medir(); r.base = medir();
    const basico = new A.THREE.MeshBasicMaterial({color: 0x888888}); A.scene.overrideMaterial = basico; medir(); r.solo_geometria = medir(); A.scene.overrideMaterial = null;
    const px = A.renderer.getPixelRatio(); A.renderer.setPixelRatio(px * 0.5); A.composer.setPixelRatio && A.composer.setPixelRatio(px * 0.5);
    medir(); r.mitad_resolucion = medir(); A.renderer.setPixelRatio(px); A.composer.setPixelRatio && A.composer.setPixelRatio(px);
    A.scene.children.forEach(c => c._v = c.visible); A.scene.children.forEach(c => { if (c.isMesh || c.isGroup || c.isObject3D) c.visible = c.isLight ? c.visible : false; }); medir(); r.escena_vacia = medir(); A.scene.children.forEach(c => c.visible = c._v);
    out[s] = r;
  }
  return out; }"""
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=False)
    pg = b.new_page(viewport={'width': 1280, 'height': 720}); pg.set_default_timeout(0)
    pg.goto('http://127.0.0.1:8065/' + URL + ('&' if '?' in URL else '?') + 'calidad=media&prueba=1&panel=0&auto=0')
    pg.on('console', lambda m: print('LOG', m.text) if ('zonas' in m.text or 'nula' in m.text) else None); pg.wait_for_function('window.__listo === true', timeout=0, polling=1000)
    print(json.dumps(pg.evaluate(JS, [0, 9, 26, 37, 42, 55]), indent=0), flush=True)
    b.close()