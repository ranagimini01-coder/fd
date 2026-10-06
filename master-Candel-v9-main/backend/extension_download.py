from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from fastapi import APIRouter
from fastapi.responses import Response
import json
from market_config import OBSERVER_BACKEND_URL

router = APIRouter(prefix='/api/v1/observer')


@router.get('/download')
async def download():
    root = Path(__file__).resolve().parent.parent / 'extensions/market-qx-observer-v2'
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        for file in root.iterdir():
            if file.suffix in {'.js', '.html', '.json', '.md', '.txt'}:
                if file.name == 'manifest.json':
                    manifest = json.loads(file.read_text())
                    manifest['optional_host_permissions'] = [f'{OBSERVER_BACKEND_URL}/*']
                    archive.writestr(f'market-qx-observer-v2/{file.name}', json.dumps(manifest, indent=2))
                else:
                    archive.write(file, f'market-qx-observer-v2/{file.name}')
    return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="market-qx-observer-v2.zip"'})