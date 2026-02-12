# Azure Public IP Swapper - Specification

## Overview

The Azure Public IP Swapper is a Python application that automatically manages Azure public IP assignments between multiple virtual machines based on configurable time schedules. It enables dynamic reallocation of limited public IP resources across VMs according to business hours and operational requirements.

## Problem Statement

Organizations often have:
- Limited public IP addresses due to cost or allocation constraints
- Multiple VMs that need public IP access at different times
- Different workloads running at different times of day (e.g., integration runtime during business hours, batch processing overnight)

Manually reassigning public IPs is error-prone and operationally burdensome. This tool automates the process based on predefined schedules.

## Goals

1. **Declarative Configuration**: Define the desired end-state (which VM should have which IP at what times) and let the system converge to it
2. **End-State Driven**: The system evaluates current state vs desired state and makes necessary changes
3. **Idempotent Operations**: Safe to run repeatedly - no changes made if already in desired state
4. **Conflict Prevention**: Detect and prevent assigning the same IP to multiple VMs
5. **Flexible Configuration**: Support arbitrary VM and IP mappings via YAML configuration
6. **Timezone Awareness**: Evaluate schedules in configurable timezones
7. **Self-Healing**: Automatically correct drift from desired state on each polling interval
8. **Manual Override**: Provide CLI for immediate manual assignments when needed

## Architecture

### Separation of Concerns

This project follows a single-responsibility principle:
- **IP Swapper** (this project): Handles IP allocation logic and Azure API interactions
- **Airflow DAG** (`07.swap_public_ip_mapping`): Orchestrates polling-based execution
- **VM Scheduler** (separate project `azure_vm_scheduler`): Handles VM start/stop

### End-State Driven Design

The system follows a **declarative, convergent** model:

```
┌─────────────────────────────────────────────────────────────┐
│                    Desired State                            │
│                 (config.yml schedule)                       │
│                                                             │
│   "At 09:00-17:00, VM 'adf' should have 'iaptus_ip'"       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Reconciliation Loop                        │
│                  (runs every 10 min)                        │
│                                                             │
│   1. What time is it now?                                   │
│   2. What SHOULD the IP assignments be?                     │
│   3. What ARE the current IP assignments?                   │
│   4. Make changes to converge to desired state              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Actual State                             │
│                   (Azure Resources)                         │
│                                                             │
│   Public IPs assigned to NICs on VMs                        │
└─────────────────────────────────────────────────────────────┘
```

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Configuration                          │
│                   (config/config.yml)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐│
│  │ VM Mappings │ │ IP Mappings │ │ Schedule Definitions   ││
│  │ (labels)    │ │ (labels)    │ │ (time windows + pairs) ││
│  └─────────────┘ └─────────────┘ └────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   Airflow Orchestration   │   │      Core Logic           │
│ (07.swap_public_ip_mapping│   │  ┌─────────────────────┐  │
│         .py)              │   │  │ azure.py            │  │
│ ┌───────────────────────┐ │   │  │ - Azure API         │  │
│ │ - Polling (every 10m) │ │   │  │ - IP operations     │  │
│ │ - Time window eval    │ │   │  │ - NIC management    │  │
│ │ - Config validation   │ │   │  └─────────────────────┘  │
│ │ - Conflict detection  │ │   └───────────────────────────┘
│ └───────────────────────┘ │               │
└───────────────────────────┘               │
        │                                   │
        ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                     Entry Point                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ cli.py                                               │   │
│  │ - sync: Evaluate schedule, converge to desired state │   │
│  │ - assign: Manual immediate assignment                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Azure Resources                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐          │
│  │ VMs      │  │ NICs     │  │ Public IPs       │          │
│  └──────────┘  └──────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Orchestration via Airflow

The IP swapping is orchestrated by an Apache Airflow DAG using a **polling-based reconciliation** model.

### DAG Behavior

| Property | Value |
|----------|-------|
| DAG ID | `07.swap_public_ip_mapping` |
| Schedule | Every 10 minutes (`*/10 * * * *`) |
| Timezone | Loaded from `config.yml` (default: Europe/London) |
| Max Active Runs | 1 |
| Catchup | Disabled |

### Restart Behavior

The Airflow host may be randomly shut down and restarted. When the stack comes back online:

- **No backfill**: The DAG will NOT re-run missed schedules (catchup disabled)
- **Forward-only**: Only future scheduled runs will be processed
- **Immediate convergence**: The next scheduled run will evaluate the current time and converge to the correct state

This behavior is intentional and correct for an end-state driven system:
1. The system doesn't need to "replay" past transitions
2. It only needs to know "what should be true RIGHT NOW"
3. On restart, the next polling cycle will bring the system to the correct state

**Example**: If Airflow is down from 08:00-10:00 and restarts at 10:05:
- Missed runs at 08:00, 08:10, 08:20, ... 10:00 are NOT executed
- The 10:10 run executes normally
- It evaluates: "At 10:10, what should the IP assignments be?"
- It converges to the correct state for 10:10, regardless of what happened during downtime

### Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Every 10 Minutes                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   validate_config                           │
│  - Load schedule from config.yml                            │
│  - Validate required fields (start, end, vm, ip)            │
│  - Detect conflicting IP assignments in overlapping windows │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   sync_ip_assignments                       │
│  1. Get current time in configured timezone                 │
│  2. Find all schedule entries where now ∈ [start, end)      │
│  3. For each active entry:                                  │
│     a. Check current IP assignment in Azure                 │
│     b. If already correct → skip (log: "no change needed")  │
│     c. If different → disassociate old, associate new       │
│  4. Log all actions taken                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              (Optional) Downstream Triggers                 │
│  - Trigger dependent DAGs based on state changes            │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Polling-Based Reconciliation**: The DAG runs every 10 minutes, evaluates the current time against the schedule, and converges to the desired state. This eliminates the need for TimeSensors and long-running DAG runs.

2. **Idempotent Execution**: Each run independently determines the desired state and makes only necessary changes. Running the same schedule multiple times has no side effects if already in the correct state.

3. **Self-Healing**: If an IP assignment drifts from the desired state (e.g., manual change, Azure issue), the next polling cycle automatically corrects it.

4. **Validation at Each Run**: Every execution validates the configuration, catching errors early and preventing invalid assignments.

5. **Simplified DAG Structure**: No TimeSensors, no complex branching - just a straightforward validate → sync flow.

### CLI Commands

| Command | Description |
|---------|-------------|
| `cli.py sync` | Evaluate schedule for current time and converge to desired state |
| `cli.py assign --vm X --ip Y` | Immediate manual assignment (bypasses schedule) |

### Comparison: Old vs New Approach

| Aspect | Old (TimeSensor) | New (Polling) |
|--------|------------------|---------------|
| DAG Schedule | Daily at midnight | Every 10 minutes |
| DAG Run Duration | Up to 24 hours | Seconds |
| Timing Precision | Exact (TimeSensor) | ±10 minutes |
| Self-Healing | No | Yes |
| Complexity | High (branching, sensors) | Low (linear flow) |
| State Changes | Only at scheduled times | Converges continuously |

## Functional Requirements

### FR-1: End-State Evaluation
- The system SHALL determine the desired IP assignments based on current time and schedule
- The system SHALL compare desired state against actual Azure state
- The system SHALL make only the changes necessary to converge to desired state

### FR-2: Time Window Evaluation
- The system SHALL support time windows in HH:MM format
- The system SHALL support time windows that cross midnight (e.g., 23:00-06:00)
- The system SHALL evaluate times in a configurable timezone
- The system SHALL treat windows as half-open intervals: [start, end)

### FR-3: IP Reassignment Logic
- The system SHALL skip reassignment if IP is already correctly assigned
- The system SHALL disassociate IP from current NIC before associating to new NIC
- The system SHALL clean up secondary IP configurations on target NICs

### FR-4: Conflict Detection
- The system SHALL detect when the same IP would be assigned to multiple VMs in overlapping windows
- The system SHALL reject invalid configurations at validation time
- The system SHALL log conflicts and prevent execution

### FR-5: Manual Assignment
- The system SHALL provide CLI interface for immediate manual IP assignment
- Manual assignments SHALL bypass schedule evaluation

### FR-6: Logging
- The system SHALL log the desired state for each polling cycle
- The system SHALL log whether changes were needed
- The system SHALL log all association/disassociation events
- The system SHALL log errors and skip invalid entries gracefully

## Configuration Requirements

### CR-1: Resource Definitions
```yaml
vms:
  <label>:
    name: <azure-vm-name>
    resource_group: <resource-group-name>

public_ips:
  <label>:
    name: <azure-ip-name>
    resource_group: <resource-group-name>
```

### CR-2: Schedule Definitions
```yaml
schedule:
  - start: "HH:MM"
    end: "HH:MM"
    vm: <vm-label>
    ip: <ip-label>
```

Each entry defines a single VM-IP assignment with its time window. The schedule is **declarative**: it describes the desired end-state at any given time.

**Time Window Semantics:**
- Windows are half-open intervals: `[start, end)`
- A time of 09:00 matches a window `09:00-17:00`
- A time of 17:00 does NOT match a window `09:00-17:00`
- Windows can span midnight: `23:00-06:00` means 23:00 to 06:00 next day

**Conflict Rules:**
- The same IP can appear in multiple entries if the time windows don't overlap
- The same IP CANNOT be assigned to different VMs in overlapping windows

### CR-3: Timezone Configuration
```yaml
schedule_timezone: "Europe/London"  # IANA timezone name
```

## Non-Functional Requirements

### NFR-1: Security
- Credentials SHALL NOT be stored in source code
- Configuration containing sensitive data SHALL be excluded from version control
- Authentication SHALL use Azure SDK's DefaultAzureCredential

### NFR-2: Reliability
- Operations SHALL be idempotent
- Partial failures SHALL not corrupt state
- The system SHALL handle Azure API transient errors gracefully
- The system SHALL self-heal on subsequent polling cycles

### NFR-3: Deployment
- The system SHALL be deployable via Docker
- The system SHALL support running as a non-root user
- The system SHALL integrate with Apache Airflow for orchestration

## Azure Permissions Required

| Permission | Scope | Purpose |
|------------|-------|---------|
| Microsoft.Network/publicIPAddresses/read | Resource Group | Read IP configurations |
| Microsoft.Network/publicIPAddresses/join/action | Resource Group | Associate IPs to NICs |
| Microsoft.Network/networkInterfaces/read | Resource Group | Read NIC configurations |
| Microsoft.Network/networkInterfaces/write | Resource Group | Update NIC IP assignments |
| Microsoft.Compute/virtualMachines/read | Resource Group | Resolve VM to NIC |

## Example Use Case

### Scenario: Shared IP for Business Hours

A company has:
- 3 VMs: `adf` (data factory), `linux` (integration runtime), `dotnine` (application)
- 2 public IPs: `iaptus_ip`, `dotnine_ip`

Schedule configuration:
```yaml
schedule:
  - start: "07:45"
    end: "08:30"
    vm: "linux"
    ip: "iaptus_ip"
  - start: "08:30"
    end: "09:00"
    vm: "linux"
    ip: "dotnine_ip"
  - start: "09:00"
    end: "17:00"
    vm: "adf"
    ip: "iaptus_ip"
  - start: "09:00"
    end: "17:00"
    vm: "dotnine"
    ip: "dotnine_ip"
  - start: "17:00"
    end: "23:59"
    vm: "linux"
    ip: "iaptus_ip"
```

**Behavior at different times:**

| Time | Active Windows | Desired State |
|------|----------------|---------------|
| 06:00 | None | No assignments managed |
| 08:00 | 07:45-08:30 | `linux` has `iaptus_ip` |
| 08:45 | 08:30-09:00 | `linux` has `dotnine_ip` |
| 10:00 | 09:00-17:00 (x2) | `adf` has `iaptus_ip`, `dotnine` has `dotnine_ip` |
| 18:00 | 17:00-23:59 | `linux` has `iaptus_ip` |

The polling-based approach means that at any point in time, the system will check the schedule, determine what SHOULD be true, and make it so.

## Future Considerations

- Integration with Azure Key Vault for credential management
- Notification/alerting on assignment failures (Airflow alerts partially address this)
- Support for IP pools with automatic selection
- Metrics/observability for tracking state changes over time
