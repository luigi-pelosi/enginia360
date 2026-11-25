"""Real Chromium Catalog ITEMS acceptance, fixed owned disposable scope."""
import os
import sys
from run_catalog_items_proof import run

# Bind reuse validation to this invocation's explicit image tags.
for flag, variable in (('--backend-image', 'CATALOG_BROWSER_BACKEND_IMAGE'), ('--frontend-image', 'CATALOG_BROWSER_FRONTEND_IMAGE')):
    for i, argument in enumerate(sys.argv[1:], 1):
        if argument == flag:
            os.environ[variable] = sys.argv[i + 1]
        elif argument.startswith(flag + '='):
            os.environ[variable] = argument.split('=', 1)[1]

if __name__ == '__main__':
    raise SystemExit(run(browser=True))
