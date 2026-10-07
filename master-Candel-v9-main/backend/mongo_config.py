import os
from urllib.parse import quote, urlencode


def mongo_url_from_environment() -> str:
    configured_url = os.environ.get('MONGO_URL', '').strip()
    if configured_url:
        return configured_url

    host = os.environ.get('MONGO_HOST', '').strip()
    if not host:
        raise RuntimeError(
            'MongoDB is not configured. Set MONGO_URL or MONGO_HOST in the environment.'
        )

    port = os.environ.get('MONGO_PORT', '27017').strip()
    try:
        port_number = int(port)
        if not 1 <= port_number <= 65535:
            raise ValueError
    except ValueError as error:
        raise RuntimeError('MONGO_PORT must be an integer between 1 and 65535.') from error

    database = os.environ.get('DB_NAME', '').strip()
    if not database:
        raise RuntimeError('DB_NAME must be set when using MONGO_HOST.')

    username = os.environ.get('MONGO_USER', '')
    password = os.environ.get('MONGO_PASSWORD', '')
    if bool(username) != bool(password):
        raise RuntimeError('Both MONGO_USER and MONGO_PASSWORD must be set together.')

    formatted_host = f'[{host}]' if ':' in host and not host.startswith('[') else host
    credentials = ''
    options = ''
    if username:
        credentials = f'{quote(username, safe="")}:{quote(password, safe="")}@'
        options = f'?{urlencode({"authSource": "admin"})}'

    return (
        f'mongodb://{credentials}{formatted_host}:{port_number}/'
        f'{quote(database, safe="")}{options}'
    )
