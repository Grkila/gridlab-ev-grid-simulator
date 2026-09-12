from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
root=Path(__file__).resolve().parents[1]
folder=root/'artifacts/handoff/screenshots';out=folder/'contact-sheets';out.mkdir(exist_ok=True)
for group,files in [('application',sorted(p for p in folder.glob('*.png') if not p.name.startswith(('slide-','presentation-'))))]:
    for start in range(0,len(files),12):
        sheet=Image.new('RGB',(1600,900),'#e5ebe7');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(files[start:start+12]):
            with Image.open(p) as im: thumb=ImageOps.contain(im.convert('RGB'),(390,265))
            x=(i%4)*400;y=(i//4)*300;sheet.paste(thumb,(x,y));draw.text((x+5,y+271),p.stem[:51],fill='black')
        sheet.save(out/f'{group}-{start//12+1:02}.jpg',quality=90)
print('Contact sheets:',len(list(out.glob('*.jpg'))))
def guide(name):
    if name.startswith('presentation'): return 'presentation'
    if name.startswith(('experiment','charging','invalid','empty-experiment')): return 'experiments'
    if 'results' in name and not name.startswith('benchmark'): return 'results'
    if 'benchmark' in name: return 'benchmarks'
    if 'strateg' in name: return 'strategies'
    if name == 'network': return 'network'
    if name == 'chat': return 'chat-and-mcp'
    if any(word in name for word in ('training','ppo','rl')): return 'training'
    return 'navigation'

lines=['# Screenshot coverage','','These captures show the actual Windows application. Runtime data remains local.','The viewport is 1600 by 1000 pixels. Long forms use full-page captures.','Each feature links to its procedure in the [user guide](USER_GUIDE.md).','','## Application','','| Feature or state | Instructions | Screenshot |','| --- | --- | --- |']
for p in sorted(folder.glob('*.png')):
    if not p.name.startswith(('slide-','presentation-')):lines.append(f'| {p.stem.replace("-"," ")} | [Procedure](USER_GUIDE.md#{guide(p.stem)}) | [{p.name}](../artifacts/handoff/screenshots/{p.name}) |')
lines+=['','## Contact sheets','']
for p in sorted(out.glob('application-*.jpg')):lines.append(f'![{p.stem}](../artifacts/handoff/screenshots/contact-sheets/{p.name})')
root.joinpath('docs/SCREENSHOTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
