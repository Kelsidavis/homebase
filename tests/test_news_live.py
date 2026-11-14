"""Live News must work while CBS's YouTube channel is offline, without playing a replay."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location('homebase_news', Path(__file__).resolve().parents[1] / 'backend/homebase.py')
homebase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(homebase)


class LiveNewsTests(unittest.TestCase):
    def setUp(self):
        self.previous_player = dict(homebase._player)
        self.addCleanup(homebase._player.update, self.previous_player)
        fake = patch.object(homebase, 'FAKE', False)
        fake.start()
        self.addCleanup(fake.stop)
        self.live = {'id': 'CBSN-US', 'is_live': True, 'live_status': 'is_live',
                     'url': 'https://example.com/national-live.m3u8', 'vcodec': 'avc1.640028',
                     'http_headers': {'User-Agent': 'Test player'}}

    def test_resolves_the_official_national_broadcast_without_youtube(self):
        with patch.object(homebase, '_ytdlp_run', return_value=(0, json.dumps(self.live), '')) as resolve, \
                patch.object(homebase, '_ytdlp_json') as youtube:
            streams = homebase._news_live_resolve()
        self.assertEqual(streams['video'], self.live['url'])
        self.assertTrue(streams['live'])
        self.assertIsNone(streams['audio'])
        self.assertEqual(streams['headers'], self.live['http_headers'])
        self.assertIn('https://www.cbsnews.com/live/', resolve.call_args.args[0])
        youtube.assert_not_called()

    def test_supports_separate_audio_and_video_streams(self):
        data = {**self.live, 'requested_formats': [
            {'url': 'https://example.com/video.m3u8', 'vcodec': 'avc1'},
            {'url': 'https://example.com/audio.m3u8', 'vcodec': 'none'},
        ]}
        with patch.object(homebase, '_ytdlp_run', return_value=(0, json.dumps(data), '')):
            streams = homebase._news_live_resolve()
        self.assertEqual(streams['video'], 'https://example.com/video.m3u8')
        self.assertEqual(streams['audio'], 'https://example.com/audio.m3u8')

    def test_does_not_play_a_replay_upcoming_broadcast_or_missing_stream(self):
        for fields in [
            {'is_live': False, 'live_status': 'was_live'},
            {'is_live': False, 'live_status': 'is_upcoming'},
            {'url': None},
        ]:
            data = {**self.live, **fields}
            if data.get('url') is None:
                del data['url']
            with self.subTest(fields=fields), \
                    patch.object(homebase, '_ytdlp_run', return_value=(0, json.dumps(data), '')):
                with self.assertRaises(homebase.ApiError) as error:
                    homebase._news_live_resolve()
                self.assertEqual(error.exception.status, 503)

    def test_extraction_failure_reports_the_cbs_stream_error(self):
        with patch.object(homebase, '_ytdlp_run', return_value=(1, '', 'connection failed')):
            with self.assertRaises(homebase.ApiError) as error:
                homebase._news_live_resolve()
        self.assertEqual(error.exception.status, 503)
        self.assertIn('CBS News 24/7', str(error.exception))

    def test_launch_uses_fresh_live_streams_and_does_not_resume(self):
        streams = [{'video': f'https://example.com/live-{i}.m3u8', 'audio': None, 'headers': {}, 'live': True}
                   for i in range(2)]
        with patch.object(homebase, '_news_live_resolve', side_effect=streams), \
                patch.object(homebase, '_play_stream') as play, patch.object(homebase.threading, 'Thread') as thread:
            for _ in streams:
                self.assertEqual(homebase.news_live({}), {'ok': True, 'title': 'CBS News 24/7'})
        self.assertEqual([call.args for call in play.call_args_list],
                         [(stream, 'CBS News 24/7') for stream in streams])
        self.assertEqual(thread.call_args.kwargs['args'], (play.return_value,))

    def test_refuses_another_launch_before_resolving_the_stream(self):
        with homebase.claim_tv('another video'), patch.object(homebase, '_news_live_resolve') as resolve:
            with self.assertRaises(homebase.ApiError) as error:
                homebase.news_live({})
            self.assertEqual(error.exception.status, 409)
            resolve.assert_not_called()

    def test_live_playback_keeps_hardware_decoding_hls_and_remote_controls(self):
        streams = {'video': self.live['url'], 'audio': None, 'headers': {}, 'live': True}
        with tempfile.TemporaryDirectory(prefix='homebase-live-news-') as conf, \
                patch.object(homebase, 'CONF_DIR', conf), patch.object(homebase, 'player_running', return_value=False), \
                patch.object(homebase, 'wayland_env', return_value={'XDG_RUNTIME_DIR': conf}), \
                patch.object(homebase, '_push_event'), patch.object(homebase, '_mpv_popen') as spawn:
            homebase._play_stream(streams, 'CBS News 24/7')
            self.assertIn('ESC quit', (Path(conf) / 'mpv-input.conf').read_text())
        args = spawn.call_args.args[0]
        self.assertIn('--hwdec=drm,v4l2m2m', args)
        self.assertIn('--demuxer-lavf-o=http_persistent=0,http_multiple=0', args)
        self.assertFalse(any(arg.startswith('--start=') for arg in args))
        self.assertEqual(args[-1], self.live['url'])

    def test_official_stream_updates_player_without_youtube_history(self):
        proc = Mock(returncode=0)
        proc.poll.side_effect = [None, 0]
        homebase._player.update(proc=proc, title='CBS News 24/7', position=0, duration=0)
        properties = {'time-pos': 2.0, 'duration': None, 'pause': False}
        with patch.object(homebase.time, 'sleep'), \
                patch.object(homebase, '_mpv_get', side_effect=properties.get), \
                patch.object(homebase, '_yt_remember') as remember, \
                patch.object(homebase, '_yt_refresh_home') as refresh, \
                patch.object(homebase, '_push_event') as event, patch.object(homebase, '_player_failed'):
            homebase._watch_video(proc)
        self.assertEqual(homebase._player['position'], 2000)
        self.assertIsNone(homebase._player['proc'])
        remember.assert_not_called()
        refresh.assert_not_called()
        event.assert_called_once_with('idle')

    def test_youtube_playback_still_saves_resume_points(self):
        proc = Mock(returncode=0)
        proc.poll.side_effect = [None, 0]
        video = {'id': 'publicvid01'}
        properties = {'time-pos': 42.0, 'duration': 120.0, 'pause': False}
        with patch.object(homebase.time, 'sleep'), \
                patch.object(homebase, '_mpv_get', side_effect=properties.get), \
                patch.object(homebase, '_yt_remember') as remember, \
                patch.object(homebase, '_yt_refresh_home') as refresh, \
                patch.object(homebase, '_push_event'), patch.object(homebase, '_player_failed'):
            homebase._watch_video(proc, video)
        remember.assert_called_with(video, 42.0, 120.0)
        refresh.assert_called_once()


if __name__ == '__main__':
    unittest.main()
