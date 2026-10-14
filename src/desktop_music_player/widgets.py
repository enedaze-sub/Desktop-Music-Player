"""Painter widgets from the Opus 5.5 theme specification."""
import math,sys
from pathlib import Path
from .core import app_root
from .icons import icon
from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QPixmap,QLinearGradient,QConicalGradient
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QHBoxLayout,QPushButton,QStyledItemDelegate,QStyle
class Surface(QWidget):
    def __init__(self,parent=None):super().__init__(parent);self.theme={};self.image=QPixmap();self.scaled=QPixmap()
    def set_theme(self,theme):self.theme=theme;self.update()
    def set_image(self,path):self.image=QPixmap(path);self.resizeEvent(None);self.update()
    def resizeEvent(self,event):
        if not self.image.isNull():self.scaled=self.image.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
        if event:super().resizeEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5);path=QPainterPath();path.addRoundedRect(rect,16,16)
        p.setClipPath(path)
        bg=QColor(self.theme.get('bg','#D9DFE6'));grad=QLinearGradient(0,0,0,self.height());grad.setColorAt(0,bg.lighter(107));grad.setColorAt(1,bg.darker(104));p.fillRect(self.rect(),grad)
        if self.theme.get('id')=='silver_blue':
            p.setPen(QColor(255,255,255,15))
            for y in range(0,min(200,self.height()),3):p.drawLine(0,y,self.width(),y)
        if not self.scaled.isNull():
            p.setOpacity(.3);p.drawPixmap((self.width()-self.scaled.width())//2,(self.height()-self.scaled.height())//2,self.scaled);p.setOpacity(1)
        p.setPen(QPen(QColor(self.theme.get('border','#9CA8B7')),1));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect,16,16)
class Artwork(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(132,132);self.accent='#E8780F';self.text='#18212C';self.ratio=0;self.letter='♪';self.pixmap=QPixmap(str(Path(getattr(sys,'_MEIPASS',app_root()))/'assets'/'default-cover.png'))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(10,10,112,112)
        bezel=QConicalGradient(66,66,90);bezel.setColorAt(0,QColor('#EFF4FA'));bezel.setColorAt(.45,QColor('#6F879B'));bezel.setColorAt(1,QColor('#DCE5EE'));p.setPen(QPen(QColor('#7E93A5'),1));p.setBrush(bezel);p.drawEllipse(QRectF(1,1,130,130))
        grad=QLinearGradient(0,0,104,104);grad.setColorAt(0,QColor('#455C70'));grad.setColorAt(1,QColor('#162B3B'))
        p.setPen(QPen(QColor(self.accent),1));p.setBrush(grad);p.drawEllipse(r)
        if not self.pixmap.isNull():
            p.save();path=QPainterPath();path.addEllipse(r);p.setClipPath(path);p.drawPixmap(r.toRect(),self.pixmap);p.restore()
        else:
            p.setPen(QColor('#EAF2FA'));font=p.font();font.setPixelSize(38);font.setBold(True);p.setFont(font);p.drawText(r,Qt.AlignCenter,self.letter)
        p.setPen(QPen(QColor(self.accent),3,Qt.SolidLine,Qt.RoundCap));p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(4,4,124,124),90*16,-int(self.ratio*360*16))
class Spectrum(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(42);self.levels=[0]*24;self.color='#6EF0CF';self.active=False
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick)
        self.targets=[0]*24
    def set_active(self,value):
        self.active=value
        self.timer.start() if value else self.timer.stop()
        if not value:self.levels=[0]*24;self.update()
    def accept(self,values):self.targets=values
    def tick(self):
        self.levels=[max(target,level*.76) for target,level in zip(self.targets,self.levels)]
        self.targets=[x*.72 for x in self.targets];self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        color=QColor(self.color);color.setAlpha(170);p.setBrush(color);step=self.width()/24
        for i,level in enumerate(self.levels):
            height=max(2,level*(self.height()-4));p.drawRoundedRect(QRectF(i*step+1,self.height()-height,step-3,height),2,2)
class DragBar(QFrame):
    def __init__(self,window):super().__init__();self.window=window
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and self.window.windowHandle():self.window.windowHandle().startSystemMove()
    def mouseDoubleClickEvent(self,e):self.window.expand('보관함')


class TrackDelegate(QStyledItemDelegate):
    def __init__(self,parent=None):
        super().__init__(parent);self.theme={'text':'#18212C','muted':'#566273','accent':'#E8780F','bg':'#D9DFE6','border':'#9CA8B7'}
        self.cover=QPixmap(str(Path(getattr(sys,'_MEIPASS',app_root()))/'assets'/'default-cover.png'))
    def paint(self,p,option,index):
        track=index.data(Qt.UserRole)
        if not track:return
        p.save();p.setRenderHint(QPainter.Antialiasing);r=option.rect;t=self.theme
        if option.state & QStyle.State_Selected:
            color=QColor(t['accent']);color.setAlpha(22);p.fillRect(r,color);p.fillRect(r.x(),r.y()+5,3,r.height()-10,QColor(t['accent']))
        image=QRectF(r.x()+10,r.y()+10,34,34);path=QPainterPath();path.addRoundedRect(image,6,6);p.save();p.setClipPath(path);p.drawPixmap(image.toRect(),self.cover);p.restore()
        x=r.x()+55;right=r.right()-12;titlefont=p.font();titlefont.setPixelSize(13);titlefont.setBold(False);p.setFont(titlefont);p.setPen(QColor(t['text']))
        title=p.fontMetrics().elidedText(track.title,Qt.ElideRight,max(10,right-x));p.drawText(QRectF(x,r.y()+7,right-x,21),Qt.AlignVCenter,title)
        meta=(track.artist or track.album or '내 음악');meta=('YOUTUBE' if track.kind=='youtube' else 'LOCAL')+'  ·  '+meta
        font=p.font();font.setPixelSize(11);p.setFont(font);p.setPen(QColor(t['muted']));meta=p.fontMetrics().elidedText(meta,Qt.ElideRight,max(10,right-x));p.drawText(QRectF(x,r.y()+29,right-x,16),Qt.AlignVCenter,meta)
        p.setPen(QColor(t['border']));p.drawLine(r.x()+55,r.bottom(),r.right()-10,r.bottom());p.restore()


class Deck(QWidget):
    def __init__(self,art,lcd,pad):
        super().__init__();self.setFixedHeight(136);self.art,self.lcd,self.pad=art,lcd,pad
        for child in (art,lcd,pad):child.setParent(self);child.show()
    def resizeEvent(self,event):
        self.art.setGeometry(0,2,132,132)
        self.pad.setGeometry(self.width()-132,2,132,132)
        self.lcd.setGeometry(148,6,max(140,self.width()-296),124)
        super().resizeEvent(event)

class LCDFrame(QFrame):
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);path=QPainterPath();path.addRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),10,10);p.setClipPath(path)
        gloss=QLinearGradient(0,0,0,self.height()*.45);gloss.setColorAt(0,QColor(255,255,255,24));gloss.setColorAt(1,QColor(255,255,255,0));p.fillRect(2,2,self.width()-4,int(self.height()*.45),gloss)
