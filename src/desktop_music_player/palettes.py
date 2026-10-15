"""Theme resolution and brushes shared by the player and appearance preview."""
import re
from PySide6.QtGui import QColor,QLinearGradient
COLOR_LABELS={'bg':'배경','panel':'패널','text':'본문','muted':'보조 글자','accent':'강조','border':'테두리','spectrum':'파형'}
GRADIENT_TARGETS={'bg':'배경','panel':'패널','accent':'강조','spectrum':'파형'}
DIRECTIONS={'horizontal':'가로','vertical':'세로','diagonal':'대각선'}
STYLES={'bars':'클래식 막대','led':'LED 계단','mirror':'미러 막대','line':'라인 스펙트럼','glow':'네온 파형'}
def valid_color(value):return isinstance(value,str) and bool(re.fullmatch(r'#[0-9a-fA-F]{6}',value))
def palette(value,fallback):
    value=value if isinstance(value,dict) else {}
    result={key:value[key].upper() if valid_color(value.get(key)) else fallback.get(key,fallback['accent']) for key in COLOR_LABELS}
    if not valid_color(value.get('spectrum')):result['spectrum']=result['accent']
    return result

def gradient_settings(value,colors):
    value=value if isinstance(value,dict) else {};result={}
    for key in GRADIENT_TARGETS:
        item=value.get(key);item=item if isinstance(item,dict) else {}
        result[key]={'enabled':item.get('enabled') is True,'end':item['end'].upper() if valid_color(item.get('end')) else colors[key],
                     'direction':item.get('direction') if item.get('direction') in DIRECTIONS else 'vertical'}
    return result

def resolve_theme(config,themes):
    theme=dict(next((t for t in themes if t['id']==config['theme']),themes[0]))
    if theme['id']=='custom':theme.update(palette(config.get('custom_theme'),theme))
    elif valid_color(config.get('accent')):theme['accent']=config['accent'];theme['spectrum']=config['accent']
    theme.setdefault('spectrum',theme['accent'])
    gradients=gradient_settings(config.get('custom_gradients') if theme['id']=='custom' else {},theme)
    for key,item in gradients.items():theme[key+'_end']=item['end'] if item['enabled'] else '';theme[key+'_direction']=item['direction']
    return theme
LCD_COLORS={'silver_blue':('#2B66C4','#0F3373','#EEF5FF','#A9C3EA','#8A97AA'),'midnight':('#10284F','#07132A','#DCE9FF','#8FA6CC','#243E62'),'warm_cream':('#3C6E86','#1C3B4B','#F6EEDF','#BFD3D9','#819A9E'),'visualizer':('#06191D','#020A0C','#E6FFF7','#86A8A0','#224B45')}
def lcd_colors(theme):
    return LCD_COLORS.get(theme['id'],(theme['panel'],theme.get('panel_end') or theme['panel'],theme['text'],theme['muted'],theme['border']))
def gradient_points(direction):return (1,0) if direction=='horizontal' else (1,1) if direction=='diagonal' else (0,1)
def brush(rect,start,end='',direction='vertical'):
    if not end:return QColor(start)
    x,y=gradient_points(direction);grad=QLinearGradient(rect.left(),rect.top(),rect.left()+rect.width()*x,rect.top()+rect.height()*y);grad.setColorAt(0,QColor(start));grad.setColorAt(1,QColor(end));return grad

def theme_brush(theme,key,rect):return brush(rect,theme[key],theme.get(key+'_end',''),theme.get(key+'_direction','vertical'))
def qss_fill(theme,key):
    end=theme.get(key+'_end')
    if not end:return theme[key]
    x,y=gradient_points(theme.get(key+'_direction','vertical'));return f'qlineargradient(x1:0,y1:0,x2:{x},y2:{y},stop:0 {theme[key]},stop:1 {end})'
def lcd_fill(theme):
    if theme['id']=='custom':return qss_fill(theme,'panel')
    a,b,*_=lcd_colors(theme);return f'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {a},stop:1 {b})'
