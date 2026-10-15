"""Theme resolution shared by the player and appearance preview."""
import re
from PySide6.QtGui import QColor
COLOR_LABELS={'bg':'배경','panel':'패널','text':'본문','muted':'보조 글자','accent':'강조','border':'테두리'}
STYLES={'bars':'클래식 막대','led':'LED 계단','mirror':'미러 막대','line':'라인 스펙트럼'}
def palette(value,fallback):
    value=value if isinstance(value,dict) else {}
    return {key:value[key].upper() if isinstance(value.get(key),str) and re.fullmatch(r'#[0-9a-fA-F]{6}',value[key]) else fallback[key] for key in COLOR_LABELS}
def resolve_theme(config,themes):
    theme=dict(next((t for t in themes if t['id']==config['theme']),themes[0]))
    if theme['id']=='custom':theme.update(palette(config.get('custom_theme'),theme))
    elif config.get('accent') and QColor(config['accent']).isValid():theme['accent']=config['accent']
    return theme
LCD_COLORS={'silver_blue':('#2B66C4','#0F3373','#EEF5FF','#A9C3EA','#8A97AA'),'midnight':('#10284F','#07132A','#DCE9FF','#8FA6CC','#243E62'),'warm_cream':('#3C6E86','#1C3B4B','#F6EEDF','#BFD3D9','#819A9E'),'visualizer':('#06191D','#020A0C','#E6FFF7','#86A8A0','#224B45')}
def lcd_colors(theme):
    return LCD_COLORS.get(theme['id'],(QColor(theme['panel']).lighter(108).name(),theme['panel'],theme['text'],theme['muted'],theme['border']))
