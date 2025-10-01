# Azure Public IP Swapper

A Python application that automatically manages Azure public IP assignments between two virtual machines based on time schedules. This project focuses on intelligent IP allocation while working in coordination with the `azure_vm_scheduler` for VM lifecycle management.

## 📑 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Architecture](#️-architecture)
  - [Project Structure](#project-structure)
  - [Time-based Logic](#time-based-logic)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
  - [Azure Resources](#azure-resources)
  - [Time Configuration](#time-configuration)
- [Docker Deployment](#-docker-deployment)
  - [Container Features](#container-features)
  - [Docker Compose Services](#docker-compose-services)
- [Core Functions](#-core-functions)
- [Workflow](#-workflow)
- [Logging](#-logging)
- [Testing](#-testing)
  - [Jupyter Notebooks](#jupyter-notebooks)
  - [Manual Testing](#manual-testing)
- [Integration with Azure VM Scheduler](#-integration-with-azure-vm-scheduler)
  - [Coordination Flow](#coordination-flow)
- [Development](#-development)
- [Dependencies](#-dependencies)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Monitoring](#-monitoring)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)
- [Changelog](#-changelog)

## 🚀 Features

- **Time-based IP Assignment**: Automatically assigns public IPs based on business hours
- **Dual IP Management**: Manages both main and spare IP addresses
- **Azure Integration**: Seamless integration with Azure networking services
- **Docker Support**: Containerized deployment with Azure CLI authentication
- **Logging & Monitoring**: Comprehensive logging for operational visibility
- **Network Interface Management**: Handles NIC configurations and IP associations

## 📋 Prerequisites

- Docker and Docker Compose
- Azure CLI installed and authenticated on the host
- Azure subscription with appropriate permissions to manage:
  - Public IP addresses
  - Network interfaces
  - Virtual machines (read access)
- Access to the target Azure resource group

## 🏗️ Architecture

### Project Structure
```
swap_public_ip/
├── common/
│   ├── azure.py          # Azure API interactions
│   ├── utilis.py        # Configuration constants
│   └── check_time.py    # Time-based logic
├── pipeline/
│   ├── main.py           # Main execution script
│   └── run_log.txt       # Execution logs
├── docker-compose.yaml   # Container orchestration
├── Dockerfile           # Container definition
└── requirements.txt    # Python dependencies
```

### Time-based Logic
- **Daytime (7:00 AM - 5:00 PM)**: 
  - VM1 gets the main public IP
  - VM2 gets the spare public IP
- **Nighttime (5:00 PM - 7:00 AM)**:
  - VM2 gets the main public IP
  - VM1 is not assigned any public IP

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd swap_public_ip
```

### 2. Configure Azure Authentication
Ensure Azure CLI is authenticated on the host:
```bash
az login
az account set --subscription "your-subscription-id"
```

### 3. Update Configuration
Edit `common/utilis.py` to match your Azure resources:
```python
subscription_id = "your-subscription-id"
resource_group = "your-resource-group"
vm1_name = "your-vm1-name"
vm2_name = "your-vm2-name"
public_ip_name = "your-main-public-ip"
day_time_spare_ip = "your-spare-public-ip"
```

### 4. Run with Docker
```bash
# Build and start the container
docker-compose up -d

# Execute the IP swapping logic
docker exec swap-ip python pipeline/main.py

# View logs
docker exec swap-ip cat pipeline/run_log.txt
```

### 5. Complete Workflow Script
For a complete workflow that handles container lifecycle:
```bash
#!/bin/bash

cd /home/david/code/swap_public_ip 

docker-compose down 

docker-compose up -d

docker exec -it swap-ip python /app/pipeline/main.py

docker-compose down 
```

### 6. Manual Execution
```bash
# Run directly in the container
docker exec -it swap-ip bash
python pipeline/main.py
```

## 🔧 Configuration

### Azure Resources
The application expects the following Azure resources:

| Resource Type | Purpose | Example Name |
|---------------|---------|--------------|
| Virtual Machine 1 | Primary VM (daytime) | `iaptus-IR` |
| Virtual Machine 2 | Secondary VM (nighttime) | `vm-SelfHostedIR-2` |
| Public IP 1 | Main public IP | `vm-SelfHostedIR-ip` |
| Public IP 2 | Spare public IP | `vm-SelfHostedIR-2-ip` |

### Time Configuration
```python
# Business hours (daytime)
day_start = time(7, 00)  # 7:00 AM
day_end = time(17, 00)   # 5:00 PM
```

## 🐳 Docker Deployment

### Container Features
- **Base Image**: Python 3.10-slim
- **Azure CLI**: Pre-installed for authentication
- **User Management**: Runs as non-root user (david)
- **Volume Mounts**: Azure credentials and application code
- **Network**: Bridge mode with DNS configuration

### Docker Compose Services
```yaml
services:
  swap-ip:
    build: .
    container_name: swap-ip
    volumes:
      - .:/app
      - /home/david/.azure:/home/david/.azure
    environment:
      - PYTHONUNBUFFERED=1
    user: "1000:1000"
```

## 📊 Core Functions

### IP Management
- `get_current_ip_association()` - Check current IP assignments
- `disassociate_public_ip()` - Remove IP from NIC
- `associate_public_ip()` - Assign IP to NIC
- `assign_spare_ip()` - Assign spare IP during daytime

### Network Interface Management
- `cleanup_secondary_ip_configs()` - Remove secondary IP configurations
- `extract_nic_id()` - Parse NIC resource IDs
- `normalize_nic_id()` - Standardize NIC ID format

### Main Logic
- `swap_public_ip()` - Core IP swapping logic
- `is_daytime()` - Time-based decision making
- `get_resource_ids()` - Fetch Azure resource IDs

## 🔄 Workflow

1. **Time Check**: Determine if it's daytime or nighttime
2. **Current State**: Check which VM currently has the main public IP
3. **Decision Logic**: Determine the correct VM for the current time
4. **IP Assignment**: 
   - Disassociate IP from current VM (if needed)
   - Associate IP with correct VM
   - Assign spare IP during daytime
5. **Logging**: Record all operations for monitoring

## 📝 Logging

The application provides comprehensive logging:
- **Execution logs**: `pipeline/run_log.txt`
- **Azure operations**: IP assignments and disassociations
- **Error handling**: Detailed error messages and stack traces
- **Time-based decisions**: Logs showing daytime/nighttime logic

## 🧪 Testing

### Jupyter Notebooks
The `notebook/` directory contains testing notebooks:
- `001.check_ip.ipynb` - IP address checking
- `002.check_time.ipynb` - Time logic testing
- `003.current_assign.ipynb` - Current assignments
- `004.swap.ipynb` - Full swap testing

### Manual Testing
```bash
# Test time logic
docker exec swap-ip python -c "from common.check_time import is_daytime; print(f'Is daytime: {is_daytime()}')"

# Test Azure connectivity
docker exec swap-ip python -c "from common.azure import get_resource_ids; print(get_resource_ids())"
```

## 🔗 Integration with Azure VM Scheduler

This project works in coordination with `azure_vm_scheduler`:

- **VM Scheduler**: Handles VM start/stop based on business hours
- **IP Swapper**: Manages IP assignments between running VMs
- **Separation of Concerns**: Each project has a single responsibility

### Coordination Flow
1. **Scheduler** starts/stops VMs based on time
2. **IP Swapper** assigns appropriate IPs to running VMs
3. **Clean Architecture**: No overlap in functionality

## 🛠️ Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires Azure authentication)
python pipeline/main.py
```

### Container Development
```bash
# Build development image
docker build -t swap-ip-dev .

# Run with volume mount
docker run -it -v $(pwd):/app -v ~/.azure:/home/david/.azure swap-ip-dev bash
```

## 📋 Dependencies

### Python Packages
- `azure-identity` - Azure authentication
- `azure-mgmt-network` - Network management
- `azure-mgmt-compute` - Compute management
- `pytz` - Timezone handling

### System Requirements
- Python 3.10+
- Docker and Docker Compose
- Azure CLI (on host)
- Internet connectivity for Azure API calls

## 🔒 Security

### Authentication
- Uses Azure CLI credentials from host
- No hardcoded credentials in code
- Secure credential mounting in container

### Permissions Required
- **Network Contributor**: Manage public IPs and NICs
- **Virtual Machine Reader**: Read VM information
- **Resource Group Access**: Access to target resource group

## 🚨 Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   # Ensure Azure CLI is logged in
   az login
   az account show
   ```

2. **Permission Denied**
   ```bash
   # Check Azure permissions
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

3. **Container Issues**
   ```bash
   # Check container logs
   docker logs swap-ip
   
   # Rebuild container
   docker-compose down && docker-compose up --build
   ```

### Debug Mode
```bash
# Enable verbose logging
docker exec swap-ip python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from pipeline.main import *
"
```

## 📈 Monitoring

### Log Analysis
```bash
# View recent logs
docker exec swap-ip tail -f pipeline/run_log.txt

# Search for errors
docker exec swap-ip grep -i error pipeline/run_log.txt
```

### Azure Monitoring
- Monitor public IP assignments in Azure Portal
- Set up alerts for IP assignment changes
- Track VM network interface status

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Verify Azure permissions and connectivity
4. Create an issue in the repository

## 📝 Changelog

### [2024-09-27] - VM Control Functionality Removed

#### Changed
- **Removed VM start/stop functionality** from `swap_public_ip` project
- VM control is now handled by the dedicated `azure_vm_scheduler` project
- Updated `swap_public_ip()` function to focus only on IP assignment
- Simplified logic by removing VM lifecycle management

#### Removed Functions
- `shutdown_vm(vm_name)` - VM shutdown functionality
- `start_vm(vm_name)` - VM startup functionality

#### Updated Functions
- `swap_public_ip()` - Now only handles IP assignment, assumes VMs are already running/stopped by scheduler

#### Benefits
- **Separation of Concerns**: VM scheduling handled by dedicated scheduler
- **Simplified Logic**: IP swapping logic is cleaner and more focused
- **Better Architecture**: Each project has a single responsibility
- **Easier Maintenance**: Changes to VM scheduling don't affect IP swapping

#### Dependencies
- This project now depends on `azure_vm_scheduler` for VM lifecycle management
- Ensure `azure_vm_scheduler` is running and managing VM states before running IP swaps

#### Migration Notes
- No breaking changes to the main interface
- `swap_public_ip()` function signature remains the same
- Only internal implementation changed to remove VM control calls
- All IP assignment logic remains intact

---

**Note**: This project works in coordination with `azure_vm_scheduler` for complete VM and IP management. Ensure both projects are properly configured for optimal operation.
