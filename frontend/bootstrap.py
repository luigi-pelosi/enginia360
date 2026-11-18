from pathlib import Path
import urllib.request,json,hashlib
root=Path(__file__).parent
manifest={}
for name in ['button','input','textarea','dialog','switch','badge','table']:
 url=f'https://ui.shadcn.com/r/styles/new-york/{name}.json'
 raw=urllib.request.urlopen(url).read()
 data=json.loads(raw)
 for item in data['files']:
  content=item['content'].replace('@/lib/utils','@/lib/utils')
  target=root/'components/ui'/Path(item['path']).name
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(content)
 manifest[name]={'source':url,'sha256':hashlib.sha256(raw).hexdigest()}
(root/'shadcn-sources.json').write_text(json.dumps(manifest,indent=2))
license=urllib.request.urlopen('https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md').read()
(root/'SHADCN-LICENSE.md').write_bytes(license)
