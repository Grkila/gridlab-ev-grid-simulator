"""Archive final challenge evidence without old exploratory runs or QA images."""
from pathlib import Path
import hashlib
import json
import zipfile
import challenge_study as study

root = Path(__file__).resolve().parents[1]
out = study.OUT
review = study.read(out / 'independent-review.json')
assert review['status'] == 'PASS' and not review['errors']
assert (out / 'final-review.md').exists()
files = {}
for path in out.rglob('*'):
    if not path.is_file():
        continue
    rel = path.relative_to(out)
    if any(part in {'__pycache__', 'tmp'} for part in rel.parts) or path.suffix in {'.zip', '.pyc'}:
        continue
    if rel.as_posix() == 'bundle-manifest.json':
        continue
    if rel.parts[0] == 'runs' and study.read(path)['parameters'].get('runner_hash') != study.RUNNER_HASH:
        continue
    files['challenge-study/' + rel.as_posix()] = path
for path in sorted((root / 'scripts').glob('*challenge*.py')):
    files['reproduction/scripts/' + path.name] = path
files['reproduction/docs/challenge-study.md'] = root / 'docs/challenge-study.md'
manifest = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
study.write(out / 'bundle-manifest.json', manifest)
target = out / 'output/novi_sad_ev_study_evidence.zip'
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, path in files.items():
        archive.write(path, name)
    archive.write(out / 'bundle-manifest.json', 'bundle-manifest.json')
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for name, expected in manifest.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
print(json.dumps({'path': str(target), 'bytes': target.stat().st_size, 'files': len(files), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))
