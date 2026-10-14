"""Bounded background jobs and virtualized track list."""
from PySide6.QtCore import QObject,Signal,QRunnable,Qt,QAbstractListModel,QModelIndex
class Signals(QObject):
    done=Signal(int,object,str)
class Job(QRunnable):
    def __init__(self,ident,function,*args):
        super().__init__();self.ident=ident;self.function=function;self.args=args;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.ident,self.function(*self.args),'')
        except Exception as error:
            # Do not expose signed media URLs or credential-like request internals.
            message=str(error) if isinstance(error,(ValueError,FileNotFoundError)) else '처리하지 못했습니다. 연결이나 파일 상태를 확인해 주세요.'
            self.signals.done.emit(self.ident,None,message[:300])
class TrackModel(QAbstractListModel):
    def __init__(self,tracks=None,parent=None):super().__init__(parent);self.tracks=list(tracks or [])
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.tracks)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or index.row()>=len(self.tracks):return None
        t=self.tracks[index.row()]
        if role==Qt.DisplayRole:return t.title+'\n'+('YOUTUBE' if t.kind=='youtube' else 'LOCAL')+'  ·  '+(t.artist or t.album)
        if role==Qt.ToolTipRole:return t.title+'\n'+t.album
        if role==Qt.UserRole:return t
        if role==Qt.SizeHintRole:
            from PySide6.QtCore import QSize
            return QSize(100,54)
    def replace(self,tracks):
        self.beginResetModel();self.tracks=list(tracks);self.endResetModel()
