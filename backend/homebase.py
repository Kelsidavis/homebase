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
import struct
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
    # a Vizio SmartCast TV paired over the network: picture settings Home Base keeps in place
    # ({"ip", "token", "keep": {"more_picture/backlight_control": "Off", "backlight": 65}}); the token stays here
    'tv': {'ip': None, 'token': None, 'keep': {}},
    # YouTube: channels followed here (no Google account) and watch history with resume points
    'youtube': {'subs': [], 'history': []},
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
    # a mode change drops the signal for a moment: ask the TV to come back to this input (HDMI-CEC)
    subprocess.Popen([os.path.join(ROOT, 'bin', 'homebase-cec-active')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


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
    """No saved choice yet: 1080p at 60 Hz when the TV offers it - every TV and cable shows it, while a 4K TV's own
    preferred mode can leave the screen black over an older cable or adapter (4K is a choice in Settings, tried
    with a 15-second revert). Otherwise the TV's preferred mode, with 4K capped at 30 Hz."""
    info = display_info()
    modes = info.get('modes') or []
    if not modes:
        raise ApiError('No display modes reported', 500)
    full_hd = [m for m in modes if m['width'] == 1920 and m['height'] == 1080 and 59 <= m['refresh'] <= 61]
    if full_hd:
        m = min(full_hd, key=lambda m: abs(m['refresh'] - 60))
        apply_mode(1920, 1080, m['refresh'], 1.0)
        return
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


# ---------------------------------------------------------------- remote keys
# Nothing else in a kiosk session acts on volume keys, so Home Base reads the
# remote's key presses itself (the homebase user is in the input group) and
# changes the volume of the default output. Every other key still reaches the
# browser as usual. Key codes are logged so new remotes are easy to map.

KEY_MUTE, KEY_VOLUMEDOWN, KEY_VOLUMEUP, KEY_HOMEPAGE = 113, 114, 115, 172
MEDIA_KEYS = {164: 'playpause', 163: 'next', 165: 'previous', 208: 'forward', 168: 'rewind', 166: 'stop',
              200: 'play', 201: 'pause'}
# Letters, digits, punctuation, space and the keypad are never logged: only keys like media, volume,
# Home, Escape and arrows, which is all that mapping a remote needs.
TYPING_KEYS = set(range(2, 14)) | set(range(16, 28)) | set(range(30, 42)) | set(range(43, 54)) | {57} | set(range(71, 84))
_INPUT_EVENT = struct.Struct('llHHi')
_volume_state = {'changed': 0.0}
# Remote events for the Home Base page, which polls /api/events while it is on screen.
_events = {'seq': 0, 'items': [], 'page_seen': 0.0}
_events_lock = threading.Lock()


def _push_event(name):
    with _events_lock:
        _events['seq'] += 1
        _events['items'] = (_events['items'] + [{'seq': _events['seq'], 'name': name}])[-20:]


def events_since(q):
    since = int((q.get('since') or ['0'])[0] or 0)
    with _events_lock:
        _events['page_seen'] = time.time()
        return {'seq': _events['seq'], 'events': [e for e in _events['items'] if e['seq'] > since]}


def _home_pressed():
    """Home: close a running game, else bring the home screen back."""
    if player_running():
        player_stop()
        return
    proc = _app_proc['proc'] if '_app_proc' in globals() else None
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, 15)
        except OSError:
            pass
        return
    if time.time() - _events['page_seen'] < 2:
        _push_event('home')          # Home Base is on screen: it goes to its home view
    else:
        run(['pkill', '-x', 'chromium'], timeout=5)   # another site: the kiosk restarts on the home screen


def _has_volume_keys(event_name):
    """True if an input device reports any of the volume keys."""
    try:
        with open(f'/sys/class/input/{event_name}/device/capabilities/key') as f:
            words = f.read().split()
    except OSError:
        return False
    bits = 0
    for w in words:   # highest word first, each a hex long
        bits = (bits << (struct.calcsize('l') * 8)) | int(w, 16)
    return any(bits >> code & 1 for code in (KEY_MUTE, KEY_VOLUMEDOWN, KEY_VOLUMEUP, KEY_HOMEPAGE, *MEDIA_KEYS))


def _change_volume(code):
    if code == KEY_MUTE:
        cmd = ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle']
    else:
        step = '5%+' if code == KEY_VOLUMEUP else '5%-'
        cmd = ['wpctl', 'set-volume', '-l', '1.0', '@DEFAULT_AUDIO_SINK@', step]
    run(cmd, timeout=5)
    _volume_state['changed'] = time.time()


def volume_status():
    if FAKE:
        return {'volume': 0.7, 'muted': False, 'changed': _volume_state['changed']}
    code, out, _ = run(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'], timeout=5)
    parts = out.split()
    vol = float(parts[1]) if code == 0 and len(parts) > 1 else None
    return {'volume': vol, 'muted': '[MUTED]' in out, 'changed': _volume_state['changed']}


def _log_key(code, device):
    """Recent non-typing key presses, for mapping a new remote: $XDG_RUNTIME_DIR/homebase-keys.log (last 200)."""
    path = os.path.join(os.environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}', 'homebase-keys.log')
    try:
        with open(path) as f:
            lines = f.read().splitlines()[-199:]
    except OSError:
        lines = []
    lines.append(f'{time.strftime("%H:%M:%S")} key {code} on {device}')
    try:
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass


def watch_keys():
    import select
    open_devs = {}
    last_scan = 0.0
    while True:
        if time.time() - last_scan > 5:   # pick up remotes plugged in later
            last_scan = time.time()
            for path in glob.glob('/dev/input/event*'):
                name = os.path.basename(path)
                if name in open_devs.values() or not _has_volume_keys(name):
                    continue
                try:
                    open_devs[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = name
                except OSError:
                    pass
        if not open_devs:
            time.sleep(5)
            continue
        ready, _, _ = select.select(list(open_devs), [], [], 5)
        for fd in ready:
            try:
                data = os.read(fd, _INPUT_EVENT.size * 64)
            except OSError:   # unplugged
                os.close(fd)
                open_devs.pop(fd, None)
                continue
            for i in range(0, len(data) - _INPUT_EVENT.size + 1, _INPUT_EVENT.size):
                _, _, typ, code, value = _INPUT_EVENT.unpack_from(data, i)
                if typ != 1 or value == 0:   # key presses (1) and auto-repeats (2) only
                    continue
                if value == 1 and code not in TYPING_KEYS:
                    _log_key(code, open_devs.get(fd))
                if value == 1 and code == KEY_HOMEPAGE:
                    _home_pressed()
                elif value == 1 and code in MEDIA_KEYS and not player_running():
                    _push_event(MEDIA_KEYS[code])   # (while a video plays, mpv takes them itself)
                if code in (KEY_VOLUMEUP, KEY_VOLUMEDOWN) or (code == KEY_MUTE and value == 1):
                    _change_volume(code)


# ---------------------------------------------------------------- TV picture keeper (Vizio SmartCast)
# Some TVs drop edited picture settings (a dynamic backlight comes back on, the backlight to 100) after a power cycle
# or a signal change. With a paired Vizio SmartCast TV, Home Base puts the chosen values back when the TV turns on and
# once a minute while it is on, and logs each correction to $XDG_RUNTIME_DIR/homebase-tv.log.

_TV_SSL = None


def _tv_request(tv, path, body=None):
    global _TV_SSL
    if _TV_SSL is None:
        import ssl
        _TV_SSL = ssl.create_default_context()
        _TV_SSL.check_hostname = False
        _TV_SSL.verify_mode = ssl.CERT_NONE   # (the TV's certificate is self-signed; it is only reached on the LAN)
    req = urllib.request.Request(f"https://{tv['ip']}:7345{path}", method='PUT' if body is not None else 'GET',
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={'AUTH': tv['token'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5, context=_TV_SSL) as r:
        return json.loads(r.read() or b'{}')


def _tv_log(msg):
    path = os.path.join(os.environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}', 'homebase-tv.log')
    try:
        with open(path, 'a') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {msg}\n')
    except OSError:
        pass


def _tv_enforce(tv):
    base = '/menu_native/dynamic/tv_settings/picture/'
    for item, want in (tv.get('keep') or {}).items():
        cur = (_tv_request(tv, base + item).get('ITEMS') or [{}])[0]
        if cur.get('VALUE') == want or 'HASHVAL' not in cur:
            continue
        _tv_request(tv, base + item, {'REQUEST': 'MODIFY', 'HASHVAL': cur['HASHVAL'], 'VALUE': want})
        _tv_log(f'{item}: {cur.get("VALUE")!r} -> {want!r}')


def watch_tv():
    was_on, last = False, 0.0
    while True:
        time.sleep(15)
        tv = load_settings()['tv']
        if not tv.get('ip') or not tv.get('token') or not tv.get('keep'):
            continue
        try:
            power = _tv_request(tv, '/state/device/power_mode')
            on = (power.get('ITEMS') or [{}])[0].get('VALUE') == 1
            if on and (not was_on or time.time() - last >= 60):
                if not was_on:
                    _tv_log('TV turned on')
                    time.sleep(5)   # (let it settle on its input and picture mode)
                _tv_enforce(tv)
                last = time.time()
            was_on = on
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            was_on = False   # (off, asleep or unreachable)


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

# ---------------------------------------------------------------- plex video player
# Movies and episodes play full screen in mpv (hardware video decoding) on top of the
# home screen. Progress goes back to the Plex server, so Continue Watching and resume
# work on every device.

MPV_INPUT = '''# Home Base remote keys for mpv
ESC quit
BS quit
q quit
ENTER cycle pause
KP_ENTER cycle pause
SPACE cycle pause
PLAYPAUSE cycle pause
PLAY set pause no
PAUSE set pause yes
STOP quit
LEFT seek -10
RIGHT seek 10
UP seek 60
DOWN seek -60
REWIND seek -10
FORWARD seek 10
PREV seek -60
NEXT seek 60
s cycle sub
a cycle audio
i script-binding stats/display-stats
'''

_player = {'proc': None, 'title': None, 'rating_key': None, 'duration': 0, 'position': 0, 'paused': False}
_player_lock = threading.Lock()


def player_running():
    p = _player['proc']
    return p is not None and p.poll() is None


def player_stop():
    p = _player['proc']
    if p is not None and p.poll() is None:
        p.terminate()


def _mpv_socket():
    return os.path.join(wayland_env()['XDG_RUNTIME_DIR'], 'homebase-mpv.sock')


def _mpv_get(prop):
    """Read a property from the running mpv over its JSON IPC socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
            c.settimeout(1)
            c.connect(_mpv_socket())
            c.sendall(json.dumps({'command': ['get_property', prop]}).encode() + b'\n')
            buf = b''
            while b'\n' not in buf:
                chunk = c.recv(4096)
                if not chunk:
                    break
                buf += chunk
        reply = json.loads(buf.split(b'\n')[0] or b'{}')
        return reply.get('data') if reply.get('error') == 'success' else None
    except (OSError, ValueError):
        return None


def _plex_timeline(server, rating_key, state, position_ms, duration_ms):
    q = urllib.parse.urlencode({'ratingKey': rating_key, 'key': f'/library/metadata/{rating_key}', 'state': state,
                                'time': int(position_ms), 'duration': int(duration_ms)})
    try:
        http_get(f"{server['uri'].rstrip('/')}/:/timeline?{q}", plex_headers(server['token']), timeout=5)
    except (urllib.error.URLError, OSError):
        pass


def _watch_player(proc, server, rating_key, duration_ms):
    """Report progress to Plex every 10 s while mpv plays, then stopped (and watched past 90%)."""
    last_report = 0.0
    while proc.poll() is None:
        time.sleep(1)
        pos = _mpv_get('time-pos')
        paused = bool(_mpv_get('pause'))
        if pos is not None:
            _player.update(position=float(pos) * 1000, paused=paused)
        dur = _mpv_get('duration')
        if dur:
            duration_ms = float(dur) * 1000
            _player['duration'] = duration_ms
        if time.time() - last_report >= 10:
            last_report = time.time()
            _plex_timeline(server, rating_key, 'paused' if paused else 'playing', _player['position'], duration_ms)
    _plex_timeline(server, rating_key, 'stopped', _player['position'], duration_ms)
    if duration_ms and _player['position'] >= 0.9 * duration_ms:
        q = urllib.parse.urlencode({'key': rating_key, 'identifier': 'com.plexapp.plugins.library'})
        try:
            http_get(f"{server['uri'].rstrip('/')}/:/scrobble?{q}", plex_headers(server['token']), timeout=5)
        except (urllib.error.URLError, OSError):
            pass
    with _player_lock:
        if _player['proc'] is proc:
            _player.update(proc=None, title=None, rating_key=None)
    _push_event('idle')


def plex_play(body):
    """Play a movie or episode by its ratingKey, from the start or where it was left."""
    rating_key = str(body.get('key') or '')
    if not rating_key.isdigit():
        raise ApiError('key must be a Plex ratingKey')
    if player_running():
        raise ApiError('Something is already playing', 409)
    server = plex_server()
    meta = http_json(f"{server['uri'].rstrip('/')}/library/metadata/{rating_key}", plex_headers(server['token']))
    items = (meta.get('MediaContainer') or {}).get('Metadata') or []
    if not items:
        raise ApiError('Not found on the Plex server', 404)
    item = items[0]
    try:
        part = item['Media'][0]['Part'][0]
    except (KeyError, IndexError):
        raise ApiError('This item has no playable file')
    offset = int(item.get('viewOffset') or 0) if body.get('resume') else 0
    title = item.get('title') or ''
    if item.get('type') == 'episode':
        title = f"{item.get('grandparentTitle', '')} · S{item.get('parentIndex', '?')}E{item.get('index', '?')} · {title}"
    url = server['uri'].rstrip('/') + part['key']
    # Raspberry Pi 4: H.264 / MPEG-2 / MPEG-4 decode in hardware through V4L2 and HEVC through DRM; their frames go to
    # the compositor as dma-bufs with no GPU pass (mpv's GPU output dropped frames on 1080p). Other codecs decode in
    # software and use the GPU output's fast profile.
    codec = str(item['Media'][0].get('videoCodec') or '').lower()
    if codec in ('h264', 'hevc', 'h265', 'mpeg2video', 'mpeg4'):
        video = ['--hwdec=drm,v4l2m2m', '--vo=dmabuf-wayland']
    else:
        video = ['--hwdec=auto-safe', '--vo=gpu', '--profile=fast']
    env = wayland_env()
    input_conf = os.path.join(CONF_DIR, 'mpv-input.conf')
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(input_conf, 'w') as f:
        f.write(MPV_INPUT)
    cmd = ['mpv', '--fs', '--no-terminal', '--force-window=immediate', '--keep-open=no',
           *video, '--input-default-bindings=no', f'--input-conf={input_conf}',
           f'--input-ipc-server={_mpv_socket()}', f'--title={title}', f'--force-media-title={title}',
           f"--http-header-fields=X-Plex-Token: {server['token']}", '--osd-level=1',
           f'--start={offset / 1000:.1f}', url]
    if FAKE:
        return {'ok': True, 'title': title}
    _push_event('busy')   # the home screen pauses its animations: the GPU is the video's
    with _player_lock:
        proc = subprocess.Popen(cmd, env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _player.update(proc=proc, title=title, rating_key=rating_key, position=offset, paused=False,
                       duration=float(item.get('duration') or 0))
    threading.Thread(target=_watch_player, args=(proc, server, rating_key, float(item.get('duration') or 0)),
                     daemon=True).start()
    return {'ok': True, 'title': title}


# ---------------------------------------------------------------- YouTube
# Browsing through yt-dlp (search, channels) and YouTube's public channel feeds (the latest uploads of followed
# channels); playback in mpv with hardware-decoded H.264 from YouTube's own streams - no ads, no Google account.
# Subscriptions, history and resume points stay in settings.json.

VENV_BIN = os.path.join(ROOT, 'venv', 'bin')
YT_FORMAT = 'bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/b[vcodec^=avc1][height<=1080]/b'
_yt_cache = {}
_yt_cache_lock = threading.Lock()


def _yt_env():
    env = dict(os.environ)
    env['PATH'] = VENV_BIN + os.pathsep + env.get('PATH', '')   # (yt-dlp finds deno, its JavaScript runtime, here)
    return env


def _ytdlp():
    p = os.path.join(VENV_BIN, 'yt-dlp')
    return p if os.path.exists(p) else 'yt-dlp'


def _yt_cached(key, ttl, fn):
    with _yt_cache_lock:
        hit = _yt_cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _yt_cache_lock:
        _yt_cache[key] = (time.time(), value)
    return value


def _ytdlp_json(args, timeout=40):
    code, out, err = run([_ytdlp(), '--flat-playlist', '-J', '--no-warnings', *args], timeout=timeout, env=_yt_env())
    if code != 0:
        raise ApiError(f'YouTube: {(err or out).strip().splitlines()[-1] if (err or out).strip() else "failed"}', 502)
    return json.loads(out)


def _yt_video(e):
    vid = e.get('id') or ''
    return {'id': vid, 'title': e.get('title') or '', 'channel': e.get('channel') or e.get('uploader') or '',
            'channel_id': e.get('channel_id') or '', 'duration': e.get('duration'), 'views': e.get('view_count'),
            'published': e.get('timestamp') or e.get('release_timestamp'),
            'live': e.get('live_status') == 'is_live', 'thumb': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'}


def yt_search(q):
    query = (q.get('q') or [''])[0].strip()
    if not query:
        return []
    def fetch():
        d = _ytdlp_json([f'ytsearch40:{query}'])
        return [_yt_video(e) for e in d.get('entries') or [] if e.get('ie_key') in (None, 'Youtube') and e.get('id')]
    return _yt_cached(('search', query), 600, fetch)


def _yt_avatar(d):
    for t in reversed(d.get('thumbnails') or []):
        if t.get('id') in ('avatar_uncropped', 'avatar') or 'avatar' in str(t.get('id')):
            return t.get('url')
    return None


def yt_channel(q):
    cid = (q.get('id') or [''])[0]
    if not cid.startswith('UC') or not cid.replace('-', '').replace('_', '').isalnum():
        raise ApiError('not a channel id')
    def fetch():
        d = _ytdlp_json(['--playlist-items', '1-40', f'https://www.youtube.com/channel/{cid}/videos'])
        vids = []
        for e in d.get('entries') or []:
            v = _yt_video(e)
            v['channel'] = v['channel'] or d.get('channel') or d.get('uploader') or ''
            v['channel_id'] = cid
            vids.append(v)
        return {'id': cid, 'name': d.get('channel') or d.get('uploader') or d.get('title') or '',
                'avatar': _yt_avatar(d), 'videos': vids}
    data = _yt_cached(('channel', cid), 1800, fetch)
    subs = load_settings()['youtube']['subs']
    return dict(data, subscribed=any(sub.get('id') == cid for sub in subs))


def _yt_feed(cid):
    """A channel's 15 latest uploads from its public Atom feed (fast; no yt-dlp)."""
    def fetch():
        root = ET.fromstring(http_get(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}', timeout=10))
        ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
              'media': 'http://search.yahoo.com/mrss/'}
        out = []
        for en in root.findall('a:entry', ns):
            vid = en.findtext('yt:videoId', default='', namespaces=ns)
            link = en.find('a:link', ns)
            if link is not None and '/shorts/' in (link.get('href') or ''):
                continue   # (Shorts are vertical and seconds long: not for the TV feed)
            try:
                ts = datetime_ts(en.findtext('a:published', default='', namespaces=ns))
            except ValueError:
                ts = None
            stats = en.find('media:group/media:community/media:statistics', ns)
            out.append({'id': vid, 'title': en.findtext('a:title', default='', namespaces=ns),
                        'channel': en.findtext('a:author/a:name', default='', namespaces=ns), 'channel_id': cid,
                        'duration': None, 'views': int(stats.get('views')) if stats is not None and stats.get('views') else None,
                        'published': ts, 'live': False, 'thumb': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'})
        return out
    return _yt_cached(('feed', cid), 1800, fetch)


def datetime_ts(text):
    from datetime import datetime
    return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def yt_home(q):
    subs = load_settings()['youtube']['subs']
    from concurrent.futures import ThreadPoolExecutor
    videos = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for feed in pool.map(lambda sub: _safe(lambda: _yt_feed(sub['id']), []), subs):
            videos.extend(feed)
    videos.sort(key=lambda v: -(v.get('published') or 0))
    return {'subs': len(subs), 'videos': videos[:80]}


def _safe(fn, default):
    try:
        return fn()
    except (ApiError, urllib.error.URLError, OSError, ValueError, ET.ParseError):
        return default


def yt_subs(q):
    return load_settings()['youtube']['subs']


def yt_subscribe(body):
    cid = str(body.get('id') or '')
    if not cid.startswith('UC'):
        raise ApiError('not a channel id')
    entry = {'id': cid, 'name': str(body.get('name') or '')[:120], 'avatar': body.get('avatar')}

    def upd(st):
        subs = [x for x in st['youtube']['subs'] if x.get('id') != cid]
        if body.get('subscribe', True):
            subs.append(entry)
        st['youtube']['subs'] = sorted(subs, key=lambda x: x.get('name', '').lower())
    update_settings(upd)
    return {'subscribed': bool(body.get('subscribe', True))}


def yt_import(body):
    """Subscriptions from Google Takeout's subscriptions.csv (Channel Id, Channel Url, Channel Title)."""
    import csv, io
    rows = list(csv.reader(io.StringIO(str(body.get('csv') or ''))))
    found = [{'id': r[0].strip(), 'name': r[2].strip() if len(r) > 2 else '', 'avatar': None}
             for r in rows if r and r[0].strip().startswith('UC')]

    def upd(st):
        have = {x['id'] for x in st['youtube']['subs']}
        st['youtube']['subs'] = sorted(st['youtube']['subs'] + [f for f in found if f['id'] not in have],
                                       key=lambda x: x.get('name', '').lower())
    update_settings(upd)
    return {'imported': len(found)}


def yt_history(q):
    return load_settings()['youtube']['history']


def _yt_remember(video, position, duration):
    def upd(st):
        hist = [h for h in st['youtube']['history'] if h.get('id') != video['id']]
        hist.insert(0, dict(video, position=position, duration=duration, watched=time.time()))
        st['youtube']['history'] = hist[:200]
    update_settings(upd)


def _watch_yt(proc, video):
    """Remember where a YouTube video was left, every 10 s and when it closes."""
    last = 0.0
    while proc.poll() is None:
        time.sleep(1)
        pos, dur = _mpv_get('time-pos'), _mpv_get('duration')
        if pos is not None:
            _player.update(position=float(pos) * 1000, paused=bool(_mpv_get('pause')))
        if dur:
            _player['duration'] = float(dur) * 1000
        if time.time() - last >= 10 and pos is not None:
            last = time.time()
            _yt_remember(video, float(pos), float(dur or 0))
    _yt_remember(video, _player['position'] / 1000, _player['duration'] / 1000)
    with _player_lock:
        if _player['proc'] is proc:
            _player.update(proc=None, title=None, rating_key=None)
    _push_event('idle')


def yt_play(body):
    vid = str(body.get('id') or '')
    if not (8 <= len(vid) <= 16) or not vid.replace('-', '').replace('_', '').isalnum():
        raise ApiError('not a video id')
    if player_running():
        raise ApiError('Something is already playing', 409)
    video = {k: body.get(k) for k in ('id', 'title', 'channel', 'channel_id', 'thumb')}
    start = 0.0
    if body.get('resume'):
        h = next((h for h in load_settings()['youtube']['history'] if h.get('id') == vid), None)
        if h and h.get('duration') and 30 < h.get('position', 0) < 0.95 * h['duration']:
            start = float(h['position'])
    title = str(video.get('title') or 'YouTube')
    input_conf = os.path.join(CONF_DIR, 'mpv-input.conf')
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(input_conf, 'w') as f:
        f.write(MPV_INPUT)
    cmd = ['mpv', '--fs', '--no-terminal', '--force-window=immediate', '--keep-open=no',
           '--hwdec=drm,v4l2m2m', '--vo=dmabuf-wayland', f'--ytdl-format={YT_FORMAT}',
           f'--script-opts=ytdl_hook-ytdl_path={_ytdlp()}', '--input-default-bindings=no', f'--input-conf={input_conf}',
           f'--input-ipc-server={_mpv_socket()}', f'--title={title}', f'--force-media-title={title}', '--osd-level=1',
           f'--start={start:.1f}', f'https://www.youtube.com/watch?v={vid}']
    if FAKE:
        return {'ok': True, 'title': title}
    env = wayland_env()
    env['PATH'] = VENV_BIN + os.pathsep + env.get('PATH', '')
    _push_event('busy')
    with _player_lock:
        proc = subprocess.Popen(cmd, env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _player.update(proc=proc, title=title, rating_key=None, position=start * 1000, paused=False, duration=0)
    threading.Thread(target=_watch_yt, args=(proc, video), daemon=True).start()
    return {'ok': True, 'title': title, 'start': start}


def _yt_update_tools():
    """YouTube changes often and yt-dlp follows: update it (and its solver scripts) once a day."""
    pip = os.path.join(VENV_BIN, 'pip')
    while os.path.exists(pip):
        run([pip, 'install', '-q', '-U', 'yt-dlp[default]'], timeout=600, env=_yt_env())
        time.sleep(24 * 3600)


def player_status():
    return {'playing': player_running(), 'title': _player['title'], 'position': _player['position'],
            'duration': _player['duration'], 'paused': _player['paused']}

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
    '/api/volume': lambda q: volume_status(),
    '/api/events': events_since,
    '/api/plex/servers': lambda q: plex_servers(),
    '/api/yt/search': yt_search,
    '/api/yt/channel': yt_channel,
    '/api/yt/home': yt_home,
    '/api/yt/subs': yt_subs,
    '/api/yt/history': yt_history,
    '/api/player': lambda q: player_status(),
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
    '/api/plex/play': plex_play,
    '/api/yt/play': yt_play,
    '/api/yt/subscribe': yt_subscribe,
    '/api/yt/import': yt_import,
    '/api/player/stop': lambda b: (player_stop(), {'ok': True})[1],
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
    if not FAKE:
        threading.Thread(target=watch_keys, name='keys', daemon=True).start()
        threading.Thread(target=watch_tv, name='tv', daemon=True).start()
        threading.Thread(target=_yt_update_tools, name='yt-dlp-update', daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    print(f'Home Base backend on http://{HOST}:{PORT}', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
