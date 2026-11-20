using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Autodesk.Navisworks.Api;
using Autodesk.Navisworks.Api.Plugins;
using NwApp = Autodesk.Navisworks.Api.Application;

namespace NwMobileExport
{
    /// <summary>
    /// Entrada sin interfaz para la instancia oculta de Navisworks (Automation API o Roamer -NoGui):
    ///   ExecuteAddInPlugin("NwMobileExport.Lote.NWMX", "salida=C:\x\area.nmraw", "raices=0:27/6/0/0,0:28", "excluir=...")
    /// - salida  (obligatorio): ruta del .nmraw; junto a él quedan .piezas.json y .estado.json.
    /// - raices  (opcional): ids "modelo:pathId" separados por coma. Vacío = todos los modelos del documento
    ///           (lo normal con un NWD de área, p. ej. "area 1313.nwd").
    /// - excluir (opcional): ids a omitir.
    /// No muestra ventanas: cualquier error queda en &lt;salida&gt;.estado.json y en el registro del plugin.
    /// Devuelve 0 si terminó bien y 1 si falló o se canceló.
    /// </summary>
    [Plugin("NwMobileExport.Lote", "NWMX", DisplayName = "NavisMobile: exportar sin interfaz")]
    [AddInPlugin(AddInLocation.None)]
    public class ExportLote : AddInPlugin
    {
        public override int Execute(params string[] parameters)
        {
            var arg = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var p in parameters ?? new string[0])
            {
                int i = (p ?? "").IndexOf('=');
                if (i > 0) arg[p.Substring(0, i).Trim()] = p.Substring(i + 1).Trim().Trim('"');
            }
            string salida;
            if (!arg.TryGetValue("salida", out salida) || salida.Length == 0)
            {
                Log.Error("Lote: falta el parámetro salida=<ruta.nmraw>");
                return 1;
            }
            string estado = salida + ".estado.json";
            // Registro propio junto al .nmraw: en la instancia oculta export.log no siempre recibe las líneas.
            Action<string> anotar = m =>
            {
                Log.Info(m);
                try { File.AppendAllText(salida + ".log", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + m + Environment.NewLine); } catch { }
            };
            try
            {
                var doc = NwApp.ActiveDocument;
                if (doc == null || doc.Models.Count == 0) throw new InvalidOperationException("No hay documento abierto en la instancia oculta");
                string[] raices = Lista(arg, "raices");
                if (raices.Length == 0)
                {
                    // Todo el documento: un id por modelo raíz ("<índice>:" + pathId del raíz).
                    raices = doc.Models.RootItems
                        .Select(r => { var id = doc.Models.CreatePathId(r); return id.ModelIndex + ":" + id.PathId; })
                        .ToArray();
                }
                var t = new Trabajo
                {
                    Raices = raices,
                    Excluir = Lista(arg, "excluir"),
                    Salida = salida,
                    Estado = estado,
                    Cancelar = salida + ".cancelar",
                };
                anotar("Lote: " + doc.FileName + " -> " + salida + " (" + raices.Length + " raíces)");
                string r = new Exportador(t).Ejecutar();
                anotar("Lote: " + r);
                return r.StartsWith("Cancelado") ? 1 : 0;
            }
            catch (Exception ex)
            {
                Log.Error("Lote: " + ex);
                try { File.AppendAllText(salida + ".log", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ERROR " + ex + Environment.NewLine); } catch { }
                Estado.Escribir(estado, new Dictionary<string, object> { { "estado", "error" }, { "error", ex.Message } });
                return 1;
            }
        }

        private static string[] Lista(Dictionary<string, string> a, string k)
        {
            string v;
            if (!a.TryGetValue(k, out v) || string.IsNullOrEmpty(v)) return new string[0];
            return v.Split(new[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries).Select(s => s.Trim()).Where(s => s.Length > 0).ToArray();
        }
    }
}
