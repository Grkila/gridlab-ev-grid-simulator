"""State polling must tolerate transient Windows replacement sharing locks."""
from pathlib import Path
import unittest
from unittest.mock import patch
from mvgrid.novi_sad.playground.service import read_json


class StateIOTests(unittest.TestCase):
    def test_read_retries_only_transient_permission_errors(self):
        with patch.object(Path,'read_text',side_effect=[PermissionError('busy'),' {"status":"running"}']) as read, patch('mvgrid.novi_sad.playground.service.time.sleep'):
            self.assertEqual(read_json(Path('state.json')),{'status':'running'})
            self.assertEqual(read.call_count,2)
        with patch.object(Path,'read_text',side_effect=FileNotFoundError), self.assertRaises(FileNotFoundError):
            read_json(Path('missing.json'))
        with patch.object(Path,'read_text',side_effect=PermissionError), patch('mvgrid.novi_sad.playground.service.time.sleep'), self.assertRaises(PermissionError):
            read_json(Path('denied.json'))
