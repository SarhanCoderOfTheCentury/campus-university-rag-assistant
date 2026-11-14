"""Build a standalone LMS ZIP below 5 MB, excluding secrets, caches and environments."""
from pathlib import Path
import argparse
import zipfile
from rag.config import ROOT


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'dist/Campus-Evidence-Streamlit-Agent.zip')
    args=p.parse_args()
    output=args.output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    files=[]
    for folder in ['rag','scripts','tests','knowledge','data','evaluation','evidence','docs']:
        for file in (ROOT/folder).rglob('*'):
            if not file.is_file() or any(part in ('__pycache__','demo-frames','screenshots') for part in file.parts):
                continue
            files.append(file)
    for name in ['README.md','requirements.txt','requirements-dev.txt','pyproject.toml','.env.example','.gitignore',
        '.streamlit/config.toml','.streamlit/secrets.toml.example','.github/workflows/ci.yml','streamlit_app.py']:
        files.append(ROOT/name)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(set(files)):
            z.write(file,'campus-evidence/'+str(file.relative_to(ROOT)))
    if output.stat().st_size>=5_000_000:
        raise ValueError('ZIP exceeds the assignment attachment limit; keep the demo video as a separate link.')
    print(f'{output}: {output.stat().st_size:,} bytes; {len(files)} files; under 5 MB')

if __name__=='__main__':
    main()
