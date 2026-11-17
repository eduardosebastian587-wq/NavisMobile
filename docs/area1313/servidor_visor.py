#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================================
  servidor_visor.py · Visor 3D v3 · Servidor local con conversión Navisworks (.nwd)
-------------------------------------------------------------------------------------
  Sustituye a "python -m http.server": sirve la carpeta del visor igual que antes y
  añade una pequeña API para que el navegador pueda abrir archivos .nwd.

  El navegador no puede leer .nwd (formato cerrado de Autodesk). Este servidor:
    1. recibe el .nwd (si ya está en esta carpeta, no lo copia: lo usa en su sitio),
    2. lo convierte a FBX con Navisworks instalado (herramientas/nwd_a_fbx.ps1),
    3. lo deja en "convertidos_nwd/<nombre>.fbx" y el visor lo carga como cualquier FBX.
  Las conversiones quedan en caché: si el .nwd no cambió, no se vuelve a convertir.

  Uso:   python servidor_visor.py [puerto]          (por defecto 8000; lo lanza INICIAR_VISOR_V3.bat)
  Solo escucha en 127.0.0.1 (este equipo). Sin dependencias externas (biblioteca estándar).

  API (todas las respuestas en JSON):
    GET  /api/estado                               → versión, Navisworks detectado, conversión en curso
    POST /api/nwd/convertir?nombre=&tamano=[&forzar=1]
                                                   → inicia (o reutiliza) la conversión; 409 si hay que subir el archivo
    PUT  /api/nwd/subir?nombre=                    → recibe el .nwd (cuerpo binario) en convertidos_nwd/entrantes/
    GET  /api/nwd/trabajo?id=                      → estado de la conversión (etapa, segundos, MB escritos, FBX)
    POST /api/nwd/cancelar?id=                     → detiene la conversión (cierra Navisworks)
    PUT  /api/paquete?destino=<ruta>.visor.glb     → guarda el paquete optimizado junto al FBX convertido
=====================================================================================
"""
import glob
import http.server
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

VERSION = 3
RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_CONV = os.path.join(RAIZ, 'convertidos_nwd')
CARPETA_ENTRANTES = os.path.join(CARPETA_CONV, 'entrantes')
SCRIPT_PS = os.path.join(RAIZ, 'herramientas', 'nwd_a_fbx.ps1')
TIEMPO_MAX_S = int(os.environ.get('VISOR_TIEMPO_MAX_S', '7200'))   # tope por conversión (2 h)
EXT_NAVIS = ('.nwd',)
BLOQUE = 4 * 1024 * 1024


# ---------------------------------------------------------------------------------
# Navisworks
# ---------------------------------------------------------------------------------
def buscar_navisworks():
    """Carpeta de Navisworks Manage/Simulate más reciente con la API de automatización (o None)."""
    candidatos = []
    if os.environ.get('NAVISWORKS_DIR'):
        candidatos.append(os.environ['NAVISWORKS_DIR'])
    bases = {os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramW6432', r'C:\Program Files')}
    encontrados = []
    for base in bases:
        for d in glob.glob(os.path.join(base, 'Autodesk', 'Navisworks *')):
            m = re.search(r'Navisworks (Manage|Simulate) (\d{4})$', d)
            if m:
                encontrados.append((int(m.group(2)), d))
    candidatos += [d for _, d in sorted(encontrados, reverse=True)]
    for d in candidatos:
        if os.path.isfile(os.path.join(d, 'Autodesk.Navisworks.Automation.dll')):
            return d
    return None


NAVISWORKS = buscar_navisworks()


# ---------------------------------------------------------------------------------
# Trabajos de conversión (uno a la vez: Navisworks usa mucha memoria)
# ---------------------------------------------------------------------------------
class Trabajo:
    def __init__(self, nwd, fbx):
        self.id = uuid.uuid4().hex[:12]
        self.nwd = nwd
        self.fbx = fbx
        self.tmp = fbx[:-4] + '.parcial.fbx'
        self.estado = 'en_cola'          # en_cola | convirtiendo | listo | error | cancelado
        self.etapa = 'en_cola'           # iniciando | abriendo | exportando | listo
        self.mensaje = ''
        self.inicio = time.time()
        self.fin = None
        self.proc = None
        self.cancelado = False
        self.desde_cache = False
        self.registro = []
        self.analisis = None             # mallas / vértices / triángulos del FBX resultante

    def como_json(self):
        escrito = 0
        if self.estado == 'convirtiendo' and os.path.exists(self.tmp):
            try:
                escrito = os.path.getsize(self.tmp)
            except OSError:
                pass
        fbx_ok = self.estado == 'listo'
        return {
            'id': self.id, 'estado': self.estado, 'etapa': self.etapa, 'mensaje': self.mensaje,
            'segundos': round((self.fin or time.time()) - self.inicio, 1),
            'bytes_escritos': escrito,
            'nwd': os.path.basename(self.nwd), 'tamano_nwd': tamano(self.nwd),
            'fbx': ruta_web(self.fbx) if fbx_ok else None,
            'tamano_fbx': tamano(self.fbx) if fbx_ok else 0,
            'desde_cache': self.desde_cache,
            'analisis': self.analisis,
        }


def analizar_fbx(ruta):
    """Cuenta mallas, vértices y triángulos de un FBX binario leyendo sólo cabeceras (segundos, sin cargarlo entero).
    Sirve para avisar en el visor antes de enviar al navegador un modelo que no podría abrir."""
    res = {'mallas': 0, 'vertices': 0, 'triangulos': 0, 'curvas': 0}
    try:
        with open(ruta, 'rb') as f:
            cab = f.read(27)
            if cab[:18] != b'Kaydara FBX Binary':
                return None
            ver = struct.unpack('<I', cab[23:27])[0]
            ancho = 8 if ver >= 7500 else 4
            fmt_nodo = '<QQQ' if ancho == 8 else '<III'
            centinela = 13 * (2 if ancho == 8 else 1) - (1 if ancho == 8 else 0)

            def nodo():
                fin, nprop, lprop = struct.unpack(fmt_nodo, f.read(3 * ancho))
                nom = f.read(f.read(1)[0])
                return fin, nprop, lprop, nom

            def props(n):
                out = []
                for _ in range(n):
                    t = f.read(1)
                    if t in (b'S', b'R'):
                        k = struct.unpack('<I', f.read(4))[0]
                        out.append(f.read(k).split(b'\x00')[0])
                    elif t == b'L':
                        out.append(struct.unpack('<q', f.read(8))[0])
                    elif t in (b'd', b'i', b'f', b'l', b'b'):
                        largo, _, comp = struct.unpack('<III', f.read(12))
                        out.append(largo)
                        f.seek(comp, 1)
                    else:
                        break
                return out

            tam = f.seek(0, 2)
            f.seek(27)
            while f.tell() < tam - 200:
                fin, _, lprop, nom = nodo()
                if fin == 0:
                    break
                if nom != b'Objects':
                    f.seek(fin)
                    continue
                f.seek(lprop, 1)
                while f.tell() < fin - centinela:
                    cfin, cn, _, cnom = nodo()
                    if cfin == 0:
                        break
                    if cnom == b'Geometry':
                        p = props(cn)
                        tipo = p[2] if len(p) > 2 else b''
                        if tipo == b'NurbsCurve':
                            res['curvas'] += 1
                        elif tipo == b'Mesh':
                            res['mallas'] += 1
                            while f.tell() < cfin - centinela:
                                gfin, gn, _, gnom = nodo()
                                if gfin == 0:
                                    break
                                if gnom == b'Vertices':
                                    res['vertices'] += props(gn)[0] // 3
                                elif gnom == b'PolygonVertexIndex':
                                    res['triangulos'] += props(gn)[0] // 3
                                f.seek(gfin)
                    f.seek(cfin)
                f.seek(fin)
    except (OSError, struct.error, IndexError) as e:
        print(f'[FBX] No se pudo analizar {ruta}: {e}')
        return None
    return res


TRABAJOS = {}
CANDADO = threading.Lock()
SEMAFORO = threading.Semaphore(1)


def tamano(ruta):
    try:
        return os.path.getsize(ruta)
    except OSError:
        return 0


def ruta_web(ruta_abs):
    return os.path.relpath(ruta_abs, RAIZ).replace(os.sep, '/')


def matar_arbol(proc):
    """Cierra PowerShell y la instancia de Navisworks (Roamer.exe) que lanzó."""
    if proc and proc.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
        else:
            proc.kill()


def ejecutar(t):
    with SEMAFORO:
        if t.cancelado:
            return
        t.estado, t.etapa, t.inicio = 'convirtiendo', 'iniciando', time.time()
        for viejo in (t.tmp,):
            if os.path.exists(viejo):
                os.remove(viejo)
        cmd = ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', SCRIPT_PS,
               '-Entrada', t.nwd, '-Salida', t.tmp, '-NavisDir', NAVISWORKS]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        try:
            t.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
        except OSError as e:
            t.estado, t.mensaje, t.fin = 'error', f'No se pudo iniciar PowerShell: {e}', time.time()
            return

        def leer():
            for crudo in t.proc.stdout:
                linea = crudo.decode('utf-8', 'replace').strip().lstrip('\ufeff')
                if not linea:
                    continue
                t.registro = (t.registro + [linea])[-30:]
                if linea.startswith('ETAPA:'):
                    t.etapa = linea[6:]
                elif linea.startswith('ERROR:'):
                    t.mensaje = linea[6:]
        lector = threading.Thread(target=leer, daemon=True)
        lector.start()
        try:
            rc = t.proc.wait(timeout=TIEMPO_MAX_S)
        except subprocess.TimeoutExpired:
            matar_arbol(t.proc)
            rc = -1
            t.mensaje = f'La conversión superó el tiempo máximo ({TIEMPO_MAX_S // 60} min) y se detuvo.'
        lector.join(timeout=5)
        t.fin = time.time()
        if t.cancelado:
            t.estado, t.mensaje = 'cancelado', 'Conversión cancelada por el usuario.'
        elif rc == 0 and tamano(t.tmp) > 1024:
            os.replace(t.tmp, t.fbx)           # el FBX final sólo aparece cuando está completo
            t.analisis = analizar_fbx(t.fbx)
            t.estado, t.etapa = 'listo', 'listo'
            print(f'[NWD] {os.path.basename(t.nwd)} → {ruta_web(t.fbx)} ({tamano(t.fbx) / 1048576:.1f} MB, {t.fin - t.inicio:.0f} s)')
        else:
            t.estado = 'error'
            if not t.mensaje:
                t.mensaje = 'Navisworks no completó la exportación. ' + ' | '.join(t.registro[-5:])
            print(f'[NWD] ERROR {os.path.basename(t.nwd)}: {t.mensaje}')
        if t.estado != 'listo' and os.path.exists(t.tmp):
            try:
                os.remove(t.tmp)
            except OSError:
                pass


def ubicar_nwd(nombre, tam):
    """Busca el .nwd en la carpeta del visor o en entrantes/ (mismo nombre y, si se indica, mismo tamaño)."""
    for carpeta in (RAIZ, CARPETA_ENTRANTES):
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta) and (not tam or tamano(ruta) == tam):
            return ruta
    return None


def iniciar_conversion(nwd, forzar=False):
    base = os.path.splitext(os.path.basename(nwd))[0]
    fbx = os.path.join(CARPETA_CONV, base + '.fbx')
    os.makedirs(CARPETA_CONV, exist_ok=True)
    with CANDADO:
        for t in TRABAJOS.values():         # misma conversión ya en marcha → se reutiliza
            if t.nwd == nwd and t.estado in ('en_cola', 'convirtiendo'):
                return t
        t = Trabajo(nwd, fbx)
        TRABAJOS[t.id] = t
    # Caché: FBX ya convertido y no más antiguo que el .nwd
    if not forzar and tamano(fbx) > 1024 and os.path.getmtime(fbx) >= os.path.getmtime(nwd):
        t.analisis = analizar_fbx(fbx)
        t.estado, t.etapa, t.desde_cache, t.fin = 'listo', 'listo', True, time.time()
        return t
    threading.Thread(target=ejecutar, args=(t,), daemon=True).start()
    return t


# ---------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------
class Manejador(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **{
        '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.fbx': 'application/octet-stream',
        '.json': 'application/json', '.js': 'text/javascript', '.hdr': 'application/octet-stream',
    })

    def __init__(self, *a, **k):
        super().__init__(*a, directory=RAIZ, **k)

    def log_message(self, fmt, *args):       # sólo errores y la API (no cada petición de archivo)
        ruta = self.path or ''
        if (len(args) > 1 and str(args[1])[:1] in '45') or ('/api/' in ruta and '/api/nwd/trabajo' not in ruta and '/api/estado' not in ruta):
            sys.stderr.write('[%s] %s\n' % (self.log_date_time_string(), fmt % args))

    # ---- utilidades ----
    def responder(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def parametros(self):
        u = urllib.parse.urlsplit(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def recibir_a_archivo(self, destino):
        largo = int(self.headers.get('Content-Length') or 0)
        if largo <= 0:
            raise ValueError('Cuerpo vacío.')
        tmp = destino + '.subiendo'
        restante = largo
        with open(tmp, 'wb') as f:
            while restante > 0:
                trozo = self.rfile.read(min(BLOQUE, restante))
                if not trozo:
                    raise ValueError('La transferencia se interrumpió.')
                f.write(trozo)
                restante -= len(trozo)
        os.replace(tmp, destino)
        return largo

    # ---- verbos ----
    def do_GET(self):
        ruta, q = self.parametros()
        if ruta == '/api/estado':
            activo = any(t.estado in ('en_cola', 'convirtiendo') for t in TRABAJOS.values())
            return self.responder(200, {'version': VERSION, 'navisworks': NAVISWORKS,
                                        'navisworks_nombre': os.path.basename(NAVISWORKS) if NAVISWORKS else None,
                                        'formatos': list(EXT_NAVIS), 'conversion_en_curso': activo})
        if ruta == '/api/nwd/trabajo':
            t = TRABAJOS.get(q.get('id', ''))
            return self.responder(200, t.como_json()) if t else self.responder(404, {'error': 'Trabajo no encontrado.'})
        if ruta.startswith('/api/'):
            return self.responder(404, {'error': 'Ruta de API desconocida.'})
        return super().do_GET()

    def do_POST(self):
        ruta, q = self.parametros()
        if ruta == '/api/nwd/convertir':
            nombre = os.path.basename(q.get('nombre', ''))
            if not nombre.lower().endswith(EXT_NAVIS):
                return self.responder(400, {'error': 'Se esperaba un archivo .nwd.'})
            if not NAVISWORKS:
                return self.responder(503, {'error': 'No se encontró Navisworks Manage/Simulate en este equipo. '
                                                     'Navisworks Freedom no permite exportar.'})
            tam = int(q.get('tamano') or 0)
            nwd = ubicar_nwd(nombre, tam)
            if not nwd:
                return self.responder(409, {'necesita_subir': True})
            t = iniciar_conversion(nwd, forzar=q.get('forzar') == '1')
            return self.responder(200, t.como_json())
        if ruta == '/api/nwd/cancelar':
            t = TRABAJOS.get(q.get('id', ''))
            if not t:
                return self.responder(404, {'error': 'Trabajo no encontrado.'})
            t.cancelado = True
            matar_arbol(t.proc)
            return self.responder(200, {'ok': True})
        return self.responder(404, {'error': 'Ruta de API desconocida.'})

    def do_PUT(self):
        ruta, q = self.parametros()
        try:
            if ruta == '/api/nwd/subir':
                nombre = os.path.basename(q.get('nombre', ''))
                if not nombre.lower().endswith(EXT_NAVIS):
                    return self.responder(400, {'error': 'Se esperaba un archivo .nwd.'})
                os.makedirs(CARPETA_ENTRANTES, exist_ok=True)
                n = self.recibir_a_archivo(os.path.join(CARPETA_ENTRANTES, nombre))
                return self.responder(200, {'ok': True, 'bytes': n})
            if ruta == '/api/paquete':
                destino = os.path.normpath(os.path.join(RAIZ, q.get('destino', '')))
                if not destino.lower().endswith('.visor.glb') or os.path.commonpath([destino, CARPETA_CONV]) != CARPETA_CONV:
                    return self.responder(400, {'error': 'Destino no permitido (sólo .visor.glb dentro de convertidos_nwd).'})
                n = self.recibir_a_archivo(destino)
                return self.responder(200, {'ok': True, 'bytes': n, 'ruta': ruta_web(destino)})
        except (ValueError, OSError) as e:
            return self.responder(500, {'error': str(e)})
        return self.responder(404, {'error': 'Ruta de API desconocida.'})


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)    # mensajes visibles al instante (también si se redirige)
    except AttributeError:
        pass
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor = http.server.ThreadingHTTPServer(('127.0.0.1', puerto), Manejador)
    servidor.daemon_threads = True
    print('=' * 72)
    print(f' Visor 3D v{VERSION} · servidor local en http://localhost:{puerto}/')
    print(f' Carpeta: {RAIZ}')
    print(f' Navisworks: {NAVISWORKS or "NO ENCONTRADO (los .nwd no se podrán convertir)"}')
    print(' Cierra esta ventana (o Ctrl+C) para detener el servidor.')
    print('=' * 72)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for t in TRABAJOS.values():
            matar_arbol(t.proc)


if __name__ == '__main__':
    main()
