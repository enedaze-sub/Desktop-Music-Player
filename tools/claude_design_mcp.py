"""Project-local MCP bridge; sends design-only prompts to authenticated Claude Code."""
import json, os, subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
ROOT=Path(__file__).resolve().parents[1]
server=FastMCP('Claude Opus 5.5 Design')
MODEL='claude-opus-5-5'
@server.tool()
def design_spec(brief: str) -> str:
    """Ask Opus 5.5 for a music-player theme and typography specification; no code edits."""
    prompt=("You are the visual designer for a Windows native PySide6 music player. Coding is handled by GPT-6.1 Sol. "
            "Return ONLY a JSON object with keys: name, font_family, korean_font, rationale, themes (array of objects with id,name,bg,panel,text,muted,accent,border), layout (object describing collapsed and expanded dimensions), refinements (array). "
            "Preserve a compact nostalgic MP3 player, circular artwork and a tactile central play control. Expand downward for library, queue, playlists or video. "
            "Create 4 polished themes including silver-blue retro, midnight, warm cream and a visualizer theme. Focus on typography, contrast, Korean readability, density and spacing. "
            "Use bundled NanumSquareRound with Windows fallbacks; no paid font dependencies. Do not access credentials. "
            "Read the reference image at artifacts/reference.png. " + brief)
    env=os.environ.copy()
    for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN'):
        env.pop(key,None)
    env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC']='1'
    command=[str(ROOT/'tools'/'claude.exe'),'-p','--model',MODEL,'--output-format','json','--no-session-persistence',
             '--tools','Read','--allowedTools','Read','--add-dir',str(ROOT),
             '--strict-mcp-config','--mcp-config','{"mcpServers":{}}']
    result=subprocess.run(command,input=prompt,text=True,encoding='utf-8',capture_output=True,cwd=ROOT,env=env,timeout=600)
    if result.returncode:
        raise RuntimeError('Claude design request failed: '+result.stderr[-1000:])
    response=json.loads(result.stdout)
    if response.get('is_error'):
        raise RuntimeError(str(response.get('result','Claude request rejected')))
    # Keep the model result, but never authentication headers or tokens.
    output=response.get('result','')
    output=output.strip().removeprefix('```json').removesuffix('```').strip()
    design=json.loads(output)
    if not isinstance(design.get('themes'),list) or len(design['themes'])<3:
        raise ValueError('Claude returned an incomplete design')
    (ROOT/'docs'/'claude_design.json').write_text(json.dumps({'requested_model':MODEL,'model_usage':response.get('modelUsage',{}),'design':design},ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps(design,ensure_ascii=False)
@server.tool()
def typography_review(brief: str) -> str:
    """Review soft readable Korean typography with Opus 5.5; no implementation edits."""
    prompt=("You are the typography designer of this compact PySide6 music player. User says fonts feel too stiff; replace with soft, readable typography. "
            "We intend to bundle official NAVER NanumSquareRound Regular and Bold under OFL1.1, with Malgun Gothic fallback for unsupported glyphs. "
            "Read artifacts/silver_blue-compact.png and artifacts/silver_blue-expanded.png. Read src/desktop_music_player/widgets.py and app.py if useful. "
            "Return ONLY JSON with family, fallback_families, rationale, sizes_px (body,brand,track_title,list_title,list_meta,status,time,nav,badge), weights, spacing, checks. "
            "Existing compact width600 minimum560, art132 LCD124high listrows54. Preserve fit. Avoid Light weights, avoid fake semibold: only Regular400/Bold700 available. "
            "Recommend crisp sizes for small Korean text; softer rounded rather than handwritten. No credentials. "+brief)
    env=os.environ.copy()
    for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN'):env.pop(key,None)
    env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC']='1'
    command=[str(ROOT/'tools'/'claude.exe'),'-p','--model',MODEL,'--output-format','json','--no-session-persistence',
             '--tools','Read','--allowedTools','Read','--add-dir',str(ROOT),'--strict-mcp-config','--mcp-config','{"mcpServers":{}}']
    result=subprocess.run(command,input=prompt,text=True,encoding='utf-8',capture_output=True,cwd=ROOT,env=env,timeout=600)
    if result.returncode:raise RuntimeError('Claude typography review failed: '+result.stderr[-500:])
    response=json.loads(result.stdout)
    if response.get('is_error'):raise RuntimeError(str(response.get('result')))
    output=response.get('result','').strip().removeprefix('```json').removesuffix('```').strip()
    design=json.loads(output)
    (ROOT/'docs'/'claude_typography.json').write_text(json.dumps({'requested_model':MODEL,'model_usage':response.get('modelUsage',{}),'typography':design},ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps(design,ensure_ascii=False)

if __name__=='__main__':server.run(transport='stdio')
