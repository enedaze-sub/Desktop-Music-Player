"""Build a portable Windows distribution; excludes personal paths and credentials."""
import subprocess,sys,shutil,zipfile,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 stage='--stage' in sys.argv
 build_root=ROOT/'artifacts'/'staged-build' if stage else ROOT
 dist_root=build_root/'dist'
 build_root.mkdir(parents=True,exist_ok=True)
 os.environ['PYINSTALLER_CONFIG_DIR']=str(ROOT/'artifacts'/'pyinstaller-cache')
 deno=Path(sys.executable).parent/'deno.exe'
 if not deno.exists():raise SystemExit('Install deno into this environment first')
 args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','DesktopMusicPlayer',
       '--icon',str(ROOT/'assets'/'app.ico'),'--version-file',str(ROOT/'tools'/'version-info.txt'),'--distpath',str(dist_root),'--workpath',str(build_root/'build'),'--paths',str(ROOT/'src'),'--add-data',str(ROOT/'assets')+';assets','--add-data',str(ROOT/'themes.json')+';.',
       '--add-binary',str(deno)+';tools','--collect-submodules','yt_dlp','--collect-all','yt_dlp_ejs',
       '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtWebEngineQuick',
       '--exclude-module','PySide6.QtPdf','--exclude-module','PySide6.QtPdfWidgets','--exclude-module','PySide6.QtQuick','--exclude-module','PySide6.QtQml',str(ROOT/'run.py')]
 if '--package-only' not in sys.argv:
  import psutil,datetime
  expected=(dist_root/'DesktopMusicPlayer'/'DesktopMusicPlayer.exe').resolve()
  for process in psutil.process_iter(['exe']):
   if process.info['exe'] and Path(process.info['exe']).resolve()==expected:raise SystemExit('Close the player before building; private state will be preserved.')
  private=expected.parent/'data';backup=ROOT/'artifacts'/('build-state-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
  if private.exists():shutil.copytree(private,backup)
  try:subprocess.run(args,cwd=ROOT,check=True)
  finally:
   if backup.exists():shutil.copytree(backup,private,dirs_exist_ok=True)
  csc=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET'/'Framework64'/'v4.0.30319'/'csc.exe'
  if not csc.exists():csc=csc.parents[2]/'Framework'/'v4.0.30319'/'csc.exe'
  subprocess.run([str(csc),'/nologo','/target:winexe','/optimize+',str('/win32icon:'+str(ROOT/'assets'/'app.ico')),str('/out:'+str(build_root/'노래 플레이어.exe')),'/reference:System.Windows.Forms.dll',str(ROOT/'tools'/'Launcher.cs')],check=True)

 out=dist_root/'DesktopMusicPlayer';(out/'music').mkdir(exist_ok=True)
 # Qt needs its newer VC runtime; Python 3.10 bundles older copies.
 for name in ('VCRUNTIME140.dll','VCRUNTIME140_1.dll'):
  shutil.copy2(Path(sys.executable).parent.parent/'Lib'/'site-packages'/'PySide6'/name,out/'_internal'/name)
 # Qt uses Windows' system ICU. Deno's unrelated ICU DLL must not shadow it.
 for name in ('icuuc.dll','icudt78.dll'):
  target=(out/'_internal'/name).resolve()
  assert target.parent==(out/'_internal').resolve()
  if target.exists():target.unlink()
 shutil.copy(ROOT/'README.md',out/'README.md');shutil.copy(ROOT/'THIRD_PARTY_NOTICES.md',out/'THIRD_PARTY_NOTICES.md')
 shutil.copy(ROOT/'config.example.json',out/'config.example.json')
 shutil.copytree(ROOT/'licenses',out/'licenses',dirs_exist_ok=True)
 archive=dist_root/'DesktopMusicPlayer-Windows.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  z.writestr('DesktopMusicPlayer/music/',b'')
  for path in out.rglob('*'):
   if path.is_file() and 'data' not in path.relative_to(out).parts:z.write(path,path.relative_to(dist_root))
 print('Portable executable:',out/'DesktopMusicPlayer.exe')
 print('Distribution ZIP:',archive)
if __name__=='__main__':main()
