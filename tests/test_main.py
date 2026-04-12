import io
import unittest
from unittest import mock

import main


class MainRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    @mock.patch.object(main, 'process_file', return_value=False)
    def test_storage_events_return_500_on_processing_failure(self, process_file):
        response = self.client.post('/', json={'bucket': 'input-bucket', 'name': 'test.csv'})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_data(as_text=True), 'Processing failed')
        process_file.assert_called_once_with('input-bucket', 'test.csv')

    @mock.patch.object(main.run_pipeline, 'run_pipeline', side_effect=RuntimeError('pipeline failed'))
    def test_upload_returns_json_when_pipeline_raises(self, pipeline):
        response = self.client.post(
            '/api/process',
            data={'file': (io.BytesIO(b'URL\nhttps://example.com\n'), 'sample.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {'error': 'pipeline failed'})
        pipeline.assert_called_once()
