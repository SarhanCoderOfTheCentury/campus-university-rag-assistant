"""Keep just official comments/books glyphs; no glyphs are redrawn or substituted."""
from pathlib import Path
import subprocess

source=Path('node_modules/@flaticon/flaticon-uicons/css/uicons-regular-rounded-J3WOUERV.woff2')
Path('public/fonts').mkdir(parents=True,exist_ok=True)
subprocess.run(['pyftsubset',str(source),'--unicodes=U+F4BC,U+F28D','--flavor=woff2','--output-file=public/fonts/campus-flaticon.woff2'],check=True)
print('Official glyph subset bytes:',Path('public/fonts/campus-flaticon.woff2').stat().st_size)
