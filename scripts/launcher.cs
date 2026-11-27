using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class VisionaryLauncher
{
    [STAThread]
    static void Main(string[] args)
    {
        try
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string electronExe = Path.Combine(baseDir, "node_modules", "electron", "dist", "electron.exe");
            string mainJs = Path.Combine(baseDir, "electron", "main.js");

            string arguments = "\"" + mainJs + "\"";
            if (args != null && args.Length > 0)
            {
                arguments += " " + string.Join(" ", args);
            }

            ProcessStartInfo psi;

            if (File.Exists(electronExe) && File.Exists(mainJs))
            {
                psi = new ProcessStartInfo(electronExe, arguments);
            }
            else
            {
                string npmCmd = "/c npm start";
                if (args != null && args.Length > 0)
                {
                    npmCmd += " -- " + string.Join(" ", args);
                }
                psi = new ProcessStartInfo("cmd.exe", npmCmd);
                psi.CreateNoWindow = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;
            }

            psi.WorkingDirectory = baseDir;
            psi.UseShellExecute = false;

            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show("Erro ao iniciar o Visionary Studio:\n" + ex.Message, "Visionary Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
