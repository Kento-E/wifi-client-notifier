#!/usr/bin/env python3
"""
Aterm Router Client - Alternative implementation using web scraping

This module provides functions to scrape device information from Aterm router
web interface when API access is not available.
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict


def parse_wireless_lan_status(html_content: str) -> List[Dict[str, str]]:
    """
    Parse wireless LAN status page to extract connected devices.
    
    This function attempts to parse common Aterm router HTML formats.
    
    Args:
        html_content: HTML content from the router's wireless status page
        
    Returns:
        List of dictionaries with device information
    """
    devices = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find tables containing device information
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                
                if len(cells) >= 2:
                    # Look for MAC address pattern
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        
                        # MAC address pattern: XX:XX:XX:XX:XX:XX
                        mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
                        mac_match = re.search(mac_pattern, text)
                        
                        if mac_match:
                            device = {
                                'mac': mac_match.group(0).upper(),
                                'ip': '',
                                'hostname': ''
                            }
                            
                            # Try to get IP address from nearby cells
                            if i + 1 < len(cells):
                                next_text = cells[i + 1].get_text(strip=True)
                                ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                                ip_match = re.search(ip_pattern, next_text)
                                if ip_match:
                                    device['ip'] = ip_match.group(0)
                            
                            # Try to get hostname
                            if i > 0:
                                prev_text = cells[i - 1].get_text(strip=True)
                                if prev_text and not re.search(mac_pattern, prev_text):
                                    device['hostname'] = prev_text
                            
                            devices.append(device)
                            break
        
        return devices
        
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []


def extract_devices_from_json(json_data: Dict) -> List[Dict[str, str]]:
    """
    Extract device information from JSON response.
    
    Some Aterm routers return JSON data for device lists.
    
    Args:
        json_data: JSON response from router
        
    Returns:
        List of dictionaries with device information
    """
    devices = []
    
    try:
        # Handle different JSON structures
        # Common keys: 'clients', 'devices', 'wlan_clients'
        
        if 'clients' in json_data:
            client_list = json_data['clients']
        elif 'devices' in json_data:
            client_list = json_data['devices']
        elif 'wlan_clients' in json_data:
            client_list = json_data['wlan_clients']
        else:
            # Try to find a list in the JSON
            for value in json_data.values():
                if isinstance(value, list):
                    client_list = value
                    break
            else:
                return []
        
        for client in client_list:
            if isinstance(client, dict):
                device = {
                    'mac': client.get('mac', client.get('macaddr', '')).upper(),
                    'ip': client.get('ip', client.get('ipaddr', '')),
                    'hostname': client.get('hostname', client.get('name', ''))
                }
                
                if device['mac']:
                    devices.append(device)
        
        return devices
        
    except Exception as e:
        print(f"Error extracting devices from JSON: {e}")
        return []
