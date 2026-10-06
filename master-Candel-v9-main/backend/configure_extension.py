"""Generate exact extension backend permission from env; never embeds a key."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv


def configure():
    load_dotenv(Path(__file__).parent / '.env')
    url = urlsplit(os.environ.get('OBSERVER_BACKEND_URL') or os.environ['PUBLIC_APP_URL'])
    local_http = url.scheme == 'http' and url.hostname in {'localhost', '127.0.0.1', '::1'}
    if (url.scheme != 'https' and not local_http) or not url.netloc or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment:
        raise ValueError('OBSERVER_BACKEND_URL must be an HTTPS origin (HTTP is allowed for localhost only)')
    manifest = Path(__file__).resolve().parent.parent / 'extensions/market-qx-observer-v2/manifest.json'
    config = json.loads(manifest.read_text())
    config['optional_host_permissions'] = [f'{url.scheme}://{url.netloc}/*']
    manifest.write_text(json.dumps(config, indent=2) + '\n')


if __name__ == '__main__':
    configure()