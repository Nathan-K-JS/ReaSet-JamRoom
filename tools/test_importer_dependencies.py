import subprocess
import unittest
from unittest.mock import Mock, patch

import ensure_importer_dependencies as deps


class RuntimeTests(unittest.TestCase):
    @patch.object(deps.metadata, 'version', return_value='0.11.0')
    def test_installed_metadata_still_checks_runtime_and_repairs_failure(self, version):
        with patch.object(deps, 'probe', side_effect=['', 'DLL load failed', '']) as probe, \
                patch.object(deps, 'repair_audio') as repair:
            deps.main()
        repair.assert_called_once_with('DLL load failed')
        self.assertEqual(probe.call_args_list[-1].args, (deps.AUDIO_PROBE,))

    @patch.object(deps.metadata, 'version', return_value='0.11.0')
    def test_failed_optional_repair_warns_and_starts_importer(self, version):
        with patch.object(deps, 'probe', side_effect=['', 'DLL load failed', 'still broken']), \
                patch.object(deps, 'repair_audio', side_effect=OSError('not installed')), \
                patch('builtins.print') as output:
            deps.main()
        self.assertIn('Fadr fixed-tempo', str(output.call_args_list))

    @patch.object(deps.metadata, 'version', return_value='0.11.0')
    def test_core_failure_is_not_hidden_as_optional_audio_failure(self, version):
        with patch.object(deps, 'probe', return_value='numpy missing'), \
                patch.object(deps, 'repair_audio') as repair:
            with self.assertRaisesRegex(RuntimeError, 'numpy missing'):
                deps.main()
        repair.assert_not_called()

    def test_subprocess_crash_and_timeout_are_detected(self):
        with patch.object(deps.subprocess, 'run', return_value=Mock(returncode=-1, stderr='', stdout='')):
            self.assertIn('exited', deps.probe('pass'))
        with patch.object(deps.subprocess, 'run', side_effect=subprocess.TimeoutExpired('python', 120)):
            self.assertIn('timed out', deps.probe('pass'))
