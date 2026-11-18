using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using Autodesk.Navisworks.Api;
using Autodesk.Navisworks.Api.ComApi;
using ComApi = Autodesk.Navisworks.Api.Interop.ComApi;
using NwApp = Autodesk.Navisworks.Api.Application;

namespace NwMobileExport
{
    internal sealed class Trabajo
    {
        public string[] Raices, Excluir;
        public string Salida, Estado, Cancelar;
    }

    /// <summary>
    /// Recorre los nodos raíz (saltando lo oculto y lo excluido) y escribe:
    ///  · &lt;salida&gt;.nmraw : "NMRAW001", desfase (3 double, Z arriba) y por cada pieza con geometría:
    ///                      int32 pieza, int32 nTri, float32[nTri*9] (mundo - desfase, Z arriba, metros).
    ///  · &lt;salida&gt;.piezas.json : TAG (con propiedades SmartPlant 3D), grupos y [tag, grupo, color] por pieza.
    /// La geometría se lee con la API COM (GenerateSimplePrimitives), sin pasar por FBX.
    /// </summary>
    internal sealed class Exportador
    {
        private static readonly Regex TagRe = new Regex(@"(?<![\w-])(\d{4}-[A-Z]{1,5}-[A-Z0-9][\w.]*)", RegexOptions.Compiled);
        private static readonly Regex Area4 = new Regex(@"^\d{4}$", RegexOptions.Compiled);

        private readonly Trabajo _t;
        private readonly Stopwatch _sw = Stopwatch.StartNew();
        private long _ultimoEstado;
        private BinaryWriter _w;
        private double[] _desfase;
        private HashSet<ModelItem> _excluir;
        private readonly Dictionary<string, int> _tagIdx = new Dictionary<string, int>();
        private readonly List<Dictionary<string, object>> _tags = new List<Dictionary<string, object>>();
        private readonly HashSet<string> _tagExacto = new HashSet<string>();
        private readonly Dictionary<string, int> _grupoIdx = new Dictionary<string, int>();
        private readonly List<string> _grupos = new List<string>();
        private readonly List<object[]> _piezas = new List<object[]>();
        private long _tri, _nodos;
        private bool _cancelado;
        private readonly Recolector _cb = new Recolector();

        public Exportador(Trabajo t) { _t = t; }

        public string Ejecutar()
        {
            var doc = NwApp.ActiveDocument ?? throw new InvalidOperationException("No hay documento abierto");
            var raices = _t.Raices.Select(id => Resolver(doc, id)).ToList();
            _excluir = new HashSet<ModelItem>(_t.Excluir.Select(id => Resolver(doc, id)));
            if (File.Exists(_t.Cancelar)) File.Delete(_t.Cancelar);
            Log.Info("Exportando " + raices.Count + " raíces a " + _t.Salida);

            // desfase: centro de las cajas de las raíces, redondeado a 10 m (evita vibración en float32)
            BoundingBox3D caja = null;
            foreach (var r in raices) { var b = r.BoundingBox(); if (b != null && !b.IsEmpty) caja = caja == null ? b : caja.Extend(b); }
            var c = caja == null ? new Point3D(0, 0, 0) : caja.Center;
            _desfase = new[] { Math.Round(c.X / 10) * 10, Math.Round(c.Y / 10) * 10, Math.Round(c.Z / 10) * 10 };
            _cb.Desfase = _desfase;

            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(_t.Salida)));
            string tmp = _t.Salida + ".parcial";
            using (var fs = new FileStream(tmp, FileMode.Create, FileAccess.Write, FileShare.Read, 1 << 22))
            using (_w = new BinaryWriter(fs))
            {
                _w.Write(Encoding.ASCII.GetBytes("NMRAW001"));
                foreach (var v in _desfase) _w.Write(v);
                foreach (var r in raices)
                {
                    var cadena = r.AncestorsAndSelf.Reverse().Select(a => a.DisplayName ?? "").ToList();
                    cadena.RemoveAt(cadena.Count - 1);
                    string tag = null;
                    foreach (var a in r.Ancestors) { var m = TagRe.Match(a.DisplayName ?? ""); if (m.Success) { tag = m.Groups[1].Value; break; } }
                    Visitar(doc, r, cadena, tag);
                    if (_cancelado) break;
                }
            }
            if (_cancelado)
            {
                File.Delete(tmp);
                EscribirEstado("cancelado", true);
                return "Cancelado.";
            }
            if (File.Exists(_t.Salida)) File.Delete(_t.Salida);
            File.Move(tmp, _t.Salida);

            var json = new Dictionary<string, object>
            {
                { "formato", "nmraw-piezas-v1" },
                { "documento", doc.FileName },
                { "raices", _t.Raices },
                { "desfase", _desfase },
                { "tags", _tags },
                { "grupos", _grupos },
                { "piezas", _piezas },
            };
            File.WriteAllText(_t.Salida + ".piezas.json", new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(json), new UTF8Encoding(false));
            EscribirEstado("listo", true);
            string res = string.Format("Listo en {0:0.0} s: {1:N0} piezas, {2:N0} triángulos, {3:N0} TAG.", _sw.Elapsed.TotalSeconds, _piezas.Count, _tri, _tags.Count);
            Log.Info(res);
            return res;
        }

        private void Visitar(Document doc, ModelItem it, List<string> cadena, string tag)
        {
            if (_cancelado || it.IsHidden || _excluir.Contains(it)) return;
            _nodos++;
            string nombre = it.DisplayName ?? "";
            var m = TagRe.Match(nombre);
            if (m.Success)
            {
                tag = m.Groups[1].Value;
                // los subcomponentes (1313-ML-1401-DSP2) comparten TAG con el equipo: el nodo cuyo nombre
                // es exactamente el TAG reemplaza las propiedades tomadas de un subcomponente
                bool exacto = nombre == tag;
                if (!_tagIdx.ContainsKey(tag) || (exacto && !_tagExacto.Contains(tag))) RegistrarTag(it, tag, cadena, nombre);
                if (exacto) _tagExacto.Add(tag);
            }
            cadena.Add(nombre);
            if (it.HasGeometry) Geometria(it, cadena, tag);
            foreach (var h in it.Children)
            {
                Visitar(doc, h, cadena, tag);
                if (_cancelado) break;
            }
            cadena.RemoveAt(cadena.Count - 1);

            if (_sw.ElapsedMilliseconds - _ultimoEstado > 2000)
            {
                _ultimoEstado = _sw.ElapsedMilliseconds;
                if (File.Exists(_t.Cancelar)) { _cancelado = true; return; }
                EscribirEstado("exportando", false);
            }
        }

        private void RegistrarTag(ModelItem it, string tag, List<string> cadena, string nombre)
        {
            // Propiedades SmartPlant 3D: del propio nodo o de un hijo directo cuyo "Name" sea el TAG (p. ej. "Aspects")
            Dictionary<string, string> props = null;
            foreach (var cand in new[] { it }.Concat(it.Children.Take(6)))
            {
                var cat = cand.PropertyCategories.FindCategoryByDisplayName("SmartPlant 3D");
                if (cat == null) continue;
                var p = new Dictionary<string, string>();
                foreach (var dp in cat.Properties)
                {
                    string v = Texto(dp.Value);
                    if (!string.IsNullOrEmpty(v)) p[dp.DisplayName] = v;
                }
                string n;
                bool exacto = p.TryGetValue("Name", out n) && (n == nombre || n == tag);
                if (props == null || exacto) props = p;
                if (exacto) break;
            }
            var ruta = cadena.Concat(new[] { nombre }).Where(x => x != "Geometry" && x != "Aspects" && x.Length > 0).ToList();
            var d = new Dictionary<string, object>
            {
                { "tag", tag },
                { "ruta", string.Join(" / ", ruta.Skip(Math.Max(0, ruta.Count - 8))) },
                { "props", props ?? new Dictionary<string, string>() },
            };
            int i;
            if (_tagIdx.TryGetValue(tag, out i)) _tags[i] = d;
            else { _tagIdx[tag] = _tags.Count; _tags.Add(d); }
        }

        private static string Texto(VariantData v)
        {
            try
            {
                if (v == null || v.IsNone) return null;
                if (v.IsDisplayString) return v.ToDisplayString();
                if (v.IsIdentifierString) return v.ToIdentifierString();
                if (v.IsDateTime) return v.ToDateTime().ToString("s");
                if (v.IsNamedConstant) return v.ToNamedConstant().DisplayName;
                if (v.IsAnyDouble) return v.ToAnyDouble().ToString(System.Globalization.CultureInfo.InvariantCulture);
                if (v.IsInt32) return v.ToInt32().ToString();
                if (v.IsBoolean) return v.ToBoolean() ? "true" : "false";
                return v.ToString();
            }
            catch { return null; }
        }

        private string Grupo(List<string> cad)
        {
            if (cad.Take(3).Contains("Structure"))
            {
                string hoja = cad.LastOrDefault(x => x != "Geometry" && x != "Aspects" && x.Length > 0) ?? "";
                return hoja.StartsWith("WallPart") ? "Muros (capa Structure)" : "Volúmenes de reserva (capa Structure)";
            }
            for (int i = 0; i < cad.Count - 1; i++)
                if (Area4.IsMatch(cad[i]) && !Area4.IsMatch(cad[i + 1])) return cad[i + 1] + " sin TAG";
            return "Otros sin TAG";
        }

        private void Geometria(ModelItem it, List<string> cadena, string tag)
        {
            var path = ComApiBridge.ToInwOaPath(it);
            var ruta = (Array)(object)path.ArrayData;
            _cb.Inicio();
            foreach (ComApi.InwOaFragment3 frag in path.Fragments())
            {
                // con geometría instanciada, Fragments() puede traer fragmentos de otras instancias
                if (!MismaRuta((Array)(object)frag.path.ArrayData, ruta)) continue;
                var mat = (Array)(object)((ComApi.InwLTransform3f3)frag.GetLocalToWorldMatrix()).Matrix;
                int lb = mat.GetLowerBound(0);
                for (int k = 0; k < 16; k++) _cb.M[k] = Convert.ToDouble(mat.GetValue(lb + k));
                frag.GenerateSimplePrimitives(ComApi.nwEVertexProperty.eNORMAL, _cb);
            }
            int n = _cb.Cuenta / 9;
            if (n == 0) return;

            var g = it.Geometry;
            var col = g.ActiveColor;
            double tr = g.ActiveTransparency;
            string hex = string.Format("{0:X2}{1:X2}{2:X2}", B(col.R), B(col.G), B(col.B));
            if (tr > 0.02) hex += "_A" + ((int)Math.Round((1 - tr) * 100)).ToString("00");

            int ti = tag != null && _tagIdx.ContainsKey(tag) ? _tagIdx[tag] : -1;
            int gi = -1;
            if (ti < 0)
            {
                string gr = Grupo(cadena);
                if (!_grupoIdx.TryGetValue(gr, out gi)) { gi = _grupos.Count; _grupoIdx[gr] = gi; _grupos.Add(gr); }
            }
            _w.Write(_piezas.Count);
            _w.Write(n);
            var buf = _cb.Datos;
            for (int k = 0; k < _cb.Cuenta; k++) _w.Write(buf[k]);
            _piezas.Add(new object[] { ti, gi, hex });
            _tri += n;
        }

        private static int B(double v) { return (int)Math.Round(Math.Max(0, Math.Min(1, v)) * 255); }

        private static bool MismaRuta(Array a, Array b)
        {
            if (a.Length != b.Length) return false;
            int la = a.GetLowerBound(0), lb = b.GetLowerBound(0);
            for (int i = a.Length - 1; i >= 0; i--)
                if (!Equals(a.GetValue(la + i), b.GetValue(lb + i))) return false;
            return true;
        }

        private static ModelItem Resolver(Document doc, string id)
        {
            int i = id.IndexOf(':');
            var it = doc.Models.ResolvePathId(new Autodesk.Navisworks.Api.DocumentParts.ModelItemPathId { ModelIndex = int.Parse(id.Substring(0, i)), PathId = id.Substring(i + 1) });
            if (it == null) throw new InvalidOperationException("No existe el elemento " + id);
            return it;
        }

        private void EscribirEstado(string estado, bool final)
        {
            Estado.Escribir(_t.Estado, new Dictionary<string, object>
            {
                { "estado", estado },
                { "segundos", Math.Round(_sw.Elapsed.TotalSeconds, 1) },
                { "nodos", _nodos },
                { "piezas", _piezas.Count },
                { "triangulos", _tri },
                { "tags", _tags.Count },
                { "memoria_mb", Process.GetCurrentProcess().WorkingSet64 / (1024 * 1024) },
                { "salida", _t.Salida },
            });
        }
    }

    /// <summary>Recibe los triángulos de un fragmento y los guarda transformados (mundo - desfase) en float32.</summary>
    internal sealed class Recolector : ComApi.InwSimplePrimitivesCB
    {
        public readonly double[] M = new double[16];
        public double[] Desfase;
        public float[] Datos = new float[1 << 16];
        public int Cuenta;

        public void Inicio() { Cuenta = 0; }

        private void V(ComApi.InwSimpleVertex v)
        {
            var a = (Array)(object)v.coord;
            int lb = a.GetLowerBound(0);
            double x = Convert.ToDouble(a.GetValue(lb)), y = Convert.ToDouble(a.GetValue(lb + 1)), z = Convert.ToDouble(a.GetValue(lb + 2));
            if (Cuenta + 3 > Datos.Length) Array.Resize(ref Datos, Datos.Length * 2);
            Datos[Cuenta++] = (float)(x * M[0] + y * M[4] + z * M[8] + M[12] - Desfase[0]);
            Datos[Cuenta++] = (float)(x * M[1] + y * M[5] + z * M[9] + M[13] - Desfase[1]);
            Datos[Cuenta++] = (float)(x * M[2] + y * M[6] + z * M[10] + M[14] - Desfase[2]);
        }

        public void Triangle(ComApi.InwSimpleVertex v1, ComApi.InwSimpleVertex v2, ComApi.InwSimpleVertex v3) { V(v1); V(v2); V(v3); }
        public void Line(ComApi.InwSimpleVertex v1, ComApi.InwSimpleVertex v2) { }
        public void Point(ComApi.InwSimpleVertex v1) { }
        public void SnapPoint(ComApi.InwSimpleVertex v1) { }
    }
}
