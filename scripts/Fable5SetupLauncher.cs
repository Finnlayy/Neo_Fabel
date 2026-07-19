using System;
using System.Diagnostics;
using System.Windows.Forms;

public class Fable5Setup
{
    [STAThread]
    public static void Main()
    {
        const string script = @"D:\Neo_Fabel\scripts\Setup-Fable5Server.ps1";
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"",
                UseShellExecute = true,
                WorkingDirectory = @"D:\Neo_Fabel"
            };
            var process = Process.Start(psi);
            if (process == null)
            {
                Environment.Exit(1);
                return;
            }
            process.WaitForExit();
            Environment.Exit(process.ExitCode);
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Fable5 Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Environment.Exit(1);
        }
    }
}
