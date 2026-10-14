"""Draft background controls and a draggable preview of the actual player."""
from pathlib import Path
from PySide6.QtCore import Qt,QRect,QSize,QTimer,Signal,QSignalBlocker
from PySide6.QtGui import QPixmap,QPainter,QColor,QImageReader
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,QLabel,QSlider,QSpinBox,QDoubleSpinBox,QComboBox,QDialogButtonBox,QFileDialog,QMessageBox,QSizePolicy,QScrollArea,QFrame
from .scaling import scale_tree,stylesheet
from .storage import BACKGROUND_DEFAULTS
from .widgets import ElidedLabel

class PlayerPreview(QWidget):
    moved=Signal(float,float)
    def __init__(self,parent=None):
        super().__init__(parent);self.pixmap=QPixmap();self.target=QRect();self.anchor=None;self.editable=True
        self.setMinimumSize(200,180);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setMouseTracking(True)
    def set_scene(self,pixmap):self.pixmap=pixmap;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#111923'))
        if self.pixmap.isNull():return
        size=self.pixmap.size();size.scale(self.size()-QSize(20,20),Qt.KeepAspectRatio)
        self.target=QRect((self.width()-size.width())//2,(self.height()-size.height())//2,size.width(),size.height())
        p.setRenderHint(QPainter.SmoothPixmapTransform);p.drawPixmap(self.target,self.pixmap)
    def mousePressEvent(self,event):
        if self.editable and event.button()==Qt.LeftButton and self.target.contains(event.position().toPoint()):self.anchor=event.position();self.setCursor(Qt.ClosedHandCursor)
    def mouseMoveEvent(self,event):
        if not self.editable:self.setCursor(Qt.ArrowCursor);return
        if self.anchor is None:self.setCursor(Qt.OpenHandCursor if self.target.contains(event.position().toPoint()) else Qt.ArrowCursor);return
        delta=event.position()-self.anchor;self.anchor=event.position();self.moved.emit(delta.x()/max(1,self.target.width()),delta.y()/max(1,self.target.height()))
    def mouseReleaseEvent(self,event):self.anchor=None;self.setCursor(Qt.OpenHandCursor)

TRANSFORM_KEYS=('background_fit','background_zoom','background_x','background_y','background_opacity','background_tint')

class BackgroundEditor(QDialog):
    MODES=('follow','header','custom')
    def __init__(self,owner,persist=True,parent=None):
        from copy import deepcopy
        super().__init__(parent or owner);self.owner=owner;self.persist=persist;self.closed=False;self.setWindowTitle('배경 이미지 꾸미기')
        self.original={key:deepcopy(owner.config.get(key,value)) for key,value in BACKGROUND_DEFAULTS.items()};self.draft=deepcopy(self.original)
        root=QVBoxLayout(self);root.setContentsMargins(18,16,18,14);root.setSpacing(12);columns=QHBoxLayout();columns.setSpacing(18);root.addLayout(columns,1)
        controls=QWidget();controls.setFixedWidth(305);left=QVBoxLayout(controls);left.setContentsMargins(0,0,0,0);left.setSpacing(10)
        self.filename=ElidedLabel();self.filename.setFixedHeight(18);left.addWidget(self.filename)
        choose=QPushButton('이미지 선택…');choose.clicked.connect(self.choose_image);clear=QPushButton('이미지 없애기');clear.clicked.connect(self.clear_image);row=QHBoxLayout();row.addWidget(choose);row.addWidget(clear);left.addLayout(row)
        form=QFormLayout();form.setSpacing(10)
        self.view=QComboBox();self.view.addItems(['접힌 플레이어','목록이 펼쳐진 플레이어']);self.view.setCurrentIndex(1 if owner.expanded else 0);form.addRow('편집할 모습',self.view)
        self.mode=QComboBox();self.mode.addItems(['접힌 창과 같은 설정','윗부분 이미지 구도 유지','펼친 창을 별도로 꾸미기']);self.mode.setCurrentIndex(self.MODES.index(self.draft['background_expanded_mode']));form.addRow('펼친 창의 배경',self.mode)
        self.fit=QComboBox();self.fit.addItems(['창에 채우기','이미지 전체 보기','원본 크기']);form.addRow('맞춤 방식',self.fit)
        active=self.active_values();self.fit.setCurrentIndex(['cover','contain','original'].index(active['background_fit']))
        self.zoom=self.percent_control(form,'이미지 크기',25,400,round(active['background_zoom']*100))
        self.x=QDoubleSpinBox();self.y=QDoubleSpinBox()
        for widget,label,value in [(self.x,'좌우 이동',active['background_x']),(self.y,'상하 이동',active['background_y'])]:
            widget.setRange(-100,100);widget.setDecimals(1);widget.setSuffix('%');widget.setValue(value*100);form.addRow(label,widget)
        self.transparency=self.percent_control(form,'이미지 투명도',0,100,round((1-active['background_opacity'])*100))
        self.tint=self.percent_control(form,'테마 색 반영',0,100,round(active['background_tint']*100))
        self.list_transparency=self.percent_control(form,'목록 배경 투명도',0,90,round(self.draft['background_list_transparency']*100));left.addLayout(form)
        self.context_note=QLabel();self.context_note.setWordWrap(True);self.context_note.setObjectName('muted');left.addWidget(self.context_note)
        note=QLabel('미리보기에서 배경을 드래그해 이동하세요.\n이미지 투명도 0% · 테마 색 반영 0%: 원본 색\n목록 배경 투명도를 높이면 이미지가 비쳐요.');note.setWordWrap(True);note.setObjectName('muted');left.addWidget(note)
        self.original_button=QPushButton('원본 색으로');self.original_button.clicked.connect(self.original_colors)
        self.reset_button=QPushButton('구도 초기화');self.reset_button.clicked.connect(self.reset);row=QHBoxLayout();row.addWidget(self.original_button);row.addWidget(self.reset_button);left.addLayout(row);left.addStretch();scroll=QScrollArea();scroll.setFrameShape(QFrame.NoFrame);scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroll.setFixedWidth(323);scroll.setWidget(controls);controls.setAutoFillBackground(False);scroll.viewport().setAutoFillBackground(False);columns.addWidget(scroll)
        right=QVBoxLayout();self.preview_label=QLabel();self.preview_label.setWordWrap(True);right.addWidget(self.preview_label);self.preview=PlayerPreview();right.addWidget(self.preview,1);columns.addLayout(right,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('적용');buttons.button(QDialogButtonBox.Cancel).setText('취소');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(33);self.timer.timeout.connect(self.render_preview)
        for control in (self.fit,self.zoom,self.x,self.y,self.transparency,self.tint):
            (control.currentIndexChanged if control is self.fit else control.valueChanged).connect(self.controls_changed)
        self.mode.currentIndexChanged.connect(self.mode_changed);self.view.currentIndexChanged.connect(self.view_changed);self.list_transparency.valueChanged.connect(self.controls_changed)
        self.preview.moved.connect(self.move_image)
        # An inert copy renders both states without altering real playback or the drawer.
        from .app import Window
        self.preview_window=Window(owner.store,demo=True);self.preview_window.setParent(self,Qt.Window);self.preview_window.setAttribute(Qt.WA_DontShowOnScreen,True)
        self.preview_window.config.update(owner.config);self.preview_window.set_ui_scale(owner.ui_scale,persist=False)
        self.preview_window.set_library(owner.library);self.preview_window.queue.replace(list(owner.queue.tracks));self.preview_window.refresh_queue()
        self.preview_window.tabs.setCurrentIndex(owner.tabs.currentIndex() if owner.tabs.currentIndex()<3 else 0)
        self.preview_window.show();self.preview_window.tick.stop();self.preview_window.spectrum.set_active(False)
        self.finished.connect(self.dispose_preview)
        for button in self.findChildren(QPushButton):button.setCursor(Qt.PointingHandCursor)
        dialog_scale=max(.8,min(1.2,owner.ui_scale));self.setStyleSheet(stylesheet(owner.base_theme_style,dialog_scale));scale_tree(self,dialog_scale);area=owner.screen().availableGeometry();self.resize(min(round(1000*dialog_scale),area.width()-48),min(round(730*dialog_scale),area.height()-80))
        self.sync_controls();QTimer.singleShot(0,self.render_preview)
    def active_values(self):
        if self.view.currentIndex()==1 and self.draft['background_expanded_mode']=='custom':
            if not self.draft['background_expanded']:self.draft['background_expanded']={key:self.draft[key] for key in TRANSFORM_KEYS}
            return self.draft['background_expanded']
        return self.draft
    def can_edit_transform(self):return self.view.currentIndex()==0 or self.draft['background_expanded_mode']=='custom'
    def percent_control(self,form,label,low,high,value):
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        slider=QSlider(Qt.Horizontal);slider.setRange(low,high);slider.setValue(value);slider.setAccessibleName(label);spin=QSpinBox();spin.setRange(low,high);spin.setSuffix('%');spin.setValue(value);spin.setMinimumWidth(88)
        slider.valueChanged.connect(spin.setValue);spin.valueChanged.connect(slider.setValue);layout.addWidget(slider,1);layout.addWidget(spin);form.addRow(label,row);spin.slider=slider;return spin
    def schedule_preview(self):
        # Throttle to the newest draft each frame; continuous dragging never
        # restarts the timer and postpones rendering until the mouse stops.
        if not self.closed and not self.timer.isActive():self.timer.start()
    def controls_changed(self,*_):
        if self.can_edit_transform():self.active_values().update(background_fit=['cover','contain','original'][self.fit.currentIndex()],background_zoom=self.zoom.value()/100,background_x=self.x.value()/100,background_y=self.y.value()/100,background_opacity=1-self.transparency.value()/100,background_tint=self.tint.value()/100)
        self.draft['background_list_transparency']=self.list_transparency.value()/100;self.schedule_preview()
    def mode_changed(self,*_):self.draft['background_expanded_mode']=self.MODES[self.mode.currentIndex()];self.sync_controls()
    def view_changed(self,*_):self.sync_controls()
    def sync_controls(self):
        active=self.active_values();controls=(self.fit,self.zoom,self.x,self.y,self.transparency,self.tint,self.list_transparency);blockers=[QSignalBlocker(c) for c in controls]
        self.fit.setCurrentIndex(['cover','contain','original'].index(active['background_fit']));self.zoom.setValue(round(active['background_zoom']*100));self.x.setValue(active['background_x']*100);self.y.setValue(active['background_y']*100);self.transparency.setValue(round((1-active['background_opacity'])*100));self.tint.setValue(round(active['background_tint']*100));self.list_transparency.setValue(round(self.draft['background_list_transparency']*100))
        for control in (self.zoom,self.transparency,self.tint,self.list_transparency):
            with QSignalBlocker(control.slider):control.slider.setValue(control.value())
        del blockers
        self.update_filename();self.schedule_preview()
    def update_filename(self):
        path=self.draft['background'];self.filename.setText(Path(path).name if path else '선택한 이미지가 없습니다.');self.filename.setToolTip(path)
        editing=self.can_edit_transform();self.preview.editable=editing and bool(path)
        for control in (self.fit,self.zoom,self.zoom.slider,self.x,self.y,self.transparency,self.transparency.slider,self.tint,self.tint.slider,self.original_button,self.reset_button):control.setEnabled(bool(path) and editing)
        expanded=self.view.currentIndex()==1
        for control in (self.list_transparency,self.list_transparency.slider):control.setEnabled(expanded)
        self.preview_label.setText('펼친 모습 미리보기 · 실제 재생에는 영향을 주지 않아요' if expanded else '접힌 모습 미리보기 · 배경만 드래그해 이동')
        self.context_note.setText('펼친 창만의 크기·위치·색감을 편집합니다.' if expanded and editing else '윗부분의 구도를 유지하며 아래로 펼쳐집니다.' if expanded and self.mode.currentIndex()==1 else '접힌 창의 설정을 함께 사용합니다. 별도로 꾸미기를 선택하면 펼친 창만 편집할 수 있어요.' if expanded else '접힌 창의 이미지 크기·위치·색감을 편집합니다.')
    def choose_image(self):
        path,_=QFileDialog.getOpenFileName(self,'배경 이미지 선택','','이미지 (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:return
        if not QImageReader(path).canRead():QMessageBox.information(self,'이미지 확인','이 이미지를 읽지 못했습니다. 다른 파일을 선택해 주세요.');return
        self.draft.update(background=path,background_zoom=1.0,background_x=0.0,background_y=0.0);self.sync_controls()
    def move_image(self,dx,dy):
        if not self.can_edit_transform() or not self.draft['background']:return
        active=self.active_values();active['background_x']=max(-1,min(1,active['background_x']+dx));active['background_y']=max(-1,min(1,active['background_y']+dy));self.sync_controls()
    def original_colors(self):self.active_values().update(background_opacity=1.0,background_tint=0.0);self.sync_controls()
    def reset(self):self.active_values().update({key:BACKGROUND_DEFAULTS[key] for key in TRANSFORM_KEYS});self.sync_controls()
    def clear_image(self):self.draft['background']='';self.sync_controls()
    def render_preview(self):
        if self.closed:return
        self.owner.apply_background(self.draft);window=self.preview_window
        for name in ('title','artist','time','badge','status_label'):getattr(window,name).setText(getattr(self.owner,name).text())
        window.art.pixmap=self.owner.art.pixmap;window.art.ratio=self.owner.art.ratio
        window._transitioning=True;window.expanded=self.view.currentIndex()==1;window.compact_height=self.owner.compact_height;window.saved_height=self.owner.saved_height
        window.setMinimumHeight(window.px(510 if window.expanded else 252));window.resize(self.owner.width(),max(window.px(270)+window.saved_height,window.compact_height) if window.expanded else window.compact_height)
        window.drawer_viewport.setVisible(window.expanded);window._transitioning=False;window.sync_nav();window.layout_surface();window.apply_background(self.draft)
        self.preview.set_scene(window.grab())
    def dispose_preview(self):self.preview_window.hide();self.preview_window.deleteLater()
    def accept(self):
        if self.closed:return
        from copy import deepcopy
        self.timer.stop();self.owner.config.update(deepcopy(self.draft))
        if self.persist:self.owner.store.set_many(self.draft)
        self.owner.apply_background(self.draft);self.closed=True;super().accept()
    def reject(self):
        if self.closed:return
        self.timer.stop();self.owner.apply_background(self.original);self.closed=True;super().reject()
