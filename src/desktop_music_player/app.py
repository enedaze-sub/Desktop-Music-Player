"""Compact native MP3-style window with a downward drawer."""
import json,logging,random,sys,time
from .scaling import scale_tree,stylesheet
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QThreadPool,QUrl,QPropertyAnimation,QEasingCurve,QSize,Slot,Property,QEvent,QAbstractAnimation
from PySide6.QtGui import QFont,QColor,QDesktopServices,QAction,QIcon,QPainter,QPixmap,QShortcut,QKeySequence,QFontDatabase
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,
 QSizePolicy,QSlider,QLineEdit,QListView,QTabWidget,QComboBox,QFileDialog,QInputDialog,QMessageBox,QDialog,QFormLayout,QCheckBox,
 QSizeGrip,QSystemTrayIcon,QMenu,QAbstractItemView,QDialogButtonBox,QSpinBox,QColorDialog,QTextEdit,QPlainTextEdit,QAbstractSpinBox)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from .core import Track,Queue,scan_library,app_root,AUDIO,VIDEO,playlist_id
from .storage import Store
from .jobs import Job,TrackModel
from .engine import Engine
from .widgets import Surface,Artwork,Spectrum,DragBar,TrackDelegate,Deck,LCDFrame,ElidedLabel,VideoCanvas,ResizeHandle,install_button_focus_filter
from .icons import icon
from . import youtube
from .background_editor import BackgroundEditor

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
    QApplication.instance().setFont(font);install_button_focus_filter(QApplication.instance())
    return families

def duration(ms):
    sec=max(0,int(ms//1000));return f'{sec//60}:{sec%60:02d}'

def load_themes():
    return json.loads(resource('themes.json').read_text(encoding='utf-8'))

COMPACT_HEIGHT=252
EXPANDED_BASE=270
MIN_PANEL_HEIGHT=240

class Window(QMainWindow):
    def __init__(self,store=None,demo=False):
        super().__init__();self.store=store or Store();self.config=self.store.config();self.themes=load_themes();self.demo=demo
        self.ui_scale=1.0
        self.setWindowTitle('Desktop Music Player');self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint)
        self.compact_height=max(COMPACT_HEIGHT,int(self.config.get('compact_height',COMPACT_HEIGHT)))
        self.setAttribute(Qt.WA_TranslucentBackground);self.setMinimumSize(560,COMPACT_HEIGHT);self.setMaximumSize(1600,16777215);self.resize(max(560,self.config.get('width',600)),self.compact_height)
        self.setAcceptDrops(True);self.queue=Queue();self.queue.repeat=self.config.get('repeat','off');self.queue.set_shuffle(self.config.get('shuffle',False))
        self.engine=Engine(self);self.engine.audio.setVolume(self.config['volume'])
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(2);self.jobs={};self.job_id=0;self.scan_pending=False
        self.library=[];self.filtered=[];self.youtube_results=[];self.source='local';self.expanded=False;self.video_widget=None;self.saved_height=max(MIN_PANEL_HEIGHT,self.config.get('panel_height',340));self._transitioning=False
        self.surface=Surface(self);self.setCentralWidget(self.surface);self.header=QWidget(self.surface);outer=QVBoxLayout(self.header);outer.setContentsMargins(0,0,0,0);outer.setSpacing(4)
        self.bar=DragBar(self);self.bar.setFixedHeight(30);bar=QHBoxLayout(self.bar);bar.setContentsMargins(2,0,0,0);bar.setSpacing(5)
        self.brand=QLabel('Desktop Music');self.brand.setObjectName('brand');bar.addWidget(self.brand);bar.addStretch()
        self.pin=self.button('◇','항상 위에 표시',self.toggle_pin);bar.addWidget(self.pin)
        bar.addWidget(self.button('⚙','테마·배경·투명도 설정',self.settings));bar.addWidget(self.button('−','최소화',self.showMinimized));bar.addWidget(self.button('×','트레이로 숨기기',self.hide_player))
        outer.addWidget(self.bar)
        top=QHBoxLayout();top.setSpacing(12);self.art=Artwork();top.addWidget(self.art)
        self.lcd=LCDFrame();self.lcd.setObjectName('lcd');lcd=QVBoxLayout(self.lcd);lcd.setContentsMargins(10,9,10,8);lcd.setSpacing(3)
        self.title=ElidedLabel('음악을 골라 주세요',lines=2);self.title.setObjectName('trackTitle');self.title.setMinimumWidth(100);self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed);self.title.setWordWrap(True);self.title.setFixedHeight(42);lcd.addWidget(self.title)
        self.artist=ElidedLabel('로컬 음악 · 유튜브');self.artist.setFixedHeight(16);self.artist.setObjectName('muted');lcd.addWidget(self.artist)
        meta=QHBoxLayout();self.time=QLabel('0:00 / 0:00');self.time.setObjectName('time');self.time.setMinimumWidth(self.time.fontMetrics().horizontalAdvance('00:00 / 00:00'));meta.addWidget(self.time);meta.addStretch();self.badge=QLabel('READY');self.badge.setObjectName('badge');meta.addWidget(self.badge);lcd.addLayout(meta)
        self.seek=QSlider(Qt.Horizontal);self.seek.setFocusPolicy(Qt.NoFocus);self.seek.setRange(0,1000);self.seek.sliderReleased.connect(self.seek_to);lcd.addWidget(self.seek)
        top.addWidget(self.lcd,1)
        pad=QFrame();pad.setObjectName('pad');pad.setFixedSize(132,132);pad_layout=QGridLayout(pad);pad_layout.setContentsMargins(6,6,6,6);pad_layout.setSpacing(0)
        self.shuffle=self.button('⤨','셔플',self.toggle_shuffle);pad_layout.addWidget(self.shuffle,0,1,Qt.AlignCenter)
        pad_layout.addWidget(self.button('‹','이전 곡',self.previous),1,0)
        self.play=self.button('▶','재생 / 일시정지',self.toggle_play);self.play.setObjectName('play');self.play.setFixedSize(56,56);self.play.setIconSize(QSize(24,24));pad_layout.addWidget(self.play,1,1)
        pad_layout.addWidget(self.button('›','다음 곡',self.next),1,2)
        self.repeat=self.button('↻','반복 모드',self.toggle_repeat);pad_layout.addWidget(self.repeat,2,1,Qt.AlignCenter);top.addWidget(pad)
        self.deck=Deck(self.art,self.lcd,pad);outer.addWidget(self.deck)
        self.controls=QWidget();self.controls.setFixedHeight(34);controls=QHBoxLayout(self.controls);controls.setContentsMargins(0,0,0,0);controls.setSpacing(16)
        volume_group=QWidget();volume_group.setFixedWidth(132);vol_layout=QHBoxLayout(volume_group);vol_layout.setSpacing(4);vol_layout.setContentsMargins(0,0,0,0)
        mute=self.button('','음소거',lambda:self.engine.audio.setMuted(not self.engine.audio.isMuted()));mute.setProperty('icon_name','volume');mute.setIcon(icon('volume'));vol_layout.addWidget(mute)
        self.volume=QSlider(Qt.Horizontal);self.volume.setFocusPolicy(Qt.NoFocus);self.volume.setRange(0,100);self.volume.setValue(round(self.config['volume']*100));self.volume.setFixedWidth(66)
        self.volume.valueChanged.connect(self.volume_changed);vol_layout.addWidget(self.volume);self.volume_label=QLabel(f'{self.volume.value()}');self.volume_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter);vol_layout.addWidget(self.volume_label);controls.addWidget(volume_group)
        self.nav_rail=QFrame();self.nav_rail.setObjectName('navRail');nav=QHBoxLayout(self.nav_rail);nav.setContentsMargins(2,2,2,2);nav.setSpacing(2);self.nav_buttons={}
        for name in ('보관함','대기열','재생목록','영상'):
            b=self.button(name,name+' 열기',lambda checked=False,name=name:self.expand(name),wide=True);b.setProperty('nav',True);b.setProperty('active',False);nav.addWidget(b,1);self.nav_buttons[name]=b
        controls.addWidget(self.nav_rail,1);outer.addWidget(self.controls)
        self.status_label=ElidedLabel('폴더를 선택하거나 유튜브를 검색해 시작하세요.');self.status_label.setFixedHeight(18);self.status_label.setObjectName('status');outer.addWidget(self.status_label)
        self.drawer_viewport=QWidget(self.surface);self.drawer_viewport.hide();self.drawer=QFrame(self.drawer_viewport);self.drawer.setObjectName('drawer');drawer_layout=QVBoxLayout(self.drawer);drawer_layout.setContentsMargins(6,8,6,3);drawer_layout.setSpacing(6)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();drawer_layout.addWidget(self.tabs)
        self.make_library();self.make_queue();self.make_playlists();self.make_video_page()
        self.tabs.currentChanged.connect(self.tab_changed)
        self.footer=QWidget(self.surface);bottom=QHBoxLayout(self.footer);bottom.setContentsMargins(0,0,0,0);self.counter=QLabel('LOCAL LIBRARY');self.counter.setObjectName('brand');bottom.addWidget(self.counter);bottom.addStretch();self.grip=QSizeGrip(self);self.grip.setFixedSize(14,14);bottom.addWidget(self.grip)
        self.spectrum=Spectrum(self.lcd);self.spectrum.hide();self.spectrum.setFixedHeight(24);lcd.addWidget(self.spectrum)
        self.engine.changed.connect(self.update_transport);self.engine.ended.connect(lambda:self.next(automatic=True));self.engine.message.connect(self.tell);self.engine.spectrum.connect(self.spectrum.accept)
        self.tick=QTimer(self);self.tick.setInterval(500);self.tick.timeout.connect(self.position_tick);self.tick.start()
        self.filter_timer=QTimer(self);self.filter_timer.setSingleShot(True);self.filter_timer.setInterval(220);self.filter_timer.timeout.connect(self.apply_filter)
        self.search_box.textChanged.connect(lambda:self.filter_timer.start() if self.source=='local' else None)
        self.anim=QPropertyAnimation(self,b'panelExtent',self);self.anim.setDuration(180);self.anim.setEasingCurve(QEasingCurve.OutCubic);self.anim.finished.connect(self.animation_done)
        self.build_tray();self.apply_theme();self.refresh_playlists();self.update_transport()
        self.setWindowOpacity(self.config['opacity']);self.setWindowFlag(Qt.WindowStaysOnTopHint,self.config['always_on_top'])
        QApplication.instance().installEventFilter(self)
        self.brand.setToolTip('Space: 재생/일시정지 · F1: 단축키 도움말')
        self.resize_handles=[ResizeHandle(self,edges) for edges in (Qt.LeftEdge,Qt.RightEdge,Qt.TopEdge,Qt.BottomEdge,Qt.LeftEdge|Qt.TopEdge,Qt.RightEdge|Qt.TopEdge,Qt.LeftEdge|Qt.BottomEdge,Qt.RightEdge|Qt.BottomEdge)]
        self.layout_surface();self.set_ui_scale(self.config.get('ui_scale',.8),persist=False)
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
        b=QPushButton('' if name and icon_only else text);b.setProperty('iconOnly',icon_only);b.setToolTip(tip);b.setAccessibleName(tip);b.clicked.connect(callback);b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(30)
        if name:b.setProperty('icon_name',name);b.setIcon(icon(name));b.setIconSize(QSize(18,18))
        if icon_only:b.setFixedSize(30,30)
        return b
    def list_view(self,model):
        view=QListView();view.setModel(model);view.setItemDelegate(TrackDelegate(view));view.setUniformItemSizes(True);view.setLayoutMode(QListView.Batched);view.setBatchSize(128);view.setSelectionMode(QAbstractItemView.ExtendedSelection);view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);return view
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
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(4,8,4,4)
        self.playlist_combo=QComboBox();layout.addWidget(self.playlist_combo)
        note=QLabel('로컬과 유튜브 곡을 하나의 재생목록에 함께 저장할 수 있어요.\n음악 파일은 복사하지 않고 곡 정보와 위치만 저장합니다.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        for actions in ([('재생',self.load_playlist),('현재 대기열 저장',self.save_playlist),('삭제',self.delete_playlist)],[('내보내기',self.export_playlist),('가져오기',self.import_playlist)]):
            row=QHBoxLayout()
            for text,method in actions:row.addWidget(self.button(text,text,method,True))
            row.addStretch();layout.addLayout(row)
        layout.addStretch();self.tabs.addTab(page,'재생목록')
    def make_video_page(self):
        self.video_page=QWidget();self.video_layout=QVBoxLayout(self.video_page);self.video_layout.setContentsMargins(4,8,4,4)
        self.video_note=QLabel('유튜브 곡을 재생한 뒤 영상으로 이어 볼 수 있어요.');self.video_note.setWordWrap(True);self.video_note.setObjectName('muted');self.video_layout.addWidget(self.video_note)
        self.video_layout.addWidget(self.button('원본 영상으로 이어보기','현재 위치에서 브라우저로 열기',self.open_original,True));self.tabs.addTab(self.video_page,'영상')
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
            if self.queue.current:self.play_index(self.queue.index)
            elif self.queue.tracks:self.next()
            else:self.expand('보관함')
        else:self.engine.toggle()
    def next(self,automatic=False):
        track=self.queue.next(automatic=automatic)
        if track:self.engine.play_track(track,self.expanded and self.tabs.tabText(self.tabs.currentIndex())=='영상');self.refresh_queue();self.update_transport()
        else:self.engine.player.stop();self.engine.clear_video();self.tell('재생목록의 마지막 곡입니다.');self.update_transport()
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
    def seek_to(self):self.engine.seek_to(round(self.seek.value()/1000*self.engine.player.duration()))
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
            self.title.setText(track.title);self.title.setToolTip(track.title);self.artist.setText(track.artist or track.album or '내 음악');self.artist.setToolTip(self.artist.text());self.badge.setText('YOUTUBE' if track.kind=='youtube' else Path(track.uri).suffix.upper().lstrip('.'));self.art.letter=track.title[:1]
        else:self.title.setText('음악을 골라 주세요');self.artist.setText('로컬 음악 · 유튜브');self.badge.setText('READY');self.art.letter='♪'
        self.visual_state()
    def get_panel_extent(self):return self.height()
    def set_panel_extent(self,value):self.resize(self.width(),value);self.layout_surface()
    panelExtent=Property(int,get_panel_extent,set_panel_extent)
    def px(self,value):return round(value*self.ui_scale)
    def set_ui_scale(self,value,persist=True):
        value=max(.5,min(1.5,float(value)))
        self.finish_transition();old=self.ui_scale;logical_width=self.width()/old
        compact=self.compact_height/old;panel=self.saved_height/old
        self._transitioning=True;self.ui_scale=value;self.config['ui_scale']=value
        scale_tree(self,value);self.setMinimumSize(self.px(560),self.px(EXPANDED_BASE+MIN_PANEL_HEIGHT if self.expanded else COMPACT_HEIGHT));self.setMaximumWidth(self.px(1600))
        self.compact_height=self.px(compact);self.saved_height=self.px(panel)
        self.resize(self.px(logical_width),max(self.px(EXPANDED_BASE)+self.saved_height,self.compact_height) if self.expanded else self.compact_height)
        self.apply_theme();self._transitioning=False;self.deck.layout_children();self.layout_surface()
        for view in (self.library_view,self.queue_view):view.viewport().update()
        if persist:self.store.set('ui_scale',value)
    def layout_surface(self):
        if not hasattr(self,'header'):return
        self.surface.set_background_view(self.expanded,self.compact_height)
        width=max(0,self.width()-self.px(32))
        self.header.setGeometry(self.px(16),self.px(6),width,self.px(230))
        if hasattr(self,'drawer_viewport'):
            visible_height=max(0,self.height()-self.px(EXPANDED_BASE))
            self.drawer_viewport.setGeometry(self.px(16),self.px(242),width,visible_height)
            content_height=self.saved_height if self._transitioning else max(self.px(MIN_PANEL_HEIGHT),visible_height)
            self.drawer.setGeometry(0,0,width,content_height)
        if hasattr(self,'footer'):self.footer.setGeometry(self.px(16),self.height()-self.px(26),width,self.px(16))
        if hasattr(self,'resize_handles'):
            w,h=self.width(),self.height();e=max(5,self.px(7))
            geometry=[(0,e,e,h-2*e),(w-e,e,e,h-2*e),(e,0,w-2*e,e),(e,h-e,w-2*e,e),(0,0,e,e),(w-e,0,e,e),(0,h-e,e,e),(w-e,h-e,e,e)]
            for handle,rect in zip(self.resize_handles,geometry):handle.setGeometry(*rect);handle.show();handle.raise_()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'expanded') and self.expanded and not self._transitioning:
            self.saved_height=max(self.px(MIN_PANEL_HEIGHT),self.height()-self.px(EXPANDED_BASE));self.compact_height=min(self.compact_height,self.height())
        elif hasattr(self,'expanded') and not self.expanded and not self._transitioning:self.compact_height=max(self.px(COMPACT_HEIGHT),self.height())
        self.layout_surface()
    def expand(self,name):
        tab=next((n for n in range(self.tabs.count()) if self.tabs.tabText(n)==name),0)
        close=self.expanded and self.tabs.currentIndex()==tab
        if close and not self._transitioning:self.saved_height=max(self.px(MIN_PANEL_HEIGHT),self.height()-self.px(EXPANDED_BASE))
        self.anim.stop();self._transitioning=True
        self.setMinimumHeight(self.px(COMPACT_HEIGHT));self.setMaximumHeight(16777215)
        self.expanded=not close
        if not close:self.tabs.setCurrentIndex(tab);self.drawer_viewport.show()
        self.footer.hide();self.sync_nav()
        self.switch_video(self.expanded and self.tabs.tabText(tab)=='영상')
        self.layout_surface()
        self.anim.setStartValue(self.get_panel_extent())
        target=max(self.px(EXPANDED_BASE)+self.saved_height,self.compact_height) if self.expanded else self.compact_height
        if self.expanded:self.saved_height=max(self.px(MIN_PANEL_HEIGHT),target-self.px(EXPANDED_BASE))
        self.layout_surface();self.anim.setEndValue(target)
        self.anim.start()
    def sync_nav(self,force=False):
        for name,button in self.nav_buttons.items():
            active=self.expanded and self.tabs.tabText(self.tabs.currentIndex())==name
            changed=button.property('active')!=active
            if changed:button.setProperty('active',active);button.style().unpolish(button);button.style().polish(button)
            if changed or force:button.setIcon(icon(button.property('icon_name'),self.theme['accent'] if active else self.theme['muted']))
        self.footer.setVisible(self.expanded and not self._transitioning)
    def animation_done(self):
        self._transitioning=False
        if self.video_widget:self.video_widget.updates_paused=False
        if not self.expanded:
            self.drawer_viewport.hide();self.setMinimumHeight(self.px(COMPACT_HEIGHT));self.setMaximumHeight(16777215);self.resize(self.width(),self.compact_height)
        else:
            self.setMinimumHeight(self.px(EXPANDED_BASE+MIN_PANEL_HEIGHT))
        self.layout_surface();self.sync_nav()
    def finish_transition(self):
        if not self._transitioning:return
        target=self.anim.endValue();self.anim.stop();self.set_panel_extent(target);self.animation_done()
    def tab_changed(self,index):
        self.sync_nav()
        if self.expanded:self.switch_video(self.tabs.tabText(index)=='영상')
    def switch_video(self,value):
        if value and self.video_widget is None:
            self.video_widget=VideoCanvas();self.video_layout.insertWidget(0,self.video_widget,1);scale_tree(self,self.ui_scale)
        if self.video_widget:self.video_widget.setVisible(value)
        self.engine.set_video_mode(value,self.video_widget)
        if self.video_widget:self.video_widget.updates_paused=self._transitioning
        self.engine.set_video_visible(self.isVisible() and not self.isMinimized())
    def eventFilter(self,watched,event):
        if event.type()!=QEvent.KeyPress or QApplication.activeWindow() is not self:return super().eventFilter(watched,event)
        focus=QApplication.focusWidget();key=event.key();mod=event.modifiers();ctrl=bool(mod&Qt.ControlModifier)
        editing=isinstance(focus,(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox,QComboBox))
        if ctrl and editing and key in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):return False
        if ctrl:
            actions={Qt.Key_L:lambda:self.expand('보관함'),Qt.Key_F:self.focus_search,Qt.Key_Left:self.previous,Qt.Key_Right:self.next,Qt.Key_Up:lambda:self.volume.setValue(self.volume.value()+5),Qt.Key_Down:lambda:self.volume.setValue(self.volume.value()-5),Qt.Key_Q:self.exit_app}
            for number,name in enumerate(('보관함','대기열','재생목록','영상'),Qt.Key_1):actions[number]=lambda name=name:self.expand(name)
            if key in actions:actions[key]();return True
        if editing:return False
        if key==Qt.Key_F1:self.shortcut_help();return True
        if key==Qt.Key_Escape and self.expanded:self.expand(self.tabs.tabText(self.tabs.currentIndex()));return True
        if key==Qt.Key_Space:self.toggle_play();return True
        if key in (Qt.Key_Left,Qt.Key_Right):
            seconds=30 if mod&Qt.ShiftModifier else 5
            self.engine.seek_to(self.engine.player.position()+seconds*1000*(1 if key==Qt.Key_Right else -1));return True
        if key in (Qt.Key_Up,Qt.Key_Down) and not isinstance(focus,QListView):
            self.volume.setValue(self.volume.value()+(5 if key==Qt.Key_Up else -5));return True
        if key==Qt.Key_M:self.engine.audio.setMuted(not self.engine.audio.isMuted());return True
        if key==Qt.Key_S:self.engine.stop();self.tell('재생을 정지했어요.');return True
        if key==Qt.Key_Home:self.engine.seek_to(0);return True
        if key==Qt.Key_Delete and focus is self.queue_view:self.remove_selected();return True
        return super().eventFilter(watched,event)
    def focus_search(self):
        if not self.expanded or self.tabs.currentIndex()!=0:self.expand('보관함')
        self.finish_transition();self.search_box.setFocus();self.search_box.selectAll()
    def shortcut_help(self):
        QMessageBox.information(self,'키보드 단축키','Space  재생 / 일시정지\nS  정지 · M  음소거\n← / →  5초 이동 · Shift + ← / →  30초 이동\n↑ / ↓  볼륨 ±5 (목록에서는 항목 이동)\nCtrl + ↑ / ↓  볼륨 ±5\nCtrl + ← / →  이전 / 다음 곡\nHome  곡 처음으로 · Delete  선택 대기 곡 삭제\nCtrl + 1 / 2 / 3 / 4  보관함 / 대기열 / 재생목록 / 영상\nCtrl + F  검색 · Esc  목록 닫기 · Ctrl + Q  종료\n\n검색창에 글을 입력할 때는 Space와 방향키를 가로채지 않습니다.')
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
        from .settings_editor import SettingsEditor
        dialog=SettingsEditor(self);dialog.exec();dialog.deleteLater()
    def apply_background(self,values):
        self.surface.configure_background(values)
        if hasattr(self,'drawer'):
            color=QColor(self.theme['panel']);alpha=round(255*(1-max(0,min(.9,float(values.get('background_list_transparency',0))))))
            style=f"QFrame#drawer{{background:rgba({color.red()},{color.green()},{color.blue()},{alpha});border:1px solid {self.theme['border']};border-radius:{self.px(10)}px;}}"
            if self.drawer.styleSheet()!=style:self.drawer.setStyleSheet(style)
    def choose_background(self):
        dialog=BackgroundEditor(self);dialog.exec();dialog.deleteLater()
    def set_background(self,path):
        self.config['background']=path;self.store.set('background',path);self.apply_background(self.config)
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
        signature=(tuple(sorted(self.theme.items())),self.ui_scale)
        if getattr(self,'_theme_signature',None)==signature:
            self.apply_background(self.config);self.visual_state();return
        self._theme_signature=signature
        t=self.theme;self.surface.set_theme(t);self.apply_background(self.config);self.art.accent=t['accent'];self.art.update();self.spectrum.color=t['accent']
        for button in self.findChildren(QPushButton):
            name=button.property('icon_name')
            if name:button.setIcon(icon(name,self.play_ink() if button.objectName()=='play' else t['muted']))
        for view in self.findChildren(QListView):
            delegate=view.itemDelegate()
            if isinstance(delegate,TrackDelegate):delegate.theme=t
            view.viewport().update()
        dark=QColor(t['panel']).lightness()<120;foreground='#081016' if QColor(t['accent']).lightness()>130 else '#FFFFFF'
        base_style=f'''QWidget{{font-family:'NanumSquareRound','Malgun Gothic','Segoe UI Symbol';font-size:12px;color:{t['text']};}} QMainWindow,QDialog{{background:{t['bg']};}} QLabel{{background:transparent;}} QLabel#brand{{font-size:11px;font-weight:700;color:{t['muted']};}} QLabel#muted,QLabel#status{{color:{t['muted']};}} QLabel#status{{font-size:11px;}} QLabel#trackTitle{{font-size:14px;font-weight:700;}} QLabel#time{{font-family:'NanumSquareRound','Malgun Gothic';font-size:12px;}} QLabel#badge{{font-size:10px;font-weight:700;color:{t['muted']};}} QFrame#lcd{{background:{t['panel']};border:1px solid {t['border']};border-radius:10px;}} QFrame#pad{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {QColor(t['panel']).lighter(108).name()},stop:1 {QColor(t['bg']).darker(106).name()});border:1px solid {t['border']};border-radius:66px;}} QFrame#drawer{{background:{t['panel']};border:1px solid {t['border']};border-radius:10px;}} QPushButton{{background:transparent;border:1px solid transparent;border-radius:7px;padding:4px 6px;}} QPushButton:hover{{background:{t['panel']};border-color:{t['border']};}} QPushButton[iconOnly="true"]:hover{{border-color:transparent;}} QPushButton[keyboardFocus="true"]:focus{{border:1px solid {t['accent']};}} QPushButton[active="true"]{{color:{t['accent']};font-weight:700;}} QPushButton#play{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {QColor(t['accent']).lighter(114).name()},stop:1 {QColor(t['accent']).darker(110).name()});border:1px solid {QColor(t['accent']).darker(125).name()};border-radius:28px;}} QPushButton#play:pressed{{background:{QColor(t['accent']).darker(118).name()};}} QLineEdit,QComboBox,QAbstractSpinBox{{background:{t['panel']};border:1px solid {t['border']};border-radius:6px;padding:6px;}} QAbstractSpinBox QLineEdit{{background:transparent;border:0;border-radius:0;padding:0;}} QListView{{background:transparent;border:0;outline:0;}} QListView::item{{padding:7px 9px;border-bottom:1px solid {t['border']};}} QListView::item:selected{{background:{t['bg']};color:{t['text']};border-left:3px solid {t['accent']};}} QTabWidget::pane{{border:0;}} QTabBar::tab{{background:transparent;padding:8px 10px;color:{t['muted']};border-bottom:2px solid transparent;}} QTabBar::tab:selected{{color:{t['text']};border-bottom:2px solid {t['accent']};}} QSlider::groove:horizontal{{height:3px;background:{t['border']};border-radius:1px;}} QSlider::sub-page:horizontal{{background:{t['accent']};}} QSlider::handle:horizontal{{background:{t['accent']};width:9px;margin:-4px 0;border-radius:4px;}} QScrollBar:vertical{{background:transparent;width:7px;}} QScrollBar::handle:vertical{{background:{t['border']};border-radius:3px;min-height:24px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}} QMenu{{background:{t['panel']};padding:5px;}}'''
        lcd_colors={'silver_blue':('#2B66C4','#0F3373','#EEF5FF','#A9C3EA','#8A97AA'),'midnight':('#10284F','#07132A','#DCE9FF','#8FA6CC','#243E62'),'warm_cream':('#3C6E86','#1C3B4B','#F6EEDF','#BFD3D9','#819A9E'),'visualizer':('#06191D','#020A0C','#E6FFF7','#86A8A0','#224B45')}
        a,b,text,muted,border=lcd_colors[t['id']]
        lcd_style=f"QFrame#lcd{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {a},stop:1 {b});border:2px solid {border};border-radius:12px;}} QFrame#lcd QLabel{{color:{text};}} QFrame#lcd QLabel#muted,QFrame#lcd QLabel#badge{{color:{muted};}}"
        base_style+=f"QFrame#navRail{{background:{t['bg']};border:1px solid {t['border']};border-radius:10px;}} QPushButton[nav=\"true\"]{{padding:4px 2px;font-size:12px;}} QPushButton[nav=\"true\"][active=\"true\"]{{background:{t['panel']};border:1px solid {t['border']};}}"
        self.base_theme_style=base_style
        root_style=stylesheet(base_style,self.ui_scale);lcd_style=stylesheet(lcd_style,self.ui_scale)
        if self.styleSheet()!=root_style:self.setStyleSheet(root_style)
        if self.lcd.styleSheet()!=lcd_style:self.lcd.setStyleSheet(lcd_style)
        self.apply_background(self.config)
        self.sync_nav(force=True)
        self.visual_state()
    def visual_state(self):
        enabled=(self.config['visualizer'] or self.config['theme']=='visualizer') and self.isVisible() and not self.isMinimized()
        visual_theme=self.config['visualizer'] or self.config['theme']=='visualizer'
        self.artist.setVisible(not visual_theme)
        self.spectrum.setVisible(visual_theme);self.spectrum.set_active(enabled and self.engine.playing());self.engine.set_visualizer(enabled)
    def build_tray(self):
        self.setWindowIcon(QIcon(str(resource('assets/app.ico'))));self.tray=QSystemTrayIcon(self.windowIcon(),self);menu=QMenu(self)
        for name,callback in [('플레이어 열기',self.restore),('재생 / 일시정지',self.toggle_play),('다음 곡',self.next),('종료',self.exit_app)]:action=menu.addAction(name);action.triggered.connect(callback)
        self.tray.setContextMenu(menu);self.tray.setToolTip('Desktop Music Player');self.tray.activated.connect(lambda reason:self.restore() if reason==QSystemTrayIcon.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable() and not self.demo:self.tray.show()
    def hide_player(self):
        if self.tray.isVisible():self.hide()
        else:self.showMinimized()
    def restore(self):self.showNormal();self.raise_();self.activateWindow()
    def exit_app(self):
        self.finish_transition();self.store.set('volume',self.volume.value()/100);self.store.set('width',round(self.width()/self.ui_scale));self.store.set('panel_height',round(self.saved_height/self.ui_scale));self.store.set('compact_height',round(self.compact_height/self.ui_scale))
        self.store.set('last_queue',[t.to_dict() for t in self.queue.tracks]);self.engine.stop();self.tray.hide();self.hide();self.deleteLater();QTimer.singleShot(250,QApplication.quit)
    def closeEvent(self,e):e.ignore();self.hide_player()
    def showEvent(self,e):super().showEvent(e);self.tick.start();self.visual_state();self.engine.set_video_visible(not self.isMinimized())
    def hideEvent(self,e):super().hideEvent(e);self.tick.stop();self.spectrum.set_active(False);self.engine.set_visualizer(False);self.engine.set_video_visible(False)
    def changeEvent(self,e):super().changeEvent(e);QTimer.singleShot(0,self.refresh_visibility)
    def refresh_visibility(self):self.visual_state();self.engine.set_video_visible(self.isVisible() and not self.isMinimized())
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):
        files=[url.toLocalFile() for url in e.mimeData().urls() if url.isLocalFile()]
        tracks=[Track(Path(p).stem,p) for p in files if Path(p).suffix.lower() in AUDIO|VIDEO]
        self.add_tracks(tracks);e.acceptProposedAction()

def main():
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DesktopMusicPlayer.Desktop')
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv);app.setApplicationName('Desktop Music Player');app.setQuitOnLastWindowClosed(False)
    configure_fonts();app.setWindowIcon(QIcon(str(resource('assets/app.ico'))))
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
            from .settings_editor import SettingsEditor
            original_theme=test.config['theme'];original_scale=test.ui_scale;source=test.engine.player.source()
            editor=SettingsEditor(test);editor.themes.setCurrentIndex(1);editor.opacity.setValue(25);editor.scale.setValue(100);editor.apply_preview()
            result['appearance_live_preview']=test.theme['id']==test.themes[1]['id'] and abs(test.windowOpacity()-.75)<.01 and test.ui_scale==1
            editor.reject();editor.deleteLater()
            result['appearance_cancel_restored']=test.config['theme']==original_theme and test.ui_scale==original_scale and test.windowOpacity()>.99
            background=BackgroundEditor(test);background.draft['background']=str(resource('assets/default-cover.png'));background.view.setCurrentIndex(1);background.mode.setCurrentIndex(2);background.list_transparency.setValue(60);background.render_preview()
            result['expanded_background_preview']=background.preview_window.expanded and not background.preview.pixmap.isNull() and not test.expanded
            result['appearance_source_unchanged']=test.engine.player.source()==source
            background.reject();background.deleteLater()
            result['passed']=result['position_ms']>500 and result['spectrum_frames']>1 and result['font_family']=='NanumSquareRound' and result['bold_available'] and all(result[key] for key in ('appearance_live_preview','appearance_cancel_restored','expanded_background_preview','appearance_source_unchanged'))
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
    app.aboutToQuit.connect(window.tray.hide)
    sys.exit(app.exec())
