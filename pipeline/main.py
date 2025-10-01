import sys
import os

# Configure logging to write to the mapped directory
import logging

# Basic logging setup
logging.basicConfig(filename='pipeline/run_log.txt', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.utilis import *
from common.azure import *
from common.check_time import *

# Example usage:
if __name__ == "__main__":
    # Get the resource IDs for both VMs and the public IP
    vm1_nic_id, vm2_nic_id, public_ip_id = get_resource_ids()
    
    # Swap the public IP between VMs based on time
    # Note: VM start/stop is now handled by azure_vm_scheduler
    # During daytime:
    # - VM1 will get the main public IP (vm-SelfHostedIR-ip)
    # - VM2 will automatically get the spare IP (vm-SelfHostedIR-2-ip)
    # During nighttime:
    # - VM2 will get the main public IP (vm-SelfHostedIR-ip)
    swap_public_ip(vm1_nic_id, vm2_nic_id, public_ip_id, vm1_name, vm2_name)