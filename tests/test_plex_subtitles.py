"""Exercise Plex's language defaults against real mpv track selection, without opening a window."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('homebase', Path(__file__).resolve().parents[1] / 'backend/homebase.py')
homebase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(homebase)


@unittest.skipUnless(shutil.which('mpv') and shutil.which('ffmpeg'), 'requires mpv and ffmpeg')
class PlexSubtitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='homebase-subtitles-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.subtitle = cls.root / 'captions.srt'
        cls.subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nTest subtitles\n')
        cls.probe = cls.root / 'probe.lua'
        cls.probe.write_text('''
local utils = require('mp.utils')
local function selected(kind)
    for _, track in ipairs(mp.get_property_native('track-list') or {}) do
        if track.type == kind and track.selected then
            return {lang = track.lang, forced = track.forced or false}
        end
    end
    return false
end
mp.register_event('file-loaded', function()
    local result = {audio = selected('audio'), subtitles = selected('sub')}
    if mp.get_opt('probe-manual') == 'yes' then
        mp.commandv('cycle', 'sub')
        result.manual_subtitles = selected('sub')
    end
    local file = assert(io.open(mp.get_opt('probe-output'), 'w'))
    file:write(utils.format_json(result))
    file:close()
    mp.commandv('quit')
end)
''')
        cls.files = {
            'english': cls.make_media('english', ['eng']),
            'japanese': cls.make_media('japanese', ['jpn']),
            'dubbed': cls.make_media('dubbed', ['jpn', 'eng']),
            'french': cls.make_media('french', ['fra']),
            'no_english_subs': cls.make_media('no_english_subs', ['jpn'], ['spa']),
        }

    @classmethod
    def make_media(cls, name, audio_languages, subtitle_languages=('eng', 'eng', 'fra')):
        path = cls.root / f'{name}.mkv'
        cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'anullsrc=r=8000:cl=mono',
               '-i', str(cls.subtitle)]
        for index, language in enumerate(audio_languages):
            cmd += ['-map', '0:a', f'-metadata:s:a:{index}', f'language={language}',
                    f'-disposition:a:{index}', 'default' if index == 0 else '0']
        for index, language in enumerate(subtitle_languages):
            # English subtitles are both default and forced in the fixtures, to catch unwanted autoselection.
            cmd += ['-map', '1:s', f'-metadata:s:s:{index}', f'language={language}',
                    f'-disposition:s:{index}', 'forced' if index == 1 else 'default']
        cmd += ['-t', '1', '-c:a', 'pcm_s16le', '-c:s', 'srt', str(path)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return path

    def play(self, media, country='US', weather_country=None, manual=False):
        settings = {'country': country, 'weather': {'country': weather_country}}
        with patch.object(homebase, 'load_settings', return_value=settings):
            args = homebase._plex_language_args()
        output = self.root / 'result.json'
        output.unlink(missing_ok=True)
        cmd = ['mpv', '--no-config', '--no-terminal', '--load-scripts=no', '--vo=null', '--ao=null',
               '--audio-display=no', f'--script={self.probe}',
               f'--script-opts=probe-output={output},probe-manual={"yes" if manual else "no"}',
               *args, str(self.files[media])]
        subprocess.run(cmd, check=True, capture_output=True, timeout=15)
        return json.loads(output.read_text())

    def test_english_audio_starts_without_default_or_forced_subtitles(self):
        result = self.play('english')
        self.assertEqual(result['audio']['lang'], 'eng')
        self.assertFalse(result['subtitles'])

    def test_foreign_audio_uses_full_english_subtitles(self):
        result = self.play('japanese')
        self.assertEqual(result['audio']['lang'], 'jpn')
        self.assertEqual(result['subtitles']['lang'], 'eng')
        self.assertFalse(result['subtitles']['forced'])

    def test_english_dub_is_preferred_and_does_not_enable_subtitles(self):
        result = self.play('dubbed')
        self.assertEqual(result['audio']['lang'], 'eng')
        self.assertFalse(result['subtitles'])

    def test_other_locations_use_their_primary_language(self):
        result = self.play('english', country='FR')
        self.assertEqual(result['subtitles']['lang'], 'fra')
        self.assertFalse(self.play('french', country='FR')['subtitles'])

    def test_bilingual_locations_use_the_first_language_for_subtitles(self):
        result = self.play('french', country='CA')
        self.assertEqual(result['audio']['lang'], 'fra')
        self.assertEqual(result['subtitles']['lang'], 'eng')

    def test_weather_location_is_used_when_country_is_unset(self):
        result = self.play('english', country=None, weather_country='FR')
        self.assertEqual(result['subtitles']['lang'], 'fra')

    def test_configured_country_takes_precedence_over_weather(self):
        result = self.play('english', country='US', weather_country='FR')
        self.assertFalse(result['subtitles'])

    def test_no_subtitles_are_selected_in_an_unrelated_language(self):
        self.assertFalse(self.play('no_english_subs')['subtitles'])

    def test_unknown_location_defaults_subtitles_off(self):
        for country in (None, 'AQ'):
            with self.subTest(country=country):
                self.assertFalse(self.play('english', country=country)['subtitles'])

    def test_the_subtitle_key_can_still_enable_subtitles_manually(self):
        result = self.play('english', manual=True)
        self.assertFalse(result['subtitles'])
        self.assertEqual(result['manual_subtitles']['lang'], 'eng')


if __name__ == '__main__':
    unittest.main()
