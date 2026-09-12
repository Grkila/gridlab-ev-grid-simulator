from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.novi_sad.playground.schema import Experiment
from mvgrid.novi_sad.playground.benchmark import BenchmarkConfig,BenchmarkRunConfig

def type_label(p):
    if '$ref' in p:return p['$ref'].split('/')[-1]
    if 'anyOf' in p:return ' or '.join(type_label(x) for x in p['anyOf'])
    if 'enum' in p:return ' / '.join(str(x) for x in p['enum'])
    if p.get('type')=='array':return 'list of '+type_label(p.get('items',{}))
    if p.get('type')=='object' and isinstance(p.get('additionalProperties'),dict):return 'map to '+type_label(p['additionalProperties'])
    return p.get('type','object')
lines=['# Configuration reference','','This reference lists accepted experiment and benchmark fields from the current Python schema.','Use the [user guide](USER_GUIDE.md) for procedures and interpretation.','Saved definitions and GUI presets can override schema defaults.','A dash means the schema provides no literal default.','','Generated with `python scripts/export_configuration_reference.py`.','']
seen=set()
for model in (Experiment,BenchmarkConfig,BenchmarkRunConfig):
    schema=model.model_json_schema()
    for name,definition in [(model.__name__,schema),*schema.get('$defs',{}).items()]:
        if name in seen:continue
        seen.add(name);lines+=['## '+name,'','| Field | Type or choices | Default | Constraints |','| --- | --- | --- | --- |']
        for key,p in definition.get('properties',{}).items():
            constraints=[]
            for field in ('minimum','maximum','exclusiveMinimum','exclusiveMaximum','minLength','maxLength','minItems','maxItems'):
                if field in p:constraints.append(f'{field}: {p[field]}')
            if key in definition.get('required',[]):constraints.append('required')
            default=json.dumps(p['default'],ensure_ascii=False) if 'default' in p else '—'
            lines.append('| `'+key+'` | '+type_label(p).replace('|',' / ')+' | `'+default+'` | '+', '.join(constraints)+' |')
        lines.append('')
Path(__file__).resolve().parents[1].joinpath('docs/CONFIGURATION.md').write_text('\n'.join(lines),encoding='utf8')
print('Configuration sections:',len(seen))
