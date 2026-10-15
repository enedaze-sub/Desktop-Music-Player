using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
[assembly: System.Reflection.AssemblyTitle("Desktop Music Player")]
[assembly: System.Reflection.AssemblyVersion("0.2.3.0")]
class Launcher {
 [STAThread] static void Main() {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  string exe=Path.Combine(root,"dist","DesktopMusicPlayer","DesktopMusicPlayer.exe");
  if(!File.Exists(exe)) { MessageBox.Show("dist 폴더의 DesktopMusicPlayer.exe를 찾을 수 없습니다. 프로그램 폴더 전체를 함께 옮겨 주세요.","Desktop Music Player",MessageBoxButtons.OK,MessageBoxIcon.Information); return; }
  try { Process.Start(new ProcessStartInfo(exe) { WorkingDirectory=Path.GetDirectoryName(exe),UseShellExecute=true }); }
  catch(Exception) { MessageBox.Show("플레이어를 실행하지 못했습니다. dist 폴더의 실행 파일을 확인해 주세요.","Desktop Music Player",MessageBoxButtons.OK,MessageBoxIcon.Error); }
 }
}
