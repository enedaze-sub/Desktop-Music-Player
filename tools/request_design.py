import asyncio,json,sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
async def main():
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools'/'claude_design_mcp.py')],cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            if '--inspect' in sys.argv:
                listing=await session.list_tools();print([t.name for t in listing.tools]);return
            if '--typography' in sys.argv:
                result=await session.call_tool('typography_review',{'brief':'Apply to every theme including compact, drawer and settings. Provide a short Korean explanation too.'})
                if result.isError:raise RuntimeError(str(result.content))
                print('Claude MCP typography saved:',ROOT/'docs'/'claude_typography.json');return
            result=await session.call_tool('design_spec',{'brief':'The user rejected the first implementation as cheap-looking, inconsistent tiny text icons and misaligned positions. READ screenshots at artifacts/silver_blue-compact.png, artifacts/midnight-expanded.png and artifacts/visualizer-compact.png. Read assets/default-cover.png which image_gen generated for the default circular artwork. Redesign it into a polished, carefully aligned tactile retro MP3 player, NOT a flat generic dashboard. Give concrete coordinates, row/column spacing and control sizing for a 560-600px wide compact shell about 240px tall. Define a balanced record bezel, a beautiful blue LCD, a precise circular transport pad with SVG icon buttons, a unified 18-20px icon system, 32px hit targets, a clearly aligned source/navigation rail, and an elegant expanding list with 48-52px rows. User rejected tiny Unicode placeholders; eliminate them. Include exact theme gradients, border and highlight treatments in refinements. Bundled NanumSquareRound Regular/Bold typography with Windows fallback. Preserve theme IDs silver_blue, midnight, warm_cream, visualizer so implementation can apply them. Identify and fix layout defects in the actual screenshots. Prioritize a visibly premium complete revision.'})
            if result.isError:raise RuntimeError(str(result.content))
            print('Claude MCP design saved:',ROOT/'docs'/'claude_design.json')
asyncio.run(main())
