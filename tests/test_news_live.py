"""Keep the home shortcut on CBS's current live broadcast, rather than an archived video."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('homebase_news', Path(__file__).resolve().parents[1] / 'backend/homebase.py')
homebase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(homebase)


class NewsLiveTests(unittest.TestCase):
    def test_prefers_the_live_national_channel_over_events_and_replays(self):
        entries = [
            {'id': 'old_video01', 'title': 'CBS News 24/7', 'live_status': 'was_live'},
            {'id': 'event_live1', 'title': 'Breaking news event', 'live_status': 'is_live'},
            {'id': 'news_live01', 'title': 'LIVE: Breaking News and Top Stories on CBS News 24/7',
             'live_status': 'is_live', 'channel': 'CBS News'},
        ]
        with patch.object(homebase, '_ytdlp_json', return_value={'entries': entries}), \
                patch.object(homebase, '_yt_play', return_value={'ok': True}) as play:
            self.assertEqual(homebase.yt_news_live({}), {'ok': True})
        video = play.call_args.args[0]
        self.assertEqual(video['id'], 'news_live01')
        self.assertEqual(video['channel'], 'CBS News')
        self.assertFalse(video['resume'])

    def test_does_not_play_a_replay_or_upcoming_broadcast_when_offline(self):
        entries = [
            {'id': 'old_video01', 'live_status': 'was_live'},
            {'id': 'futurevid01', 'live_status': 'is_upcoming'},
        ]
        with patch.object(homebase, '_ytdlp_json', return_value={'entries': entries}), \
                patch.object(homebase, '_yt_play') as play:
            with self.assertRaises(homebase.ApiError) as error:
                homebase.yt_news_live({})
            self.assertEqual(error.exception.status, 503)
            play.assert_not_called()

    def test_follows_a_replacement_live_video_on_the_next_launch(self):
        channels = [{'entries': [{'id': vid, 'live_status': 'is_live'}]}
                    for vid in ('news_live01', 'news_live02')]
        with patch.object(homebase, '_ytdlp_json', side_effect=channels), \
                patch.object(homebase, '_yt_play') as play:
            homebase.yt_news_live({})
            homebase.yt_news_live({})
        self.assertEqual([call.args[0]['id'] for call in play.call_args_list], ['news_live01', 'news_live02'])

    def test_refuses_another_launch_before_looking_up_the_channel(self):
        with homebase.claim_tv('another video'), patch.object(homebase, '_ytdlp_json') as lookup:
            with self.assertRaises(homebase.ApiError) as error:
                homebase.yt_news_live({})
            self.assertEqual(error.exception.status, 409)
            lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
