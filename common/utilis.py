# Configuration loader for Azure resources
import os
import yaml
from datetime import time
from pathlib import Path

def load_config():
    """
    Load configuration from secrets/config.yml file.
    Returns a dictionary with all configuration values.
    """
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    config_path = project_root / "secrets" / "config.yml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    return config

# Load configuration
try:
    config = load_config()
    
    # Azure configuration
    subscription_id = config['azure']['subscription_id']
    resource_group = config['azure']['resource_group']
    
    # VM configuration
    vm1_name = config['vms']['vm1_name']
    vm2_name = config['vms']['vm2_name']
    
    # Public IP configuration
    public_ip_name = config['public_ips']['main_ip']
    day_time_spare_ip = config['public_ips']['spare_ip']
    
    # Time configuration
    day_start_str = config['schedule']['day_start']
    day_end_str = config['schedule']['day_end']
    
    # Parse time strings to time objects
    day_start = time(int(day_start_str.split(':')[0]), int(day_start_str.split(':')[1]))
    day_end = time(int(day_end_str.split(':')[0]), int(day_end_str.split(':')[1]))
    
except Exception as e:
    raise RuntimeError(f"Failed to load configuration: {e}")