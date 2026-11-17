// =====================================================================================================
// 8b) EQUIPOS ANIMADOS DEL ÁREA 1313 — mismas particiones, materiales y pistas que el visor v4.1 (animaciones.json,
//     animación «ciclo-completo», 60 s, se repite): molinos ML-1401/1402 (gira solo el tambor, con franjas guía),
//     pórtico CN-1406 (traslación sobre rieles, carro y 2 ganchos con cable estirable) y pescantes CN-1404/1405 (giro de
//     pluma + gancho). Geometría: unir_capas_1313.py -> area1313_web_equipos.bin (coordenadas del visor v4, Y arriba).
//     El grupo «marco» lleva el v4 a los ejes del modelo: giro de 180° en Y + traslación (TX, TZ, -TY).
//     Las piezas móviles no proyectan sombra (el mapa de sombras es estático, como la grúa del Hito).
// =====================================================================================================
const EQUIPOS = __EQUIPOS__;
const GRUA = {activa: Q.get('grua') !== '0', partes: {}, listo: null, marco: null};
const DEG = Math.PI / 180;

// ---- Aspecto del visor v4 (materialIndustrial + parchearMaterial de index_v4.html): PBR por disciplina/color, barniz,
//      variación de superficie y vetas de intemperie en coordenadas de objeto; franjas guía en el tambor de los molinos.
const UMARCA = {value: 1};
const GLSL_V4 = `
float h31(vec3 p){ p = fract(p * 0.1031); p += dot(p, p.yzx + 33.33); return fract((p.x + p.y) * p.z); }
float vruido(vec3 p){
  vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = mix(mix(h31(i), h31(i + vec3(1.,0.,0.)), f.x), mix(h31(i + vec3(0.,1.,0.)), h31(i + vec3(1.,1.,0.)), f.x), f.y);
  float b = mix(mix(h31(i + vec3(0.,0.,1.)), h31(i + vec3(1.,0.,1.)), f.x), mix(h31(i + vec3(0.,1.,1.)), h31(i + vec3(1.,1.,1.)), f.x), f.y);
  return mix(a, b, f.z);
}`;
function parchearV4(mat, piv, terreno) {
  const marca = !!piv;
  mat.onBeforeCompile = sh => {
    sh.uniforms.uReal = UG.real;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vPosO;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvPosO = position;');
    let decl = '#include <common>\nvarying vec3 vPosO;\nuniform float uReal;\n' + GLSL_V4 + '\n';
    if (marca) { sh.uniforms.uMarca = UMARCA; sh.uniforms.uPiv = {value: piv.clone()}; decl += 'uniform float uMarca;\nuniform vec3 uPiv;\n'; }
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', decl)
      .replace('#include <color_fragment>', `#include <color_fragment>
        float nzA = vruido(vPosO * 1.7) * 0.65 + vruido(vPosO * 9.0) * 0.35;
        float vet = vruido(vec3(vPosO.x * 2.2, vPosO.y * 0.22, vPosO.z * 2.2));
        diffuseColor.rgb *= 1.0 - uReal * (0.20 * (nzA - 0.5) + 0.16 * smoothstep(0.55, 0.95, vet));
        ${marca ? `float angG = atan(vPosO.z - uPiv.z, vPosO.y - uPiv.y);
        float franja = smoothstep(0.1, 0.35, cos(angG * 4.0));
        diffuseColor.rgb *= 1.0 - uMarca * 0.50 * franja;` : ''}`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = clamp(roughnessFactor + uReal * (nzA - 0.5) * 0.30 + uReal * 0.10 * smoothstep(0.55, 0.95, vet), 0.04, 1.0);`)
      // terreno (campo de alturas de Navisworks con facetas de normales dispares): normal de iluminación 70 % hacia la vertical,
      // igual que el terreno del visor del Hito (si no, las facetas se ven como franjas claras y oscuras)
      .replace('#include <normal_fragment_maps>', terreno ? `#include <normal_fragment_maps>
        normal = normalize(mix(normal, normalize((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz), 0.7));` : '#include <normal_fragment_maps>');
  };
  mat.customProgramCacheKey = () => 'v4real' + (marca ? 'M' : '') + (terreno ? 'T' : '');
}
function materialV4(ent, piv) {
  const color = new THREE.Color(ent.color), hsl = {}; color.getHSL(hsl);
  const gris = hsl.s < 0.2;
  if (ent.a && ent.a !== 1) color.multiplyScalar(ent.a);
  const envBase = gris ? 1.0 : (ent.metal > 0.3 ? 0.9 : 0.45);
  const base = {color, metalness: ent.metal, roughness: ent.rug, envMapIntensity: envBase * luz.reflejos, side: THREE.DoubleSide,
                transparent: ent.alfa < 1, opacity: ent.alfa, depthWrite: ent.alfa >= 1};
  const m = ent.cc ? new THREE.MeshPhysicalMaterial(Object.assign(base, {clearcoat: ent.cc, clearcoatRoughness: 0.35})) : new THREE.MeshStandardMaterial(base);
  m.userData.envBase = envBase;
  parchearV4(m, piv, ent.id === 'MAT_C6B88D');
  return m;
}

// ---- Suelo extenso: mismo material que el terreno de Navisworks, justo bajo su punto más bajo
function ajustarSuelo(raiz) {
  const e = MATS['MAT_C6B88D']; if (!e || !e.mallas.length) return;
  const b = new THREE.Box3(); for (const m of e.mallas) b.expandByObject(m);
  suelo.position.y = b.min.y - 0.15; suelo.updateMatrixWorld();
  // el terreno no proyecta sombra (como en el Hito): sus huecos de malla dejaban ver la sombra sobre el suelo extenso
  for (const m of e.mallas) m.userData.sinSombra = true;
  suelo.userData.sinSombra = true; if (!e.mallas.includes(suelo)) e.mallas.push(suelo);
  aplicarMaterial(e, false); suelo.material = e.material;
}

// ---- Montaje de las partes (montarPartes del v4): nodo en su pivote; mallas desplazadas −pivote. Parte «estirable»
//      (gancho + cable): el nodo es solo un impulsor; su Δy se aplica a los vértices (rígido bajo y1, anclado sobre y2).
async function prepararGrua() {
  if (!EQUIPOS) return;
  let buf;
  try { const r = await fetch(CONFIG.EQUIPOS_BIN); if (!r.ok) throw new Error('HTTP ' + r.status); buf = await r.arrayBuffer(); }
  catch (e) { console.warn('Equipos animados no disponibles:', e); aviso('No se encontró ' + CONFIG.EQUIPOS_BIN); return; }
  const marco = new THREE.Group(); marco.name = 'equipos_v4';
  marco.rotation.y = Math.PI; marco.position.set(EQUIPOS.TX, EQUIPOS.TZ, -EQUIPOS.TY);
  const P = GRUA.partes, tocadas = new Set();
  for (const p of EQUIPOS.partes) P[p.id] = Object.assign({}, p, {nodo: new THREE.Group(), mal: []});
  for (const p of Object.values(P)) p.piv = new THREE.Vector3(...(p.pivote || (p.padre && P[p.padre].pivote) || [0, 0, 0]));
  for (const p of Object.values(P)) {
    const pa = p.padre ? P[p.padre] : null, cont = pa ? pa.nodo : marco, off = pa ? pa.piv : new THREE.Vector3();
    p.nodo.name = 'parte_' + p.id; p.nodo.position.copy(p.piv).sub(off); p.rest = p.nodo.position.clone(); cont.add(p.nodo);
    for (const s of p.mallas) {
      const pos = new Float32Array(buf, s.pos, s.vert * 3), nor = new Int8Array(buf, s.nor, s.vert * 3);
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(p.estirable ? pos.slice() : pos, 3));
      g.setAttribute('normal', new THREE.BufferAttribute(nor, 3, true));
      g.computeBoundingSphere();
      const id = `V4_${s.disciplina}_${s.color.toString(16).toUpperCase().padStart(6, '0')}`;
      const ent = MATS[id] || (MATS[id] = crearEntrada(id));
      const m = new THREE.Mesh(g); m.name = 'equipo_' + p.id; m.userData.sinSombra = true; m.receiveShadow = true;
      if (/_giro$/.test(p.id)) { m.userData.entMarca = ent; m.material = materialV4(ent, p.piv); }   // franjas guía: material propio
      else { ent.mallas.push(m); tocadas.add(ent); }
      ent.tris += s.vert / 3; nTri += s.vert / 3;
      if (p.estirable) { m.position.copy(off).negate(); cont.add(m); m.userData.pos0 = pos.slice(); m.frustumCulled = false; }
      else { m.position.copy(p.piv).negate(); p.nodo.add(m); }
      p.mal.push(m);
    }
  }
  scene.add(marco); GRUA.marco = marco;
  for (const e of tocadas) aplicarMaterial(e, !e.material);
  for (const e of tocadas) for (const m of e.mallas) if (m.userData.sinSombra) m.castShadow = false;
  pintarListaMat();
  animarGrua(t);
  console.log('Equipos animados:', Object.values(P).map(p => `${p.id} ${p.tri}`).join(', '));
}

// ---- Pistas (crearPistas/muestrear del v4): «suave» = smoothstep por tramo; «lineal»; «escalon». Δ sobre el reposo.
function evPista(k, tt) {
  const ks = k.claves, n = ks.length;
  if (tt <= ks[0][0]) return ks[0][1];
  if (tt >= ks[n - 1][0]) return ks[n - 1][1];
  let i = 0; while (i < n - 2 && tt > ks[i + 1][0]) i++;
  const [t0, a] = ks[i], [t1, b] = ks[i + 1];
  let u = t1 > t0 ? (tt - t0) / (t1 - t0) : 1;
  if (k.modo === 'suave') u = u * u * (3 - 2 * u); else if (k.modo === 'escalon') u = 0;
  return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
}
function estirar(p, dy) {
  const e = p.estirable; if (p.ultimo !== undefined && Math.abs(dy - p.ultimo) < 1e-5) return;
  p.ultimo = dy; const den = Math.max(1e-6, e.y2 - e.y1);
  for (const m of p.mal) {
    const a = m.geometry.attributes.position, q = a.array, q0 = m.userData.pos0;
    for (let i = 1; i < q.length; i += 3) { const y = q0[i]; q[i] = y + dy * (y <= e.y1 ? 1 : (y >= e.y2 ? 0 : (e.y2 - y) / den)); }
    a.needsUpdate = true; m.geometry.computeBoundingSphere();
  }
}
function animarGrua(tt) {
  if (!GRUA.marco) return;
  const D = EQUIPOS.duracion, tc = GRUA.activa ? ((tt % D) + D) % D : 0;
  for (const [id, pk] of Object.entries(EQUIPOS.pistas)) {
    const p = GRUA.partes[id]; if (!p) continue;
    if (pk.posicion) {
      const d = evPista(pk.posicion, tc);
      p.nodo.position.set(p.rest.x + d[0], p.rest.y + d[1], p.rest.z + d[2]);
      if (p.estirable) estirar(p, d[1]);
    }
    if (pk.rotacion) { const d = evPista(pk.rotacion, tc); p.nodo.rotation.set(d[0] * DEG, d[1] * DEG, d[2] * DEG, 'XYZ'); }
  }
}
