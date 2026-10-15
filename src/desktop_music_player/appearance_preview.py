"""Small in-dialog theme sample using the player's actual spectrum painter."""
import math
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QFont
from PySide6.QtWidgets import QWidget
from .widgets import Spectrum
from .palettes import lcd_colors,theme_brush,brush
from .icons import icon
class AppearancePreview(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumWidth(300);self.setFixedHeight(144)
        self.theme=None;self.phase=0.;self.enabled=True;self.spectrum=Spectrum(self);self.spectrum.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.animate)
    def set_appearance(self,theme,style,enabled):
        self.theme=dict(theme);self.enabled=enabled;self.spectrum.set_colors(theme['spectrum'],theme.get('spectrum_end',''),theme.get('spectrum_direction','vertical'));self.spectrum.background=lcd_colors(theme)[1];self.spectrum.set_style(style);self.spectrum.setVisible(enabled);self.update();self.animate()
        if self.isVisible() and enabled:self.timer.start()
        else:self.timer.stop()
    def animate(self):
        self.phase+=.15
        self.spectrum.levels=[.12+.78*abs(math.sin(i*.32+self.phase)*math.cos(i*.13-self.phase*.6)) for i in range(24)];self.spectrum.update()
    def layout_sample(self):
        scale=float(self.property('uiScale') or 1);self.s=self.height()/144
        self.spectrum.setGeometry(round(96*self.s),round(86*self.s),max(1,self.width()-round(184*self.s)),round(40*self.s))
    def resizeEvent(self,event):self.layout_sample();super().resizeEvent(event)
    def showEvent(self,event):
        self.layout_sample()
        if self.enabled:self.timer.start()
        super().showEvent(event)
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def paintEvent(self,event):
        if not self.theme:return
        t=self.theme;s=self.height()/144;p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(t['border']),1));p.setBrush(theme_brush(t,'bg',QRectF(self.rect())));p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),12*s,12*s)
        p.setBrush(theme_brush(t,'panel',QRectF(14*s,40*s,58*s,58*s)));p.drawEllipse(QRectF(14*s,40*s,58*s,58*s));p.setPen(QColor(t['accent']));font=QFont(self.font());font.setPixelSize(round(27*s));p.setFont(font);p.drawText(QRectF(14*s,40*s,58*s,58*s),Qt.AlignCenter,'♪')
        a,b,text,muted,border=lcd_colors(t);rect=QRectF(84*s,10*s,self.width()-166*s,124*s);grad=brush(rect,a,b,t.get('panel_direction','vertical'));p.setBrush(grad);p.setPen(QPen(QColor(border),1));p.drawRoundedRect(rect,9*s,9*s)
        font.setPixelSize(round(13*s));font.setBold(True);p.setFont(font);p.setPen(QColor(text));p.drawText(rect.adjusted(12*s,10*s,-8*s,-80*s),Qt.AlignLeft|Qt.AlignVCenter,'오늘의 음악 · My Playlist')
        font.setPixelSize(round(11*s));font.setBold(False);p.setFont(font);p.setPen(QColor(muted));p.drawText(rect.adjusted(12*s,36*s,-8*s,-61*s),Qt.AlignLeft|Qt.AlignVCenter,'0:42 / 3:28')
        p.setPen(QPen(QColor(border),2*s));p.drawLine(rect.left()+12*s,rect.top()+65*s,rect.right()-12*s,rect.top()+65*s);p.setPen(QPen(theme_brush(t,'accent',rect),3*s));p.drawLine(rect.left()+12*s,rect.top()+65*s,rect.left()+rect.width()*.4,rect.top()+65*s)
        if not self.enabled:p.setPen(QColor(muted));p.drawText(rect.adjusted(12*s,80*s,-8*s,-6*s),Qt.AlignLeft|Qt.AlignVCenter,'비주얼라이저 꺼짐')
        button=QRectF(self.width()-66*s,49*s,48*s,48*s);p.setPen(Qt.NoPen);p.setBrush(theme_brush(t,'accent',button));p.drawEllipse(button);ink=t.get('on_accent') or ('#10202B' if QColor(t['accent']).lightnessF()>.55 else '#FFFFFF');icon('pause',ink).paint(p,button.adjusted(13*s,13*s,-13*s,-13*s).toRect())
