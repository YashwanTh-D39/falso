import re
import glob
from pathlib import Path
from app.main import app, FRONTEND_ROOT
from fastapi.testclient import TestClient

client = TestClient(app)

addon_files = glob.glob('frontend/vendor/three/addons/**/*.js', recursive=True)
addon_files.extend(glob.glob('frontend/modules/*.js', recursive=True))
print(f'Scanning {len(addon_files)} JS files for module imports...')

missing_imports = []
for file_path in addon_files:
    abs_path = Path(file_path).resolve()
    rel_file = abs_path.relative_to(FRONTEND_ROOT.resolve())
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        imports = re.findall(r'from\s+[\'\"]([^\'\"]+)[\'\"]', content)
        for imp in imports:
            if imp == 'three':
                resolved = 'vendor/three/three.module.js'
            elif imp == 'three/webgpu':
                resolved = 'vendor/three/three.webgpu.js'
            elif imp == 'three/tsl':
                resolved = 'vendor/three/three.tsl.js'
            elif imp.startswith('three/addons/'):
                resolved = imp.replace('three/addons/', 'vendor/three/addons/')
            elif imp.startswith('.'):
                parent_dir = rel_file.parent
                try:
                    resolved = (parent_dir / imp).resolve().relative_to(FRONTEND_ROOT.resolve()).as_posix()
                except Exception:
                    resolved = (parent_dir / imp).as_posix()
            else:
                resolved = imp

            res = client.get(f'/{resolved}')
            ct = res.headers.get('content-type', '')
            is_html = '<!DOCTYPE html>' in res.text or 'text/html' in ct
            if res.status_code != 200 or is_html or 'javascript' not in ct:
                missing_imports.append({
                    'source_file': str(rel_file),
                    'import_specifier': imp,
                    'resolved_path': resolved,
                    'status_code': res.status_code,
                    'content_type': ct,
                    'is_html': is_html
                })

print('=== ES MODULE IMPORT AUDIT REPORT ===')
if missing_imports:
    print(f'FAILED: Found {len(missing_imports)} failing module imports!')
    for item in missing_imports:
        print(f'[FAILED]')
        print(f'   Source file: {item["source_file"]}')
        print(f'   Import specifier: {item["import_specifier"]}')
        print(f'   Expected path: {item["resolved_path"]}')
        print(f'   Status code: {item["status_code"]}')
        print(f'   Content-Type: {item["content_type"]}')
        print(f'   Returned index.html: {item["is_html"]}')
else:
    print('ALL MODULE IMPORTS VERIFIED SUCCESSFUL!')
    print('✓ Every module file exists')
    print('✓ Every URL is correct')
    print('✓ FastAPI serves every module as application/javascript or text/javascript')
    print('✓ Zero modules return index.html')
