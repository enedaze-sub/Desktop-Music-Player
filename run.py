import sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'src'))
if __name__=='__main__':
    try:
        from desktop_music_player.app import main
        main()
    except Exception:
        root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
        (root/'data').mkdir(exist_ok=True)
        (root/'data'/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise
