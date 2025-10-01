from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkInterfaceIPConfiguration
from azure.mgmt.compute import ComputeManagementClient
import logging
# Basic logging setup
logging.getLogger("azure").setLevel(logging.WARNING)

import sys
sys.path.append("..")

from common.utilis import *
from common.check_time import *

# Authentication
credential = DefaultAzureCredential()

# Create clients
compute_client = ComputeManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)
compute_client = ComputeManagementClient(credential, subscription_id)

# Get resource IDs
def get_resource_ids():
    # Fetch the public IP resource
    public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
    public_ip_id = public_ip.id
    
    # Get the network interface for both VMs
    vm1 = compute_client.virtual_machines.get(resource_group, vm1_name)
    vm2 = compute_client.virtual_machines.get(resource_group, vm2_name)

    # Assuming there's only one NIC per VM, fetch its ID
    vm1_nic_id = vm1.network_profile.network_interfaces[0].id
    vm2_nic_id = vm2.network_profile.network_interfaces[0].id
    
    return vm1_nic_id, vm2_nic_id, public_ip_id

def get_current_ip_association(public_ip_id):
    """
    Fetch the current network interface (NIC) that is associated with the public IP.
    Returns the NIC resource ID if associated, or None if no association.
    """
    try:
        # Fetch the public IP resource
        public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
        
        # Check if the public IP is associated with a NIC
        if public_ip.ip_configuration:
            nic_id = public_ip.ip_configuration.id
            logging.info(f"Public IP is currently associated with NIC: {nic_id}")
            return nic_id
        else:
            logging.warning("Public IP is not associated with any NIC.")
            return None
    except Exception as e:
        logging.error(f"Failed to retrieve public IP association: {e}")
        return None

def extract_nic_id(nic_id_full):
    """
    Extract the NIC resource ID from the full NIC path returned by the Azure SDK.
    Example input:
    /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkInterfaces/{nic_name}/ipConfigurations/{ip_config_name}
    Example output:
    /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkInterfaces/{nic_name}
    """
    # Split the full NIC ID at the '/ipConfigurations/' part and return the first segment
    return nic_id_full.split('/ipConfigurations/')[0]

def check_current_ip_assignment(vm1_nic_id, vm2_nic_id, public_ip_id):
    """
    Check which VM currently has the public IP by comparing NIC IDs.
    """
    current_nic_id_full = get_current_ip_association(public_ip_id)
    
    if current_nic_id_full:
        # Extract the base NIC ID for comparison
        current_nic_id = extract_nic_id(current_nic_id_full)
        
        # Normalize NIC IDs
        vm1_nic_id_normalized = normalize_nic_id(vm1_nic_id)
        vm2_nic_id_normalized = normalize_nic_id(vm2_nic_id)
        current_nic_id_normalized = normalize_nic_id(current_nic_id)

        # Print for debugging
        logging.info(f"Normalized Current NIC ID: {current_nic_id_normalized}")
        logging.info(f"Normalized VM1 NIC ID: {vm1_nic_id_normalized}")
        logging.info(f"Normalized VM2 NIC ID: {vm2_nic_id_normalized}")
        
        # Compare the normalized NIC IDs
        if current_nic_id_normalized == vm1_nic_id_normalized:
            logging.info("Public IP is currently assigned to VM1.")
        elif current_nic_id_normalized == vm2_nic_id_normalized:
            logging.info("Public IP is currently assigned to VM2.")
        else:
            logging.warning("Public IP is not currently assigned to either VM1 or VM2.")
    else:
        logging.warning("Public IP is not associated with any NIC.")

def normalize_nic_id(nic_id):
    """
    Normalize the NIC ID by trimming whitespace and slashes, and converting to lowercase.
    """
    return nic_id.strip().rstrip('/').lower()

# VM start/stop functionality removed - now handled by azure_vm_scheduler

def disassociate_public_ip(nic_id):
    """
    Disassociate the public IP from the provided NIC.
    """
    nic = network_client.network_interfaces.get(resource_group, nic_id.split('/')[-1])
    
    # Iterate over the IP configurations and remove the public IP association
    updated_ip_configs = []
    for ip_config in nic.ip_configurations:
        if ip_config.public_ip_address:
            logging.info(f"Disassociating public IP from NIC: {nic_id}")
            ip_config.public_ip_address = None
        updated_ip_configs.append(ip_config)

    # Update the NIC with the removed public IP
    nic.ip_configurations = updated_ip_configs
    network_client.network_interfaces.begin_create_or_update(resource_group, nic.name, nic).result()
    logging.info(f"Public IP disassociated from {nic_id}")


def associate_public_ip(nic_id, public_ip_id):
    """
    Associate the public IP with the provided NIC.
    """
    nic = network_client.network_interfaces.get(resource_group, nic_id.split('/')[-1])
    
    # Find the first IP configuration and associate the public IP
    for ip_config in nic.ip_configurations:
        logging.info(f"Associating public IP {public_ip_id} with NIC: {nic_id}")
        ip_config.public_ip_address = network_client.public_ip_addresses.get(resource_group, public_ip_name)
        break

    # Update the NIC with the new public IP association
    network_client.network_interfaces.begin_create_or_update(resource_group, nic.name, nic)
    logging.info(f"Public IP {public_ip_id} associated with {nic_id}")

def get_spare_ip_id():
    """
    Get the resource ID for the spare IP address.
    """
    try:
        spare_ip = network_client.public_ip_addresses.get(resource_group, day_time_spare_ip)
        return spare_ip.id
    except Exception as e:
        logging.error(f"Failed to retrieve spare IP: {e}")
        return None

def assign_spare_ip(vm2_nic_id):
    """
    Assign the spare IP to VM2 during daytime.
    """
    try:
        spare_ip_id = get_spare_ip_id()
        if spare_ip_id:
            nic = network_client.network_interfaces.get(resource_group, vm2_nic_id.split('/')[-1])
            
            # Always use the primary IP configuration (ipconfig1)
            primary_ip_config_name = "ipconfig1"
            
            # Find the primary IP configuration
            for ip_config in nic.ip_configurations:
                if ip_config.name == primary_ip_config_name:
                    # Update the primary IP configuration with the spare IP
                    ip_config.public_ip_address = network_client.public_ip_addresses.get(resource_group, day_time_spare_ip)
                    break
            
            # Update the NIC
            network_client.network_interfaces.begin_create_or_update(resource_group, nic.name, nic).result()
            logging.info(f"Spare IP {day_time_spare_ip} assigned to VM2 on primary IP configuration")
            return True
    except Exception as e:
        logging.error(f"Failed to assign spare IP to VM2: {e}")
    return False

def cleanup_secondary_ip_configs(nic_id):
    """
    Remove any secondary IP configurations (ipconfig2, ipconfig3, etc.) from the NIC,
    keeping only the primary ipconfig1.
    """
    try:
        nic = network_client.network_interfaces.get(resource_group, nic_id.split('/')[-1])
        
        # Filter to keep only the primary IP configuration
        primary_configs = [ip_config for ip_config in nic.ip_configurations if ip_config.name == "ipconfig1"]
        
        if len(nic.ip_configurations) > len(primary_configs):
            logging.info(f"Removing secondary IP configurations from NIC: {nic_id}")
            nic.ip_configurations = primary_configs
            network_client.network_interfaces.begin_create_or_update(resource_group, nic.name, nic).result()
            logging.info(f"Secondary IP configurations removed from NIC: {nic_id}")
        else:
            logging.info(f"No secondary IP configurations found on NIC: {nic_id}")
    except Exception as e:
        logging.error(f"Failed to clean up secondary IP configurations: {e}")

def swap_public_ip(vm1_nic_id, vm2_nic_id, public_ip_id, vm1_name, vm2_name):
    """
    Swap the public IP between VM1 and VM2 based on the current time.
    Note: VM start/stop is now handled by azure_vm_scheduler.
    During daytime:
    1. Main public IP is assigned to VM1
    2. Spare IP is assigned to VM2
    During nighttime:
    - Main public IP is assigned to VM2
    """
    # First, clean up any secondary IP configurations
    cleanup_secondary_ip_configs(vm1_nic_id)
    cleanup_secondary_ip_configs(vm2_nic_id)
    
    # Check if it is daytime or nighttime
    is_day = is_daytime()
    
    # Determine the correct NIC and VM that should have the public IP
    correct_nic_id = vm1_nic_id if is_day else vm2_nic_id
    current_nic_id_full = get_current_ip_association(public_ip_id)
    
    if current_nic_id_full:
        current_nic_id = extract_nic_id(current_nic_id_full)

        if current_nic_id == correct_nic_id:
            logging.info(f"Public IP is already correctly assigned to {correct_nic_id}. No changes needed.")
            # During daytime, assign spare IP to VM2 if it's not the one with the main IP
            if is_day:
                assign_spare_ip(vm2_nic_id)
        else:
            # First, disassociate the public IP from current NIC
            disassociate_public_ip(current_nic_id)
            
            # Assign public IP to the correct NIC (VM start/stop handled by azure_vm_scheduler)
            associate_public_ip(correct_nic_id, public_ip_id)
            logging.info(f"Public IP has been reassigned to {correct_nic_id}.")
            
            # During daytime, also assign spare IP to VM2
            if is_day:
                assign_spare_ip(vm2_nic_id)
    else:
        # If no NIC has the public IP, assign to the correct one
        associate_public_ip(correct_nic_id, public_ip_id)
        logging.info(f"Public IP assigned to {correct_nic_id} because no NIC had it.")
        
        # During daytime, also assign spare IP to VM2
        if is_day:
            assign_spare_ip(vm2_nic_id)
