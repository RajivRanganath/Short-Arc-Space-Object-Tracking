import pytest
import os
import requests
import unittest.mock
from unittest.mock import patch, MagicMock
from src.data_loader import download_fengyun_data

@patch("src.data_loader.requests.get")
def test_download_fengyun_data_success(mock_get, tmp_path):
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "LINE 1\nLINE 2\nLINE 3\nLINE 4\nLINE 5\nLINE 6\n"
    mock_get.return_value = mock_response
    
    # Override save_path temporarily for the test
    original_getcwd = os.getcwd
    
    with patch("src.data_loader.os.path.dirname", return_value=str(tmp_path)):
        with patch("src.data_loader.os.makedirs"):
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                download_fengyun_data()
                mock_file.assert_called_once_with("data/fengyun_1c.txt", "w")
                mock_file().write.assert_called_once_with(mock_response.text)

@patch("src.data_loader.requests.get")
def test_download_fengyun_data_error(mock_get):
    # Mock error response
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    download_fengyun_data() # Should just print error and return, not crash

@patch("src.data_loader.requests.get")
def test_download_fengyun_data_exception(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Network error")
    download_fengyun_data() # Should handle exception smoothly
