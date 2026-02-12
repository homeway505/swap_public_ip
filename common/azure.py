from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
import logging
import pytz

# Basic logging setup
logging.getLogger("azure").setLevel(logging.WARNING)

import sys
sys.path.append("..")

from common.utilis import (
    subscription_id,
    resource_group,
    vms,
    public_ips,
    schedule,
    schedule_timezone,
    parse_time_str,
)

# Authentication
credential = DefaultAzureCredential()

# Create clients
compute_client = ComputeManagementClient(credential, subscription_id)
network_client = NetworkManagementClient(credential, subscription_id)
compute_client = ComputeManagementClient(credential, subscription_id)

# Get resource IDs
def resolve_vm(vm_label):
    """
    Resolve a VM label to (name, resource_group).
    """
    if vm_label not in vms:
        raise ValueError(f"Unknown VM label: {vm_label}")
    entry = vms[vm_label]
    if isinstance(entry, dict):
        name = entry["name"]
        rg = entry.get("resource_group", resource_group)
    else:
        name = entry
        rg = resource_group
    return name, rg


def resolve_public_ip(ip_label):
    """
    Resolve a public IP label to (name, resource_group).
    """
    if ip_label not in public_ips:
        raise ValueError(f"Unknown public IP label: {ip_label}")
    entry = public_ips[ip_label]
    if isinstance(entry, dict):
        name = entry["name"]
        rg = entry.get("resource_group", resource_group)
    else:
        name = entry
        rg = resource_group
    return name, rg


def extract_resource_group_from_id(resource_id):
    """
    Extract the resource group name from an Azure resource ID.
    """
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return resource_group


def get_nic_id_for_vm_label(vm_label):
    """
    Resolve a VM label to its NIC ID.
    """
    vm_name, vm_rg = resolve_vm(vm_label)
    vm = compute_client.virtual_machines.get(vm_rg, vm_name)
    return vm.network_profile.network_interfaces[0].id

def get_public_ip_id_for_label(ip_label):
    """
    Resolve a public IP label to its resource ID.
    """
    ip_name, ip_rg = resolve_public_ip(ip_label)
    public_ip = network_client.public_ip_addresses.get(ip_rg, ip_name)
    return public_ip.id

def get_current_ip_association(public_ip_label):
    """
    Fetch the current network interface (NIC) that is associated with the public IP.
    Returns the NIC resource ID if associated, or None if no association.
    """
    try:
        # Fetch the public IP resource
        ip_name, ip_rg = resolve_public_ip(public_ip_label)
        public_ip = network_client.public_ip_addresses.get(ip_rg, ip_name)
        
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
    nic_rg = extract_resource_group_from_id(nic_id)
    nic = network_client.network_interfaces.get(nic_rg, nic_id.split('/')[-1])
    
    # Iterate over the IP configurations and remove the public IP association
    updated_ip_configs = []
    for ip_config in nic.ip_configurations:
        if ip_config.public_ip_address:
            logging.info(f"Disassociating public IP from NIC: {nic_id}")
            ip_config.public_ip_address = None
        updated_ip_configs.append(ip_config)

    # Update the NIC with the removed public IP
    nic.ip_configurations = updated_ip_configs
    network_client.network_interfaces.begin_create_or_update(nic_rg, nic.name, nic).result()
    logging.info(f"Public IP disassociated from {nic_id}")


def associate_public_ip(nic_id, public_ip_label):
    """
    Associate the public IP (by label) with the provided NIC.
    """
    nic_rg = extract_resource_group_from_id(nic_id)
    ip_name, ip_rg = resolve_public_ip(public_ip_label)
    nic = network_client.network_interfaces.get(nic_rg, nic_id.split('/')[-1])
    
    # Find the first IP configuration and associate the public IP
    for ip_config in nic.ip_configurations:
        logging.info(f"Associating public IP {ip_name} with NIC: {nic_id}")
        ip_config.public_ip_address = network_client.public_ip_addresses.get(ip_rg, ip_name)
        break

    # Update the NIC with the new public IP association
    network_client.network_interfaces.begin_create_or_update(nic_rg, nic.name, nic).result()
    logging.info(f"Public IP {ip_name} associated with {nic_id}")

def cleanup_secondary_ip_configs(nic_id):
    """
    Remove any secondary IP configurations (ipconfig2, ipconfig3, etc.) from the NIC,
    keeping only the primary ipconfig1.
    """
    try:
        nic_rg = extract_resource_group_from_id(nic_id)
        nic = network_client.network_interfaces.get(nic_rg, nic_id.split('/')[-1])
        
        # Filter to keep only the primary IP configuration
        primary_configs = [ip_config for ip_config in nic.ip_configurations if ip_config.name == "ipconfig1"]
        
        if len(nic.ip_configurations) > len(primary_configs):
            logging.info(f"Removing secondary IP configurations from NIC: {nic_id}")
            nic.ip_configurations = primary_configs
            network_client.network_interfaces.begin_create_or_update(nic_rg, nic.name, nic).result()
            logging.info(f"Secondary IP configurations removed from NIC: {nic_id}")
        else:
            logging.info(f"No secondary IP configurations found on NIC: {nic_id}")
    except Exception as e:
        logging.error(f"Failed to clean up secondary IP configurations: {e}")

def assign_ip_to_vm(vm_label, ip_label):
    """
    Assign a specific public IP label to a specific VM label immediately.
    Returns True if assignment was made, False if already correct.
    """
    target_nic_id = get_nic_id_for_vm_label(vm_label)
    ip_name, ip_rg = resolve_public_ip(ip_label)

    cleanup_secondary_ip_configs(target_nic_id)

    current_nic_id_full = get_current_ip_association(ip_label)
    if current_nic_id_full:
        current_nic_id = extract_nic_id(current_nic_id_full)
        if normalize_nic_id(current_nic_id) == normalize_nic_id(target_nic_id):
            logging.info(f"Public IP {ip_name} already assigned to {target_nic_id}.")
            return False  # No change needed
        disassociate_public_ip(current_nic_id)

    associate_public_ip(target_nic_id, ip_label)
    logging.info(f"Public IP {ip_name} assigned to VM label {vm_label}.")
    return True  # Change was made


def is_time_in_window(current_time, start_time, end_time):
    """
    Check if current_time falls within [start_time, end_time).
    Supports windows that cross midnight.
    Uses half-open interval: start is inclusive, end is exclusive.
    """
    if start_time <= end_time:
        # Normal window (e.g., 09:00-17:00)
        return start_time <= current_time < end_time
    else:
        # Window crosses midnight (e.g., 23:00-06:00)
        return current_time >= start_time or current_time < end_time


def get_active_schedule_entries(now=None):
    """
    Return list of schedule entries that are active at the given time.
    If now is None, uses current time in configured timezone.
    """
    tz = pytz.timezone(schedule_timezone)
    if now is None:
        now = datetime.now(tz)
    current_time = now.time()

    active = []
    for entry in schedule:
        start = parse_time_str(entry["start"])
        end = parse_time_str(entry["end"])
        if is_time_in_window(current_time, start, end):
            active.append(entry)

    return active


def sync_ip_assignments():
    """
    Evaluate the schedule for the current time and converge to the desired state.
    This is the main entry point for the polling-based reconciliation loop.

    Returns a dict with:
        - desired_state: list of (vm, ip) tuples that should be active
        - changes_made: list of (vm, ip) tuples where changes were made
        - already_correct: list of (vm, ip) tuples that were already correct
        - errors: list of error messages
    """
    tz = pytz.timezone(schedule_timezone)
    now = datetime.now(tz)
    current_time_str = now.strftime("%H:%M:%S")

    logging.info(f"Sync started at {current_time_str} ({schedule_timezone})")

    result = {
        "desired_state": [],
        "changes_made": [],
        "already_correct": [],
        "errors": [],
    }

    # Get active schedule entries
    active_entries = get_active_schedule_entries(now)

    if not active_entries:
        logging.info("No active schedule entries at current time. No changes needed.")
        return result

    logging.info(f"Active schedule entries: {len(active_entries)}")
    for entry in active_entries:
        logging.info(f"  - {entry['vm']} should have {entry['ip']} ({entry['start']}-{entry['end']})")

    # Check for conflicts (same IP assigned to multiple VMs)
    ip_to_vms = {}
    for entry in active_entries:
        ip_label = entry["ip"]
        vm_label = entry["vm"]
        if ip_label not in ip_to_vms:
            ip_to_vms[ip_label] = []
        ip_to_vms[ip_label].append(vm_label)

    for ip_label, vm_labels in ip_to_vms.items():
        if len(vm_labels) > 1:
            error_msg = f"Conflict: IP {ip_label} assigned to multiple VMs: {vm_labels}"
            logging.error(error_msg)
            result["errors"].append(error_msg)

    if result["errors"]:
        logging.error("Aborting sync due to configuration conflicts.")
        return result

    # Process each active entry
    for entry in active_entries:
        vm_label = entry["vm"]
        ip_label = entry["ip"]
        result["desired_state"].append((vm_label, ip_label))

        try:
            changed = assign_ip_to_vm(vm_label, ip_label)
            if changed:
                result["changes_made"].append((vm_label, ip_label))
                logging.info(f"Changed: {vm_label} now has {ip_label}")
            else:
                result["already_correct"].append((vm_label, ip_label))
                logging.info(f"No change: {vm_label} already has {ip_label}")
        except Exception as e:
            error_msg = f"Error assigning {ip_label} to {vm_label}: {e}"
            logging.error(error_msg)
            result["errors"].append(error_msg)

    # Summary
    logging.info(f"Sync complete: {len(result['changes_made'])} changes, "
                 f"{len(result['already_correct'])} already correct, "
                 f"{len(result['errors'])} errors")

    return result
