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

        public static void Stop() { if (_timer != null) { _timer.Stop(); _timer.Dispose(); _timer = null; } Postproceso.Detener(); }

        private static void Revisar()
        {
            if (_ocupado) return;
            _ocupado = true;
            try { Postproceso.Revisar(); } finally { _ocupado = false; }
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

    /// <summary>
    /// Botón: exporta la selección actual (respeta lo oculto) a &lt;trabajo&gt;\&lt;id&gt;\&lt;id&gt;.nmraw y, al terminar,
    /// lanza en segundo plano la conversión + publicación (actualizar_area.mjs --solo-convertir): el área queda
    /// en el catálogo del PC (Wi-Fi) y, si config.publicar_github, en GitHub. Sin pasos manuales.
    /// </summary>
    [Plugin("NwMobileExport.Seleccion", "NWMX", DisplayName = "NavisMobile: exportar y publicar selección", ToolTip = "Exporta la selección y la publica en NavisMobile")]
    [AddInPlugin(AddInLocation.AddIn)]
    public class ExportSeleccion : AddInPlugin
    {
        public override int Execute(params string[] parameters)
        {
            var doc = NwApp.ActiveDocument;
            if (doc == null || doc.CurrentSelection.SelectedItems.Count == 0)
            {
                MessageBox.Show("Selecciona primero los nodos del área a exportar (por ejemplo, el nodo \"1411\").", "NavisMobile");
                return 0;
            }
            var cfg = Config.Leer();
            var items = doc.CurrentSelection.SelectedItems.ToList();
            var nombres = items.Select(i => (i.DisplayName ?? "").Trim()).Where(n => n.Length > 0).Distinct().ToList();
            string id = "area" + string.Join("_", nombres.Select(n => new string(n.Where(char.IsLetterOrDigit).ToArray()))).ToLowerInvariant();
            if (id.Length > 60) id = id.Substring(0, 60);
            string nombre = "Área " + string.Join(" + ", nombres);
            if (MessageBox.Show(
                    $"Exportar y publicar en NavisMobile:\n\n  {nombre}   (id {id})\n\n" +
                    $"Destino: {(cfg.PublicarGithub ? "PC (Wi-Fi) y GitHub" : "PC (Wi-Fi)")}\n" +
                    "Navisworks quedará ocupado mientras exporta (unos minutos según el tamaño).",
                    "NavisMobile", MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return 0;

            string dir = Path.Combine(cfg.CarpetaTrabajo, id);
            Directory.CreateDirectory(dir);
            string salida = Path.Combine(dir, id + ".nmraw");
            var t = new Trabajo
            {
                Raices = items.Select(i => { var p = doc.Models.CreatePathId(i); return p.ModelIndex + ":" + p.PathId; }).ToArray(),
                Excluir = new string[0],
                Salida = salida,
                Estado = salida + ".estado.json",
                Cancelar = salida + ".cancelar",
            };
            string r;
            try { r = new Exportador(t).Ejecutar(); }
            catch (Exception ex) { MessageBox.Show("Error al exportar: " + ex.Message, "NavisMobile"); return 0; }
            if (r.StartsWith("Cancelado")) return 0;
            try
            {
                Postproceso.Lanzar(cfg, id, nombre, dir);
                MessageBox.Show(r + "\n\nConvirtiendo y publicando en segundo plano; aviso cuando termine.\nRegistro: " + Path.Combine(dir, "publicar.log"), "NavisMobile");
            }
            catch (Exception ex) { MessageBox.Show(r + "\n\nNo se pudo iniciar la publicación: " + ex.Message, "NavisMobile"); }
            return 0;
        }
    }

    /// <summary>%LOCALAPPDATA%\NwMobileExport\config.json (se crea con valores por defecto la primera vez).</summary>
    internal sealed class Config
    {
        public string CarpetaTrabajo = @"F:\proyecto animación\NavisMobile\trabajo";
        public string RepoApp = @"C:\Users\Lenovo\NavisMobile_app";
        public string Node = @"C:\Program Files\nodejs\node.exe";
        public bool PublicarGithub = true;
        public bool ServidorWifi = true;
        public string Celda = "0.08";

        public static Config Leer()
        {
            var c = new Config();
            string f = Path.Combine(Cola.Dir, "config.json");
            var ser = new JavaScriptSerializer();
            try
            {
                if (File.Exists(f))
                {
                    var d = ser.Deserialize<Dictionary<string, object>>(File.ReadAllText(f, Encoding.UTF8));
                    object v;
                    if (d.TryGetValue("carpeta_trabajo", out v)) c.CarpetaTrabajo = (string)v;
                    if (d.TryGetValue("repo_app", out v)) c.RepoApp = (string)v;
                    if (d.TryGetValue("node", out v)) c.Node = (string)v;
                    if (d.TryGetValue("publicar_github", out v)) c.PublicarGithub = (bool)v;
                    if (d.TryGetValue("servidor_wifi", out v)) c.ServidorWifi = (bool)v;
                    if (d.TryGetValue("celda", out v)) c.Celda = Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture);
                    return c;
                }
                Directory.CreateDirectory(Cola.Dir);
                File.WriteAllText(f, ser.Serialize(new Dictionary<string, object>
                {
                    { "carpeta_trabajo", c.CarpetaTrabajo }, { "repo_app", c.RepoApp }, { "node", c.Node },
                    { "publicar_github", c.PublicarGithub }, { "servidor_wifi", c.ServidorWifi }, { "celda", c.Celda },
                }), new UTF8Encoding(false));
            }
            catch (Exception ex) { Log.Error("config.json: " + ex.Message); }
            return c;
        }
    }

    /// <summary>
    /// Conversión + publicación en un proceso aparte (prioridad baja, sin ventana): no bloquea Navisworks.
    /// El temporizador de la cola avisa al terminar. También levanta el servidor Wi-Fi (servir_areas.mjs)
    /// si no está corriendo, y lo detiene al cerrar Navisworks.
    /// </summary>
    internal static class Postproceso
    {
        private sealed class EnCurso { public System.Diagnostics.Process P; public string Nombre, Log; }
        private static readonly List<EnCurso> Activos = new List<EnCurso>();
        private static System.Diagnostics.Process _servidor;

        public static void Lanzar(Config cfg, string id, string nombre, string dir)
        {
            string script = Path.Combine(cfg.RepoApp, "herramientas", "actualizar_area.mjs");
            if (!File.Exists(script)) throw new FileNotFoundException("No existe " + script);
            string log = Path.Combine(dir, "publicar.log");
            string args = $"\"{script}\" --id {id} --nombre \"{nombre.Replace("\"", "")}\" --solo-convertir --celda {cfg.Celda} " +
                          $"--trabajo \"{cfg.CarpetaTrabajo}\"" + (cfg.PublicarGithub ? " --push" : "");
            var p = Iniciar(cfg, $"/c \"\"{cfg.Node}\" {args} > \"{log}\" 2>&1\"");
            Activos.Add(new EnCurso { P = p, Nombre = nombre, Log = log });
            Log.Info("Publicando " + id + " (pid " + p.Id + ")");
            if (cfg.ServidorWifi) AsegurarServidor(cfg);
        }

        private static System.Diagnostics.Process Iniciar(Config cfg, string cmdArgs)
        {
            var psi = new System.Diagnostics.ProcessStartInfo("cmd.exe", cmdArgs)
            {
                UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = cfg.RepoApp,
            };
            var p = System.Diagnostics.Process.Start(psi);
            try { p.PriorityClass = System.Diagnostics.ProcessPriorityClass.BelowNormal; } catch { }
            return p;
        }

        private static void AsegurarServidor(Config cfg)
        {
            if (_servidor != null && !_servidor.HasExited) return;
            try
            {
                using (var c = new System.Net.Sockets.TcpClient())
                    if (c.ConnectAsync("127.0.0.1", 8090).Wait(300) && c.Connected) return;   // ya hay uno corriendo
            }
            catch { }
            string s = Path.Combine(cfg.RepoApp, "herramientas", "servir_areas.mjs");
            _servidor = Iniciar(cfg, $"/c \"\"{cfg.Node}\" \"{s}\" > \"{Path.Combine(Cola.Dir, "servidor_wifi.log")}\" 2>&1\"");
            Log.Info("Servidor Wi-Fi iniciado (pid " + _servidor.Id + ")");
        }

        /// <summary>Llamado por el temporizador de la cola (hilo de UI): avisa de las publicaciones terminadas.</summary>
        public static void Revisar()
        {
            for (int i = Activos.Count - 1; i >= 0; i--)
            {
                var a = Activos[i];
                if (!a.P.HasExited) continue;
                Activos.RemoveAt(i);
                string cola = "";
                try { cola = string.Join("\n", File.ReadAllLines(a.Log).Reverse().Take(3).Reverse()); } catch { }
                bool ok = a.P.ExitCode == 0;
                Log.Info("Publicación " + a.Nombre + (ok ? " lista" : " falló: " + cola));
                MessageBox.Show(ok ? $"{a.Nombre} publicada.\nEn el teléfono: Escenas › Recargar."
                                   : $"Falló la publicación de {a.Nombre}:\n\n{cola}\n\nRegistro: {a.Log}",
                    "NavisMobile", MessageBoxButtons.OK, ok ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
            }
        }

        public static void Detener()
        {
            try { if (_servidor != null && !_servidor.HasExited) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("taskkill", "/T /F /PID " + _servidor.Id) { CreateNoWindow = true, UseShellExecute = false }); } catch { }
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
