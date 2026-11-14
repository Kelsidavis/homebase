"""Keep access-gated videos out of YouTube browsing and recommendation rows."""

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('homebase_youtube', Path(__file__).resolve().parents[1] / 'backend/homebase.py')
homebase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(homebase)


def tile(vid, **metadata):
    return {'tileRenderer': {
        'onSelectCommand': {'watchEndpoint': {'videoId': vid}},
        'title': {'simpleText': 'A public video about members-only content'},
        **metadata,
    }}


class YouTubeAvailabilityTests(unittest.TestCase):
    def setUp(self):
        homebase._yt_cache.clear()
        self.settings = copy.deepcopy(homebase.DEFAULTS)
        self.settings['country'] = 'US'
        self.settings_patch = patch.object(homebase, 'load_settings', return_value=self.settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(homebase._yt_cache.clear)

    def test_tv_filters_membership_and_premium_badge_styles(self):
        for field, style in [('style', 'BADGE_STYLE_TYPE_MEMBERS_ONLY'),
                             ('style', 'BADGE_STYLE_TYPE_PREMIUM'),
                             ('badgeStyle', 'BADGE_MEMBERS_ONLY')]:
            with self.subTest(style=style):
                page = [tile('lockedvid01', badges=[{'metadataBadgeRenderer': {field: style}}]),
                        tile('publicvid01')]
                self.assertEqual([v['id'] for v in homebase._yt_tv_videos(page)], ['publicvid01'])

    def test_tv_filters_badge_text_and_thumbnail_overlays(self):
        metadata = [
            {'badges': [{'metadataBadgeRenderer': {'label': 'Members only'}}]},
            {'badges': [{'metadataBadgeRenderer': {'accessibilityData': {'label': 'Members-only video'}}}]},
            {'thumbnailOverlays': [{'thumbnailOverlayBottomPanelRenderer': {
                'text': {'runs': [{'text': 'Members only'}]}}}]},
            {'badges': [{'metadataBadgeRenderer': {'icon': {'iconType': 'SPONSORSHIP_STAR'}}}]},
            {'badges': [{'metadataBadgeRenderer': {'icon': {'iconType': 'PRIVACY_PRIVATE'}}}]},
        ]
        for fields in metadata:
            with self.subTest(fields=fields):
                self.assertEqual(homebase._yt_tv_videos([tile('lockedvid01', **fields)]), [])

    def test_public_titles_and_ordinary_badges_are_kept(self):
        page = [tile('publicvid01', badges=[{'metadataBadgeRenderer': {'label': '4K'}}]),
                tile('publicvid02', ownerBadges=[{'metadataBadgeRenderer': {'label': 'Verified'}}])]
        self.assertEqual([v['id'] for v in homebase._yt_tv_videos(page)], ['publicvid01', 'publicvid02'])

    def test_mixed_shelves_keep_public_videos_and_deduplicate(self):
        page = {'contents': [
            {'items': [tile('publicvid01'), tile('lockedvid01', badges=[{
                'metadataBadgeRenderer': {'label': 'Members only'}}])]},
            {'items': [tile('publicvid01'), tile('publicvid02')]},
        ]}
        self.assertEqual([v['id'] for v in homebase._yt_tv_videos(page)], ['publicvid01', 'publicvid02'])

    def test_home_fetches_public_continuation_when_initial_tiles_are_locked(self):
        page = {'sectionListRenderer': {'contents': [{'shelfRenderer': {
            'title': {'simpleText': 'Recommended'},
            'content': {'horizontalListRenderer': {
                'items': [tile('lockedvid01', badges=[{'metadataBadgeRenderer': {'label': 'Members only'}}])],
                'continuations': [{'nextContinuationData': {'continuation': 'more'}}],
            }},
        }}]}}
        more = {'continuationContents': {'horizontalListContinuation': {
            'items': [tile('publicvid01'), tile('publicvid02'), tile('publicvid03')]}}}
        with patch.object(homebase, '_yt_tv_browse', return_value=page), \
                patch.object(homebase, '_yt_tv_post', return_value=more) as post:
            result = homebase.yt_row({'id': ['rec']})
        self.assertEqual([v['id'] for v in result['videos']], ['publicvid01', 'publicvid02', 'publicvid03'])
        post.assert_called_once_with('browse', {'continuation': 'more'})

    def test_ytdlp_browsing_filters_restrictions_and_keeps_unknown_availability(self):
        entries = [{'id': f'video{index:06}', 'availability': availability}
                   for index, availability in enumerate([
                       'subscriber_only', 'premium_only', 'private', 'needs_auth', 'public', 'unlisted', None])]
        entries.append({'id': 'unknownvid1'})
        expected = [e['id'] for e in entries[4:]]
        with patch.object(homebase, '_ytdlp_json', return_value={'entries': entries}):
            self.assertEqual([v['id'] for v in homebase.yt_search({'q': ['science']})], expected)
            self.assertEqual([v['id'] for v in homebase._yt_topic_videos(2)], expected)
            self.assertEqual([v['id'] for v in homebase.yt_channel({'id': ['UCtest']})['videos']], expected)


if __name__ == '__main__':
    unittest.main()
