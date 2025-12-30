#!/usr/bin/env python3
"""
Aterm WiFi Client Notifier

This script monitors an Aterm router for new WiFi connections and sends
email notifications when specific devices connect.
"""

import requests
import time
import smtplib
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Set, Optional
import hashlib
from aterm_scraper import parse_wireless_lan_status, extract_devices_from_json


class AtermRouter:
    """Interface to communicate with Aterm router."""
    
    def __init__(self, router_ip: str, username: str, password: str):
        """
        Initialize router connection.
        
        Args:
            router_ip: IP address of the router
            username: Admin username
            password: Admin password
        """
        self.router_ip = router_ip
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"http://{router_ip}"
        
    def login(self) -> bool:
        """
        Login to the router.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Note: This is a generic implementation. 
            # Actual Aterm routers may require different authentication methods
            # Users may need to customize this based on their specific router model
            login_url = f"{self.base_url}/index.cgi/login"
            
            # Create password hash (common for older Aterm routers)
            # NOTE: MD5 is used here for compatibility with older Aterm router models
            # that require MD5 hashing. This is not for security purposes as the
            # connection is over HTTP. For newer models, see CUSTOMIZATION.md for
            # examples using SHA-256 or other methods.
            password_hash = hashlib.md5(self.password.encode()).hexdigest()
            
            login_data = {
                'user': self.username,
                'passwd': password_hash
            }
            
            response = self.session.post(login_url, data=login_data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logging.error(f"Login failed: {e}")
            return False
    
    def get_connected_devices(self) -> List[Dict[str, str]]:
        """
        Get list of currently connected WiFi devices.
        
        Returns:
            List of dictionaries containing device information
            Each dict has keys: 'mac', 'ip', 'hostname'
        """
        try:
            # Note: The actual endpoint varies by Aterm model
            # Common endpoints: /wlmaclist.cgi, /index.cgi/wireless_status
            # Users may need to customize this for their specific model
            
            devices_url = f"{self.base_url}/index.cgi/wireless_client_list"
            response = self.session.get(devices_url, timeout=10)
            
            if response.status_code != 200:
                logging.warning(f"Failed to get device list: {response.status_code}")
                return []
            
            # Parse the response - this will vary by router model
            # This is a placeholder implementation
            devices = self._parse_device_list(response.text)
            return devices
            
        except Exception as e:
            logging.error(f"Error getting connected devices: {e}")
            return []
    
    def _parse_device_list(self, html_content: str) -> List[Dict[str, str]]:
        """
        Parse HTML response to extract device information.
        
        This method first tries to parse as JSON, then falls back to HTML scraping.
        
        Args:
            html_content: HTML/JSON response from router
            
        Returns:
            List of device dictionaries
        """
        devices = []
        
        # Try parsing as JSON first
        try:
            json_data = json.loads(html_content)
            devices = extract_devices_from_json(json_data)
            if devices:
                logging.debug(f"Parsed {len(devices)} devices from JSON")
                return devices
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fall back to HTML scraping
        devices = parse_wireless_lan_status(html_content)
        if devices:
            logging.debug(f"Parsed {len(devices)} devices from HTML")
        
        return devices


class EmailNotifier:
    """Handle email notifications via SMTP."""
    
    def __init__(self, smtp_server: str, smtp_port: int, smtp_user: str, 
                 smtp_password: str, sender_email: str, recipient_emails: List[str],
                 use_tls: bool = True):
        """
        Initialize email notifier.
        
        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            sender_email: Sender email address
            recipient_emails: List of recipient email addresses
            use_tls: Whether to use TLS (default: True)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_email = sender_email
        self.recipient_emails = recipient_emails
        self.use_tls = use_tls
    
    def send_notification(self, device_info: Dict[str, str]) -> bool:
        """
        Send email notification about new device connection.
        
        Args:
            device_info: Dictionary containing device information
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipient_emails)
            msg['Subject'] = f"新しいWiFi接続を検出 - {device_info.get('hostname', 'Unknown Device')}"
            
            # Create email body
            body = self._create_email_body(device_info)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Send email
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logging.info(f"Notification sent for device: {device_info.get('mac', 'Unknown')}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
    
    def _create_email_body(self, device_info: Dict[str, str]) -> str:
        """
        Create email body text.
        
        Args:
            device_info: Dictionary containing device information
            
        Returns:
            Formatted email body
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        body = f"""
新しいWiFi接続が検出されました

検出時刻: {timestamp}
MACアドレス: {device_info.get('mac', 'Unknown')}
IPアドレス: {device_info.get('ip', 'Unknown')}
ホスト名: {device_info.get('hostname', 'Unknown')}

---
Aterm WiFi Client Notifier
"""
        return body.strip()


class WiFiMonitor:
    """Monitor WiFi connections and send notifications."""
    
    def __init__(self, config_path: str):
        """
        Initialize monitor with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self._setup_logging()  # Setup logging before anything else
        self.router = None
        self.notifier = None
        self.known_devices: Set[str] = set()
        self.monitored_macs: Set[str] = set()
        self._initialize_components()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            # Use print here since logging is not yet configured
            print(f"Failed to load config: {e}")
            raise
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('log_level', 'INFO')
        log_file = self.config.get('log_file', 'wifi_notifier.log')
        
        # Clear any existing handlers and configure from scratch
        logging.root.handlers = []
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )
    
    def _initialize_components(self):
        """Initialize router and email notifier components."""
        # Initialize router connection
        router_config = self.config['router']
        self.router = AtermRouter(
            router_config['ip'],
            router_config['username'],
            router_config['password']
        )
        
        # Initialize email notifier
        email_config = self.config['email']
        self.notifier = EmailNotifier(
            email_config['smtp_server'],
            email_config['smtp_port'],
            email_config['smtp_user'],
            email_config['smtp_password'],
            email_config['sender_email'],
            email_config['recipient_emails'],
            email_config.get('use_tls', True)
        )
        
        # Load monitored devices (if specified)
        monitored_devices = self.config.get('monitored_devices', [])
        self.monitored_macs = {mac.lower() for mac in monitored_devices}
        
        logging.info("Components initialized successfully")
    
    def start(self):
        """Start monitoring WiFi connections."""
        logging.info("Starting WiFi monitor")
        
        # Login to router
        if not self.router.login():
            logging.error("Failed to login to router")
            return
        
        logging.info("Successfully logged in to router")
        
        # Get initial device list
        initial_devices = self.router.get_connected_devices()
        self.known_devices = {dev['mac'].lower() for dev in initial_devices}
        logging.info(f"Initial devices: {len(self.known_devices)}")
        
        # Start monitoring loop
        check_interval = self.config.get('check_interval', 60)
        
        try:
            while True:
                self._check_for_new_devices()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logging.info("Stopping WiFi monitor")
        except Exception as e:
            logging.error(f"Monitor error: {e}")
    
    def _check_for_new_devices(self):
        """Check for new device connections."""
        try:
            current_devices = self.router.get_connected_devices()
            current_macs = {dev['mac'].lower() for dev in current_devices}
            
            # Find new devices
            new_macs = current_macs - self.known_devices
            
            for mac in new_macs:
                # Find device info
                device_info = next((dev for dev in current_devices if dev['mac'].lower() == mac), None)
                
                if device_info:
                    # Check if we should notify about this device
                    should_notify = (
                        not self.monitored_macs or  # Notify all if no filter
                        mac in self.monitored_macs   # Or if in monitored list
                    )
                    
                    if should_notify:
                        logging.info(f"New device detected: {mac}")
                        self.notifier.send_notification(device_info)
                    else:
                        logging.debug(f"New device detected but not monitored: {mac}")
                    
                    self.known_devices.add(mac)
            
            # Remove disconnected devices from known set
            disconnected = self.known_devices - current_macs
            if disconnected:
                logging.info(f"Devices disconnected: {len(disconnected)}")
                self.known_devices = current_macs
                
        except Exception as e:
            logging.error(f"Error checking for new devices: {e}")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python wifi_notifier.py <config_file>")
        print("Example: python wifi_notifier.py config.json")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        monitor = WiFiMonitor(config_file)
        monitor.start()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
