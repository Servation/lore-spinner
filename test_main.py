import unittest
from unittest.mock import patch
import io
import os
import sys

# Import the module to test
import main

class TestMainScreenClear(unittest.TestCase):
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('os.system')
    def test_clear_screen_uses_ansi_escape(self, mock_os_system, mock_stdout):
        # Call the clear_screen function
        main.clear_screen()

        # Verify os.system was NOT called
        mock_os_system.assert_not_called()

        # Verify the ANSI escape sequence was printed
        self.assertEqual(mock_stdout.getvalue(), "\033[2J\033[H")

if __name__ == '__main__':
    unittest.main()
