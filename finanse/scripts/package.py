"""Build a portable source/data archive, excluding local development environments."""
from pathlib import Path
import os
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
target=root.parent/'potok-updated.zip'
excluded={'.venv','node_modules','__pycache__','.git','.packages','output','.playwright-cli'}
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9) as archive:
    for directory,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in excluded)
        for name in sorted(files):
            path=Path(directory)/name
            if path.suffix in {'.pyc','.log','.wal'}:
                continue
            archive.write(path,Path('finanse')/path.relative_to(root))
with ZipFile(target) as archive:
    assert archive.testzip() is None
    for required in ['finanse/vendor/three.module.js','finanse/ui/graph.js',
                     'finanse/data/nodes.parquet','finanse/database/bank.sqlite3',
                     'finanse/out/dashboard.json','finanse/UI_GUIDE.md']:
        assert required in archive.namelist(),required
print(f'{target.name}: {target.stat().st_size:,} bytes')
