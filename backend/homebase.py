#!/usr/bin/env python3
"""Home Base backend.

Serves the TV interface and a small JSON API on 127.0.0.1 for settings,
network, display, weather, news, power and the Plex music library.
Standard library only. Set HB_FAKE=1 to run on a development machine with
canned system data.
"""

import glob
import ipaddress
import json
import os
import pwd
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, 'ui')
CONF_DIR = os.path.expanduser(os.environ.get('HB_CONF_DIR', '~/.config/homebase'))
SETTINGS_PATH = os.path.join(CONF_DIR, 'settings.json')
FAKE = os.environ.get('HB_FAKE') == '1'
HOST = os.environ.get('HB_HOST', '127.0.0.1')
PORT = int(os.environ.get('HB_PORT', '8099'))
OUTPUT = os.environ.get('HB_OUTPUT', 'HDMI-A-1')

# Countries that use Fahrenheit for everyday temperatures.
FAHRENHEIT_COUNTRIES = {'US', 'LR', 'MM', 'BS', 'BZ', 'KY', 'PW', 'FM', 'MH'}
# Countries where a 12-hour clock is the everyday norm.
TWELVE_HOUR_COUNTRIES = {'US', 'CA', 'AU', 'NZ', 'PH', 'IN', 'PK', 'BD', 'EG', 'SA', 'CO', 'MY'}

THEMES = {'midnight', 'oled', 'ember', 'daylight', 'ocean', 'forest', 'arctic', 'synthwave',
          'sakura', 'sunset', 'royal', 'solar', 'terminal', 'mono'}

AP_FEED = ('https://news.google.com/rss/search?q=site:apnews.com+when:1d'
           '&hl=en-US&gl=US&ceid=US:en')

DEFAULTS = {
    'setup_done': False,
    'country': None,
    'weather': {'name': None, 'lat': None, 'lon': None, 'country': None, 'timezone': None},
    'units': 'auto',
    'clock': 'auto',
    'ticker': True,
    'theme': 'midnight',
    'wallpaper': 'ambient',
    # width None means "use the TV's preferred mode" until the user picks one.
    'display': {'width': None, 'height': None, 'refresh': None, 'scale': None, 'edges': 0},
    'plex': {'client_id': None, 'token': None, 'server': None, 'preferred': None},
}

# ---------------------------------------------------------------- settings

_settings_lock = threading.Lock()


def _merge(defaults, data):
    out = {}
    for key, value in defaults.items():
        given = data.get(key)
        if isinstance(value, dict):
            out[key] = _merge(value, given if isinstance(given, dict) else {})
        else:
            out[key] = given if key in data else value
    return out


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    settings = _merge(DEFAULTS, data)
    if not settings['plex']['client_id']:
        settings['plex']['client_id'] = str(uuid.uuid4())
        save_settings(settings)
    return settings


def save_settings(settings):
    os.makedirs(CONF_DIR, exist_ok=True)
    tmp = SETTINGS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(settings, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, SETTINGS_PATH)


def update_settings(fn):
    with _settings_lock:
        settings = load_settings()
        fn(settings)
        save_settings(settings)
        return settings


def public_settings():
    s = load_settings()
    country = s['country'] or s['weather'].get('country')
    clock = s['clock'] if s['clock'] in ('12', '24') else ('12' if country in TWELVE_HOUR_COUNTRIES else '24')
    return {
        'setup_done': s['setup_done'],
        'country': s['country'],
        'weather': s['weather'],
        'units': s['units'],
        'clock': s['clock'],
        'clock_resolved': clock,
        'ticker': s['ticker'],
        'theme': s['theme'],
        'wallpaper': s['wallpaper'],
        'display': s['display'],
    }

# ---------------------------------------------------------------- helpers


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def run(cmd, sudo=False, timeout=30, env=None, stdin=None):
    if sudo and os.geteuid() != 0:
        cmd = ['sudo', '-n'] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, input=stdin)
    except FileNotFoundError:
        return 127, '', f'{cmd[0]} not found'
    except subprocess.TimeoutExpired:
        return 124, '', 'timed out'
    return p.returncode, p.stdout, p.stderr


def http_get(url, headers=None, timeout=10, data=None, method=None):
    h = {'User-Agent': 'HomeBase/1.0'}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_json(url, headers=None, timeout=10, data=None, method=None):
    h = {'Accept': 'application/json'}
    h.update(headers or {})
    return json.loads(http_get(url, h, timeout, data, method) or b'null')


def split_terse(line):
    """Split one line of `nmcli -t` output on unescaped colons."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == '\\':
            esc = True
        elif ch == ':':
            fields.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append(''.join(cur))
    return fields


def hostname():
    return socket.gethostname().split('.')[0]

# ---------------------------------------------------------------- network


def _nmcli(args, sudo=False):
    code, out, err = run(['nmcli'] + args, sudo=sudo)
    if code != 0:
        raise ApiError((err or out).strip() or 'nmcli failed', 500)
    return out


def _signal_word(signal):
    if signal is None:
        return None
    return 'Strong' if signal >= 70 else 'Good' if signal >= 40 else 'Weak'


# Simulated device for development (HB_FAKE=1): starts offline like a fresh install.
_fake = {'ssid': None, 'ssh': False, 'has_password': False, 'country': None}


def network_status():
    if FAKE:
        on = _fake['ssid'] is not None
        return {'hostname': 'homebase',
                'wifi': {'device': 'wlan0', 'connected': on, 'ssid': _fake['ssid'], 'signal': 78 if on else None,
                         'signal_word': 'Strong' if on else None, 'connection': _fake['ssid']},
                'ethernet': {'connected': False}, 'ip': '192.168.1.40' if on else None, 'prefix': 24 if on else None,
                'gateway': '192.168.1.1' if on else None, 'dns': ['192.168.1.1'] if on else [],
                'method': 'auto' if on else None, 'active_connection': _fake['ssid']}
    status = {'hostname': hostname(), 'wifi': {'connected': False}, 'ethernet': {'connected': False},
              'ip': None, 'prefix': None, 'gateway': None, 'dns': [], 'method': None,
              'active_connection': None}
    primary = None
    for line in _nmcli(['-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device']).splitlines():
        dev, typ, state, con = (split_terse(line) + ['', '', '', ''])[:4]
        connected = state.startswith('connected') and not state.startswith('connected (externally')
        if typ == 'wifi' and 'device' not in status['wifi']:
            status['wifi'] = {'device': dev, 'connected': connected, 'connection': con or None}
            if connected and primary is None:
                primary = (dev, con)
        elif typ == 'ethernet' and 'device' not in status['ethernet']:
            status['ethernet'] = {'device': dev, 'connected': connected, 'connection': con or None}
            if connected:
                primary = (dev, con)
    if status['wifi'].get('connected'):
        for line in _nmcli(['-t', '-f', 'IN-USE,SSID,SIGNAL', 'device', 'wifi', 'list', '--rescan', 'no']).splitlines():
            inuse, ssid, signal = (split_terse(line) + ['', '', ''])[:3]
            if inuse.strip() == '*':
                sig = int(signal) if signal.isdigit() else None
                status['wifi'].update(ssid=ssid, signal=sig, signal_word=_signal_word(sig))
                break
    if primary:
        dev, con = primary
        status['active_connection'] = con
        addr = _nmcli(['-g', 'IP4.ADDRESS', 'device', 'show', dev]).strip().split(' | ')[0]
        if '/' in addr:
            status['ip'], prefix = addr.split('/', 1)
            status['prefix'] = int(prefix)
        status['gateway'] = _nmcli(['-g', 'IP4.GATEWAY', 'device', 'show', dev]).strip() or None
        dns = _nmcli(['-g', 'IP4.DNS', 'device', 'show', dev]).strip()
        status['dns'] = [d for d in dns.split(' | ') if d]
        status['method'] = _nmcli(['-g', 'ipv4.method', 'connection', 'show', con]).strip() or None
    return status


def wifi_scan():
    if FAKE:
        nets = [{'ssid': 'Example Wi-Fi', 'signal': 78, 'secure': True},
                {'ssid': 'Example Guest', 'signal': 52, 'secure': False},
                {'ssid': 'Neighbor', 'signal': 31, 'secure': True}]
        return [dict(n, in_use=n['ssid'] == _fake['ssid']) for n in nets]
    seen = {}
    out = _nmcli(['-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list', '--rescan', 'yes'])
    for line in out.splitlines():
        inuse, ssid, signal, security = (split_terse(line) + ['', '', '', ''])[:4]
        if not ssid:
            continue
        sig = int(signal) if signal.isdigit() else 0
        entry = {'ssid': ssid, 'signal': sig, 'secure': bool(security.strip()) and security.strip() != '--',
                 'in_use': inuse.strip() == '*'}
        if ssid not in seen or entry['in_use'] or sig > seen[ssid]['signal']:
            entry['in_use'] = entry['in_use'] or seen.get(ssid, {}).get('in_use', False)
            seen[ssid] = entry
    return sorted(seen.values(), key=lambda e: (not e['in_use'], -e['signal']))


def wifi_connect(body):
    ssid = (body.get('ssid') or '').strip()
    if not ssid:
        raise ApiError('Enter a network name')
    cmd = ['device', 'wifi', 'connect', ssid]
    if body.get('password'):
        cmd += ['password', body['password']]
    if body.get('hidden'):
        cmd += ['hidden', 'yes']
    if FAKE:
        _fake['ssid'] = ssid
        return {'ok': True}
    _nmcli(cmd, sudo=True)
    return {'ok': True}


def set_ip(body):
    mode = body.get('mode')
    status = network_status()
    con = status.get('active_connection')
    if not con:
        raise ApiError('Not connected to a network')
    if mode == 'auto':
        args = ['ipv4.method', 'auto', 'ipv4.addresses', '', 'ipv4.gateway', '', 'ipv4.dns', '']
    elif mode == 'manual':
        try:
            addr = ipaddress.IPv4Address(body['address'])
            net = ipaddress.IPv4Network(f"0.0.0.0/{body.get('netmask') or '255.255.255.0'}")
            gw = ipaddress.IPv4Address(body['gateway'])
            dns = [str(ipaddress.IPv4Address(d.strip())) for d in str(body.get('dns') or '').split(',') if d.strip()]
        except (KeyError, ValueError):
            raise ApiError('Check the addresses: one of them is not a valid IPv4 address')
        args = ['ipv4.method', 'manual', 'ipv4.addresses', f'{addr}/{net.prefixlen}',
                'ipv4.gateway', str(gw), 'ipv4.dns', ' '.join(dns)]
    else:
        raise ApiError('mode must be auto or manual')
    if FAKE:
        return {'ok': True}
    _nmcli(['connection', 'modify', con] + args, sudo=True)
    # Re-activate in the background: the connection drops for a moment.
    subprocess.Popen(['sudo', '-n', 'nmcli', 'connection', 'up', con],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {'ok': True}


def _login_user():
    return pwd.getpwuid(os.getuid()).pw_name


def _has_password():
    if FAKE:
        return _fake['has_password']
    code, out, _ = run(['passwd', '-S', _login_user()], sudo=True)
    fields = out.split()
    return code == 0 and len(fields) > 1 and fields[1] == 'P'


def ssh_status():
    if FAKE:
        return {'enabled': _fake['ssh'], 'has_password': _fake['has_password'], 'user': 'homebase'}
    code, out, _ = run(['systemctl', 'is-active', 'ssh'])
    return {'enabled': out.strip() == 'active', 'has_password': _has_password(), 'user': _login_user()}


def ssh_set(body):
    """Turn remote login on or off. Turning it on needs a login password:
    the shared image ships without one, so SSH is never open by default."""
    enable = bool(body.get('enabled'))
    password = body.get('password') or ''
    if enable and password:
        if len(password) < 8:
            raise ApiError('Use at least 8 characters for the password')
        if FAKE:
            _fake['has_password'] = True
        else:
            code, out, err = run(['/usr/local/sbin/homebase-setpass'], sudo=True, stdin=password + '\n')
            if code != 0:
                raise ApiError((err or out).strip() or 'Could not set the password', 500)
    if enable and not _has_password():
        raise ApiError('Set a password first', 409)
    if FAKE:
        _fake['ssh'] = enable
        return ssh_status()
    if enable:
        code, out, err = run(['systemctl', 'enable', '--now', 'ssh'], sudo=True)
    else:
        run(['systemctl', 'disable', '--now', 'ssh.socket'], sudo=True)
        code, out, err = run(['systemctl', 'disable', '--now', 'ssh'], sudo=True)
    if code != 0:
        raise ApiError((err or out).strip() or 'Could not change SSH', 500)
    return ssh_status()

# ---------------------------------------------------------------- country and time zone


def set_country(body):
    """Set the Wi-Fi regulatory country. Raspberry Pi OS keeps Wi-Fi switched
    off until a country is chosen."""
    cc = str(body.get('country') or '').upper()
    if len(cc) != 2 or not cc.isalpha():
        raise ApiError('country must be a two-letter code')
    if FAKE:
        _fake['country'] = cc
    else:
        code, out, err = run(['raspi-config', 'nonint', 'do_wifi_country', cc], sudo=True, timeout=30)
        if code != 0:
            run(['iw', 'reg', 'set', cc], sudo=True)
        run(['rfkill', 'unblock', 'wifi'], sudo=True)
        run(['nmcli', 'radio', 'wifi', 'on'], sudo=True)

    def upd(s):
        s['country'] = cc
    update_settings(upd)
    return public_settings()


def set_timezone(tz):
    if not tz or FAKE:
        return
    if '..' in tz or not os.path.isfile(os.path.join('/usr/share/zoneinfo', tz)):
        return
    run(['timedatectl', 'set-timezone', tz], sudo=True)


def setup_done(_body):
    def upd(s):
        s['setup_done'] = True
    update_settings(upd)
    return public_settings()

# ---------------------------------------------------------------- display

_display_lock = threading.Lock()
_display_pending = {'timer': None, 'previous': None, 'candidate': None, 'deadline': None}


def wayland_env():
    env = dict(os.environ)
    runtime = env.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
    env['XDG_RUNTIME_DIR'] = runtime
    try:
        with open(os.path.join(runtime, 'homebase-wayland')) as f:
            env['WAYLAND_DISPLAY'] = f.read().strip() or 'wayland-0'
    except OSError:
        env.setdefault('WAYLAND_DISPLAY', 'wayland-0')
    return env


def edid_name():
    for path in glob.glob(f'/sys/class/drm/card*-{OUTPUT}/edid'):
        try:
            data = open(path, 'rb').read()
        except OSError:
            continue
        if len(data) < 128:
            continue
        for off in (54, 72, 90, 108):
            block = data[off:off + 18]
            if block[0:3] == b'\x00\x00\x00' and block[3] == 0xFC:
                return block[5:18].split(b'\n')[0].decode('ascii', 'replace').strip()
    return None


def _randr_outputs():
    code, out, err = run(['wlr-randr', '--json'], env=wayland_env(), timeout=10)
    if code != 0:
        raise ApiError(f'Display tool failed: {(err or out).strip()}', 500)
    return json.loads(out)


def display_info():
    if FAKE:
        modes = [{'width': 3840, 'height': 2160, 'refresh': r} for r in (30.0, 29.97, 25.0, 24.0, 23.976)]
        modes += [{'width': 1920, 'height': 1080, 'refresh': r} for r in (60.0, 59.94, 50.0, 30.0, 24.0)]
        modes += [{'width': 1280, 'height': 720, 'refresh': r} for r in (60.0, 50.0)]
        return {'tv': 'Example TV', 'output': OUTPUT, 'connected': True, 'modes': modes,
                'current': {'width': 3840, 'height': 2160, 'refresh': 30.0}, 'scale': 2.0,
                'pending': None}
    info = {'tv': edid_name(), 'output': OUTPUT, 'connected': False, 'modes': [], 'current': None,
            'scale': None, 'pending': None}
    try:
        outputs = _randr_outputs()
    except ApiError as e:
        info['error'] = str(e)
        return info
    out = next((o for o in outputs if o.get('name') == OUTPUT), None) or (outputs[0] if outputs else None)
    if not out:
        return info
    info['output'] = out.get('name')
    info['connected'] = True
    info['scale'] = out.get('scale')
    seen = set()
    for m in out.get('modes', []):
        key = (m['width'], m['height'], round(m['refresh'], 2))
        if key in seen:
            continue
        seen.add(key)
        mode = {'width': m['width'], 'height': m['height'], 'refresh': round(m['refresh'], 3),
                'preferred': bool(m.get('preferred'))}
        info['modes'].append(mode)
        if m.get('current'):
            info['current'] = {'width': m['width'], 'height': m['height'], 'refresh': round(m['refresh'], 3)}
    with _display_lock:
        if _display_pending['deadline']:
            info['pending'] = {'seconds_left': max(0, int(_display_pending['deadline'] - time.time()))}
    return info


def _closest_mode(width, height, refresh):
    info = display_info()
    candidates = [m for m in info['modes'] if m['width'] == width and m['height'] == height]
    if not candidates:
        return None
    return min(candidates, key=lambda m: abs(m['refresh'] - refresh))


def apply_mode(width, height, refresh, scale):
    if FAKE:
        return
    mode = _closest_mode(width, height, refresh)
    if not mode:
        raise ApiError(f'The TV does not offer {width}x{height}', 400)
    arg = f"{mode['width']}x{mode['height']}@{mode['refresh']:.3f}Hz"
    code, out, err = run(['wlr-randr', '--output', OUTPUT, '--mode', arg, '--scale', f'{scale:g}'],
                         env=wayland_env(), timeout=15)
    if code != 0:
        raise ApiError(f'Could not switch mode: {(err or out).strip()}', 500)


def _revert_display():
    with _display_lock:
        prev = _display_pending['previous']
        _display_pending.update(timer=None, previous=None, candidate=None, deadline=None)
    if prev:
        try:
            apply_mode(prev['width'], prev['height'], prev['refresh'], prev['scale'])
        except ApiError:
            pass


def display_try(body):
    try:
        width, height = int(body['width']), int(body['height'])
        refresh, scale = float(body['refresh']), float(body.get('scale') or 1)
    except (KeyError, ValueError):
        raise ApiError('width, height, refresh and scale are required')
    if not 1 <= scale <= 3:
        raise ApiError('scale must be between 1 and 3')
    info = display_info()
    cur = info.get('current') or {}
    previous = {'width': cur.get('width', width), 'height': cur.get('height', height),
                'refresh': cur.get('refresh', refresh), 'scale': info.get('scale') or 1}
    with _display_lock:
        if _display_pending['timer']:
            _display_pending['timer'].cancel()
            previous = _display_pending['previous'] or previous
    apply_mode(width, height, refresh, scale)
    timer = threading.Timer(15, _revert_display)
    timer.daemon = True
    with _display_lock:
        _display_pending.update(timer=timer, previous=previous, deadline=time.time() + 15,
                                candidate={'width': width, 'height': height, 'refresh': refresh, 'scale': scale})
    timer.start()
    return {'ok': True, 'seconds': 15}


def display_keep(_body):
    with _display_lock:
        cand = _display_pending['candidate']
        if _display_pending['timer']:
            _display_pending['timer'].cancel()
        _display_pending.update(timer=None, previous=None, candidate=None, deadline=None)
    if not cand:
        raise ApiError('No display change is waiting to be kept')

    def keep(s):
        s['display'].update(cand)
    update_settings(keep)
    return {'ok': True}


def display_revert(_body):
    with _display_lock:
        if _display_pending['timer']:
            _display_pending['timer'].cancel()
    _revert_display()
    return {'ok': True}


def auto_scale(width):
    """Interface scale that keeps menus the same physical size on any TV."""
    return 2.0 if width >= 3200 else 1.5 if width >= 2400 else 1.0


def apply_preferred_mode():
    """No saved choice yet: use the TV's own preferred mode. Pi 4 can't drive
    4K above 30 Hz without extra configuration, so cap 4K at 30 Hz."""
    info = display_info()
    modes = info.get('modes') or []
    if not modes:
        raise ApiError('No display modes reported', 500)
    pref = next((m for m in modes if m.get('preferred')), modes[0])
    w, hgt, r = pref['width'], pref['height'], pref['refresh']
    if w >= 3200 and r > 31:
        thirty = [m for m in modes if m['width'] == w and m['height'] == hgt and m['refresh'] <= 31]
        if thirty:
            r = max(m['refresh'] for m in thirty)
        else:
            w, hgt, r = 1920, 1080, 60
    apply_mode(w, hgt, r, auto_scale(w))


def apply_display_from_settings():
    """Called by the session script once the compositor is up."""
    d = load_settings()['display']
    try:
        if d.get('width'):
            apply_mode(d['width'], d['height'], d['refresh'], d['scale'])
        else:
            apply_preferred_mode()
        return
    except ApiError as e:
        print(f'saved mode failed: {e}', file=sys.stderr)
    # Fall back to 1080p at 1x so the screen is never left blank.
    try:
        apply_mode(1920, 1080, 60, 1)
    except ApiError as e:
        print(f'fallback mode failed: {e}', file=sys.stderr)

# ---------------------------------------------------------------- weather

WMO = {
    0: ('Clear', 'clear'), 1: ('Mostly clear', 'clear'), 2: ('Partly cloudy', 'partly'),
    3: ('Cloudy', 'cloudy'), 45: ('Fog', 'fog'), 48: ('Freezing fog', 'fog'),
    51: ('Light drizzle', 'rain'), 53: ('Drizzle', 'rain'), 55: ('Heavy drizzle', 'rain'),
    56: ('Freezing drizzle', 'rain'), 57: ('Freezing drizzle', 'rain'),
    61: ('Light rain', 'rain'), 63: ('Rain', 'rain'), 65: ('Heavy rain', 'rain'),
    66: ('Freezing rain', 'rain'), 67: ('Freezing rain', 'rain'),
    71: ('Light snow', 'snow'), 73: ('Snow', 'snow'), 75: ('Heavy snow', 'snow'), 77: ('Snow grains', 'snow'),
    80: ('Showers', 'rain'), 81: ('Showers', 'rain'), 82: ('Heavy showers', 'rain'),
    85: ('Snow showers', 'snow'), 86: ('Snow showers', 'snow'),
    95: ('Thunderstorms', 'storm'), 96: ('Thunderstorms, hail', 'storm'), 99: ('Thunderstorms, hail', 'storm'),
}
_weather_cache = {'key': None, 'at': 0, 'data': None}


def weather_unit(settings):
    if settings['units'] in ('f', 'c'):
        return settings['units']
    country = (settings['weather'].get('country') or '').upper()
    return 'f' if country in FAHRENHEIT_COUNTRIES else 'c'


def get_weather():
    s = load_settings()
    w = s['weather']
    if w.get('lat') is None or w.get('lon') is None:
        return {'configured': False}
    unit = weather_unit(s)
    key = (w['lat'], w['lon'], unit)
    if _weather_cache['key'] == key and time.time() - _weather_cache['at'] < 600:
        return _weather_cache['data']
    q = urllib.parse.urlencode({
        'latitude': w['lat'], 'longitude': w['lon'],
        'current': 'temperature_2m,weather_code,is_day',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'temperature_unit': 'fahrenheit' if unit == 'f' else 'celsius',
        'timezone': 'auto', 'forecast_days': 1,
    })
    try:
        d = http_json(f'https://api.open-meteo.com/v1/forecast?{q}')
    except (urllib.error.URLError, OSError, ValueError) as e:
        if _weather_cache['data'] and _weather_cache['key'] == key:
            return _weather_cache['data']
        return {'configured': True, 'error': f'Weather unavailable ({e})', 'place': w['name']}
    code = d['current']['weather_code']
    text, icon = WMO.get(code, ('', 'cloudy'))
    data = {'configured': True, 'place': w['name'], 'unit': unit,
            'temp': round(d['current']['temperature_2m']),
            'high': round(d['daily']['temperature_2m_max'][0]),
            'low': round(d['daily']['temperature_2m_min'][0]),
            'conditions': text, 'icon': icon, 'is_day': bool(d['current'].get('is_day', 1))}
    _weather_cache.update(key=key, at=time.time(), data=data)
    return data


def geocode(query):
    query = (query or '').strip()
    if len(query) < 2:
        return []
    q = urllib.parse.urlencode({'name': query, 'count': 8, 'language': 'en', 'format': 'json'})
    d = http_json(f'https://geocoding-api.open-meteo.com/v1/search?{q}')
    out = []
    for r in d.get('results') or []:
        parts = [r.get('name'), r.get('admin1'), r.get('country_code')]
        out.append({'name': ', '.join(p for p in parts if p), 'lat': r['latitude'], 'lon': r['longitude'],
                    'country': r.get('country_code'), 'timezone': r.get('timezone')})
    return out


def set_weather_location(body):
    try:
        loc = {'name': str(body['name'])[:120], 'lat': float(body['lat']), 'lon': float(body['lon']),
               'country': (body.get('country') or '')[:2].upper() or None,
               'timezone': str(body.get('timezone') or '')[:64] or None}
    except (KeyError, ValueError):
        raise ApiError('name, lat and lon are required')

    def upd(s):
        s['weather'] = loc
    update_settings(upd)
    # The location also sets the clock's time zone.
    set_timezone(loc['timezone'])
    _weather_cache['key'] = None
    return public_settings()

# ---------------------------------------------------------------- news

_news_cache = {'at': 0, 'items': [], 'updated': None}


def get_news():
    if time.time() - _news_cache['at'] < 900 and _news_cache['items']:
        return {'source': 'AP News', 'items': _news_cache['items'], 'updated': _news_cache['updated']}
    try:
        root = ET.fromstring(http_get(AP_FEED, timeout=10))
        items = []
        for it in root.iter('item'):
            source = (it.findtext('source') or '').strip()
            if source != 'AP News':
                continue
            title = (it.findtext('title') or '').strip()
            if title.endswith(' - AP News'):
                title = title[:-len(' - AP News')]
            try:
                ts = parsedate_to_datetime(it.findtext('pubDate')).timestamp()
            except (TypeError, ValueError):
                ts = 0
            # Skip AP topic and hub pages ("Texas", "College football | Latest News"):
            # real stories are full sentences.
            if not title or title.startswith('-') or '|' in title or len(title.split()) < 5:
                continue
            items.append({'title': title, 'ts': ts})
        items.sort(key=lambda i: -i['ts'])
        seen, unique = set(), []
        for i in items:
            if i['title'] not in seen:
                seen.add(i['title'])
                unique.append(i)
        _news_cache.update(at=time.time(), items=unique[:30], updated=time.time())
    except (urllib.error.URLError, OSError, ET.ParseError) as e:
        if not _news_cache['items']:
            return {'source': 'AP News', 'items': [], 'updated': None, 'error': str(e)}
    return {'source': 'AP News', 'items': _news_cache['items'], 'updated': _news_cache['updated']}

# ---------------------------------------------------------------- power


def power(body):
    action = body.get('action')
    if action not in ('reboot', 'poweroff'):
        raise ApiError('action must be reboot or poweroff')
    if not FAKE:
        threading.Timer(1.0, lambda: run(['systemctl', action], sudo=True)).start()
    return {'ok': True}

# ---------------------------------------------------------------- cast


def cast_status():
    if FAKE:
        return {'ready': True}
    code, out, _ = run(['systemctl', '--user', 'is-active', 'plex-mpv-shim'])
    return {'ready': out.strip() == 'active'}

# ---------------------------------------------------------------- plex

PLEX_TV = 'https://plex.tv'
_plex_lock = threading.Lock()


def plex_headers(token=None):
    s = load_settings()
    h = {
        'Accept': 'application/json',
        'X-Plex-Product': 'Home Base',
        'X-Plex-Version': '1.0',
        'X-Plex-Client-Identifier': s['plex']['client_id'],
        'X-Plex-Device-Name': hostname(),
        'X-Plex-Platform': 'Linux',
    }
    if token:
        h['X-Plex-Token'] = token
    return h


def plex_link_start(_body):
    d = http_json(f'{PLEX_TV}/api/v2/pins?strong=false', plex_headers(), data=b'', method='POST')
    return {'id': d['id'], 'code': d['code'], 'url': 'https://plex.tv/link'}


def plex_link_check(pin_id):
    d = http_json(f'{PLEX_TV}/api/v2/pins/{int(pin_id)}', plex_headers())
    token = d.get('authToken')
    if not token:
        return {'linked': False}

    def upd(s):
        s['plex']['token'] = token
    update_settings(upd)
    server = plex_choose_server()
    return {'linked': True, 'server': server and server['name']}


def _plex_reachable(uri, token):
    try:
        http_get(f'{uri.rstrip("/")}/identity', plex_headers(token), timeout=4)
        return True
    except (urllib.error.URLError, OSError):
        return False


def _plex_resources(token):
    resources = http_json(f'{PLEX_TV}/api/v2/resources?includeHttps=1&includeRelay=0&includeIPv6=0',
                          plex_headers(token), timeout=15)
    return [r for r in resources if 'server' in (r.get('provides') or '')]


def plex_servers():
    token = load_settings()['plex']['token']
    if not token:
        return []
    current = (load_settings()['plex'].get('server') or {}).get('machine')
    return [{'name': r.get('name'), 'id': r.get('clientIdentifier'), 'owned': bool(r.get('owned')),
             'current': r.get('clientIdentifier') == current} for r in _plex_resources(token)]


def plex_select_server(body):
    sid = body.get('id')

    def upd(s):
        s['plex']['preferred'] = sid
        s['plex']['server'] = None
    update_settings(upd)
    server = plex_choose_server()
    if not server or server['machine'] != sid:
        raise ApiError('That server did not answer on your network', 502)
    return {'server': server['name']}


def plex_choose_server():
    s = load_settings()
    token = s['plex']['token']
    if not token:
        return None
    prefer = s['plex'].get('preferred')
    servers = _plex_resources(token)
    servers.sort(key=lambda r: (r.get('clientIdentifier') != prefer, not r.get('owned', False)))
    for r in servers:
        srv_token = r.get('accessToken') or token
        conns = r.get('connections') or []
        candidates = []
        for c in sorted(conns, key=lambda c: not c.get('local')):
            if c.get('local') and c.get('address'):
                candidates.append(f"http://{c['address']}:{c.get('port', 32400)}")
            if c.get('uri'):
                candidates.append(c['uri'])
        for uri in dict.fromkeys(candidates):
            if _plex_reachable(uri, srv_token):
                server = {'name': r.get('name'), 'uri': uri, 'token': srv_token,
                          'machine': r.get('clientIdentifier')}

                def upd(st):
                    st['plex']['server'] = server
                update_settings(upd)
                return server
    return None


def plex_status():
    p = load_settings()['plex']
    server = p.get('server') or {}
    return {'linked': bool(p.get('token')), 'server': server.get('name'),
            'reachable': bool(server) and _plex_reachable(server['uri'], server['token'])}


def plex_unlink(_body):
    def upd(s):
        s['plex']['token'] = None
        s['plex']['server'] = None
        s['plex']['preferred'] = None
    update_settings(upd)
    return {'ok': True}


def plex_server():
    server = load_settings()['plex'].get('server')
    if not server:
        with _plex_lock:
            server = plex_choose_server()
    if not server:
        raise ApiError('Plex is not linked yet', 409)
    return server

# ---------------------------------------------------------------- http


ROUTES_GET = {
    '/api/settings': lambda q: public_settings(),
    '/api/network': lambda q: network_status(),
    '/api/wifi/scan': lambda q: wifi_scan(),
    '/api/ssh': lambda q: ssh_status(),
    '/api/display': lambda q: display_info(),
    '/api/weather': lambda q: get_weather(),
    '/api/geocode': lambda q: geocode(q.get('q', [''])[0]),
    '/api/news': lambda q: get_news(),
    '/api/plex/status': lambda q: plex_status(),
    '/api/session': lambda q: {'hostname': hostname()},
    '/api/cast': lambda q: cast_status(),
    '/api/plex/servers': lambda q: plex_servers(),
}


def _set_simple(body):
    def upd(s):
        if 'units' in body:
            if body['units'] not in ('auto', 'f', 'c'):
                raise ApiError('units must be auto, f or c')
            s['units'] = body['units']
        if 'clock' in body:
            if body['clock'] not in ('auto', '12', '24'):
                raise ApiError('clock must be auto, 12 or 24')
            s['clock'] = body['clock']
        if 'ticker' in body:
            s['ticker'] = bool(body['ticker'])
        if 'theme' in body:
            if body['theme'] not in THEMES:
                raise ApiError('unknown theme')
            s['theme'] = body['theme']
        if 'wallpaper' in body:
            if body['wallpaper'] not in ('none', 'ambient', 'art'):
                raise ApiError('wallpaper must be none, ambient or art')
            s['wallpaper'] = body['wallpaper']
        if 'edges' in body:
            s['display']['edges'] = max(0, min(5, int(body['edges'])))
    update_settings(upd)
    _weather_cache['key'] = None
    return public_settings()


ROUTES_POST = {
    '/api/settings': _set_simple,
    '/api/weather/location': set_weather_location,
    '/api/wifi/connect': wifi_connect,
    '/api/network/ip': set_ip,
    '/api/ssh': ssh_set,
    '/api/display/try': display_try,
    '/api/display/keep': display_keep,
    '/api/display/revert': display_revert,
    '/api/power': power,
    '/api/plex/link': plex_link_start,
    '/api/plex/unlink': plex_unlink,
    '/api/plex/server': plex_select_server,
    '/api/country': set_country,
    '/api/setup/done': setup_done,
}

MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.ttf': 'font/ttf',
        '.woff2': 'font/woff2', '.png': 'image/png', '.json': 'application/json'}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'HomeBase/1.0'

    def log_message(self, fmt, *args):
        if os.environ.get('HB_DEBUG'):
            super().log_message(fmt, *args)

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            raise ApiError('Request body is not valid JSON')

    def _dispatch(self, fn, *args):
        try:
            self._json(fn(*args))
        except ApiError as e:
            self._json({'error': str(e)}, e.status)
        except urllib.error.HTTPError as e:
            self._json({'error': f'Upstream error {e.code}'}, 502)
        except (urllib.error.URLError, OSError) as e:
            self._json({'error': f'Network error: {e}'}, 502)

    def _allowed(self, post=False, page=False):
        """Guard the API against other sites open in the same browser.

        YouTube, Plex and anything linked from them can send requests to
        127.0.0.1. API and Plex requests must be same-origin, POSTs must carry
        a JSON body type (so the browser's CORS preflight applies), and every
        request must name our own Host (DNS rebinding). The page itself is
        allowed from anywhere: the Home key navigates to it from YouTube and
        Plex, and the UI files hold nothing private.
        """
        hosts = {f'127.0.0.1:{PORT}', f'localhost:{PORT}', f'{HOST}:{PORT}'}
        ok = self.headers.get('Host', '') in hosts
        site = self.headers.get('Sec-Fetch-Site')
        if site and site not in ('same-origin', 'none') and not page:
            ok = False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{h}' for h in hosts}:
            ok = False
        if post and not (self.headers.get('Content-Type') or '').startswith('application/json'):
            ok = False
        if not ok:
            self._json({'error': 'forbidden'}, 403)
        return ok

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        page = not url.path.startswith(('/api/', '/plex/'))
        if not self._allowed(page=page):
            return
        q = urllib.parse.parse_qs(url.query)
        if url.path in ROUTES_GET:
            return self._dispatch(ROUTES_GET[url.path], q)
        if url.path.startswith('/api/plex/link/'):
            return self._dispatch(plex_link_check, url.path.rsplit('/', 1)[1])
        if url.path.startswith('/plex/'):
            return self._plex_proxy(url)
        return self._static(url.path)

    def do_POST(self):
        if not self._allowed(post=True):
            return
        url = urllib.parse.urlsplit(self.path)
        if url.path in ROUTES_POST:
            try:
                body = self._body()
            except ApiError as e:
                return self._json({'error': str(e)}, 400)
            return self._dispatch(ROUTES_POST[url.path], body)
        self._json({'error': 'not found'}, 404)

    def _static(self, path):
        if path == '/':
            path = '/index.html'
        full = os.path.realpath(os.path.join(UI_DIR, path.lstrip('/')))
        if not full.startswith(os.path.realpath(UI_DIR) + os.sep) or not os.path.isfile(full):
            return self._json({'error': 'not found'}, 404)
        with open(full, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', MIME.get(os.path.splitext(full)[1], 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    def _plex_proxy(self, url):
        """Forward /plex/<path> to the Plex server, adding the token.

        Keeps audio and artwork same-origin so the visualizer can analyse
        the audio, and keeps the token out of the browser.
        """
        try:
            server = plex_server()
        except ApiError as e:
            return self._json({'error': str(e)}, e.status)
        except (urllib.error.URLError, OSError) as e:
            return self._json({'error': f'Plex unreachable: {e}'}, 502)
        query = urllib.parse.parse_qsl(url.query)
        query.append(('X-Plex-Token', server['token']))
        target = server['uri'].rstrip('/') + url.path[len('/plex'):] + '?' + urllib.parse.urlencode(query)
        headers = plex_headers(server['token'])
        headers['Accept'] = self.headers.get('Accept') or 'application/json'
        if self.headers.get('Range'):
            headers['Range'] = self.headers['Range']
        req = urllib.request.Request(target, headers=headers)
        try:
            upstream = urllib.request.urlopen(req, timeout=20)
        except urllib.error.HTTPError as e:
            upstream = e
        except (urllib.error.URLError, OSError) as e:
            return self._json({'error': f'Plex unreachable: {e}'}, 502)
        with upstream:
            self.send_response(upstream.status if hasattr(upstream, 'status') else upstream.code)
            for h in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
                if upstream.headers.get(h):
                    self.send_header(h, upstream.headers[h])
            if not upstream.headers.get('Content-Length'):
                self.send_header('Connection', 'close')
                self.close_connection = True
            self.end_headers()
            try:
                while True:
                    chunk = upstream.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'apply-display':
        apply_display_from_settings()
        return
    load_settings()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    print(f'Home Base backend on http://{HOST}:{PORT}', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
