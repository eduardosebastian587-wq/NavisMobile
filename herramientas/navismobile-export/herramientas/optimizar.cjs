// weld -> simplify -> draco en una sola lectura/escritura (sin intermedios _w.glb / _s.glb).
// Uso: node optimizar.cjs entrada.glb salida.glb [--ratio 0.25] [--error 0.0001] [--modulos <carpeta node_modules>]
const path = require('path');
const { pathToFileURL } = require('url');
const arg = (n, d) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const MOD = arg('--modulos', [path.join(__dirname, '..', 'node_modules'), path.join(__dirname, '..', '..', '..', 'node_modules')]
  .find((d) => require('fs').existsSync(path.join(d, '@gltf-transform'))) || 'C:/Users/Lenovo/NavisMobile_app/node_modules');
const req = (p) => require(path.join(MOD, p));

(async () => {
  const t0 = Date.now(); const log = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${m}`);
  const [entrada, salida] = process.argv.slice(2);
  const { NodeIO } = req('@gltf-transform/core');
  const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
  const { weld, simplify, draco } = req('@gltf-transform/functions');
  const draco3d = req('draco3dgltf');
  const { MeshoptSimplifier } = await import(pathToFileURL(path.join(MOD, 'meshoptimizer/index.js')).href);
  await MeshoptSimplifier.ready;
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
    'draco3d.encoder': await draco3d.createEncoderModule(),
    'draco3d.decoder': await draco3d.createDecoderModule(),
  });
  const doc = await io.read(entrada); log('leído');
  await doc.transform(
    weld(),
    simplify({ simplifier: MeshoptSimplifier, ratio: +arg('--ratio', 0.25), error: +arg('--error', 0.0001) }),
    draco({ quantizePosition: 16, quantizeNormal: 8, quantizeGeneric: 16 }),
  );
  log('optimizado');
  await io.write(salida, doc);
  log(`escrito ${salida} (${(require('fs').statSync(salida).size / 1e6).toFixed(1)} MB)`);
})().catch((e) => { console.error(e); process.exit(1); });
