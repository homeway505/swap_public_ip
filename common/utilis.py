# Configuration loader for Azure resources
import yaml
from datetime import time
from pathlib import Path


def parse_time_str(value):
    """
    Parse a time string in HH:MM format into a datetime.time object.
    """
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {value}")
    return time(int(parts[0]), int(parts[1]))


def load_config():
    """
    Load configuration from config/config.yml file.
    Returns a dictionary with all configuration values.
    """
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "config.yml"
    
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
    
    # VM configuration (label -> Azure VM name)
    vms = config['vms']
    
    # Public IP configuration (label -> Azure public IP name)
    public_ips = config['public_ips']

    # Schedule configuration
    schedule = config.get('schedule', [])
    schedule_timezone = config.get('schedule_timezone', 'Europe/London')

except Exception as e:
    raise RuntimeError(f"Failed to load configuration: {e}")
