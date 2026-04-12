import unittest
from unittest import mock

import cdn_detector
import run_pipeline


class RunPipelineTests(unittest.TestCase):
    @mock.patch.object(run_pipeline.process_urls, 'process_csv')
    @mock.patch.object(run_pipeline.resolve_ips, 'process_csv')
    @mock.patch.object(run_pipeline.tag_gcp_ips, 'process_csv', side_effect=RuntimeError('tagging failed'))
    def test_run_pipeline_raises_instead_of_exiting(self, tag_ips, resolve_ips, process_urls):
        with self.assertRaises(RuntimeError) as exc:
            run_pipeline.run_pipeline('input.csv', 'output.csv')

        self.assertIn('Pipeline failed during execution', str(exc.exception))
        process_urls.assert_called_once()
        resolve_ips.assert_called_once()
        tag_ips.assert_called_once()


class CdnDetectorTests(unittest.TestCase):
    def setUp(self):
        self.original_ipv4_starts = cdn_detector.ipv4_starts
        self.original_ipv4_ranges = cdn_detector.ipv4_ranges
        self.original_ipv6_starts = cdn_detector.ipv6_starts
        self.original_ipv6_ranges = cdn_detector.ipv6_ranges
        self.original_loaded = cdn_detector.provider_ranges_loaded
        self.original_last_attempt = cdn_detector.last_refresh_attempt

        cdn_detector.ipv4_starts = []
        cdn_detector.ipv4_ranges = []
        cdn_detector.ipv6_starts = []
        cdn_detector.ipv6_ranges = []
        cdn_detector.provider_ranges_loaded = False
        cdn_detector.last_refresh_attempt = 0.0

    def tearDown(self):
        cdn_detector.ipv4_starts = self.original_ipv4_starts
        cdn_detector.ipv4_ranges = self.original_ipv4_ranges
        cdn_detector.ipv6_starts = self.original_ipv6_starts
        cdn_detector.ipv6_ranges = self.original_ipv6_ranges
        cdn_detector.provider_ranges_loaded = self.original_loaded
        cdn_detector.last_refresh_attempt = self.original_last_attempt

    @mock.patch.object(cdn_detector, 'refresh_provider_ranges')
    def test_detect_provider_lazily_loads_ranges(self, refresh_provider_ranges):
        def fake_refresh(force=False):
            cdn_detector.ipv4_starts = [1]
            cdn_detector.ipv4_ranges = [(1, 10, 'Example CDN', 'Global')]
            cdn_detector.provider_ranges_loaded = True

        refresh_provider_ranges.side_effect = fake_refresh

        provider, detail = cdn_detector.detect_provider('0.0.0.5')

        self.assertEqual(provider, 'Example CDN')
        self.assertEqual(detail, 'Global')
        refresh_provider_ranges.assert_called_once_with()
