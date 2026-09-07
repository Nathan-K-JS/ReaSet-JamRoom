"""Startup diagnostics must distinguish stale importers from other bind errors."""
import contextlib
import io
import threading
import unittest
from unittest.mock import Mock, patch

import requests
import jamroom_importer_server as server


class StartupTests(unittest.TestCase):
    def test_running_identity_and_duplicate_bind(self):
        with server.ImporterServer(('127.0.0.1', 0), server.Handler) as live:
            thread = threading.Thread(target=live.serve_forever, daemon=True)
            thread.start()
            try:
                port = live.server_address[1]
                with requests.Session() as client:
                    client.trust_env = False
                    reply = client.get(f'http://127.0.0.1:{port}/api/runtime', timeout=3)
                self.assertEqual(reply.status_code, 200)
                self.assertEqual(reply.json(), server.runtime())
                with self.assertRaises(OSError):
                    with server.ImporterServer(('127.0.0.1', port), server.Handler):
                        pass
            finally:
                live.shutdown()
                thread.join(3)

    def diagnostic(self, replies):
        client = Mock()
        client.get.side_effect = replies
        output = io.StringIO()
        with patch.object(server.requests, 'Session') as session, contextlib.redirect_stdout(output):
            session.return_value.__enter__.return_value = client
            server.startup_error(OSError('permission denied (10013)'))
        return output.getvalue()

    def test_unrelated_socket_failure_is_not_called_importer(self):
        output = self.diagnostic([requests.ConnectionError(), requests.ConnectionError()])
        self.assertIn('10013', output)
        self.assertIn('No responding Jam Room Importer', output)
        self.assertNotIn('Existing importer:', output)
        self.assertNotIn('Stop-Process', output)

    def test_legacy_importer_identified_without_runtime_endpoint(self):
        response = Mock()
        response.json.return_value = dict(build='v1.9', reaper=True, ytdlp=True, config=True)
        output = self.diagnostic([requests.HTTPError(), response])
        self.assertIn('Existing importer: v1.9', output)
        self.assertIn('let any import/update finish', output)

    def test_bind_failure_returns_failure_without_opening_browser(self):
        with patch.object(server, 'ImporterServer', side_effect=OSError('occupied')), \
                patch.object(server, 'startup_error'), patch.object(server.webbrowser, 'open') as browser:
            self.assertEqual(server.main(), 1)
            browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
