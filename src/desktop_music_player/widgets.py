"""Painter widgets from the Opus 5.5 theme specification."""
import math,sys,time
from pathlib import Path
from .core import app_root
from .icons import icon
from PySide6.QtCore import Qt,QRectF,QRect,QTimer,Slot,QObject,QEvent
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QPixmap,QLinearGradient,QConicalGradient,QImage,QImageReader,QTextLayout,QTextOption
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QHBoxLayout,QPushButton,QStyledItemDelegate,QStyle,QSizePolicy
class ButtonFocusFilter(QObject):
    """Keep keyboard focus visible without a lingering mouse-click outline."""
    def eventFilter(self,widget,event):
        if isinstance(widget,QPushButton):
            visible=widget.property('keyboardFocus') is True
            target=visible
            if event.type()==QEvent.MouseButtonPress:target=False
            elif event.type()==QEvent.FocusIn:
                if event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason):target=True
                elif event.reason()==Qt.MouseFocusReason:target=False
            if target!=visible:
                widget.setProperty('keyboardFocus',target);widget.style().unpolish(widget);widget.style().polish(widget);widget.update()
        return False

def install_button_focus_filter(app):
    if not hasattr(app,'_button_focus_filter'):
        app._button_focus_filter=ButtonFocusFilter(app);app.installEventFilter(app._button_focus_filter)

class Surface(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.theme={};self.image=QPixmap();self.original_size=None;self.image_path=None;self.background={};self.cached_background=QPixmap();self.expanded_view=False;self.compact_reference=252
    def set_theme(self,theme):
        if self.theme==theme:return
        self.theme=dict(theme);self.rebuild_background();self.update()
    def set_image(self,path):
        if path==self.image_path:return
        self.image_path=path;self.image=QPixmap();self.original_size=None
        if path:
            reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size();self.original_size=size
            if size.isValid() and max(size.width(),size.height())>4096:
                scaled=size.scaled(4096,4096,Qt.KeepAspectRatio);reader.setScaledSize(scaled)
            image=reader.read()
            if not image.isNull():self.image=QPixmap.fromImage(image)
        self.rebuild_background();self.update()
    def configure_background(self,values):
        from copy import deepcopy
        background=deepcopy({k:v for k,v in values.items() if k.startswith('background_')})
        path=values.get('background','')
        if self.background==background and path==self.image_path:return
        self.background=background
        if path!=self.image_path:self.set_image(path)
        else:self.rebuild_background();self.update()
    def set_background_view(self,expanded,compact_height):
        state=(bool(expanded),compact_height)
        if state==(self.expanded_view,self.compact_reference):return
        self.expanded_view,self.compact_reference=state;self.rebuild_background();self.update()
    def resizeEvent(self,event):
        self.rebuild_background()
        if event:super().resizeEvent(event)
    def rebuild_background(self):
        if self.width()<=0 or self.height()<=0:return
        values=dict(self.background);expanded_mode=values.get('background_expanded_mode','follow')
        if self.expanded_view and expanded_mode=='custom':values.update(values.get('background_expanded') or {})
        # Closing flips expanded_view before the height animation finishes.
        # Header framing must keep the compact reference in both directions.
        rh=self.compact_reference if expanded_mode=='header' else self.height()
        # Changes to an inactive expanded profile do not repaint the real compact window.
        transform=tuple(values.get(key,default) for key,default in [('background_fit','cover'),('background_zoom',1),('background_x',0),('background_y',0),('background_opacity',.3),('background_tint',0)]) if not self.image.isNull() else ()
        key=(self.width(),self.height(),self.devicePixelRatioF(),self.theme.get('id'),self.theme.get('bg'),self.theme.get('border'),self.image.cacheKey(),rh if transform else None,transform)
        if getattr(self,'_background_key',None)==key and not self.cached_background.isNull():return
        self._background_key=key
        dpr=self.devicePixelRatioF();pix=QPixmap(round(self.width()*dpr),round(self.height()*dpr));pix.setDevicePixelRatio(dpr);pix.fill(Qt.transparent)
        p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5);path=QPainterPath();path.addRoundedRect(rect,16,16);p.setClipPath(path)
        bg=QColor(self.theme.get('bg','#D9DFE6'));grad=QLinearGradient(0,0,0,self.height());grad.setColorAt(0,bg.lighter(107));grad.setColorAt(1,bg.darker(104));p.fillRect(self.rect(),grad)
        if self.theme.get('id')=='silver_blue':
            p.setPen(QColor(255,255,255,15))
            for y in range(0,min(200,self.height()),3):p.drawLine(0,y,self.width(),y)
        if not self.image.isNull():
            rw=self.width()
            mode=values.get('background_fit','cover');iw,ih=self.image.width(),self.image.height()
            scale=min(rw/iw,rh/ih) if mode=='contain' else max(self.original_size.width(),self.original_size.height())/max(iw,ih) if mode=='original' and self.original_size and self.original_size.isValid() else max(rw/iw,rh/ih)
            scale*=max(.25,min(4,float(values.get('background_zoom',1))))
            w,h=iw*scale,ih*scale;x=(rw-w)/2+float(values.get('background_x',0))*rw;y=(rh-h)/2+float(values.get('background_y',0))*rh
            p.setOpacity(max(0,min(1,float(values.get('background_opacity',.3)))));p.setRenderHint(QPainter.SmoothPixmapTransform);p.drawPixmap(QRectF(x,y,w,h),self.image,QRectF(self.image.rect()))
            p.setOpacity(max(0,min(1,float(values.get('background_tint',0)))));p.fillRect(self.rect(),bg);p.setOpacity(1)
        p.setPen(QPen(QColor(self.theme.get('border','#9CA8B7')),1));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect,16,16);p.end();self.cached_background=pix
    def paintEvent(self,event):
        if self.cached_background.isNull() or self.cached_background.devicePixelRatioF()!=self.devicePixelRatioF():self.rebuild_background()
        p=QPainter(self);p.drawPixmap(0,0,self.cached_background)

class Artwork(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(132,132);self.accent='#E8780F';self.text='#18212C';self.ratio=0;self.letter='♪';self.pixmap=QPixmap(str(Path(getattr(sys,'_MEIPASS',app_root()))/'assets'/'default-cover.png'))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.scale(self.width()/132,self.height()/132);r=QRectF(10,10,112,112)
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
        super().__init__(parent);self.setFixedHeight(40);self.levels=[0.]*24;self.color='#6EF0CF';self.background='#07132A';self.active=False;self.style_name='bars'
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick);self.targets=[0.]*24
    def set_style(self,value):
        from .palettes import STYLES
        value=value if value in STYLES else 'bars'
        if self.style_name!=value:self.style_name=value;self.update()
    def set_active(self,value):
        if self.active==value:return
        self.active=value
        self.timer.start() if value else self.timer.stop()
        if not value:self.levels=[0.]*24;self.targets=[0.]*24;self.update()
    def accept(self,values):self.targets=[max(0.,min(1.,float(v))) for v in values[:24]]+[0.]*max(0,24-len(values))
    def tick(self):
        self.levels=[max(target,level*.79) for target,level in zip(self.targets,self.levels)]
        self.targets=[x*.72 for x in self.targets];self.update()
    def plot_rect(self):
        scale=float(self.property('uiScale') or 1);width=min(self.width(),620*scale)
        return QRectF((self.width()-width)/2,2,width,max(1,self.height()-4))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);r=self.plot_rect();step=r.width()/24
        color=QColor(self.color);bg=QColor(self.background)
        # Retain the chosen color in settings; improve only the drawn ink if needed.
        if abs(color.lightnessF()-bg.lightnessF())<.22:color=color.lighter(170) if bg.lightnessF()<.5 else color.darker(170)
        grad=QLinearGradient(0,r.top(),0,r.bottom());grad.setColorAt(0,color.lighter(145));grad.setColorAt(1,color);p.setBrush(grad)
        gap=max(1,min(4,step*.22));base=max(1,r.height()*.035)
        if self.style_name=='line':
            points=[(r.left()+step*(i+.5),r.bottom()-max(base,level*r.height())) for i,level in enumerate(self.levels)]
            path=QPainterPath();path.moveTo(*points[0])
            for x,y in points[1:]:path.lineTo(x,y)
            fill=QPainterPath(path);fill.lineTo(points[-1][0],r.bottom());fill.lineTo(points[0][0],r.bottom());fill.closeSubpath()
            shade=QColor(color);shade.setAlpha(75);p.fillPath(fill,shade);p.setBrush(Qt.NoBrush);p.setPen(QPen(color,max(1.5,r.height()*.065),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawPath(path);return
        for i,level in enumerate(self.levels):
            height=max(base,level*r.height());x=r.left()+i*step+gap/2;width=max(1,step-gap)
            if self.style_name=='mirror':p.drawRoundedRect(QRectF(x,r.center().y()-height/2,width,height),1.5,1.5)
            elif self.style_name=='led':
                cell=max(2,r.height()/8);count=max(1,round(height/cell))
                for n in range(count):p.drawRect(QRectF(x,r.bottom()-(n+1)*cell,width,max(1,cell-1)))
            else:p.drawRoundedRect(QRectF(x,r.bottom()-height,width,height),1.5,1.5)
class DragBar(QFrame):
    def __init__(self,window):super().__init__();self.window=window
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and self.window.windowHandle():self.window.windowHandle().startSystemMove()
    def mouseDoubleClickEvent(self,e):self.window.expand('보관함')


class TrackDelegate(QStyledItemDelegate):
    def __init__(self,parent=None,covers=None):
        super().__init__(parent);self.covers=covers;self.theme={'text':'#18212C','muted':'#566273','accent':'#E8780F','bg':'#D9DFE6','border':'#9CA8B7'}
        self.cover=QPixmap(str(Path(getattr(sys,'_MEIPASS',app_root()))/'assets'/'default-cover.png'))
    def sizeHint(self,option,index):
        from PySide6.QtCore import QSize
        scale=float(self.parent().property('uiScale') or 1);return QSize(round(100*scale),round(54*scale))
    def paint(self,p,option,index):
        track=index.data(Qt.UserRole)
        if not track:return
        p.save();p.setRenderHint(QPainter.Antialiasing);scale=float(self.parent().property('uiScale') or 1);p.translate(option.rect.topLeft());p.scale(scale,scale);r=QRect(0,0,round(option.rect.width()/scale),round(option.rect.height()/scale));t=self.theme
        if option.state & QStyle.State_Selected:
            color=QColor(t['accent']);color.setAlpha(22);p.fillRect(r,color);p.fillRect(r.x(),r.y()+5,3,r.height()-10,QColor(t['accent']))
        image=QRectF(r.x()+10,r.y()+10,34,34);path=QPainterPath();path.addRoundedRect(image,6,6);p.save();p.setClipPath(path);p.drawPixmap(image.toRect(),self.covers.get(track) if self.covers else self.cover);p.restore()
        x=r.x()+55;right=r.right()-12;titlefont=p.font();titlefont.setPixelSize(13);titlefont.setBold(False);p.setFont(titlefont);p.setPen(QColor(t['text']))
        status=index.data(Qt.UserRole+1);title_text=(status+'  ·  ' if status else '')+track.title
        title=p.fontMetrics().elidedText(title_text,Qt.ElideRight,max(10,right-x));p.drawText(QRectF(x,r.y()+7,right-x,21),Qt.AlignVCenter,title)
        meta=(track.artist or track.album or '내 음악');meta=('YOUTUBE' if track.kind=='youtube' else 'LOCAL')+'  ·  '+meta
        font=p.font();font.setPixelSize(11);p.setFont(font);p.setPen(QColor(t['muted']));meta=p.fontMetrics().elidedText(meta,Qt.ElideRight,max(10,right-x));p.drawText(QRectF(x,r.y()+29,right-x,16),Qt.AlignVCenter,meta)
        p.setPen(QColor(t['border']));p.drawLine(r.x()+55,r.bottom(),r.right()-10,r.bottom());p.restore()


class Deck(QWidget):
    def __init__(self,art,lcd,pad):
        super().__init__();self.setFixedHeight(136);self.art,self.lcd,self.pad=art,lcd,pad
        for child in (art,lcd,pad):child.setParent(self);child.show()
    def layout_children(self):
        scale=float(self.property('uiScale') or 1);px=lambda v:round(v*scale)
        self.art.setGeometry(0,px(2),px(132),px(132))
        self.pad.setGeometry(self.width()-px(132),px(2),px(132),px(132))
        self.lcd.setGeometry(px(148),px(2),max(px(140),self.width()-px(296)),px(132))
    def resizeEvent(self,event):self.layout_children();super().resizeEvent(event)

class LCDFrame(QFrame):
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);path=QPainterPath();path.addRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),10,10);p.setClipPath(path)
        gloss=QLinearGradient(0,0,0,self.height()*.45);gloss.setColorAt(0,QColor(255,255,255,24));gloss.setColorAt(1,QColor(255,255,255,0));p.fillRect(2,2,self.width()-4,int(self.height()*.45),gloss)


class ElidedLabel(QLabel):
    """A long title/status never forces its parent to grow or clip controls."""
    def __init__(self,text='',parent=None,lines=1):
        super().__init__(text,parent);self.lines=lines
        self.setMinimumWidth(0);self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
    def paintEvent(self,event):
        p=QPainter(self);p.setPen(self.palette().windowText().color());p.setFont(self.font())
        text=self.text().replace('\n',' ');fm=p.fontMetrics();spacing=fm.lineSpacing()
        if self.lines==1:
            p.drawText(self.rect(),Qt.AlignLeft|Qt.AlignVCenter,fm.elidedText(text,Qt.ElideRight,self.width()));return
        layout=QTextLayout(text,self.font());option=QTextOption();option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere);layout.setTextOption(option)
        layout.beginLayout();lines=[]
        for _ in range(self.lines):
            line=layout.createLine()
            if not line.isValid():break
            line.setLineWidth(self.width());lines.append(line)
        layout.endLayout();y=(self.height()-spacing*len(lines))//2
        for i,line in enumerate(lines):
            start=line.textStart()
            value=text[start:] if i==self.lines-1 else text[start:start+line.textLength()].rstrip()
            p.drawText(QRect(0,y+i*spacing,self.width(),spacing),Qt.AlignLeft|Qt.AlignVCenter,fm.elidedText(value,Qt.ElideRight,self.width()))


class VideoCanvas(QWidget):
    """Raster video composes correctly in a translucent, frameless window."""
    def __init__(self,parent=None):
        super().__init__(parent)
        from PySide6.QtMultimedia import QVideoSink
        self.sink=QVideoSink(self);self.sink.videoFrameChanged.connect(self.accept_frame)
        self.image=QImage();self.message='영상이 여기에 표시됩니다.';self.last_frame=0;self.updates_paused=False
        self.setMinimumSize(0,120);self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
    def videoSink(self):return self.sink
    def set_message(self,message,clear=True):
        self.message=message
        if clear:self.image=QImage()
        self.update()
    @Slot(QVideoFrame)
    def accept_frame(self,frame):
        if not frame.isValid() or not self.isVisible() or self.updates_paused:return
        now=time.monotonic()
        if now-self.last_frame<1/30:return
        self.last_frame=now;self.image=frame.toImage();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),8,8);p.setClipPath(path);p.fillRect(self.rect(),QColor('#080E17'))
        if self.image.isNull():
            p.setPen(QColor('#93A4BA'));p.drawText(self.rect().adjusted(12,8,-12,-8),Qt.AlignCenter|Qt.TextWordWrap,self.message);return
        size=self.image.size();size.scale(self.size(),Qt.KeepAspectRatio)
        target=QRect((self.width()-size.width())//2,(self.height()-size.height())//2,size.width(),size.height())
        p.setRenderHint(QPainter.SmoothPixmapTransform);p.drawImage(target,self.image)


class ResizeHandle(QWidget):
    def __init__(self,window,edges):
        super().__init__(window);self.window=window;self.edges=edges;self.drag=None
        self.setObjectName('resizeHandle');self.setMouseTracking(True)
    def paintEvent(self,event):
        # Windows layered windows pass clicks through alpha-zero pixels.
        # A one-step alpha hit surface keeps rounded corners draggable.
        p=QPainter(self);p.fillRect(self.rect(),QColor(0,0,0,1))
    def active_edges(self):
        return self.edges
    def enterEvent(self,event):
        edges=self.active_edges();horizontal=bool(edges&(Qt.LeftEdge|Qt.RightEdge));vertical=bool(edges&(Qt.TopEdge|Qt.BottomEdge))
        cursor=Qt.SizeFDiagCursor if edges in (Qt.LeftEdge|Qt.TopEdge,Qt.RightEdge|Qt.BottomEdge) else Qt.SizeBDiagCursor
        self.setCursor(cursor if horizontal and vertical else Qt.SizeHorCursor if horizontal else Qt.SizeVerCursor if vertical else Qt.ArrowCursor)
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton or not self.active_edges():return
        self.window.finish_transition();handle=self.window.windowHandle()
        if handle and handle.startSystemResize(self.active_edges()):return
        self.drag=(event.globalPosition().toPoint(),self.window.geometry());event.accept()
    def mouseMoveEvent(self,event):
        if self.drag is None:return
        start,original=self.drag;delta=event.globalPosition().toPoint()-start;rect=QRect(original);edges=self.active_edges()
        if edges&Qt.LeftEdge:rect.setLeft(min(rect.right()-self.window.minimumWidth()+1,original.left()+delta.x()))
        if edges&Qt.RightEdge:rect.setRight(max(rect.left()+self.window.minimumWidth()-1,original.right()+delta.x()))
        if edges&Qt.TopEdge:rect.setTop(min(rect.bottom()-self.window.minimumHeight()+1,original.top()+delta.y()))
        if edges&Qt.BottomEdge:rect.setBottom(max(rect.top()+self.window.minimumHeight()-1,original.bottom()+delta.y()))
        self.window.setGeometry(rect)
    def mouseReleaseEvent(self,event):self.drag=None
