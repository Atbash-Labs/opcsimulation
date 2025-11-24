# PowerShell Backup Scripts

Two PowerShell scripts for automated OPC UA backup and restore operations.

## Scripts

### `export_opc_backup.ps1`
Exports all nodes/values from an OPC UA server to a timestamped JSON backup file.

### `import_opc_backup.ps1`
Imports nodes/values from a JSON backup file to an OPC UA server.

## Usage

### Export (Backup)

```powershell
# Basic usage (defaults to localhost:4840)
.\export_opc_backup.ps1

# Specify custom server
.\export_opc_backup.ps1 -ServerUrl "opc.tcp://192.168.1.100:4840"

# With authentication
.\export_opc_backup.ps1 -ServerUrl "opc.tcp://server:4840" -Username "admin" -Password "secret"

# Custom backup directory
.\export_opc_backup.ps1 -BackupDir "D:\backups\opc"
```

### Import (Restore)

```powershell
# Use most recent backup (auto-detects latest file)
.\import_opc_backup.ps1

# Specify a specific backup file
.\import_opc_backup.ps1 -BackupFile "opc_backup_20241120_143022.json"

# Full path to backup file
.\import_opc_backup.ps1 -BackupFile "C:\opcbackup\opc_backup_20241120_143022.json"

# Dry run (validate without making changes)
.\import_opc_backup.ps1 -DryRun

# With authentication
.\import_opc_backup.ps1 -ServerUrl "opc.tcp://server:4840" -Username "admin" -Password "secret"
```

## Parameters

### export_opc_backup.ps1
- `-ServerUrl`: OPC UA server URL (default: `opc.tcp://localhost:4840`)
- `-BackupDir`: Backup directory path (default: `C:\opcbackup`)
- `-Username`: Optional username for authentication
- `-Password`: Optional password for authentication

### import_opc_backup.ps1
- `-ServerUrl`: OPC UA server URL (default: `opc.tcp://localhost:4840`)
- `-BackupDir`: Backup directory path (default: `C:\opcbackup`)
- `-BackupFile`: Specific backup file to import (default: most recent)
- `-Username`: Optional username for authentication
- `-Password`: Optional password for authentication
- `-DryRun`: Validate without making changes

## File Naming

Backup files are automatically named with timestamps:
- Format: `opc_backup_YYYYMMDD_HHMMSS.json`
- Example: `opc_backup_20241120_143022.json`

This ensures:
- Unique filenames (no overwrites)
- Easy sorting by date/time
- Clear identification of backup time

## Examples

### Scheduled Daily Backup (Task Scheduler)

Create a scheduled task to run:
```powershell
powershell.exe -File "C:\path\to\export_opc_backup.ps1" -ServerUrl "opc.tcp://production-server:4840"
```

### Restore from Specific Backup

```powershell
# First, list available backups
Get-ChildItem C:\opcbackup\opc_backup_*.json | Sort-Object LastWriteTime -Descending

# Restore specific backup
.\import_opc_backup.ps1 -BackupFile "opc_backup_20241120_120000.json"
```

### Test Import Before Restore

```powershell
# Validate backup file without making changes
.\import_opc_backup.ps1 -DryRun -BackupFile "opc_backup_20241120_143022.json"
```

## Notes

- The backup directory is automatically created if it doesn't exist
- If no backup file is specified for import, the most recent backup is used
- Backup files are never overwritten (timestamp ensures uniqueness)
- Use `-DryRun` flag to validate imports before applying changes



