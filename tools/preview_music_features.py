"""Small synthetic UI fixture for manual drag/menu verification."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor,QPixmap
from PySide6.QtCore import QTimer
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts';app=QApplication([]);configure_fonts();w=Window(Store(OUT/'feature-preview-state'),demo=True);w.setWindowTitle('Desktop Music Player · 기능 확인');w.set_ui_scale(1,persist=False)
tracks=[Track('현재 듣는 곡','first.mp3'),Track('다음에 들을 곡','second.mp3'),Track('봄날의 앨범','third.mp3'),Track('이미지가 없는 곡','fourth.mp3')];w.set_library(tracks);w.queue.replace(tracks);w.queue.select(0);w.engine.track=tracks[0]
for track,color in zip(tracks,('#bb6c3c','#547d79','#9f719a')):
 image=QImage(256,256,QImage.Format_RGB32);image.fill(QColor(color));w.covers.cache[track.key]=QPixmap.fromImage(image)
w.refresh_queue();w.update_transport();w.expand('대기열');w.finish_transition();w.show()
def record(*_):
 (OUT/'queue-native-drag.json').write_text(json.dumps({'order':[t.title for t in w.queue.tracks],'current':w.queue.current.title,'labels':[w.queue_model.index(i,0).data(257) for i in range(len(tracks))]},ensure_ascii=False,indent=2),encoding='utf-8')
w.queue_model.move_requested.connect(record);QTimer.singleShot(90000,w.exit_app);app.exec()
