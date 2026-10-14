"""Compact native MP3-style window with a downward drawer."""
import json,logging,random,sys,time
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QThreadPool,QUrl,QPropertyAnimation,QEasingCurve,QSize,Slot
from PySide6.QtGui import QFont,QColor,QDesktopServices,QAction,QIcon,QPainter,QPixmap,QShortcut,QKeySequence,QFontDatabase
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,
 QSizePolicy,QSlider,QLineEdit,QListView,QTabWidget,QComboBox,QFileDialog,QInputDialog,QMessageBox,QDialog,QFormLayout,QCheckBox,
 QSizeGrip,QSystemTrayIcon,QMenu,QAbstractItemView,QDialogButtonBox,QSpinBox,QColorDialog)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from .core import Track,Queue,scan_library,app_root,AUDIO,VIDEO,playlist_id
from .storage import Store
from .jobs import Job,TrackModel
from .engine import Engine
from .widgets import Surface,Artwork,Spectrum,DragBar,TrackDelegate,Deck,LCDFrame
from .icons import icon
from . import youtube

def resource(name):return Path(getattr(sys,'_MEIPASS',app_root()))/name

def configure_fonts():
    # Bundle unmodified OFL fonts. System fonts provide multilingual fallback.
    empty_system_database=not QFontDatabase.families()
    families=[]
    for name in ('NanumSquareRoundR.ttf','NanumSquareRoundB.ttf'):
        ident=QFontDatabase.addApplicationFont(str(resource('assets/fonts')/name))
        if ident>=0:
            for family in QFontDatabase.applicationFontFamilies(ident):
                if family not in families:families.append(family)
    if empty_system_database:
        for name in ('malgun.ttf','segoeui.ttf','seguisym.ttf'):
            file=Path('C:/Windows/Fonts')/name
            if file.exists():QFontDatabase.addApplicationFont(str(file))
    font=QFont();font.setFamilies(families+['Malgun Gothic','Segoe UI Symbol']);font.setPixelSize(12)
    font.setHintingPreference(QFont.PreferVerticalHinting)
    QApplication.instance().setFont(font)
    return families

def duration(ms):
    sec=max(0,int(ms//1000));return f'{sec//60}:{sec%60:02d}'

def load_themes():
    return json.loads(resource('themes.json').read_text(encoding='utf-8'))

class Window(QMainWindow):
    def __init__(self,store=None,demo=False):
        super().__init__();self.store=store or Store();self.config=self.store.config();self.themes=load_themes();self.demo=demo
        self.setWindowTitle('Desktop Music Player');self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setMinimumSize(560,252);self.resize(max(560,self.config.get('width',600)),252)
        self.setAcceptDrops(True);self.queue=Queue();self.queue.repeat=self.config.get('repeat','off');self.queue.set_shuffle(self.config.get('shuffle',False))
        self.engine=Engine(self);self.engine.audio.setVolume(self.config['volume'])
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(2);self.jobs={};self.job_id=0;self.scan_pending=False
        self.library=[];self.filtered=[];self.youtube_results=[];self.source='local';self.expanded=False;self.video_widget=None;self.saved_height=self.config.get('panel_height',360)
        self.surface=Surface(self);self.setCentralWidget(self.surface);outer=QVBoxLayout(self.surface);outer.setContentsMargins(16,6,16,10);outer.setSpacing(4)
        self.bar=DragBar(self);self.bar.setFixedHeight(30);bar=QHBoxLayout(self.bar);bar.setContentsMargins(2,0,0,0);bar.setSpacing(5)
        self.brand=QLabel('Desktop Music');self.brand.setObjectName('brand');bar.addWidget(self.brand);bar.addStretch()
        self.pin=self.button('◇','항상 위에 표시',self.toggle_pin);bar.addWidget(self.pin)
        bar.addWidget(self.button('⚙','테마·배경·투명도 설정',self.settings));bar.addWidget(self.button('−','최소화',self.showMinimized));bar.addWidget(self.button('×','트레이로 숨기기',self.hide_player))
        outer.addWidget(self.bar)
        top=QHBoxLayout();top.setSpacing(12);self.art=Artwork();top.addWidget(self.art)
        self.lcd=LCDFrame();self.lcd.setObjectName('lcd');lcd=QVBoxLayout(self.lcd);lcd.setContentsMargins(10,9,10,8);lcd.setSpacing(3)
        self.title=QLabel('음악을 골라 주세요');self.title.setObjectName('trackTitle');self.title.setMinimumWidth(100);self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed);self.title.setWordWrap(True);self.title.setFixedHeight(42);lcd.addWidget(self.title)
        self.artist=QLabel('로컬 음악 · 유튜브');self.artist.setObjectName('muted');lcd.addWidget(self.artist)
        meta=QHBoxLayout();self.time=QLabel('0:00 / 0:00');self.time.setObjectName('time');self.time.setMinimumWidth(self.time.fontMetrics().horizontalAdvance('00:00 / 00:00'));meta.addWidget(self.time);meta.addStretch();self.badge=QLabel('READY');self.badge.setObjectName('badge');meta.addWidget(self.badge);lcd.addLayout(meta)
        self.seek=QSlider(Qt.Horizontal);self.seek.setRange(0,1000);self.seek.sliderReleased.connect(self.seek_to);lcd.addWidget(self.seek)
        top.addWidget(self.lcd,1)
        pad=QFrame();pad.setObjectName('pad');pad.setFixedSize(132,132);pad_layout=QGridLayout(pad);pad_layout.setContentsMargins(6,6,6,6);pad_layout.setSpacing(0)
        self.shuffle=self.button('⤨','셔플',self.toggle_shuffle);pad_layout.addWidget(self.shuffle,0,1,Qt.AlignCenter)
        pad_layout.addWidget(self.button('‹','이전 곡',self.previous),1,0)
        self.play=self.button('▶','재생 / 일시정지',self.toggle_play);self.play.setObjectName('play');self.play.setFixedSize(56,56);self.play.setIconSize(QSize(24,24));pad_layout.addWidget(self.play,1,1)
        pad_layout.addWidget(self.button('›','다음 곡',self.next),1,2)
        self.repeat=self.button('↻','반복 모드',self.toggle_repeat);pad_layout.addWidget(self.repeat,2,1,Qt.AlignCenter);top.addWidget(pad)
        self.deck=Deck(self.art,self.lcd,pad);outer.addWidget(self.deck)
        controls=QHBoxLayout();controls.setSpacing(16)
        volume_group=QWidget();volume_group.setFixedWidth(132);vol_layout=QHBoxLayout(volume_group);vol_layout.setSpacing(4);vol_layout.setContentsMargins(0,0,0,0)
        mute=self.button('','음소거',lambda:self.engine.audio.setMuted(not self.engine.audio.isMuted()));mute.setProperty('icon_name','volume');mute.setIcon(icon('volume'));vol_layout.addWidget(mute)
        self.volume=QSlider(Qt.Horizontal);self.volume.setRange(0,100);self.volume.setValue(round(self.config['volume']*100));self.volume.setFixedWidth(66)
        self.volume.valueChanged.connect(self.volume_changed);vol_layout.addWidget(self.volume);self.volume_label=QLabel(f'{self.volume.value()}');self.volume_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter);vol_layout.addWidget(self.volume_label);controls.addWidget(volume_group)
        self.nav_rail=QFrame();self.nav_rail.setObjectName('navRail');nav=QHBoxLayout(self.nav_rail);nav.setContentsMargins(2,2,2,2);nav.setSpacing(2);self.nav_buttons={}
        for name in ('보관함','대기열','재생목록','영상'):
            b=self.button(name,name+' 열기',lambda checked=False,name=name:self.expand(name),wide=True);b.setProperty('nav',True);b.setProperty('active',False);nav.addWidget(b,1);self.nav_buttons[name]=b
        controls.addWidget(self.nav_rail,1);outer.addLayout(controls)
        self.status_label=QLabel('폴더를 선택하거나 유튜브를 검색해 시작하세요.');self.status_label.setObjectName('status');outer.addWidget(self.status_label)
        self.drawer=QFrame();self.drawer.setObjectName('drawer');self.drawer.setMaximumHeight(0);self.drawer.hide();drawer_layout=QVBoxLayout(self.drawer);drawer_layout.setContentsMargins(6,8,6,3);drawer_layout.setSpacing(6)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();drawer_layout.addWidget(self.tabs)
        self.make_library();self.make_queue();self.make_playlists();self.make_video_page()
        self.tabs.currentChanged.connect(self.tab_changed);outer.addWidget(self.drawer,1)
        bottom=QHBoxLayout();bottom.setContentsMargins(0,0,0,0);self.counter=QLabel('LOCAL LIBRARY');self.counter.setObjectName('brand');bottom.addWidget(self.counter);bottom.addStretch();self.grip=QSizeGrip(self);self.grip.setFixedSize(14,14);bottom.addWidget(self.grip);outer.addLayout(bottom)
        self.spectrum=Spectrum(self.lcd);self.spectrum.hide();self.spectrum.setFixedHeight(24);lcd.addWidget(self.spectrum)
        self.engine.changed.connect(self.update_transport);self.engine.ended.connect(lambda:self.next(automatic=True));self.engine.message.connect(self.tell);self.engine.spectrum.connect(self.spectrum.accept)
        self.tick=QTimer(self);self.tick.setInterval(500);self.tick.timeout.connect(self.position_tick);self.tick.start()
        self.filter_timer=QTimer(self);self.filter_timer.setSingleShot(True);self.filter_timer.setInterval(220);self.filter_timer.timeout.connect(self.apply_filter)
        self.search_box.textChanged.connect(lambda:self.filter_timer.start() if self.source=='local' else None)
        self.anim=QPropertyAnimation(self.drawer,b'maximumHeight',self);self.anim.setDuration(180);self.anim.setEasingCurve(QEasingCurve.OutCubic);self.anim.finished.connect(self.animation_done)
        self.build_tray();self.apply_theme();self.refresh_playlists();self.update_transport()
        self.setWindowOpacity(self.config['opacity']);self.setWindowFlag(Qt.WindowStaysOnTopHint,self.config['always_on_top'])
        QShortcut(QKeySequence('Ctrl+L'),self,activated=lambda:self.expand('보관함'));QShortcut(QKeySequence('Ctrl+Right'),self,activated=self.next);QShortcut(QKeySequence('Ctrl+Left'),self,activated=self.previous)
        if not demo:
            cached=self.store.library();self.set_library(cached)
            restored=self.store.config().get('last_queue',[])
            try:self.queue.replace([Track.from_dict(x) for x in restored]);self.queue.set_shuffle(self.config.get('shuffle',False));self.refresh_queue()
            except (TypeError,ValueError):pass
            last_scan=float(self.store.config().get('last_scan',0))
            if not cached or time.time()-last_scan>86400:self.rescan()
    def button(self,text,tip,callback,wide=False):
        icons={'◇':'pin','⚙':'settings','−':'minimize','×':'close','⤨':'shuffle','‹':'previous','▶':'play','›':'next','↻':'repeat','🎲':'random',
               '보관함':'library','대기열':'queue','재생목록':'playlist','영상':'video','LOCAL':'music','YOUTUBE':'youtube',
               '랜덤 재생':'random','폴더':'folder','새로고침':'refresh','검색':'search','선택 곡 추가':'plus','검색 결과 모두 추가':'list-plus',
               '선택 삭제':'delete','비우기':'clear','목록 저장':'save','재생':'play','현재 대기열 저장':'save','삭제':'delete',
               '내보내기':'download','가져오기':'upload','원본 영상으로 이어보기':'external'}
        name=icons.get(text)
        icon_only=not wide or text=='🎲'
        b=QPushButton('' if name and icon_only else text);b.setToolTip(tip);b.setAccessibleName(tip);b.clicked.connect(callback);b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(30)
        if name:b.setProperty('icon_name',name);b.setIcon(icon(name));b.setIconSize(QSize(18,18))
        if icon_only:b.setFixedSize(30,30)
        return b
    def list_view(self,model):
        view=QListView();view.setModel(model);view.setItemDelegate(TrackDelegate(view));view.setUniformItemSizes(True);view.setSelectionMode(QAbstractItemView.ExtendedSelection);view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);return view
    def make_library(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(4,8,4,4)
        row=QHBoxLayout();self.local_button=self.button('LOCAL','로컬 보관함',lambda:self.change_source('local'),True);self.yt_button=self.button('YOUTUBE','유튜브 검색',lambda:self.change_source('youtube'),True);row.addWidget(self.local_button);row.addWidget(self.yt_button);row.addStretch();row.addWidget(self.button('랜덤 재생','로컬 랜덤 재생',self.random_local,True));row.addWidget(self.button('폴더','음악 폴더 추가',self.choose_folder,True));row.addWidget(self.button('새로고침','보관함 갱신',self.rescan,True));layout.addLayout(row)
        row=QHBoxLayout();self.search_box=QLineEdit();self.search_box.setPlaceholderText('곡·앨범 검색 또는 유튜브 주소');self.search_box.returnPressed.connect(self.search);row.addWidget(self.search_box);row.addWidget(self.button('검색','검색',self.search,True));layout.addLayout(row)
        self.library_model=TrackModel();self.library_view=self.list_view(self.library_model);self.library_view.doubleClicked.connect(self.play_library);layout.addWidget(self.library_view)
        row=QHBoxLayout();row.addWidget(self.button('선택 곡 추가','선택한 곡을 대기열에 추가',self.add_selected,True));row.addWidget(self.button('검색 결과 모두 추가','표시 중인 곡을 대기열에 추가',self.add_all,True));row.addStretch();layout.addLayout(row);self.tabs.addTab(page,'보관함')
    def make_queue(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(4,8,4,4);self.queue_model=TrackModel();self.queue_view=self.list_view(self.queue_model);self.queue_view.doubleClicked.connect(lambda index:self.play_index(index.row()));layout.addWidget(self.queue_view)
        row=QHBoxLayout();row.addWidget(self.button('선택 삭제','선택한 대기 곡 삭제',self.remove_selected,True));row.addWidget(self.button('비우기','재생 종료와 대기열 비우기',self.clear_queue,True));row.addWidget(self.button('목록 저장','현재 대기열을 저장',self.save_playlist,True));row.addStretch();layout.addLayout(row);self.tabs.addTab(page,'대기열')
    def make_playlists(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(4,8,4,4);self.playlist_combo=QComboBox();layout.addWidget(self.playlist_combo)
        note=QLabel('로컬과 유튜브 곡을 하나의 재생목록에 함께 저장할 수 있어요.\n음악 파일은 복사하지 않고 곡 정보와 위치만 저장합니다.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        row=QHBoxLayout()
        for text,method in [('재생',self.load_playlist),('현재 대기열 저장',self.save_playlist),('삭제',self.delete_playlist),('내보내기',self.export_playlist),('가져오기',self.import_playlist)]:row.addWidget(self.button(text,text,method,True))
        layout.addLayout(row);layout.addStretch();self.tabs.addTab(page,'재생목록')
    def make_video_page(self):
        self.video_page=QWidget();self.video_layout=QVBoxLayout(self.video_page);self.video_layout.setContentsMargins(4,8,4,4)
        self.video_note=QLabel('유튜브 곡을 재생한 뒤 영상으로 이어 볼 수 있어요.');self.video_note.setWordWrap(True);self.video_note.setObjectName('muted');self.video_layout.addWidget(self.video_note)
        self.video_layout.addWidget(self.button('원본 영상으로 이어보기','현재 위치에서 브라우저로 열기',self.open_original,True));self.video_layout.addStretch();self.tabs.addTab(self.video_page,'영상')
    def submit(self,fn,args,callback):
        self.job_id+=1;ident=self.job_id;job=Job(ident,fn,*args);self.jobs[ident]=(job,callback)
        job.signals.done.connect(self.job_done);self.pool.start(job);return ident
    @Slot(int,object,str)
    def job_done(self,ident,result,error):
        pair=self.jobs.pop(ident,None)
        if pair:
            if error:self.tell(error)
            pair[1](result,error)
    def tell(self,message):self.status_label.setText(message);self.status_label.setToolTip(message)
    def rescan(self):
        if self.scan_pending:return
        self.scan_pending=True;self.tell('음악 폴더를 확인하고 있어요…')
        def scanned(result,error):
            self.scan_pending=False
            if error:return
            self.set_library(result);self.submit(self.store.save_library,(result,),lambda *_:None);self.store.set('last_scan',time.time());self.tell(f'로컬 음악 {len(result):,}곡 준비 완료')
        self.submit(scan_library,(self.store.roots(),),scanned)
    def set_library(self,tracks):self.library=tracks;self.counter.setText(f'LOCAL {len(tracks):,}');self.apply_filter()
    def apply_filter(self):
        if self.source!='local':return
        value=self.search_box.text().strip().casefold();self.filtered=[t for t in self.library if value in (t.title+' '+t.artist+' '+t.album).casefold()];self.library_model.replace(self.filtered)
    def change_source(self,source):
        self.source=source;self.search_box.clear()
        self.search_box.setPlaceholderText('곡·앨범 검색' if source=='local' else '유튜브 검색어·영상·플레이리스트 주소')
        if source=='local':self.apply_filter()
        else:self.library_model.replace(self.youtube_results)
    def search(self):
        if self.source=='local':self.apply_filter();return
        value=self.search_box.text();self.tell('유튜브에서 찾고 있어요…');self.yt_button.setEnabled(False)
        def found(result,error):
            self.yt_button.setEnabled(True)
            if error:return
            self.youtube_results=result
            if self.source=='youtube':self.library_model.replace(result)
            self.tell(f'{len(result)}곡 찾았어요. 더블클릭하면 재생합니다.' if result else '검색 결과가 없습니다.')
        self.submit(youtube.search,(value,),found)
    def selected_tracks(self):return [self.library_model.tracks[i.row()] for i in sorted(self.library_view.selectionModel().selectedIndexes(),key=lambda x:x.row())]
    def add_selected(self):self.add_tracks(self.selected_tracks())
    def add_all(self):self.add_tracks(self.library_model.tracks)
    def add_tracks(self,tracks):
        if not tracks:return
        self.queue.append(tracks);self.refresh_queue();self.tell(f'{len(tracks)}곡을 대기열에 추가했어요.')
    def play_library(self,index):
        start=len(self.queue.tracks);self.queue.append([self.library_model.tracks[index.row()]]);self.play_index(start)
    def play_index(self,index):
        track=self.queue.select(index)
        if not track:return
        self.engine.play_track(track,video=self.expanded and self.tabs.tabText(self.tabs.currentIndex())=='영상');self.refresh_queue();self.update_transport()
    def toggle_play(self):
        if not self.engine.track:
            if self.queue.tracks:self.next()
            else:self.expand('보관함')
        else:self.engine.toggle()
    def next(self,automatic=False):
        track=self.queue.next(automatic=automatic)
        if track:self.engine.play_track(track,self.expanded and self.tabs.tabText(self.tabs.currentIndex())=='영상');self.refresh_queue();self.update_transport()
        else:self.engine.player.stop();self.tell('재생목록의 마지막 곡입니다.');self.update_transport()
    def previous(self):
        track=self.queue.previous()
        if track:self.engine.play_track(track,self.engine.video);self.refresh_queue();self.update_transport()
    def random_local(self):
        tracks=self.filtered if self.source=='local' and self.search_box.text().strip() else self.library
        if not tracks:self.tell('먼저 음악 폴더를 선택해 주세요.');self.expand('보관함');return
        self.queue.replace(random.sample(tracks,len(tracks)));self.queue.set_shuffle(True);self.play_index(0);self.tell(f'로컬 {len(tracks):,}곡 랜덤 재생')
    def remove_selected(self):
        rows=sorted({index.row() for index in self.queue_view.selectionModel().selectedIndexes()},reverse=True);removed_current=False
        for row in rows:removed_current=self.queue.remove(row) or removed_current
        if removed_current:self.engine.stop();self.next()
        self.refresh_queue()
    def clear_queue(self):self.engine.stop();self.queue.replace([]);self.refresh_queue();self.update_transport()
    def refresh_queue(self):self.queue_model.replace(self.queue.tracks)
    def toggle_shuffle(self):self.queue.set_shuffle(not self.queue.shuffle);self.store.set('shuffle',self.queue.shuffle);self.update_transport()
    def toggle_repeat(self):
        self.queue.repeat={'off':'all','all':'one','one':'off'}[self.queue.repeat];self.store.set('repeat',self.queue.repeat);self.update_transport()
    def volume_changed(self,value):self.engine.audio.setVolume(value/100);self.volume_label.setText(str(value))
    def seek_to(self):self.engine.player.setPosition(round(self.seek.value()/1000*self.engine.player.duration()))
    def position_tick(self):
        total=self.engine.player.duration();pos=self.engine.player.position();self.time.setText(duration(pos)+' / '+duration(total))
        if not self.seek.isSliderDown():self.seek.setValue(round(pos/max(1,total)*1000))
        self.art.ratio=pos/max(1,total);self.art.update()
    def update_transport(self):
        track=self.queue.current if self.engine.track else None
        self.play.setIcon(icon('pause' if self.engine.playing() else 'play',self.play_ink()))
        self.shuffle.setProperty('active',self.queue.shuffle);self.repeat.setProperty('icon_name','repeat-one' if self.queue.repeat=='one' else 'repeat');self.repeat.setProperty('active',self.queue.repeat!='off')
        for b in (self.shuffle,self.repeat):
            b.setIcon(icon(b.property('icon_name'),self.theme['accent'] if b.property('active') else self.theme['muted']));b.style().unpolish(b);b.style().polish(b)
        if track:
            self.title.setText(track.title);self.title.setToolTip(track.title);self.artist.setText((track.artist or track.album or '내 음악')[:35]);self.badge.setText('YOUTUBE' if track.kind=='youtube' else Path(track.uri).suffix.upper().lstrip('.'));self.art.letter=track.title[:1]
        else:self.title.setText('음악을 골라 주세요');self.artist.setText('로컬 음악 · 유튜브');self.badge.setText('READY');self.art.letter='♪'
        self.visual_state()
    def expand(self,name):
        tab=next((n for n in range(self.tabs.count()) if self.tabs.tabText(n)==name),0)
        if self.expanded and self.tabs.currentIndex()==tab:
            self.expanded=False;self.saved_height=max(280,self.drawer.height());self.anim.stop();self.anim.setStartValue(self.drawer.height());self.anim.setEndValue(0);self.anim.start()
            if self.engine.video:self.switch_video(False)
            return
        self.tabs.setCurrentIndex(tab)
        if not self.expanded:
            self.expanded=True;self.drawer.show();self.anim.stop();self.anim.setStartValue(0);self.anim.setEndValue(self.saved_height);self.resize(self.width(),252+self.saved_height);self.anim.start()
        self.tab_changed(tab)
    def sync_nav(self):
        for name,button in self.nav_buttons.items():
            button.setProperty('active',self.expanded and self.tabs.tabText(self.tabs.currentIndex())==name);button.style().unpolish(button);button.style().polish(button)
        self.counter.setVisible(self.expanded);self.grip.setVisible(self.expanded)
    def animation_done(self):
        self.sync_nav()
        if not self.expanded:self.drawer.hide();self.resize(self.width(),252)
        else:self.drawer.setMaximumHeight(16777215)
    def tab_changed(self,index):
        self.sync_nav()
        if not self.expanded:return
        self.switch_video(self.tabs.tabText(index)=='영상')
    def switch_video(self,value):
        if value and self.video_widget is None:
            self.video_widget=QVideoWidget();self.video_widget.setMinimumHeight(180);self.video_layout.insertWidget(0,self.video_widget,1)
        self.engine.set_video_output(self.video_widget if value else None)
        if self.video_widget:self.video_widget.setVisible(value)
        if self.engine.track and self.engine.track.kind=='youtube' and self.engine.video!=value:
            pos=self.engine.player.position();playing=self.engine.playing();self.engine.play_track(self.engine.track,value,pos,playing)
        else:self.engine.video=value
    def open_original(self):
        track=self.engine.track
        if track and track.kind=='youtube':QDesktopServices.openUrl(QUrl(track.uri+'&t='+str(self.engine.player.position()//1000)))
        else:self.tell('현재 재생 중인 유튜브 곡이 없습니다.')
    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'음악 폴더 선택')
        if folder:
            roots=self.config['music_roots'];roots=[r for r in roots if r!='./music']
            if folder not in roots:roots.append(folder)
            self.config['music_roots']=roots;self.store.set('music_roots',roots);self.rescan()
    def refresh_playlists(self):self.playlist_combo.clear();self.playlist_combo.addItems(self.store.playlist_names())
    def save_playlist(self):
        if not self.queue.tracks:self.tell('저장할 대기열이 없습니다.');return
        name,ok=QInputDialog.getText(self,'재생목록 저장','이름')
        if ok and name.strip():self.store.save_playlist(name,self.queue.tracks);self.refresh_playlists();self.tell('재생목록을 저장했어요.')
    def load_playlist(self):
        tracks=self.store.playlist(self.playlist_combo.currentText())
        if tracks:self.queue.replace(tracks);self.queue.set_shuffle(self.queue.shuffle);self.play_index(0)
    def delete_playlist(self):
        name=self.playlist_combo.currentText()
        if name and QMessageBox.question(self,'재생목록 삭제',f'“{name}” 목록을 삭제할까요?')==QMessageBox.Yes:self.store.delete_playlist(name);self.refresh_playlists()
    def export_playlist(self):
        name=self.playlist_combo.currentText()
        if not name:return
        path,_=QFileDialog.getSaveFileName(self,'재생목록 내보내기',name+'.json','JSON (*.json)')
        if path:Path(path).write_text(json.dumps({'name':name,'tracks':[t.to_dict() for t in self.store.playlist(name)]},ensure_ascii=False,indent=2),encoding='utf-8');self.tell('목록을 내보냈어요. 로컬 곡 위치도 포함됩니다.')
    def import_playlist(self):
        path,_=QFileDialog.getOpenFileName(self,'재생목록 가져오기','','JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>5_000_000:raise ValueError('재생목록 파일이 너무 큽니다.')
            data=json.loads(Path(path).read_text(encoding='utf-8-sig'));tracks=[Track.from_dict(t) for t in data['tracks']]
            for t in tracks:
                if t.kind=='youtube':youtube.youtube_input(t.uri)
            self.store.save_playlist(data['name'],tracks);self.refresh_playlists();self.tell('목록을 가져왔어요.')
        except (OSError,ValueError,KeyError,TypeError):self.tell('올바른 재생목록 파일인지 확인해 주세요.')
    def toggle_pin(self):
        self.config['always_on_top']=not self.config['always_on_top'];self.setWindowFlag(Qt.WindowStaysOnTopHint,self.config['always_on_top']);self.show();self.store.set('always_on_top',self.config['always_on_top']);self.pin.setIcon(icon('pin',self.theme['accent'] if self.config['always_on_top'] else self.theme['muted']))
    def settings(self):
        dialog=QDialog(self);dialog.setWindowTitle('플레이어 꾸미기');layout=QFormLayout(dialog)
        themes=QComboBox();themes.addItems([t['name'] for t in self.themes]);themes.setCurrentIndex(next((n for n,t in enumerate(self.themes) if t['id']==self.config['theme']),0));layout.addRow('테마',themes)
        opacity=QSlider(Qt.Horizontal);opacity.setRange(60,100);opacity.setValue(round(self.config['opacity']*100));layout.addRow('투명도 (60~100%)',opacity)
        width=QSpinBox();width.setRange(560,900);width.setValue(self.width());layout.addRow('플레이어 폭',width)
        height=QSpinBox();height.setRange(280,640);height.setValue(self.saved_height);layout.addRow('펼친 목록 높이',height)
        visual=QCheckBox('실제 오디오 비주얼라이저');visual.setChecked(self.config['visualizer']);layout.addRow(visual)
        row=QHBoxLayout();row.addWidget(self.button('배경 이미지','이미지 선택',self.choose_background,True));row.addWidget(self.button('배경 지우기','기본 배경',lambda:self.set_background(''),True));row.addWidget(self.button('강조색','테마 강조색 변경',self.choose_accent,True));row.addWidget(self.button('색 초기화','테마 기본색',lambda:self.set_accent(''),True));layout.addRow(row)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        if dialog.exec()==QDialog.Accepted:
            self.config.update(theme=self.themes[themes.currentIndex()]['id'],opacity=opacity.value()/100,visualizer=visual.isChecked(),width=width.value(),panel_height=height.value())
            self.saved_height=height.value();self.resize(width.value(),252+(self.saved_height if self.expanded else 0));self.setWindowOpacity(self.config['opacity']);self.apply_theme()
            for k in ('theme','opacity','visualizer','width','panel_height'):self.store.set(k,self.config[k])
    def choose_background(self):
        path,_=QFileDialog.getOpenFileName(self,'배경 이미지 선택','','Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:self.set_background(path)
    def set_background(self,path):self.config['background']=path;self.store.set('background',path);self.surface.set_image(path)
    def choose_accent(self):
        color=QColorDialog.getColor(QColor(self.theme['accent']),self,'강조색')
        if color.isValid():self.set_accent(color.name())
    def set_accent(self,color):self.config['accent']=color;self.store.set('accent',color);self.apply_theme()
    def play_ink(self):
        color=QColor(self.theme['accent'])
        channels=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in (color.redF(),color.greenF(),color.blueF())]
        luminance=sum(x*w for x,w in zip(channels,(.2126,.7152,.0722)))
        return '#10202B' if luminance>.18 else '#FFFFFF'
    def apply_theme(self):
        self.theme=dict(next((t for t in self.themes if t['id']==self.config['theme']),self.themes[0]))
        if self.config.get('accent'):self.theme['accent']=self.config['accent']
        t=self.theme;self.surface.set_theme(t);self.surface.set_image(self.config.get('background',''));self.art.accent=t['accent'];self.art.update();self.spectrum.color=t['accent']
        for button in self.findChildren(QPushButton):
            name=button.property('icon_name')
            if name:button.setIcon(icon(name,self.play_ink() if button.objectName()=='play' else t['muted']))
        for view in self.findChildren(QListView):
            delegate=view.itemDelegate()
            if isinstance(delegate,TrackDelegate):delegate.theme=t
            view.viewport().update()
        dark=QColor(t['panel']).lightness()<120;foreground='#081016' if QColor(t['accent']).lightness()>130 else '#FFFFFF'
        self.setStyleSheet(f'''QWidget{{font-family:'NanumSquareRound','Malgun Gothic','Segoe UI Symbol';font-size:12px;color:{t['text']};}} QMainWindow,QDialog{{background:{t['bg']};}} QLabel{{background:transparent;}} QLabel#brand{{font-size:11px;font-weight:700;color:{t['muted']};}} QLabel#muted,QLabel#status{{color:{t['muted']};}} QLabel#status{{font-size:11px;}} QLabel#trackTitle{{font-size:14px;font-weight:700;}} QLabel#time{{font-family:'NanumSquareRound','Malgun Gothic';font-size:12px;}} QLabel#badge{{font-size:10px;font-weight:700;color:{t['muted']};}} QFrame#lcd{{background:{t['panel']};border:1px solid {t['border']};border-radius:10px;}} QFrame#pad{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {QColor(t['panel']).lighter(108).name()},stop:1 {QColor(t['bg']).darker(106).name()});border:1px solid {t['border']};border-radius:66px;}} QFrame#drawer{{background:{t['panel']};border:1px solid {t['border']};border-radius:10px;}} QPushButton{{background:transparent;border:1px solid transparent;border-radius:7px;padding:4px 6px;}} QPushButton:hover{{background:{t['panel']};border-color:{t['border']};}} QPushButton:focus{{border:1px solid {t['accent']};}} QPushButton[active="true"]{{color:{t['accent']};font-weight:700;}} QPushButton#play{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {QColor(t['accent']).lighter(114).name()},stop:1 {QColor(t['accent']).darker(110).name()});border:1px solid {QColor(t['accent']).darker(125).name()};border-radius:28px;}} QPushButton#play:pressed{{background:{QColor(t['accent']).darker(118).name()};}} QLineEdit,QComboBox,QSpinBox{{background:{t['panel']};border:1px solid {t['border']};border-radius:6px;padding:6px;}} QListView{{background:transparent;border:0;outline:0;}} QListView::item{{padding:7px 9px;border-bottom:1px solid {t['border']};}} QListView::item:selected{{background:{t['bg']};color:{t['text']};border-left:3px solid {t['accent']};}} QTabWidget::pane{{border:0;}} QTabBar::tab{{background:transparent;padding:8px 10px;color:{t['muted']};border-bottom:2px solid transparent;}} QTabBar::tab:selected{{color:{t['text']};border-bottom:2px solid {t['accent']};}} QSlider::groove:horizontal{{height:3px;background:{t['border']};border-radius:1px;}} QSlider::sub-page:horizontal{{background:{t['accent']};}} QSlider::handle:horizontal{{background:{t['accent']};width:9px;margin:-4px 0;border-radius:4px;}} QScrollBar:vertical{{background:transparent;width:7px;}} QScrollBar::handle:vertical{{background:{t['border']};border-radius:3px;min-height:24px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}} QMenu{{background:{t['panel']};padding:5px;}}''')
        lcd_colors={'silver_blue':('#2B66C4','#0F3373','#EEF5FF','#A9C3EA','#8A97AA'),'midnight':('#10284F','#07132A','#DCE9FF','#8FA6CC','#243E62'),'warm_cream':('#3C6E86','#1C3B4B','#F6EEDF','#BFD3D9','#819A9E'),'visualizer':('#06191D','#020A0C','#E6FFF7','#86A8A0','#224B45')}
        a,b,text,muted,border=lcd_colors[t['id']]
        self.lcd.setStyleSheet(f"QFrame#lcd{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {a},stop:1 {b});border:2px solid {border};border-radius:12px;}} QFrame#lcd QLabel{{color:{text};}} QFrame#lcd QLabel#muted,QFrame#lcd QLabel#badge{{color:{muted};}}")
        self.setStyleSheet(self.styleSheet()+f"QFrame#navRail{{background:{t['bg']};border:1px solid {t['border']};border-radius:10px;}} QPushButton[nav=\"true\"]{{padding:4px 2px;font-size:12px;}} QPushButton[nav=\"true\"][active=\"true\"]{{background:{t['panel']};border:1px solid {t['border']};}}")
        self.sync_nav()
        self.visual_state()
    def visual_state(self):
        enabled=(self.config['visualizer'] or self.config['theme']=='visualizer') and self.isVisible() and not self.isMinimized()
        visual_theme=self.config['visualizer'] or self.config['theme']=='visualizer'
        self.artist.setVisible(not visual_theme)
        self.spectrum.setVisible(visual_theme);self.spectrum.set_active(enabled and self.engine.playing());self.engine.set_visualizer(enabled)
    def build_tray(self):
        pix=QPixmap(32,32);pix.fill(Qt.transparent);p=QPainter(pix);p.setBrush(QColor('#E8780F'));p.setPen(Qt.NoPen);p.drawEllipse(1,1,30,30);p.setPen(QColor('#FFFFFF'));p.drawText(pix.rect(),Qt.AlignCenter,'♪');p.end()
        self.setWindowIcon(QIcon(pix));self.tray=QSystemTrayIcon(self.windowIcon(),self);menu=QMenu(self)
        for name,callback in [('플레이어 열기',self.restore),('재생 / 일시정지',self.toggle_play),('다음 곡',self.next),('종료',self.exit_app)]:action=menu.addAction(name);action.triggered.connect(callback)
        self.tray.setContextMenu(menu);self.tray.setToolTip('Desktop Music Player');self.tray.activated.connect(lambda reason:self.restore() if reason==QSystemTrayIcon.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable() and not self.demo:self.tray.show()
    def hide_player(self):
        if self.tray.isVisible():self.hide()
        else:self.showMinimized()
    def restore(self):self.showNormal();self.raise_();self.activateWindow()
    def exit_app(self):
        self.store.set('volume',self.volume.value()/100);self.store.set('width',self.width());self.store.set('panel_height',self.saved_height)
        self.store.set('last_queue',[t.to_dict() for t in self.queue.tracks]);self.engine.stop();self.tray.hide();self.hide();self.deleteLater();QTimer.singleShot(250,QApplication.quit)
    def closeEvent(self,e):e.ignore();self.hide_player()
    def showEvent(self,e):super().showEvent(e);self.tick.start();self.visual_state()
    def hideEvent(self,e):super().hideEvent(e);self.tick.stop();self.spectrum.set_active(False);self.engine.set_visualizer(False)
    def changeEvent(self,e):super().changeEvent(e);QTimer.singleShot(0,self.visual_state)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):
        files=[url.toLocalFile() for url in e.mimeData().urls() if url.isLocalFile()]
        tracks=[Track(Path(p).stem,p) for p in files if Path(p).suffix.lower() in AUDIO|VIDEO]
        self.add_tracks(tracks);e.acceptProposedAction()

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv);app.setApplicationName('Desktop Music Player');app.setQuitOnLastWindowClosed(False)
    configure_fonts()
    root=app_root();(root/'data').mkdir(exist_ok=True)
    logging.basicConfig(filename=root/'data'/'player.log',level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    if '--self-test' in sys.argv:
        import wave,struct,math
        folder=root/'data'/'self-test';folder.mkdir(parents=True,exist_ok=True)
        file=folder/'sample.wav'
        with wave.open(str(file),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050)
            wav.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*440*i/22050))) for i in range(44100)))
        test=Window(Store(folder),demo=True);test.engine.audio.setMuted(True);test.show()
        test.config['theme']='visualizer';test.apply_theme();test.engine.play_track(Track('Playback self-test',str(file)))
        frames=[];test.engine.spectrum.connect(lambda value:frames.append(value))
        def finish_test():
            result={'position_ms':test.engine.player.position(),'spectrum_frames':len(frames),'themes':len(test.themes),'font_family':app.font().family(),'bold_available':'Bold' in QFontDatabase.styles(app.font().family())}
            result['passed']=result['position_ms']>500 and result['spectrum_frames']>1 and result['font_family']=='NanumSquareRound' and result['bold_available']
            (folder/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            test.grab().save(str(folder/'screen.png'));test.engine.stop();test.hide();test.deleteLater();QTimer.singleShot(250,app.quit)
        QTimer.singleShot(1300,finish_test)
        app.exec();return
    socket=QLocalSocket();socket.connectToServer('DesktopMusicPlayer-v1')
    if socket.waitForConnected(150):socket.write(b'show');socket.flush();socket.waitForBytesWritten(150);return
    QLocalServer.removeServer('DesktopMusicPlayer-v1');server=QLocalServer();server.listen('DesktopMusicPlayer-v1')
    window=Window();window.show()
    def incoming():
        connection=server.nextPendingConnection()
        if connection:connection.close();window.restore()
    server.newConnection.connect(incoming)
    app.aboutToQuit.connect(lambda:window.tray.hide())
    sys.exit(app.exec())
