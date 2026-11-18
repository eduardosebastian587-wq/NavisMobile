using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Autodesk.Navisworks.Api;
using Autodesk.Navisworks.Api.Plugins;
using NwApp = Autodesk.Navisworks.Api.Application;

namespace NwMobileExport
{
    /// <summary>
    /// Cola de trabajos por archivos: %LOCALAPPDATA%\NwMobileExport\cola\&lt;id&gt;.trabajo.json
    /// { "raices": ["0:27/6/0/0", ...], "excluir": [...], "salida": "X:\\...\\area.nmraw" }
    /// El estado se escribe en &lt;id&gt;.estado.json; crear &lt;id&gt;.cancelar detiene la exportación.
    /// Un temporizador WinForms en el hilo de UI revisa la cola: la exportación corre en el hilo de UI
    /// (la API de Navisworks lo exige), sin pasar por el puente MCP.
    /// </summary>
    internal static class Cola
    {
        public static string Dir => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NwMobileExport");
        public static string DirCola => Path.Combine(Dir, "cola");
        private static Timer _timer;
        private static bool _ocupado;

        public static void Arm() { NwApp.Idle += PrimerIdle; }

        private static void PrimerIdle(object s, EventArgs e)
        {
            NwApp.Idle -= PrimerIdle;
            Directory.CreateDirectory(DirCola);
            _timer = new Timer { Interval = 1500 };
            _timer.Tick += (a, b) => Revisar();
            _timer.Start();
            Log.Info("Cola activa: " + DirCola);
        }

        public static void Stop() { if (_timer != null) { _timer.Stop(); _timer.Dispose(); _timer = null; } }

        private static void Revisar()
        {
            if (_ocupado) return;
            string f;
            try { f = Directory.GetFiles(DirCola, "*.trabajo.json").OrderBy(File.GetCreationTimeUtc).FirstOrDefault(); }
            catch { return; }
            if (f == null) return;
            _ocupado = true;
            string id = Path.GetFileName(f).Replace(".trabajo.json", "");
            string enCurso = Path.Combine(DirCola, id + ".en_curso.json");
            string estado = Path.Combine(DirCola, id + ".estado.json");
            try
            {
                if (File.Exists(enCurso)) File.Delete(enCurso);
                File.Move(f, enCurso);
                var d = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(enCurso, Encoding.UTF8));
                var t = new Trabajo
                {
                    Raices = Lista(d, "raices"),
                    Excluir = Lista(d, "excluir"),
                    Salida = (string)d["salida"],
                    Estado = estado,
                    Cancelar = Path.Combine(DirCola, id + ".cancelar"),
                };
                new Exportador(t).Ejecutar();
            }
            catch (Exception ex)
            {
                Log.Error("Trabajo " + id + ": " + ex);
                Estado.Escribir(estado, new Dictionary<string, object> { { "estado", "error" }, { "error", ex.Message } });
            }
            finally { _ocupado = false; }
        }

        private static string[] Lista(Dictionary<string, object> d, string k)
        {
            if (!d.ContainsKey(k) || d[k] == null) return new string[0];
            return ((System.Collections.ArrayList)d[k]).Cast<object>().Select(o => o.ToString()).ToArray();
        }
    }

    [Plugin("NwMobileExport", "NWMX", DisplayName = "NavisMobile Export", ToolTip = "Exportador directo a NavisMobile")]
    public class ExportWatcher : EventWatcherPlugin
    {
        public override void OnLoaded() { Cola.Arm(); }
        public override void OnUnloading() { Cola.Stop(); }
    }

    /// <summary>Botón: exporta la selección actual (respeta lo oculto).</summary>
    [Plugin("NwMobileExport.Seleccion", "NWMX", DisplayName = "NavisMobile: exportar selección", ToolTip = "Exporta la selección actual a .nmraw para NavisMobile")]
    [AddInPlugin(AddInLocation.AddIn)]
    public class ExportSeleccion : AddInPlugin
    {
        public override int Execute(params string[] parameters)
        {
            var doc = NwApp.ActiveDocument;
            if (doc == null || doc.CurrentSelection.SelectedItems.Count == 0)
            {
                MessageBox.Show("Selecciona primero los nodos del área a exportar.", "NavisMobile Export");
                return 0;
            }
            string salida = parameters != null && parameters.Length > 0 ? parameters[0] : null;
            if (salida == null)
            {
                using (var dlg = new SaveFileDialog { Filter = "NavisMobile raw (*.nmraw)|*.nmraw", FileName = "area.nmraw" })
                {
                    if (dlg.ShowDialog() != DialogResult.OK) return 0;
                    salida = dlg.FileName;
                }
            }
            var t = new Trabajo
            {
                Raices = doc.CurrentSelection.SelectedItems.Select(i => { var p = doc.Models.CreatePathId(i); return p.ModelIndex + ":" + p.PathId; }).ToArray(),
                Excluir = new string[0],
                Salida = salida,
                Estado = salida + ".estado.json",
                Cancelar = salida + ".cancelar",
            };
            try
            {
                var r = new Exportador(t).Ejecutar();
                MessageBox.Show(r, "NavisMobile Export");
            }
            catch (Exception ex) { MessageBox.Show("Error: " + ex.Message, "NavisMobile Export"); }
            return 0;
        }
    }

    internal static class Estado
    {
        public static void Escribir(string ruta, Dictionary<string, object> d)
        {
            try
            {
                string tmp = ruta + ".tmp";
                File.WriteAllText(tmp, new JavaScriptSerializer().Serialize(d), new UTF8Encoding(false));
                if (File.Exists(ruta)) File.Delete(ruta);
                File.Move(tmp, ruta);
            }
            catch { }
        }
    }

    internal static class Log
    {
        private static readonly object Gate = new object();
        public static void Info(string m) { W("INFO", m); }
        public static void Error(string m) { W("ERROR", m); }
        private static void W(string lvl, string m)
        {
            try
            {
                lock (Gate)
                {
                    Directory.CreateDirectory(Cola.Dir);
                    string p = Path.Combine(Cola.Dir, "export.log");
                    if (File.Exists(p) && new FileInfo(p).Length > 1024 * 1024) File.Delete(p);
                    File.AppendAllText(p, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " " + lvl + " " + m + Environment.NewLine, new UTF8Encoding(false));
                }
            }
            catch { }
        }
    }
}
