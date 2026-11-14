"""Recover weather when a provider is offline without mixing locations or units."""

import copy
import importlib.util
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit


spec = importlib.util.spec_from_file_location('homebase_weather', Path(__file__).resolve().parents[1] / 'backend/homebase.py')
homebase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(homebase)


class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.settings = copy.deepcopy(homebase.DEFAULTS)
        self.settings['weather'] = {'name': 'Example City, US', 'lat': 40.0, 'lon': -100.0,
                                    'country': 'US', 'timezone': 'America/Chicago'}
        homebase._weather_cache.update(key=None, at=0, data=None)
        settings_patch = patch.object(homebase, 'load_settings', return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.addCleanup(homebase._weather_cache.update, key=None, at=0, data=None)
        self.now = datetime.fromisoformat('2026-11-14T00:30:00-08:00').timestamp()
        time_patch = patch.object(homebase.time, 'time', return_value=self.now)
        time_patch.start()
        self.addCleanup(time_patch.stop)

    def respond(self, url, headers=None, timeout=10):
        if url.startswith('https://api.open-meteo.com/'):
            raise URLError('TLS handshake timed out')
        if '/points/' in url:
            return {'properties': {'forecast': 'https://api.weather.gov/gridpoints/TOP/31,80/forecast',
                                   'forecastHourly': 'https://api.weather.gov/gridpoints/TOP/31,80/forecast/hourly'}}
        celsius = parse_qs(urlsplit(url).query)['units'] == ['si']
        def period(start, end, day, temp):
            return {'startTime': start, 'endTime': end, 'isDaytime': day, 'temperature': temp,
                    'shortForecast': 'Light Rain Likely'}
        if '/hourly?' in url:
            periods = [period('2026-11-14T00:00:00-08:00', '2026-11-14T01:00:00-08:00', False, 10 if celsius else 50)]
        else:
            periods = [
                period('2026-11-14T00:00:00-08:00', '2026-11-14T06:00:00-08:00', False, 8 if celsius else 47),
                period('2026-11-14T06:00:00-08:00', '2026-11-14T18:00:00-08:00', True, 14 if celsius else 57),
                period('2026-11-14T18:00:00-08:00', '2026-11-15T06:00:00-08:00', False, 9 if celsius else 49),
            ]
        return {'properties': {'periods': periods}}

    def test_open_meteo_remains_primary_and_success_is_cached(self):
        data = {'current': {'temperature_2m': 51.2, 'weather_code': 61, 'is_day': 0},
                'daily': {'temperature_2m_max': [57.4], 'temperature_2m_min': [47.1]}}
        with patch.object(homebase, 'http_json', return_value=data) as fetch:
            result = homebase.get_weather()
            self.assertEqual(homebase.get_weather(), result)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual((result['temp'], result['high'], result['low'], result['unit']), (51, 57, 47, 'f'))
        self.assertIn('temperature_unit=fahrenheit', fetch.call_args.args[0])

    def test_us_fallback_recovers_after_a_tls_timeout_and_caches(self):
        with patch.object(homebase, 'http_json', side_effect=self.respond) as fetch:
            result = homebase.get_weather()
            self.assertEqual(homebase.get_weather(), result)
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual((result['temp'], result['high'], result['low'], result['unit']), (50, 57, 47, 'f'))
        self.assertEqual(result['conditions'], 'Light Rain Likely')
        self.assertEqual(result['icon'], 'rain')
        self.assertFalse(result['is_day'])
        self.assertNotIn('error', result)

    def test_fallback_respects_celsius(self):
        self.settings['units'] = 'c'
        with patch.object(homebase, 'http_json', side_effect=self.respond):
            result = homebase.get_weather()
        self.assertEqual((result['temp'], result['high'], result['low'], result['unit']), (10, 14, 8, 'c'))

    def test_malformed_primary_response_also_uses_fallback(self):
        def respond(url, *args, **kwargs):
            return {'current': None} if 'open-meteo.com' in url else self.respond(url, *args, **kwargs)
        with patch.object(homebase, 'http_json', side_effect=respond):
            self.assertEqual(homebase.get_weather()['temp'], 50)

    def test_does_not_send_non_us_locations_to_nws(self):
        self.settings['weather']['country'] = 'CA'
        with patch.object(homebase, 'http_json', side_effect=URLError('offline')) as fetch:
            result = homebase.get_weather()
        fetch.assert_called_once()
        self.assertIn('error', result)

    def test_keeps_last_good_forecast_if_both_providers_fail(self):
        old = {'temp': 49, 'configured': True}
        homebase._weather_cache.update(key=(40.0, -100.0, 'f'), at=self.now - 700, data=old)
        with patch.object(homebase, 'http_json', side_effect=URLError('offline')):
            self.assertEqual(homebase.get_weather(), old)

    def test_does_not_reuse_other_locations_or_units_during_outages(self):
        for key in [(0, 0, 'f'), (40.0, -100.0, 'c')]:
            with self.subTest(key=key), patch.object(homebase, 'http_json', side_effect=URLError('offline')):
                homebase._weather_cache.update(key=key, at=self.now - 700, data={'temp': 20})
                result = homebase.get_weather()
                self.assertIn('error', result)
                self.assertNotIn('temp', result)

    def test_unconfigured_weather_makes_no_requests(self):
        self.settings['weather']['lat'] = None
        with patch.object(homebase, 'http_json') as fetch:
            self.assertEqual(homebase.get_weather(), {'configured': False})
        fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
