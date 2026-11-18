"""Rigenera lo snapshot italiano dai raw archiviati, senza rete né scritture nel DB."""
import argparse
import json
from pathlib import Path
import re
from zipfile import ZipFile

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
official = {row['E']: row for row in json.loads((root / 'istat-rows.json').read_text())[1:]}
with ZipFile(root / 'garda.zip') as archive:
    name = next(name for name in archive.namelist() if name.endswith('json/gi_comuni_cap.json'))
    source = json.loads(archive.read(name).decode('utf-8-sig'))
rows = [dict(name=row['denominazione_ita'], postal_code=row['cap'],
             province=official[row['codice_istat']]['O'], region=row['denominazione_regione'],
             country_iso_code='IT', istat_code=row['codice_istat'])
        for row in source if row['codice_istat'] in official]
rows.sort(key=lambda row: (row['istat_code'], row['postal_code']))
assert len(rows) == 8458 and len(official) == 7894
assert {row['istat_code'] for row in rows} == set(official)
assert len({(row['istat_code'], row['postal_code']) for row in rows}) == len(rows)
assert all(re.fullmatch('[0-9]{5}', row['postal_code']) and row['postal_code'] != '00000'
           and re.fullmatch('[A-Z]{2}', row['province']) and row['region'] for row in rows)
assert rows == json.loads((root / 'cities.json').read_text()), 'Lo snapshot non coincide con i raw'
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
print(f'Verificati {len(official)} comuni e {len(rows)} coppie città/CAP; nessun valore postale generato.')
