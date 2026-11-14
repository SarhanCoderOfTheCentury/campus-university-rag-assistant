#!/usr/bin/env python3
"""Fetch official shadcn registry sources, only adapting imports and icon placeholders.
No UI implementation or styling in the fetched components is rewritten.
"""
import concurrent.futures, hashlib, json, pathlib, re, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
STYLE = 'base-nova'
NAMES = sys.argv[1:] or 'sidebar message-scroller message bubble trace input-group hover-card badge kbd empty item sheet tooltip separator spinner code-block'.split()
seen, dependencies, provenance = set(), set(), []
cache = ROOT / '.openai' / 'registry-cache'
cache.mkdir(parents=True, exist_ok=True)

def fetch(name):
    url = f'https://ui.shadcn.com/r/styles/{STYLE}/{name}.json'
    target = cache / f'{name}.json'
    subprocess.run(['curl','-fsSL','--retry','2','--max-time','45',url,'-o',str(target)],check=True)
    return name, url, json.loads(target.read_text())

pending = NAMES
while pending:
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, pending))
    seen.update(pending)
    following = set()
    for name, url, data in results:
        dependencies.update(data.get('dependencies', []))
        for dependency in data.get('registryDependencies', []):
            if not isinstance(dependency,str) or '/' in dependency or dependency.startswith('@'):
                raise ValueError(f'Unexpected registry dependency: {dependency}')
            if dependency not in seen:
                following.add(dependency)
        for file in data.get('files', []):
            source = file.get('content', '')
            content = source
            path = file['path']
            if '/hooks/' in path:
                target = ROOT / 'src/hooks' / pathlib.Path(path).name
            elif '/lib/' in path:
                target = ROOT / 'src/lib' / pathlib.Path(path).name
            elif '/ui/' in path:
                target = ROOT / 'src/components/ui' / pathlib.Path(path).name
            else:
                raise ValueError(f'Unexpected source file: {path}')
            content = content.replace(f'@/registry/{STYLE}/ui/', '@/components/ui/').replace(f'@/registry/{STYLE}/hooks/', '@/hooks/').replace(f'@/registry/{STYLE}/lib/', '@/lib/')
            placeholders = re.findall(r'<IconPlaceholder\s+.*?/>',content,flags=re.S)
            icons = set()
            for placeholder in placeholders:
                match = re.search(r'lucide="([^"]+)"',placeholder)
                if not match:
                    raise ValueError(f'Missing lucide icon in {path}')
                icon = match.group(1)
                icons.add(icon)
                attributes = re.sub(r'\s+(?:lucide|tabler|hugeicons|phosphor|remixicon)="[^"]*"','',placeholder)
                content = content.replace(placeholder,attributes.replace('IconPlaceholder',icon))
            content = re.sub(r'import \{ IconPlaceholder \} from "@/app/\(create\)/components/icon-placeholder"\n?', '', content)
            if icons:
                icon_import = 'import { ' + ', '.join(sorted(icons)) + ' } from "lucide-react"\n'
                content = content.replace('"use client"\n', '"use client"\n\n' + icon_import, 1) if content.startswith('"use client"') else icon_import + content
            if 'IconPlaceholder' in content or '@/registry/' in content:
                raise ValueError(f'Unresolved registry placeholder in {path}')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content)
            provenance.append({'component':name,'registry_url':url,'registry_path':path,'local_path':str(target.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'installed_sha256':hashlib.sha256(content.encode()).hexdigest(),'changes':['Registry imports mapped to local project paths','Official Lucide icon selected from registry placeholders']})
        print(f'Fetched {name}',flush=True)
    pending = sorted(following)
existing_path = ROOT/'shadcn-provenance.json'
if existing_path.exists():
    paths = {item['local_path'] for item in provenance}
    provenance = [item for item in json.loads(existing_path.read_text())['files'] if item['local_path'] not in paths] + provenance
(ROOT/'shadcn-provenance.json').write_text(json.dumps({'style':STYLE,'source':'https://ui.shadcn.com','files':provenance},indent=2)+'\n')
package_path=ROOT/'package.json'
package=json.loads(package_path.read_text())
for dependency in sorted(dependencies):
    package['dependencies'].setdefault(dependency,'latest')
package_path.write_text(json.dumps(package,indent=2)+'\n')
print('Dependencies: '+', '.join(sorted(dependencies)),flush=True)
