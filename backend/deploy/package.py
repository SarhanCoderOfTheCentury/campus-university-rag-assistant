"""Package Linux/Python-3.12 wheels plus application/index, excluding secrets/tests."""
import argparse,subprocess,zipfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--directory',default='.deploy/package');p.add_argument('--skip-install',action='store_true');args=p.parse_args()
directory=Path(args.directory);directory.mkdir(parents=True,exist_ok=True)
if not Path('backend/data/manifest.json').exists():raise RuntimeError('Build the complete document index before packaging')
if not args.skip_install:
    subprocess.run(['python','-m','pip','install','--quiet','--target',str(directory),'--platform','manylinux2014_x86_64','--implementation','cp','--python-version','3.12','--only-binary=:all:','--upgrade','-r','backend/requirements-aws.txt'],check=True)
archive=Path('.deploy/lambda.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for file in directory.rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts:z.write(file,str(file.relative_to(directory)))
    for file in Path('backend').rglob('*'):
        if file.is_file() and not any(part in ['tests','__pycache__','deploy'] for part in file.parts) and file.suffix not in ['.pyc']:
            z.write(file,str(file))
    info=zipfile.ZipInfo('run.sh');info.external_attr=0o100755<<16;z.writestr(info,Path('backend/deploy/run.sh').read_bytes())
print('Lambda ZIP:',archive,'bytes:',archive.stat().st_size)
