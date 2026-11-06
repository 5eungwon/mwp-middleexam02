#!/usr/bin/env python3
"""Deploy assessment 02 through the official PythonAnywhere API.

Requires an account API token and either an idle Bash console or an explicitly
selected one-time WSGI bootstrap. Tokens and
application credentials are never written into the repository or terminal log.
The old application files, SQLite database and WSGI configuration are preserved.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import tarfile
import tempfile
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
API_DOC = 'https://help.pythonanywhere.com/pages/API/'


class DeploymentError(RuntimeError):
    pass


def archive_source():
    output = io.BytesIO()
    excluded = {'media', 'staticfiles', '__pycache__', '.git', '.venv', 'venv'}
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for path in sorted((ROOT / 'PhotoBlogServer').rglob('*')):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(part in excluded for part in relative.parts):
                continue
            if path.name in {'.local_secret_key', 'db.sqlite3', '.env', '.coverage'}:
                continue
            if path.name.endswith(('.pyc', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm')):
                continue
            archive.add(path, arcname=str(relative), recursive=False)
    return output.getvalue()


def remote_prepare(config):
    """No API token is included in this script or its console command."""
    return '''import json, os, pathlib, shutil, sqlite3, subprocess, tarfile, traceback
C = json.loads(%r)
home = pathlib.Path(C['home'])
backup = pathlib.Path(C['backup'])
result = pathlib.Path(C['result'])
try:
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(backup, 0o700)
    shutil.copy2(C['original_wsgi'], backup / 'previous-wsgi.py')
    previous_source = pathlib.Path(C['previous_source'])
    if previous_source.exists():
        shutil.copytree(previous_source, backup / 'previous-project', ignore=shutil.ignore_patterns('__pycache__', 'venv', '.venv', 'staticfiles'))
    old_db = previous_source / 'db.sqlite3'
    integrity = 'not-present-at-source-directory'
    if old_db.is_file():
        with sqlite3.connect('file:' + str(old_db) + '?mode=ro', uri=True) as source:
            with sqlite3.connect(backup / 'previous-database.sqlite3') as target:
                source.backup(target)
                integrity = target.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError('Previous database backup integrity check failed')
    release = pathlib.Path(C['release'])
    release.mkdir(parents=True, exist_ok=False)
    with tarfile.open(C['archive'], 'r:gz') as source:
        source.extractall(release, filter='data')
    data = pathlib.Path(C['data'])
    data.mkdir(parents=True, exist_ok=True)
    (data / 'media').mkdir(exist_ok=True)
    config_path = pathlib.Path(C['config_path'])
    config_path.parent.mkdir(parents=True, exist_ok=True)
    incoming = json.loads(pathlib.Path(C['incoming_config']).read_text())
    if config_path.exists():
        existing = json.loads(config_path.read_text())
        incoming['secret_key'] = existing['secret_key']
    config_path.write_text(json.dumps(incoming))
    os.chmod(config_path, 0o600)
    credentials_path = pathlib.Path(C['credentials_path'])
    credentials_path.write_text(pathlib.Path(C['incoming_credentials']).read_text())
    os.chmod(credentials_path, 0o600)
    environment = pathlib.Path(C['virtualenv'])
    if not (environment / 'bin/python').exists():
        subprocess.run(['python3.12', '-m', 'venv', str(environment)], check=True)
    python = str(environment / 'bin/python')
    project = release / 'PhotoBlogServer'
    subprocess.run([python, '-m', 'pip', 'install', '-r', str(project / 'requirements.txt')], check=True)
    env = os.environ.copy()
    env.update(DJANGO_DEBUG='0', DJANGO_SECRET_KEY=incoming['secret_key'], DJANGO_ALLOWED_HOSTS=incoming['allowed_hosts'], DJANGO_DB_PATH=str(data / 'db.sqlite3'), DJANGO_MEDIA_ROOT=str(data / 'media'))
    credentials = json.loads(credentials_path.read_text())
    env['DEMO_PASSWORD'] = credentials['password']
    subprocess.run([python, 'manage.py', 'migrate', '--noinput'], cwd=project, env=env, check=True)
    subprocess.run([python, 'manage.py', 'seed_demo', '--username', credentials['username'], '--superuser'], cwd=project, env=env, check=True)
    subprocess.run([python, 'manage.py', 'collectstatic', '--noinput'], cwd=project, env=env, check=True)
    subprocess.run([python, 'manage.py', 'check', '--deploy'], cwd=project, env=env, check=True)
    result.write_text(json.dumps({'status': 'ready', 'database_backup_integrity': integrity, 'backup': str(backup), 'release': str(release), 'virtualenv': str(environment)}))
except Exception as error:
    result.write_text(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
    traceback.print_exc()
    raise
finally:
    for name in ['incoming_config', 'incoming_credentials']:
        pathlib.Path(C[name]).unlink(missing_ok=True)
''' % json.dumps(config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='asdfgh0986')
    parser.add_argument('--api-host', choices=['www.pythonanywhere.com', 'eu.pythonanywhere.com'], default='www.pythonanywhere.com')
    activation = parser.add_mutually_exclusive_group(required=True)
    activation.add_argument('--console-id', type=int, help='An existing idle Bash console opened in PythonAnywhere')
    activation.add_argument('--wsgi-bootstrap', action='store_true', help='Start preparation from a one-time WSGI wrapper while the previous app stays available')
    parser.add_argument('--credentials-file', type=Path, help='Private local JSON with username/password; generated outside repo if omitted')
    args = parser.parse_args()
    token = os.environ.get('PYTHONANYWHERE_API_TOKEN') or os.environ.get('API_TOKEN')
    if not token:
        parser.error('Set PYTHONANYWHERE_API_TOKEN (or API_TOKEN) in the process environment; do not put it on the command line.')
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.username):
        parser.error('Invalid account username')
    username = args.username
    domain = f'{username}.pythonanywhere.com'
    base = f'https://{args.api_host}/api/v0/user/{username}'
    session = requests.Session()
    session.headers['Authorization'] = 'Token ' + token

    def api(method, path, **kwargs):
        response = session.request(method, base + path, timeout=60, **kwargs)
        if not response.ok:
            raise DeploymentError(f'PythonAnywhere API {method} {path}: HTTP {response.status_code}')
        return response

    def put_file(path, data):
        return api('POST', '/files/path' + quote(path, safe='/'), files={'content': ('content', data)})

    def get_file(path, optional=False):
        response = session.get(base + '/files/path' + quote(path, safe='/'), timeout=60)
        if optional and response.status_code == 404:
            return None
        if response.status_code != 200:
            raise DeploymentError(f'Could not read remote file {path}: HTTP {response.status_code}')
        return response.content

    app_path = '/webapps/' + domain + '/'
    previous = api('GET', app_path).json()
    mappings = api('GET', app_path + 'static_files/').json()
    if args.console_id is not None:
        console = api('GET', f'/consoles/{args.console_id}/').json()
        if 'bash' not in str(console.get('executable', '')).lower():
            raise DeploymentError('Selected console is not a Bash console; nothing was changed')
        output = api('GET', f'/consoles/{args.console_id}/get_latest_output/').json().get('output', '')
        plain = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', output)
        if not re.search(r'[$#]\s*$', plain):
            raise DeploymentError('Selected Bash console does not show an idle prompt; nothing was changed')
    home = f'/home/{username}'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    application_root = home + '/home-guardian-assessment02'
    release = application_root + '/releases/' + stamp
    staging = application_root + '/staging/' + stamp
    backup = home + '/photoblog-backups/before-assessment02-' + stamp
    wsgi = f'/var/www/{username}_pythonanywhere_com_wsgi.py'
    previous_wsgi = get_file(wsgi)
    credentials_file = args.credentials_file
    if credentials_file:
        credentials_file = credentials_file.resolve()
        if credentials_file.is_relative_to(ROOT):
            raise DeploymentError('Credentials file must be outside the Git repository')
        credentials = json.loads(credentials_file.read_text())
    else:
        descriptor, path = tempfile.mkstemp(prefix='home-guardian-cloud-', suffix='.json')
        os.close(descriptor)
        credentials_file = Path(path)
        credentials = {'username': 'guardian', 'password': secrets.token_urlsafe(24)}
        credentials_file.write_text(json.dumps(credentials))
    credentials_file.chmod(0o600)
    if not credentials.get('username') or not credentials.get('password'):
        raise DeploymentError('Application credentials JSON needs username and password')
    configuration = {'secret_key': secrets.token_urlsafe(64), 'allowed_hosts': domain}
    prepare = {
        'home': home, 'backup': backup, 'wsgi': wsgi, 'original_wsgi': staging + '/previous-wsgi.py',
        'previous_source': previous.get('source_directory') or home + '/photoblog-server-v2/PhotoBlogServer',
        'release': release, 'archive': staging + '/source.tar.gz',
        'data': application_root + '/data',
        'config_path': home + '/.config/home-guardian-assessment02.json',
        'credentials_path': home + '/.config/home-guardian-assessment02-admin.json',
        'incoming_config': staging + '/incoming-config.json',
        'incoming_credentials': staging + '/incoming-credentials.json',
        'virtualenv': home + '/.virtualenvs/home-guardian-assessment02',
        'result': staging + '/prepare-result.json',
    }
    put_file(prepare['archive'], archive_source())
    put_file(prepare['incoming_config'], json.dumps(configuration).encode())
    put_file(prepare['incoming_credentials'], json.dumps(credentials).encode())
    put_file(staging + '/prepare.py', remote_prepare(prepare).encode())
    # The full previous API configuration is stored only in the private remote backup.
    put_file(staging + '/previous-web-settings.json', json.dumps(previous).encode())
    put_file(staging + '/previous-static-mappings.json', json.dumps(mappings).encode())
    put_file(prepare['original_wsgi'], previous_wsgi)
    if args.console_id is not None:
        command = 'python3.12 ' + shlex.quote(staging + '/prepare.py') + ' > ' + shlex.quote(staging + '/prepare.log') + ' 2>&1\n'
        api('POST', f'/consoles/{args.console_id}/send_input/', data={'input': command})
    else:
        # This code is deployed through the account's normal authenticated WSGI
        # configuration. It exposes no installation endpoint or token to users.
        old_python = (previous.get('virtualenv_path') or home + '/.virtualenvs/photoblog-v2') + '/bin/python'
        bootstrap = f'''import json, os, runpy, subprocess
from pathlib import Path
marker = Path({staging + '/prepare-started'!r})
try:
    descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
except FileExistsError:
    pass
else:
    os.close(descriptor)
    try:
        log = open({staging + '/prepare.log'!r}, 'ab', buffering=0)
        subprocess.Popen([{old_python!r}, {staging + '/prepare.py'!r}], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    except Exception as error:
        Path({prepare['result']!r}).write_text(json.dumps({{'status': 'failed', 'error_type': type(error).__name__}}))
application = runpy.run_path({prepare['original_wsgi']!r})['application']
'''
        put_file(wsgi, bootstrap.encode())
        try:
            api('POST', app_path + 'reload/')
            requests.get('https://' + domain + '/', timeout=60)
        except Exception:
            put_file(wsgi, previous_wsgi)
            api('POST', app_path + 'reload/')
            raise
    print('Source uploaded. Preparing separate environment, database and backup.', flush=True)
    deadline = time.monotonic() + 600
    ready = None
    while time.monotonic() < deadline:
        result = get_file(prepare['result'], optional=True)
        if result:
            ready = json.loads(result)
            break
        time.sleep(3)
    if not ready or ready.get('status') != 'ready':
        if args.wsgi_bootstrap:
            put_file(wsgi, previous_wsgi)
            api('POST', app_path + 'reload/')
        raise DeploymentError('Remote preparation did not finish successfully. Existing web configuration was not changed. Read the private prepare.log on PythonAnywhere.')
    # Preserve settings next to the remote WSGI/database backup after mkdir succeeds.
    put_file(backup + '/previous-web-settings.json', json.dumps(previous).encode())
    put_file(backup + '/previous-static-mappings.json', json.dumps(mappings).encode())
    project = release + '/PhotoBlogServer'
    wsgi_content = f'''import json, os, sys
from pathlib import Path
config = json.loads(Path({prepare['config_path']!r}).read_text())
sys.path.insert(0, {project!r})
os.environ['DJANGO_SETTINGS_MODULE'] = 'photoblog.settings'
os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_SECRET_KEY'] = config['secret_key']
os.environ['DJANGO_ALLOWED_HOSTS'] = config['allowed_hosts']
os.environ['DJANGO_DB_PATH'] = {prepare['data'] + '/db.sqlite3'!r}
os.environ['DJANGO_MEDIA_ROOT'] = {prepare['data'] + '/media'!r}
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
'''
    altered = []
    added = []
    changed = False
    restore_fields = {key: previous[key] if previous[key] is not None else '' for key in ['source_directory', 'virtualenv_path', 'force_https'] if key in previous}
    try:
        changed = True
        put_file(wsgi, wsgi_content.encode())
        api('PATCH', app_path, data={'source_directory': project, 'virtualenv_path': prepare['virtualenv'], 'force_https': True})
        for url, path in [('/static/', project + '/staticfiles'), ('/media/', prepare['data'] + '/media')]:
            existing = next((mapping for mapping in mappings if mapping['url'].rstrip('/') == url.rstrip('/')), None)
            if existing:
                api('PATCH', app_path + f"static_files/{existing['id']}/", data={'url': url, 'path': path})
                altered.append(existing)
            else:
                new_mapping = api('POST', app_path + 'static_files/', data={'url': url, 'path': path}).json()
                added.append(new_mapping['id'])
        api('POST', app_path + 'reload/')
        public = requests.Session()
        checks = []
        for attempt in range(12):
            health = public.get('https://' + domain + '/health/', timeout=45)
            if health.status_code == 200 and health.json().get('service') == 'PhotoBlogServer':
                break
            time.sleep(3)
        else:
            raise DeploymentError('New application health check failed')
        checks.append({'check': 'HTTPS health', 'status': health.status_code, 'result': health.json()})
        unauthorized = public.get('https://' + domain + '/api_root/Post/', timeout=45)
        if unauthorized.status_code != 401:
            raise DeploymentError('New API authentication check failed')
        checks.append({'check': 'anonymous API rejected', 'status': unauthorized.status_code})
        login = public.post('https://' + domain + '/api-token-auth/', data=credentials, timeout=45)
        if login.status_code != 200 or not login.json().get('token'):
            raise DeploymentError('New application account login failed')
        checks.append({'check': 'JWT login', 'status': login.status_code, 'token': '[redacted]'})
        summary = {'server': 'https://' + domain, 'deployed_at': datetime.now(timezone(timedelta(hours=9))).isoformat(), 'source_directory': project, 'virtualenv': prepare['virtualenv'], 'data_directory': prepare['data'], 'backup': backup, 'database_backup_integrity': ready['database_backup_integrity'], 'original_files_preserved': True, 'checks': checks, 'api_documentation': API_DOC}
        evidence = ROOT / 'docs/evidence/cloud-deployment.json'
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print('Private application credentials: ' + str(credentials_file))
    except Exception:
        if changed:
            put_file(wsgi, previous_wsgi)
            api('PATCH', app_path, data=restore_fields)
            for mapping in altered:
                api('PATCH', app_path + f"static_files/{mapping['id']}/", data={'url': mapping['url'], 'path': mapping['path']})
            for mapping_id in added:
                api('DELETE', app_path + f'static_files/{mapping_id}/')
            api('POST', app_path + 'reload/')
            print('Previous WSGI and web configuration restored after failed deployment.', flush=True)
        raise


if __name__ == '__main__':
    main()
