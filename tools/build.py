"""Build a portable Windows distribution; excludes personal paths and credentials."""
import subprocess,sys,shutil,zipfile,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 os.environ['PYINSTALLER_CONFIG_DIR']=str(ROOT/'artifacts'/'pyinstaller-cache')
 deno=Path(sys.executable).parent/'deno.exe'
 if not deno.exists():raise SystemExit('Install deno into this environment first')
 args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','DesktopMusicPlayer',
       '--paths',str(ROOT/'src'),'--add-data',str(ROOT/'assets')+';assets','--add-data',str(ROOT/'themes.json')+';.',
       '--add-binary',str(deno)+';tools','--collect-submodules','yt_dlp','--collect-all','yt_dlp_ejs',
       '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtWebEngineQuick',
       '--exclude-module','PySide6.QtPdf','--exclude-module','PySide6.QtPdfWidgets','--exclude-module','PySide6.QtQuick','--exclude-module','PySide6.QtQml',str(ROOT/'run.py')]
 if '--package-only' not in sys.argv:subprocess.run(args,cwd=ROOT,check=True)
 out=ROOT/'dist'/'DesktopMusicPlayer';(out/'music').mkdir(exist_ok=True)
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
 archive=ROOT/'dist'/'DesktopMusicPlayer-Windows.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  z.writestr('DesktopMusicPlayer/music/',b'')
  for path in out.rglob('*'):
   if path.is_file() and 'data' not in path.relative_to(out).parts:z.write(path,path.relative_to(ROOT/'dist'))
 print('Portable executable:',out/'DesktopMusicPlayer.exe')
 print('Distribution ZIP:',archive)
if __name__=='__main__':main()
