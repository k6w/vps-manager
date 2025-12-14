import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from vps_manager.core import VPSManager, Domain

class TestVPSManager(unittest.TestCase):
    def setUp(self):
        # Mock all the file operations and system calls in __init__
        with patch('vps_manager.core.VPSManager.setup_directories'), \
             patch('vps_manager.core.VPSManager.load_config'), \
             patch('vps_manager.core.VPSManager.load_domains'):
            self.manager = VPSManager()

    def test_validate_domain(self):
        """Test domain validation logic"""
        self.assertTrue(self.manager.validate_domain("example.com"))
        self.assertTrue(self.manager.validate_domain("sub.example.com"))
        self.assertTrue(self.manager.validate_domain("my-site.org"))
        self.assertTrue(self.manager.validate_domain("localhost"))
        
        self.assertFalse(self.manager.validate_domain("-start.com"))
        self.assertFalse(self.manager.validate_domain("end-.com"))
        self.assertFalse(self.manager.validate_domain("invalid_char.com"))
        self.assertFalse(self.manager.validate_domain(""))

    def test_validate_port(self):
        """Test port validation"""
        self.assertTrue(self.manager.validate_port(80))
        self.assertTrue(self.manager.validate_port(8080))
        self.assertTrue(self.manager.validate_port(65535))
        
        self.assertFalse(self.manager.validate_port(0))
        self.assertFalse(self.manager.validate_port(65536))
        self.assertFalse(self.manager.validate_port(-1))

    @patch('vps_manager.core.VPSManager.run_command')
    def test_check_nginx_status(self, mock_run):
        """Test NGINX status check"""
        mock_run.return_value = (True, "active")
        is_active, status = self.manager.get_nginx_status()
        self.assertTrue(is_active)
        self.assertEqual(status, "active")

        mock_run.return_value = (False, "inactive")
        is_active, status = self.manager.get_nginx_status()
        self.assertFalse(is_active)

    def test_domain_management(self):
        """Test adding and retrieving domains"""
        domain = Domain("test.com", 3000)
        self.manager.domains.append(domain)
        
        self.assertTrue(self.manager.domain_exists("test.com"))
        self.assertFalse(self.manager.domain_exists("other.com"))
        
        retrieved = self.manager.get_domain("test.com")
        self.assertEqual(retrieved.port, 3000)

if __name__ == '__main__':
    unittest.main()
