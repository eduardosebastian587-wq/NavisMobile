# Crea herramientas/plantilla_visor_1313.html a partir de la plantilla del visor del Hito (HITO_M33-1/herramientas/
# plantilla_visor_hito.html) cambiando SOLO lo propio del Área 1313 (2026-10-30):
#   · modelo area1313_web.glb (Capas: Piping/Control/Electrical/terreno + v4: Mechanical/Structural), sin relleno ni sueltos;
#   · materiales con el aspecto del visor v4 (PBR por disciplina y color de Navisworks + acabado y franjas guía del v4);
#   · sección 8b: equipos animados del v4.1 (molinos, pórtico CN-1406, pescantes CN-1404/1405) con las pistas de «ciclo-completo»;
#   · terreno sin aplanar, con el color de Navisworks; correas ocultas (no hay en el área); textos y claves de almacenamiento propios.
# Cada reemplazo exige encontrar el texto original exactamente una vez (si la plantilla del Hito cambia, el script se detiene).
# Uso: py parchar_plantilla_1313.py <plantilla_visor_hito.html> <plantilla_visor_1313.html>
import sys, re
ent, sal = sys.argv[1], sys.argv[2]
h = open(ent, encoding='utf-8').read()
def rep(viejo, nuevo, n=1):
    global h
    c = h.count(viejo)
    assert c == n, f'se esperaban {n} apariciones y hay {c}: {viejo[:80]!r}'
    h = h.replace(viejo, nuevo)

# ---- textos, archivos y claves propias
rep('<title>HITO M33-1 – Recorrido virtual</title>', '<title>ÁREA 1313 – Recorrido virtual</title>')
rep('║  VISOR HITO M33-1 · v3 (2026-10-29)  · Three.js r170 · PBR + texturas procedurales + GTAO    ║',
    '║  VISOR ÁREA 1313 · v1 (2026-10-30, base: visor Hito v3) · Three.js r170 · aspecto visor v4   ║')
rep('generar_visor_hito.py — NO editar', 'generar_visor_1313.py — NO editar')
rep('herramientas/plantilla_visor_hito.html o la escena', 'herramientas/plantilla_visor_1313.html o los datos')
rep('HITO M33-1 – Cargando modelo…', 'ÁREA 1313 – Cargando modelo…')
rep('HITO M33-1 – RECORRIDO VIRTUAL', 'ÁREA 1313 · MOLINOS – RECORRIDO VIRTUAL', 2)
rep('`Hito_M33-1_${', '`Area_1313_${')
rep("modelo: 'Hito M33-1'", "modelo: 'Área 1313'")
rep('mismo origen que convertidos_blender/hito_web.glb', 'mismo origen que convertidos_blender/area1313_web.glb')
for k in ('recorridos_propios', 'editor_claves', 'materiales'):
    h, n = re.subn(rf"'hito_{k}'", f"'a1313_{k}'", h); assert n >= 1, k
rep("""  MODELO: Q.get('modelo') || 'convertidos_blender/hito_web.glb',
  RELLENO: Q.get('relleno') === '0' ? null : 'convertidos_blender/hito_terreno_relleno.json',""",
    """  MODELO: Q.get('modelo') || 'convertidos_blender/area1313_web.glb',
  RELLENO: null,                                             // Área 1313: el terreno se usa tal como viene de Navisworks
  EQUIPOS_BIN: 'convertidos_blender/area1313_web_equipos.bin', // piezas animadas (unir_capas_1313.py)""")
rep("SUELTOS_GLB: 'convertidos_blender/hito_sueltos.glb',", "SUELTOS_GLB: null,")
rep("DISTANCIAS: 'convertidos_blender/hito_recorrido_distancias.bin',", "DISTANCIAS: 'convertidos_blender/area1313_recorrido_distancias.bin',")
rep("Genere el modelo con <b>EXPORTAR_HITO_GLB.bat</b> y abra el visor con <b>INICIAR_VISOR_HITO.bat</b>",
    "Genere el modelo con <b>herramientas/unir_capas_1313.py</b> y abra el visor con <b>INICIAR_VISOR_1313.bat</b>")
rep('Animar el puente grúa del edificio</label>', 'Animar los equipos (molinos, pórtico CN-1406, pescantes)</label>')
rep('hito_realista_limpio.blend → convertidos_blender/hito_web.glb (Draco).', 'Capas area 1313 + v4 → convertidos_blender/area1313_web.glb (Draco).')
rep('Los elementos sueltos detectados se quitaron y van aparte en hito_sueltos.glb.', 'Equipos animados del v4.1 aparte: area1313_web_equipos.bin.          ')
rep("descargar('materiales_hito.json'", "descargar('materiales_1313.json'")
rep('<details id="secCorreas">', '<details id="secCorreas" style="display:none">')

# ---- materiales: acabado «v4» (perfil PBR por disciplina/color del visor v4, valores puestos por generar_visor_1313.py)
rep("  terreno:           {nombre: 'Terreno (sombreador del video)'",
    "  v4:                {nombre: 'Visor v4 (PBR por disciplina y color)', patron: 0, barniz: 0, varA: 0, varR: 0, vetas: 0, desgaste: 0, piel: 0, polvo: 0},\n"
    "  terreno:           {nombre: 'Terreno (sombreador del video)'")
rep("const base = {acabado: acabadoInicial(id, v.alfa), color: '#' + v.color, metal: v.metal, rug: v.rugosidad, alfa: v.alfa, textura: 1, polvo: 1, visible: true};",
    "const base = {acabado: v.acabado || acabadoInicial(id, v.alfa), color: '#' + v.color, metal: v.metal, rug: v.rugosidad, alfa: v.alfa,\n"
    "                cc: v.cc || 0, a: v.a || 1, disciplina: v.disciplina || '', textura: 1, polvo: 1, visible: true};")
rep("  if (ent.acabado === 'terreno') return materialTerreno();\n",
    "  if (ent.acabado === 'terreno') return materialTerreno();\n  if (ent.acabado === 'v4') return materialV4(ent, null);\n")
rep("const m = ent.material; m.color.set(ent.color); m.metalness = ent.metal;",
    "const m = ent.material; m.color.set(ent.color); if (ent.acabado === 'v4' && ent.a) m.color.multiplyScalar(ent.a); m.metalness = ent.metal;")

# ---- terreno sin aplanar
rep("""const PLANO = {suelo: -41.6, polis: [
  {z: -42.2, p: [[-70, -400], [600, -400], [600, 400], [-70, 400]]}]};""",
    "const PLANO = {suelo: null, polis: []};   // Área 1313: terreno tal como viene de Navisworks (sin aplanar)")
rep("if (Q.get('plano') !== '0') { suelo.position.y = PLANO.suelo;", "if (PLANO.suelo !== null && Q.get('plano') !== '0') { suelo.position.y = PLANO.suelo;")

# ---- carga: equipos animados (asíncronos) y suelo extenso con el material del terreno
rep("  prepararGrua(gltf.scene);\n", "  GRUA.listo = prepararGrua(gltf.scene);\n")
rep("cajaPlanta.setFromObject(gltf.scene); aplicarSol();", "cajaPlanta.setFromObject(gltf.scene); ajustarSuelo(gltf.scene); aplicarSol();")
rep("cargarRelleno().finally(() => {", "Promise.all([cargarRelleno(), GRUA.listo]).finally(() => {")

# ---- sección 8b
i0 = h.index('// 8b) ANIMACIÓN DE LA GRÚA'); i0 = h.rindex('// =====', 0, i0)
i1 = h.index('// 8c) CORREAS'); i1 = h.rindex('// =====', 0, i1)
h = h[:i0] + open(sys.argv[3] if len(sys.argv) > 3 else 'seccion_8b_1313.js', encoding='utf-8').read() + '\n' + h[i1:]
assert '__EQUIPOS__' in h and 'GRUA.puenteT' not in h
open(sal, 'w', encoding='utf-8', newline='\n').write(h)
print('plantilla 1313 creada:', sal, f'({len(h)/1024:.0f} KB)')
