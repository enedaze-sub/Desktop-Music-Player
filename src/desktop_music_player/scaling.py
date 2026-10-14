"""Per-window UI scaling, independent of Windows display DPI and audio state."""
import re
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget,QLayout,QAbstractButton
MAX=16777215
def pixels(value,scale):return round(value*scale)
def stylesheet(text,scale):
    return re.sub(r'(-?\d+(?:\.\d+)?)px',lambda m:f'{float(m[1])*scale:g}px',text)
def scale_tree(root,scale):
    # Capture authored constraints once; repeated changes always use this baseline.
    for widget in root.findChildren(QWidget):
        base=widget.property('_uiMetrics')
        if base is None:
            base=(widget.minimumSize(),widget.maximumSize(),widget.iconSize() if isinstance(widget,QAbstractButton) else None)
            widget.setProperty('_uiMetrics',base)
        lo,hi,ico=base
        widget.setProperty('uiScale',scale)
        widget.setMinimumSize(pixels(lo.width(),scale),pixels(lo.height(),scale))
        widget.setMaximumSize(pixels(hi.width(),scale) if hi.width()<MAX else MAX,pixels(hi.height(),scale) if hi.height()<MAX else MAX)
        if ico is not None:widget.setIconSize(QSize(max(1,pixels(ico.width(),scale)),max(1,pixels(ico.height(),scale))))
    for layout in root.findChildren(QLayout):
        base=layout.property('_uiMetrics')
        if base is None:
            m=layout.contentsMargins();base=(m.left(),m.top(),m.right(),m.bottom(),layout.spacing());layout.setProperty('_uiMetrics',base)
        layout.setContentsMargins(*[pixels(v,scale) for v in base[:4]])
        if base[4]>=0:layout.setSpacing(pixels(base[4],scale))
        layout.invalidate()
    root.updateGeometry()
