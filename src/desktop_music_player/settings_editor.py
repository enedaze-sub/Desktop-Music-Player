"""Live appearance drafts; only Apply commits to the persistent store."""
from copy import deepcopy
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QWidget,QLabel,QComboBox,QSlider,QSpinBox,QCheckBox,QPushButton,QDialogButtonBox,QColorDialog,QScrollArea,QFrame
from .storage import BACKGROUND_DEFAULTS
from .scaling import scale_tree,stylesheet

class SettingsEditor(QDialog):
    KEYS=('theme','opacity','ui_scale','visualizer','width','compact_height','panel_height','accent',*BACKGROUND_DEFAULTS)
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('플레이어 꾸미기')
        owner.finish_transition();self.original={key:deepcopy(owner.config[key]) for key in self.KEYS}
        self.original_size=owner.size();self.original_compact=owner.compact_height;self.original_panel=owner.saved_height;self.original_opacity=owner.windowOpacity()
        self.dialog_scale=max(.8,min(1.2,owner.ui_scale));self.closed=False
        root=QVBoxLayout(self);root.setContentsMargins(18,16,18,14);root.setSpacing(14)
        note=QLabel('변경하면 뒤의 플레이어에 바로 미리보기됩니다.\n적용하면 저장하고, 취소하면 원래 모습으로 돌아갑니다.');note.setWordWrap(True);note.setObjectName('muted');root.addWidget(note)
        body=QWidget();body_layout=QVBoxLayout(body);body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(14);form=QFormLayout();form.setSpacing(12);body_layout.addLayout(form)
        self.themes=QComboBox();self.themes.addItems([t['name'] for t in owner.themes]);self.themes.setCurrentIndex(next((n for n,t in enumerate(owner.themes) if t['id']==owner.config['theme']),0));form.addRow('테마',self.themes)
        self.scale=self.percent(form,'전체 UI 배율 · 50~150%',50,150,round(owner.ui_scale*100),5)
        self.opacity=self.percent(form,'창 투명도 · 0~40%',0,40,round((1-owner.config['opacity'])*100))
        self.width_control=self.number(form,'플레이어 폭',560,1600,round(owner.width()/owner.ui_scale))
        self.compact=self.number(form,'접힌 창 높이',252,900,round(owner.compact_height/owner.ui_scale))
        self.panel=self.number(form,'펼친 목록 높이',240,900,round(owner.saved_height/owner.ui_scale))
        hint=QLabel('폭과 높이는 UI 배율 100% 기준입니다. 기본 UI 배율은 80%예요.');hint.setWordWrap(True);hint.setObjectName('muted');body_layout.addWidget(hint)
        self.visual=QCheckBox('실제 오디오 비주얼라이저');self.visual.setChecked(owner.config['visualizer']);body_layout.addWidget(self.visual)
        for actions in ([('배경 이미지 꾸미기…',self.open_background),('배경 지우기',self.clear_background)],[('강조색 선택…',self.choose_accent),('색 초기화',self.reset_accent)]):
            row=QHBoxLayout()
            for text,callback in actions:
                button=QPushButton(text);button.clicked.connect(callback);button.setCursor(Qt.PointingHandCursor);row.addWidget(button)
            body_layout.addLayout(row)
        scroll=QScrollArea();scroll.setFrameShape(QFrame.NoFrame);scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroll.setWidget(body);body.setAutoFillBackground(False);scroll.viewport().setAutoFillBackground(False);root.addWidget(scroll,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('적용');buttons.button(QDialogButtonBox.Cancel).setText('취소');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(35);self.timer.timeout.connect(self.apply_preview)
        self.themes.currentIndexChanged.connect(self.schedule_preview);self.visual.toggled.connect(self.schedule_preview)
        for control in (self.scale,self.opacity,self.width_control,self.compact,self.panel):control.valueChanged.connect(self.schedule_preview)
        scale_tree(self,self.dialog_scale);self.setStyleSheet(stylesheet(owner.base_theme_style,self.dialog_scale));area=owner.screen().availableGeometry();self.resize(min(round(680*self.dialog_scale),area.width()-48),min(round(560*self.dialog_scale),area.height()-80))
        self.place_beside_player()
    def place_beside_player(self):
        area=self.owner.screen().availableGeometry();player=self.owner.frameGeometry();w,h=self.width(),self.height()
        candidates=[(player.right()+18,player.top()),(player.left()-w-18,player.top()),(player.left(),player.bottom()+18),(player.left(),player.top()-h-48)]
        for x,y in candidates:
            if area.left()+12<=x and x+w+24<=area.right() and area.top()+12<=y and y+h+48<=area.bottom():self.move(x,y);return
        # On a narrow work area, reveal as much of the player as possible.
        x=area.left()+16 if player.center().x()>area.center().x() else area.right()-w-16
        y=max(area.top()+16,min(player.top(),area.bottom()-h-48));self.move(x,y)
    def percent(self,form,label,low,high,value,step=1):
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(7)
        a=QLabel(str(low)+'%');b=QLabel(str(high)+'%')
        for text in (a,b):text.setObjectName('muted')
        slider=QSlider(Qt.Horizontal);slider.setRange(low,high);slider.setSingleStep(step);slider.setPageStep(10);slider.setValue(value);slider.setAccessibleName(label)
        spin=QSpinBox();spin.setRange(low,high);spin.setSingleStep(step);spin.setSuffix('%');spin.setValue(value);spin.setFixedWidth(74);spin.setAccessibleName(label)
        slider.valueChanged.connect(spin.setValue);spin.valueChanged.connect(slider.setValue)
        for widget in (a,slider,b,spin):layout.addWidget(widget,1 if widget is slider else 0)
        form.addRow(label,row);spin.slider=slider;return spin
    def number(self,form,label,low,high,value):
        spin=QSpinBox();spin.setRange(low,high);spin.setValue(value);form.addRow(label,spin);return spin
    def schedule_preview(self,*_):
        if not self.closed and not self.timer.isActive():self.timer.start()
    def apply_preview(self):
        if self.closed:return
        owner=self.owner;owner.config.update(theme=owner.themes[self.themes.currentIndex()]['id'],opacity=1-self.opacity.value()/100,visualizer=self.visual.isChecked())
        factor=self.scale.value()/100
        if abs(owner.ui_scale-factor)>.001:owner.set_ui_scale(factor,persist=False)
        owner._transitioning=True;owner.compact_height=owner.px(self.compact.value());owner.saved_height=owner.px(self.panel.value())
        owner.resize(owner.px(self.width_control.value()),max(owner.px(270)+owner.saved_height,owner.compact_height) if owner.expanded else owner.compact_height);owner._transitioning=False
        owner.config.update(width=self.width_control.value(),compact_height=self.compact.value(),panel_height=self.panel.value())
        owner.setWindowOpacity(owner.config['opacity']);owner.apply_theme();owner.layout_surface()
        # Keep this dialog's metrics stable while the player's scale changes.
        style=stylesheet(owner.base_theme_style,self.dialog_scale)
        if self.styleSheet()!=style:self.setStyleSheet(style)
    def open_background(self):
        self.timer.stop();self.apply_preview()
        from .background_editor import BackgroundEditor
        editor=BackgroundEditor(self.owner,persist=False,parent=self);editor.exec();editor.deleteLater();self.apply_preview()
    def clear_background(self):self.owner.config['background']='';self.apply_preview()
    def choose_accent(self):
        color=QColorDialog.getColor(QColor(self.owner.theme['accent']),self,'강조색')
        if color.isValid():self.owner.config['accent']=color.name();self.apply_preview()
    def reset_accent(self):self.owner.config['accent']='';self.apply_preview()
    def accept(self):
        if self.closed:return
        self.timer.stop();self.apply_preview();self.owner.store.set_many({key:self.owner.config[key] for key in self.KEYS});self.closed=True;super().accept()
    def reject(self):
        if self.closed:return
        self.timer.stop();owner=self.owner;owner.config.update(deepcopy(self.original));owner.set_ui_scale(self.original['ui_scale'],persist=False)
        owner._transitioning=True;owner.compact_height=self.original_compact;owner.saved_height=self.original_panel;owner.resize(self.original_size);owner._transitioning=False
        owner.setWindowOpacity(self.original_opacity);owner.apply_theme();owner.layout_surface();self.closed=True;super().reject()
