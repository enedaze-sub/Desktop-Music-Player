"""Portable named theme profiles. Only color/visualizer fields are exchanged."""
from copy import deepcopy
import json,sys
from pathlib import Path
from functools import lru_cache
from .palettes import COLOR_LABELS,GRADIENT_TARGETS,DIRECTIONS,STYLES,valid_color,gradient_settings
from .core import app_root
FORMAT='desktop-music-player-themes'
VERSION=1

def theme_name(value):
    if not isinstance(value,str):raise ValueError('테마 이름을 입력해 주세요.')
    value=value.strip()
    if not 1<=len(value)<=60 or any(ord(char)<32 for char in value):raise ValueError('테마 이름은 줄바꿈 없이 1~60자로 입력해 주세요.')
    try:value.encode('utf-8')
    except UnicodeError:raise ValueError('테마 이름의 문자를 확인해 주세요.') from None
    return value

def validate_profile(value):
    if not isinstance(value,dict):raise ValueError('테마 형식을 확인해 주세요.')
    name=theme_name(value.get('name'));colors=value.get('colors')
    if not isinstance(colors,dict):raise ValueError('테마의 색상 정보를 찾지 못했습니다.')
    colors=dict(colors)
    if 'spectrum' not in colors:colors['spectrum']=colors.get('accent')
    for key,label in COLOR_LABELS.items():
        if not valid_color(colors.get(key)):raise ValueError(label+' 색상은 #RRGGBB 형식이어야 합니다.')
    colors={key:colors[key].upper() for key in COLOR_LABELS}
    gradients=value.get('gradients',{})
    if not isinstance(gradients,dict):raise ValueError('그라디언트 형식을 확인해 주세요.')
    for key in GRADIENT_TARGETS:
        if key not in gradients:continue
        item=gradients[key]
        if not isinstance(item,dict) or type(item.get('enabled',False))!=bool or not valid_color(item.get('end',colors[key])) or not isinstance(item.get('direction','vertical'),str) or item.get('direction','vertical') not in DIRECTIONS:raise ValueError('그라디언트 색상과 방향을 확인해 주세요.')
    visual=value.get('visualizer',{'enabled':True,'style':'bars'})
    if not isinstance(visual,dict) or type(visual.get('enabled'))!=bool or not isinstance(visual.get('style'),str) or visual.get('style') not in STYLES:raise ValueError('비주얼라이저 설정을 확인해 주세요.')
    return {'name':name,'colors':colors,'gradients':gradient_settings(gradients,colors),'visualizer':{'enabled':visual['enabled'],'style':visual['style']}}

def unique_name(name,existing):
    name=theme_name(name);taken={n.casefold() for n in existing}
    if name.casefold() not in taken:return name
    index=2
    while True:
        suffix=f' ({index})';candidate=name[:60-len(suffix)]+suffix
        if candidate.casefold() not in taken:return candidate
        index+=1

def encode_profiles(profiles):
    return json.dumps({'format':FORMAT,'version':VERSION,'themes':[validate_profile(p) for p in profiles]},ensure_ascii=False,indent=2)+'\n'

def decode_profiles(text):
    try:data=json.loads(text)
    except (ValueError,TypeError,RecursionError):raise ValueError('올바른 테마 JSON 파일을 선택해 주세요.') from None
    if not isinstance(data,dict) or data.get('format')!=FORMAT or type(data.get('version'))!=int or data['version']!=VERSION:raise ValueError('지원하는 테마 파일 형식이 아닙니다.')
    if not isinstance(data.get('themes'),list) or not data['themes']:raise ValueError('불러올 테마가 없습니다.')
    return [validate_profile(item) for item in data['themes']]

def read_profiles(path):
    path=Path(path)
    if path.stat().st_size>4*1024*1024:raise ValueError('테마 파일이 너무 큽니다. 4MB 이하 파일을 선택해 주세요.')
    return decode_profiles(path.read_text(encoding='utf-8-sig'))

def write_profiles(path,profiles):Path(path).write_text(encode_profiles(profiles),encoding='utf-8')

@lru_cache(maxsize=1)
def bundled_profiles():
    root=Path(getattr(sys,'_MEIPASS',app_root()))
    return read_profiles(root/'assets/theme-presets.json')

def library_profiles(value):
    if value is None:return {p['name']:deepcopy(p) for p in bundled_profiles()}
    result={}
    if isinstance(value,dict):
        for item in value.values():
            try:
                profile=validate_profile(item);result[profile['name']]=profile
            except ValueError:continue
    return result
