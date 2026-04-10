# Database Backup System

Automated backup and restore system for the Gram SCS PostgreSQL-backed data.

## Features

- **Automated backups** with timestamp
- **Retention policy**: Keeps last 30 backups automatically
- **Safe restore**: Upserts data by consignment number
- **Portable format**: Backups stored as JSON snapshots
- **Audit logging**: All operations logged to `backups/backup.log`

## Usage

### Create a Backup

```bash
python backup_database.py backup
```

### List All Backups

```bash
python backup_database.py list
```

### Restore from Backup

```bash
python backup_database.py restore backup_2026-03-04_123045.json
```

### Clean Old Backups

```bash
python backup_database.py clean
```

## Automated Scheduling

### Linux/Mac (cron)

Add to crontab for daily backups at 2 AM:

```bash
crontab -e
```

Add this line:

```
0 2 * * * cd /path/to/gram-scs-it-dept && /usr/bin/python3 backup_database.py backup
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 2:00 AM
4. Action: Start a program
5. Program: `python`
6. Arguments: `backup_database.py backup`
7. Start in: `C:\path\to\gram-scs-it-dept`

## Configuration

Edit `backup_database.py` to customize:

- `RETENTION_COUNT`: Number of backups to keep (default: 30)
- `BACKUP_DIR`: Directory for backups (default: `backups`)

## Backup Location

All backups are stored in the `backups/` directory with the naming format:
- `backup_YYYY-MM-DD_HHMMSS.json`

Example: `backup_2026-03-04_143025.json`

## Safety Features

- Restore is idempotent (upsert by consignment number)
- Comprehensive error handling and logging
- Non-destructive list and clean operations

## Logs

All backup operations are logged to `backups/backup.log` with timestamps for audit trail.
