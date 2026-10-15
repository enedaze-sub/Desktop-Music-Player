"""Named theme controls; edits join the settings dialog's Apply/Cancel draft."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QLabel,QMenu,QFileDialog,QMessageBox
from .theme_library import theme_name,unique_name,read_profiles,write_profiles
class ThemeLibraryControls(QWidget):
    def __init__(self,editor):
        super().__init__();self.editor=editor
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(7)
        row=QHBoxLayout();self.name=QLineEdit();self.name.setMaxLength(60);self.name.setPlaceholderText('테마 이름 · 예: 저녁의 플레이리스트');self.name.setAccessibleName('저장할 테마 이름');row.addWidget(self.name,1)
        self.save_button=QPushButton('이름으로 저장');self.save_button.clicked.connect(lambda:self.action(self.save_named,self.name.text()));row.addWidget(self.save_button);root.addLayout(row)
        row=QHBoxLayout();self.rename_button=QPushButton('이름 변경');self.rename_button.clicked.connect(lambda:self.action(self.rename_named,self.name.text()));row.addWidget(self.rename_button)
        self.delete_button=QPushButton('삭제');self.delete_button.clicked.connect(lambda:self.action(self.delete_named));row.addWidget(self.delete_button);row.addStretch()
        self.export_button=QPushButton('내보내기');menu=QMenu(self.export_button);menu.addAction('현재 테마 내보내기',lambda:self.export_dialog(False));menu.addAction('저장한 테마 전체 내보내기',lambda:self.export_dialog(True));self.export_button.setMenu(menu);row.addWidget(self.export_button)
        self.import_button=QPushButton('불러오기');self.import_button.clicked.connect(self.import_dialog);row.addWidget(self.import_button);root.addLayout(row)
        note=QLabel('저장한 테마는 위 목록에서 선택합니다. 이름·목록·선택한 테마의 편집은 적용하면 함께 저장됩니다.');note.setWordWrap(True);note.setObjectName('muted');root.addWidget(note);self.sync(editor.active_saved_name)
    def action(self,fn,*args):
        try:fn(*args)
        except (ValueError,OSError,UnicodeError) as error:QMessageBox.information(self,'테마 확인',str(error))
    def sync(self,name):
        self.name.setText(name);self.rename_button.setEnabled(bool(name));self.delete_button.setEnabled(bool(name))
    def save_named(self,name):
        name=theme_name(name);e=self.editor
        collision=next((n for n in e.library_draft if n.casefold()==name.casefold()),None)
        if collision is not None and collision!=e.active_saved_name:raise ValueError('같은 이름의 테마가 있습니다. 다른 이름으로 저장해 주세요.')
        if collision is not None:name=collision
        e.library_draft[name]=e.current_profile(name);e.select_saved_theme(name,load=False)
    def rename_named(self,name):
        e=self.editor;old=e.active_saved_name
        if not old:return
        name=theme_name(name)
        if any(n.casefold()==name.casefold() and n!=old for n in e.library_draft):raise ValueError('같은 이름의 테마가 있습니다. 다른 이름을 입력해 주세요.')
        profile=e.current_profile(name);e.library_draft={name if n==old else n:profile if n==old else p for n,p in e.library_draft.items()};e.select_saved_theme(name,load=False)
    def delete_named(self):
        e=self.editor;name=e.active_saved_name
        if name in e.library_draft:del e.library_draft[name]
        e.select_saved_theme('',load=False)
    def import_file(self,path):
        profiles=read_profiles(path);e=self.editor;draft=deepcopy(e.library_draft);names=[]
        for profile in profiles:
            name=unique_name(profile['name'],draft);profile['name']=name;draft[name]=profile;names.append(name)
        e.library_draft=draft;e.select_saved_theme(names[0]);return names
    def export_file(self,path,all_themes=False):
        e=self.editor
        if all_themes:
            profiles=deepcopy(e.library_draft)
            if e.active_saved_name:profiles[e.active_saved_name]=e.current_profile(e.active_saved_name)
            if not profiles:raise ValueError('내보낼 저장 테마가 없습니다.')
            profiles=list(profiles.values())
        else:profiles=[e.current_profile(self.name.text().strip() or '나만의 테마')]
        write_profiles(path,profiles)
    def export_dialog(self,all_themes):
        name='저장한 테마 전체' if all_themes else self.name.text().strip() or '나만의 테마'
        for char in '<>:"/\\|?*':name=name.replace(char,'_')
        path,_=QFileDialog.getSaveFileName(self,'테마 내보내기',name+'.json','테마 파일 (*.json)')
        if path:self.action(self.export_file,path,all_themes)
    def import_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,'테마 불러오기','','테마 파일 (*.json)')
        if path:self.action(self.import_file,path)
