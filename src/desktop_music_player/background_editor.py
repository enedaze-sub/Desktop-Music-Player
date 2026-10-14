"""Draft background controls and a draggable preview of the actual player."""
from pathlib import Path
from PySide6.QtCore import Qt,QRect,QSize,QTimer,Signal,QSignalBlocker
from PySide6.QtGui import QPixmap,QPainter,QColor,QImageReader
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,QLabel,QSlider,QSpinBox,QDoubleSpinBox,QComboBox,QDialogButtonBox,QFileDialog,QMessageBox,QSizePolicy
from .scaling import scale_tree
from .storage import BACKGROUND_DEFAULTS
from .widgets import ElidedLabel

class PlayerPreview(QWidget):
    moved=Signal(float,float)
    def __init__(self,parent=None):
        super().__init__(parent);self.pixmap=QPixmap();self.target=QRect();self.anchor=None
        self.setMinimumSize(400,300);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setMouseTracking(True)
    def set_scene(self,pixmap):self.pixmap=pixmap;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#111923'))
        if self.pixmap.isNull():return
        size=self.pixmap.size();size.scale(self.size()-QSize(20,20),Qt.KeepAspectRatio)
        self.target=QRect((self.width()-size.width())//2,(self.height()-size.height())//2,size.width(),size.height())
        p.setRenderHint(QPainter.SmoothPixmapTransform);p.drawPixmap(self.target,self.pixmap)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.target.contains(event.position().toPoint()):self.anchor=event.position();self.setCursor(Qt.ClosedHandCursor)
    def mouseMoveEvent(self,event):
        if self.anchor is None:self.setCursor(Qt.OpenHandCursor if self.target.contains(event.position().toPoint()) else Qt.ArrowCursor);return
        delta=event.position()-self.anchor;self.anchor=event.position();self.moved.emit(delta.x()/max(1,self.target.width()),delta.y()/max(1,self.target.height()))
    def mouseReleaseEvent(self,event):self.anchor=None;self.setCursor(Qt.OpenHandCursor)

class BackgroundEditor(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('배경 이미지 꾸미기');self.resize(920,580)
        self.original={key:owner.config.get(key,value) for key,value in BACKGROUND_DEFAULTS.items()};self.draft=dict(self.original)
        root=QVBoxLayout(self);root.setContentsMargins(18,16,18,14);root.setSpacing(12);columns=QHBoxLayout();columns.setSpacing(18);root.addLayout(columns,1)
        controls=QWidget();controls.setFixedWidth(280);left=QVBoxLayout(controls);left.setContentsMargins(0,0,0,0);left.setSpacing(12)
        self.filename=ElidedLabel();self.filename.setFixedHeight(18);left.addWidget(self.filename)
        choose=QPushButton('이미지 선택…');choose.clicked.connect(self.choose_image);clear=QPushButton('이미지 없애기');clear.clicked.connect(self.clear_image);row=QHBoxLayout();row.addWidget(choose);row.addWidget(clear);left.addLayout(row)
        form=QFormLayout();form.setSpacing(10);self.fit=QComboBox();self.fit.addItems(['창에 채우기','이미지 전체 보기','원본 크기']);self.fit.setCurrentIndex(['cover','contain','original'].index(self.draft['background_fit']));form.addRow('맞춤 방식',self.fit)
        self.zoom=self.percent_control(form,'이미지 크기',25,400,round(self.draft['background_zoom']*100))
        self.x=QDoubleSpinBox();self.y=QDoubleSpinBox()
        for widget,label,value in [(self.x,'좌우 이동',self.draft['background_x']),(self.y,'상하 이동',self.draft['background_y'])]:
            widget.setRange(-100,100);widget.setDecimals(1);widget.setSuffix('%');widget.setValue(value*100);form.addRow(label,widget)
        self.transparency=self.percent_control(form,'이미지 투명도',0,100,round((1-self.draft['background_opacity'])*100))
        self.tint=self.percent_control(form,'테마 색 반영',0,100,round(self.draft['background_tint']*100));left.addLayout(form)
        note=QLabel('미리보기에서 배경을 드래그해 이동하세요.\n\n투명도 0% · 테마 색 반영 0%: 원본 색\n크기 100%: 선택한 맞춤 방식의 기본 크기');note.setWordWrap(True);note.setObjectName('muted');left.addWidget(note)
        original=QPushButton('원본 색으로');original.clicked.connect(self.original_colors)
        reset=QPushButton('설정 초기화');reset.clicked.connect(self.reset);row=QHBoxLayout();row.addWidget(original);row.addWidget(reset);left.addLayout(row);left.addStretch();columns.addWidget(controls)
        right=QVBoxLayout();right.addWidget(QLabel('실시간 미리보기 · 배경만 드래그해 이동'));self.preview=PlayerPreview();right.addWidget(self.preview,1);columns.addLayout(right,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('적용');buttons.button(QDialogButtonBox.Cancel).setText('취소');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(20);self.timer.timeout.connect(self.render_preview)
        for control in (self.fit,self.zoom,self.x,self.y,self.transparency,self.tint):
            (control.currentIndexChanged if control is self.fit else control.valueChanged).connect(self.controls_changed)
        self.preview.moved.connect(self.move_image);self.update_filename();QTimer.singleShot(0,self.render_preview)
        for button in self.findChildren(QPushButton):button.setCursor(Qt.PointingHandCursor)
        scale_tree(self,owner.ui_scale);self.resize(owner.px(920),owner.px(580))
    def percent_control(self,form,label,low,high,value):
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        slider=QSlider(Qt.Horizontal);slider.setRange(low,high);slider.setValue(value);spin=QSpinBox();spin.setRange(low,high);spin.setSuffix('%');spin.setValue(value);spin.setFixedWidth(74)
        slider.valueChanged.connect(spin.setValue);spin.valueChanged.connect(slider.setValue);layout.addWidget(slider,1);layout.addWidget(spin);form.addRow(label,row);spin.slider=slider;return spin
    def controls_changed(self,*_):
        self.draft.update(background_fit=['cover','contain','original'][self.fit.currentIndex()],background_zoom=self.zoom.value()/100,background_x=self.x.value()/100,background_y=self.y.value()/100,background_opacity=1-self.transparency.value()/100,background_tint=self.tint.value()/100)
        self.timer.start()
    def sync_controls(self):
        controls=(self.fit,self.zoom,self.x,self.y,self.transparency,self.tint);blockers=[QSignalBlocker(c) for c in controls]
        self.fit.setCurrentIndex(['cover','contain','original'].index(self.draft['background_fit']));self.zoom.setValue(round(self.draft['background_zoom']*100));self.x.setValue(self.draft['background_x']*100);self.y.setValue(self.draft['background_y']*100);self.transparency.setValue(round((1-self.draft['background_opacity'])*100));self.tint.setValue(round(self.draft['background_tint']*100))
        for control in (self.zoom,self.transparency,self.tint):control.slider.setValue(control.value())
        del blockers
        self.update_filename();self.timer.start()
    def update_filename(self):
        path=self.draft['background'];self.filename.setText(Path(path).name if path else '선택한 이미지가 없습니다.');self.filename.setToolTip(path)
        for control in (self.fit,self.zoom,self.zoom.slider,self.x,self.y,self.transparency,self.transparency.slider,self.tint,self.tint.slider):control.setEnabled(bool(path))
    def choose_image(self):
        path,_=QFileDialog.getOpenFileName(self,'배경 이미지 선택','','이미지 (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:return
        if not QImageReader(path).canRead():QMessageBox.information(self,'이미지 확인','이 이미지를 읽지 못했습니다. 다른 파일을 선택해 주세요.');return
        self.draft.update(background=path,background_zoom=1.0,background_x=0.0,background_y=0.0);self.sync_controls()
    def move_image(self,dx,dy):
        self.draft['background_x']=max(-1,min(1,self.draft['background_x']+dx));self.draft['background_y']=max(-1,min(1,self.draft['background_y']+dy));self.sync_controls()
    def original_colors(self):self.draft.update(background_opacity=1.0,background_tint=0.0);self.sync_controls()
    def reset(self):
        image=self.draft['background'];self.draft=dict(BACKGROUND_DEFAULTS);self.draft['background']=image;self.sync_controls()
    def clear_image(self):self.draft['background']='';self.sync_controls()
    def render_preview(self):
        self.owner.surface.configure_background(self.draft);self.owner.surface.repaint();self.preview.set_scene(self.owner.grab())
    def accept(self):
        self.timer.stop();self.owner.config.update(self.draft);self.owner.store.set_many(self.draft);self.owner.surface.configure_background(self.draft);super().accept()
    def reject(self):
        self.timer.stop();self.owner.surface.configure_background(self.original);super().reject()
