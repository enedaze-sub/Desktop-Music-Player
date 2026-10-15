"""Live appearance drafts; only Apply commits to the persistent store."""
from copy import deepcopy
import re
from PySide6.QtCore import Qt,QTimer,QRegularExpression,QSignalBlocker
from PySide6.QtGui import QColor,QPixmap,QIcon,QRegularExpressionValidator
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QWidget,QLabel,QComboBox,QSlider,QSpinBox,QCheckBox,QPushButton,QDialogButtonBox,QColorDialog,QScrollArea,QFrame,QGridLayout,QLineEdit
from .storage import BACKGROUND_DEFAULTS
from .scaling import scale_tree,stylesheet
from .palettes import COLOR_LABELS,STYLES,palette,GRADIENT_TARGETS,DIRECTIONS,gradient_settings
from .layout import COMPACT_HEIGHT,EXPANDED_BASE
from .appearance_preview import AppearancePreview
from .theme_library import library_profiles,validate_profile,profile_from_theme
from .theme_library_editor import ThemeLibraryControls

class SettingsEditor(QDialog):
    KEYS=('theme','opacity','ui_scale','visualizer','width','compact_height','panel_height','accent','custom_theme','custom_gradients','theme_library','custom_theme_name','visualizer_style','layout_version',*BACKGROUND_DEFAULTS)
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('플레이어 꾸미기')
        owner.finish_transition();self.original={key:deepcopy(owner.config[key]) for key in self.KEYS}
        self.original_size=owner.size();self.original_compact=owner.compact_height;self.original_panel=owner.saved_height;self.original_opacity=owner.windowOpacity()
        self.dialog_scale=max(.8,min(1.2,owner.ui_scale));self.closed=False
        fallback=next(t for t in owner.themes if t['id']=='custom');self.custom_draft=palette(owner.config.get('custom_theme'),fallback);self.gradient_draft=gradient_settings(owner.config.get('custom_gradients'),self.custom_draft)
        self.library_draft=library_profiles(owner.config.get('theme_library'));self.active_saved_name=owner.config.get('custom_theme_name','') if owner.config['theme']=='custom' else ''
        if self.active_saved_name not in self.library_draft:self.active_saved_name=''
        root=QVBoxLayout(self);root.setContentsMargins(18,16,18,14);root.setSpacing(14)
        note=QLabel('테마와 파형을 여기에서 미리 확인하세요. 실제 플레이어에도 바로 반영됩니다.\n적용하면 저장하고, 취소하면 원래 모습으로 돌아갑니다.');note.setWordWrap(True);note.setObjectName('muted');root.addWidget(note)
        self.themes=QComboBox();self.themes.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.themes.setMinimumContentsLength(12);self.populate_theme_choices();index=self.themes.findData('saved:'+self.active_saved_name) if self.active_saved_name else self.themes.findData('base:'+owner.config['theme']);self.themes.setCurrentIndex(max(0,index))
        theme_row=QHBoxLayout();theme_row.addWidget(QLabel('테마'));theme_row.addWidget(self.themes,1);root.addLayout(theme_row)
        self.preview=AppearancePreview(self);self.preview.set_appearance(owner.theme,owner.config.get('visualizer_style','bars'),owner.config['visualizer']);root.addWidget(self.preview)
        preview_note=QLabel('미리보기의 파형은 예시입니다. 실제 재생에서는 음악에 맞춰 움직입니다.');preview_note.setObjectName('muted');preview_note.setWordWrap(True);root.addWidget(preview_note)
        visual_row=QHBoxLayout()
        self.visual=QCheckBox('오디오 비주얼라이저 사용');self.visual.setChecked(owner.config['visualizer']);visual_row.addWidget(self.visual)
        visual_row.addWidget(QLabel('파형 모양'));self.visual_style=QComboBox()
        for key,name in STYLES.items():self.visual_style.addItem(name,key)
        self.visual_style.setCurrentIndex(max(0,self.visual_style.findData(owner.config.get('visualizer_style','bars'))));visual_row.addWidget(self.visual_style,1);root.addLayout(visual_row)
        body=QWidget();body_layout=QVBoxLayout(body);body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(14);form=QFormLayout();form.setSpacing(12);body_layout.addLayout(form)

        self.custom_panel=QWidget();custom_layout=QVBoxLayout(self.custom_panel);custom_layout.setContentsMargins(0,4,0,4);custom_layout.setSpacing(8)
        self.library_controls=ThemeLibraryControls(self);custom_layout.addWidget(self.library_controls)
        seed_row=QHBoxLayout();self.seed_theme=QComboBox();self.seed_theme.addItems([t['name'] for t in owner.themes if t['id']!='custom']);seed_row.addWidget(self.seed_theme,1);self.copy_button=QPushButton('이 테마에서 시작');self.copy_button.clicked.connect(self.copy_preset);seed_row.addWidget(self.copy_button);custom_layout.addLayout(seed_row)
        grid=QGridLayout();grid.setHorizontalSpacing(8);grid.setVerticalSpacing(7);custom_layout.addLayout(grid);self.color_buttons={};self.color_fields={}
        for n,(key,label) in enumerate(COLOR_LABELS.items()):
            button=QPushButton(label);button.setCursor(Qt.PointingHandCursor);button.clicked.connect(lambda checked=False,k=key:self.choose_color(k));button.setAccessibleName(label+' 색 선택');self.color_buttons[key]=button
            edit=QLineEdit(self.custom_draft[key]);edit.setMaximumWidth(100);edit.setMaxLength(7);edit.setValidator(QRegularExpressionValidator(QRegularExpression('#[0-9A-Fa-f]{6}'),edit));edit.setAccessibleName(label+' HEX 색상');edit.textEdited.connect(lambda text,k=key:self.set_color(k,text) if len(text)==7 else None);edit.editingFinished.connect(lambda k=key:self.edit_color(k));self.color_fields[key]=edit
            row,col=divmod(n,2);grid.addWidget(button,row,col*2);grid.addWidget(edit,row,col*2+1)
        gradient_note=QLabel('그라디언트 · 시작 색은 위에서, 끝 색과 방향은 아래에서 선택');gradient_note.setObjectName('muted');gradient_note.setWordWrap(True);custom_layout.addWidget(gradient_note)
        gradient_grid=QGridLayout();gradient_grid.setHorizontalSpacing(8);gradient_grid.setVerticalSpacing(5);custom_layout.addLayout(gradient_grid);self.gradient_checks={};self.gradient_buttons={};self.gradient_directions={}
        for n,(key,label) in enumerate(GRADIENT_TARGETS.items()):
            check=QCheckBox(label);check.setChecked(self.gradient_draft[key]['enabled']);check.toggled.connect(lambda enabled,k=key:self.toggle_gradient(k,enabled));self.gradient_checks[key]=check
            button=QPushButton();button.setCursor(Qt.PointingHandCursor);button.setAccessibleName(label+' 그라디언트 끝 색');button.clicked.connect(lambda checked=False,k=key:self.choose_gradient_end(k));self.gradient_buttons[key]=button
            direction=QComboBox()
            for value,name in DIRECTIONS.items():direction.addItem(name,value)
            direction.setCurrentIndex(direction.findData(self.gradient_draft[key]['direction']));direction.currentIndexChanged.connect(lambda index,k=key:self.change_gradient_direction(k));self.gradient_directions[key]=direction
            gradient_grid.addWidget(check,n,0);gradient_grid.addWidget(button,n,1);gradient_grid.addWidget(direction,n,2)
        form.addRow(self.custom_panel);self.refresh_colors();self.custom_panel.setVisible(owner.config['theme']=='custom')
        self.scale=self.percent(form,'전체 UI 배율 · 50~150%',50,150,round(owner.ui_scale*100),5)
        self.opacity=self.percent(form,'창 투명도 · 0~40%',0,40,round((1-owner.config['opacity'])*100))
        self.width_control=self.number(form,'플레이어 폭',560,1600,round(owner.width()/owner.ui_scale))
        self.compact=self.number(form,'접힌 창 높이',COMPACT_HEIGHT,900,round(owner.compact_height/owner.ui_scale))
        self.panel=self.number(form,'펼친 목록 높이',240,900,round(owner.saved_height/owner.ui_scale))
        hint=QLabel('폭과 높이는 UI 배율 100% 기준입니다. 기본 UI 배율은 80%예요.');hint.setWordWrap(True);hint.setObjectName('muted');body_layout.addWidget(hint)
        row=QHBoxLayout()
        for text,callback in [('배경 이미지 꾸미기',self.open_background),('배경 지우기',self.clear_background)]:
            button=QPushButton(text);button.clicked.connect(callback);button.setCursor(Qt.PointingHandCursor);row.addWidget(button)
        body_layout.addLayout(row)
        scroll=QScrollArea();scroll.setFrameShape(QFrame.NoFrame);scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroll.setWidget(body);body.setAutoFillBackground(False);scroll.viewport().setAutoFillBackground(False);root.addWidget(scroll,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('적용');buttons.button(QDialogButtonBox.Cancel).setText('취소');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(35);self.timer.timeout.connect(self.apply_preview)
        self.themes.currentIndexChanged.connect(self.theme_changed);self.visual.toggled.connect(self.schedule_preview);self.visual_style.currentIndexChanged.connect(self.schedule_preview)
        for control in (self.scale,self.opacity,self.width_control,self.compact,self.panel):control.valueChanged.connect(self.schedule_preview)
        scale_tree(self,self.dialog_scale);self.setStyleSheet(stylesheet(owner.base_theme_style,self.dialog_scale));area=owner.screen().availableGeometry();self.resize(min(round(680*self.dialog_scale),area.width()-48),min(round(860*self.dialog_scale),area.height()-80))
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
        spin=QSpinBox();spin.setRange(low,high);spin.setSingleStep(step);spin.setSuffix('%');spin.setValue(value);spin.setMinimumWidth(88);spin.setAccessibleName(label)
        slider.valueChanged.connect(spin.setValue);spin.valueChanged.connect(slider.setValue)
        for widget in (a,slider,b,spin):layout.addWidget(widget,1 if widget is slider else 0)
        form.addRow(label,row);spin.slider=slider;return spin
    def number(self,form,label,low,high,value):
        spin=QSpinBox();spin.setRange(low,high);spin.setValue(value);form.addRow(label,spin);return spin
    def schedule_preview(self,*_):
        if not self.closed and not self.timer.isActive():self.timer.start()
    def apply_preview(self):
        if self.closed:return
        owner=self.owner;owner.config.update(theme=self.selected_theme_id(),custom_theme_name=self.active_saved_name,theme_library=deepcopy(self.library_draft),opacity=1-self.opacity.value()/100,visualizer=self.visual.isChecked(),custom_theme=deepcopy(self.custom_draft),custom_gradients=deepcopy(self.gradient_draft),visualizer_style=self.visual_style.currentData())
        factor=self.scale.value()/100
        if abs(owner.ui_scale-factor)>.001:owner.set_ui_scale(factor,persist=False)
        owner._transitioning=True;owner.compact_height=owner.px(self.compact.value());owner.saved_height=owner.px(self.panel.value())
        owner.resize(owner.px(self.width_control.value()),max(owner.px(EXPANDED_BASE)+owner.saved_height,owner.compact_height) if owner.expanded else owner.compact_height);owner._transitioning=False
        owner.config.update(width=self.width_control.value(),compact_height=self.compact.value(),panel_height=self.panel.value())
        owner.setWindowOpacity(owner.config['opacity']);owner.apply_theme();owner.layout_surface()
        self.preview.set_appearance(owner.theme,self.visual_style.currentData(),self.visual.isChecked())
        # Keep this dialog's metrics stable while the player's scale changes.
        style=stylesheet(owner.base_theme_style,self.dialog_scale)
        if self.styleSheet()!=style:self.setStyleSheet(style)
    def open_background(self):
        self.timer.stop();self.apply_preview()
        from .background_editor import BackgroundEditor
        editor=BackgroundEditor(self.owner,persist=False,parent=self);editor.exec();editor.deleteLater();self.apply_preview()
    def clear_background(self):self.owner.config['background']='';self.apply_preview()
    def populate_theme_choices(self):
        self.themes.clear()
        for theme in self.owner.themes:self.themes.addItem(theme['name'],'base:'+theme['id'])
        for name,profile in self.library_draft.items():
            pix=QPixmap(18,18);pix.fill(QColor(profile['colors']['accent']));self.themes.addItem(QIcon(pix),'저장 · '+name,'saved:'+name)
    def selected_theme_id(self):
        data=self.themes.currentData() or 'base:custom'
        return 'custom' if data.startswith('saved:') else data[5:]
    def current_profile(self,name):
        colors=deepcopy(self.custom_draft)
        colors.update({key:field.text().upper() for key,field in self.color_fields.items() if re.fullmatch('#[0-9A-Fa-f]{6}',field.text())})
        return validate_profile({'name':name,'colors':colors,'gradients':deepcopy(self.gradient_draft),'visualizer':{'enabled':self.visual.isChecked(),'style':self.visual_style.currentData()}})
    def capture_active_profile(self):
        if self.active_saved_name in self.library_draft:self.library_draft[self.active_saved_name]=self.current_profile(self.active_saved_name)
    def select_saved_theme(self,name,load=True):
        if load:self.capture_active_profile()
        with QSignalBlocker(self.themes):
            self.populate_theme_choices();self.themes.setCurrentIndex(self.themes.findData('saved:'+name if name else 'base:custom'))
        self.active_saved_name=name;self.custom_panel.setVisible(True);self.library_controls.sync(name)
        if name and load:self.load_saved_theme(name)
        else:self.schedule_preview()
    def load_saved_theme(self,name):
        profile=deepcopy(self.library_draft[name]);self.custom_draft=profile['colors'];self.gradient_draft=profile['gradients'];self.refresh_colors()
        self.visual.setChecked(profile['visualizer']['enabled']);self.visual_style.setCurrentIndex(self.visual_style.findData(profile['visualizer']['style']));self.schedule_preview()
    def theme_changed(self,*_):
        self.capture_active_profile()
        data=self.themes.currentData() or '';self.owner.config['accent']='';self.active_saved_name=data[6:] if data.startswith('saved:') else ''
        self.library_controls.sync(self.active_saved_name);self.custom_panel.setVisible(self.selected_theme_id()=='custom')
        if self.active_saved_name:self.load_saved_theme(self.active_saved_name)
        else:
            theme=next(t for t in self.owner.themes if t['id']==self.selected_theme_id())
            if 'visualizer_default' in theme:
                self.visual.setChecked(theme['visualizer_default']);self.visual_style.setCurrentIndex(self.visual_style.findData(theme['visualizer_style']))
        self.schedule_preview()
    def refresh_colors(self):
        for key,color in self.custom_draft.items():
            pixmap=QPixmap(18,18);pixmap.fill(QColor(color));self.color_buttons[key].setIcon(QIcon(pixmap));self.color_fields[key].setText(color)
        self.refresh_gradients()
    def refresh_gradients(self):
        for key,item in self.gradient_draft.items():
            with QSignalBlocker(self.gradient_checks[key]):self.gradient_checks[key].setChecked(item['enabled'])
            with QSignalBlocker(self.gradient_directions[key]):self.gradient_directions[key].setCurrentIndex(self.gradient_directions[key].findData(item['direction']))
            pixmap=QPixmap(18,18);pixmap.fill(QColor(item['end']));self.gradient_buttons[key].setIcon(QIcon(pixmap));self.gradient_buttons[key].setText(item['end']);self.gradient_buttons[key].setEnabled(item['enabled']);self.gradient_directions[key].setEnabled(item['enabled'])
    def toggle_gradient(self,key,enabled):
        self.gradient_draft[key]['enabled']=enabled;self.refresh_gradients();self.schedule_preview()
    def set_gradient_end(self,key,value):
        if key not in GRADIENT_TARGETS or not isinstance(value,str) or not re.fullmatch('#[0-9A-Fa-f]{6}',value):return False
        self.gradient_draft[key]['end']=value.upper();self.refresh_gradients();self.schedule_preview();return True
    def choose_gradient_end(self,key):
        color=QColorDialog.getColor(QColor(self.gradient_draft[key]['end']),self,GRADIENT_TARGETS[key]+' 그라디언트 끝 색')
        if color.isValid():self.set_gradient_end(key,color.name())
    def change_gradient_direction(self,key):
        self.gradient_draft[key]['direction']=self.gradient_directions[key].currentData();self.schedule_preview()
    def set_color(self,key,value):
        if key not in COLOR_LABELS or not isinstance(value,str) or not re.fullmatch('#[0-9A-Fa-f]{6}',value):return False
        self.custom_draft[key]=value.upper();self.refresh_colors();self.schedule_preview();return True
    def choose_color(self,key):
        color=QColorDialog.getColor(QColor(self.custom_draft[key]),self,COLOR_LABELS[key]+' 색 선택')
        if color.isValid():self.set_color(key,color.name())
    def edit_color(self,key):
        if not self.set_color(key,self.color_fields[key].text()):self.color_fields[key].setText(self.custom_draft[key])
    def copy_preset(self):
        self.select_saved_theme('',load=False)
        preset=[t for t in self.owner.themes if t['id']!='custom'][self.seed_theme.currentIndex()];profile=profile_from_theme(preset);self.custom_draft=profile['colors'];self.gradient_draft=profile['gradients']
        if 'visualizer_default' in preset:
            self.visual.setChecked(profile['visualizer']['enabled']);self.visual_style.setCurrentIndex(self.visual_style.findData(profile['visualizer']['style']))
        self.refresh_colors();self.schedule_preview()
    def accept(self):
        if self.closed:return
        self.timer.stop()
        self.custom_draft.update({key:field.text().upper() for key,field in self.color_fields.items() if re.fullmatch('#[0-9A-Fa-f]{6}',field.text())})
        if self.active_saved_name:self.library_draft[self.active_saved_name]=self.current_profile(self.active_saved_name)
        self.apply_preview();self.owner.store.set_many({key:self.owner.config[key] for key in self.KEYS});self.preview.timer.stop();self.closed=True;super().accept()
    def reject(self):
        if self.closed:return
        self.timer.stop();owner=self.owner;owner.config.update(deepcopy(self.original));owner.set_ui_scale(self.original['ui_scale'],persist=False)
        owner._transitioning=True;owner.compact_height=self.original_compact;owner.saved_height=self.original_panel;owner.resize(self.original_size);owner._transitioning=False
        owner.setWindowOpacity(self.original_opacity);owner.apply_theme();owner.layout_surface();self.preview.timer.stop();self.closed=True;super().reject()
