import sys,os,json,tempfile,wave,math,struct,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFontInfo
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts,COMPACT_HEIGHT
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts';ART.mkdir(exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts()
window=Window(Store(ART/'smoke_state'),demo=True);window.resize(window.px(600),window.px(COMPACT_HEIGHT))
tracks=[Track('밤의 플레이리스트 · Night Walk',str(ART/'sample.wav'),artist='Desktop Music Player',album='로컬 보관함'),Track('빛나는 계절 · Spring Light','https://www.youtube.com/watch?v=dQw4w9WgXcQ','youtube','YouTube','함께 듣는 곡'),Track('오늘의 작은 쉼표','track3.mp3',album='로컬 음악')]
window.set_library(tracks);window.queue.replace(tracks);window.queue.select(0);window.engine.track=tracks[0];window.update_transport();window.show();QTest.qWait(250)
results={}
assert app.font().family()=="NanumSquareRound"
assert "Bold" in QFontDatabase.styles("NanumSquareRound")
results["font_family"]=QFontInfo(app.font()).family();results["font_styles"]=QFontDatabase.styles("NanumSquareRound")
centers=[child.geometry().center().y() for child in (window.art,window.lcd,window.deck.pad)]
assert max(centers)-min(centers)<=1,centers
results['deck_vertical_centers']=centers
for theme in window.themes:
 window.config['theme']=theme['id'];window.apply_theme();QTest.qWait(120)
 if window.expanded:window.expand(window.tabs.tabText(window.tabs.currentIndex()));QTest.qWait(250)
 window.grab().save(str(ART/(theme['id']+'-compact.png')))
 window.expand('보관함');QTest.qWait(300)
 window.grab().save(str(ART/(theme['id']+'-expanded.png')))
results['screenshots']=len(window.themes)*2
window.config['theme']='silver_blue';window.apply_theme()
window.resize(window.px(560),window.height());QTest.qWait(120)
for name,b in window.nav_buttons.items():
 required=b.fontMetrics().horizontalAdvance(name)+b.iconSize().width()+window.px(12)
 assert required<=b.width(),(name,required,b.width())
window.grab().save(str(ART/'font-minimum-width.png'))
results['minimum_width_nav_fits']=True
window.resize(window.px(600),window.height())
window.search_box.setText('쉼표');QTest.qWait(350);assert window.library_model.rowCount()==1
window.search_box.clear();QTest.qWait(350)
window.store.save_playlist('Mixed',tracks);assert len(window.store.playlist('Mixed'))==3
window.engine.track=None
wav=ART/'sample.wav'
with wave.open(str(wav),'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050)
 f.writeframes(b''.join(struct.pack('<h',int(9000*math.sin(2*math.pi*440*i/22050))) for i in range(22050*4)))
received=[];window.engine.spectrum.connect(lambda bands:received.append(bands));window.engine.audio.setMuted(True)
window.config.update(theme='visualizer',visualizer=True);window.apply_theme();window.engine.play_track(Track('Sample',str(wav)));QTest.qWait(1700)
assert window.engine.player.position()>400,window.engine.player.errorString()
assert len(received)>3,('spectrum samples',len(received))
results['playback_position_ms']=window.engine.player.position();results['spectrum_frames']=len(received)
window.hide();QTest.qWait(200);assert not window.spectrum.timer.isActive()
results['hidden_visualizer_stopped']=True
window.engine.stop();(ART/'smoke-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(results)
