import sys
from unittest.mock import MagicMock

def pytest_configure(config):
    mock_settings = MagicMock()
    sys.modules['web_search.config.settings'] = mock_settings