import sys,wave,math,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
ROOT=Path(__file__).resolve().parents[1]
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);configure_fonts()
file=ROOT/'artifacts'/'keyboard-sample.wav'
with wave.open(str(file),'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050);f.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*440*i/22050))) for i in range(22050*12)))
w=Window(Store(ROOT/'artifacts'/'native-preview-v011'),demo=True);w.setWindowTitle('Desktop Music Player · 수정 검증');w.engine.audio.setMuted(True)
tracks=[Track('키보드와 크기 조절 확인',str(file),artist='수정 검증'),Track('밤의 플레이리스트 · Night Walk',str(file),album='미리보기'),Track('오늘의 작은 쉼표',str(file),album='미리보기')]
w.queue.replace(tracks);w.queue.repeat='all';w.set_library(tracks);w.refresh_queue()
if '--tall' in sys.argv:w.resize(w.width(),w.px(400))
w.show()
if '--background' in sys.argv:
 from desktop_music_player.background_editor import BackgroundEditor
 from PySide6.QtCore import QTimer
 w.expand('보관함');w.finish_transition();editor=BackgroundEditor(w);editor.draft['background']=str(ROOT/'assets'/'default-cover.png');editor.sync_controls();editor.show()
 QTimer.singleShot(400,lambda:editor.grab().save(str(ROOT/'artifacts'/'background-editor.png')))
if '--capture' in sys.argv:
 QTimer.singleShot(700,lambda:(editor.reject(),w.exit_app()))
app.exec()
