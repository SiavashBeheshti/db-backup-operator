"""
Database Backup Operator for Kubernetes

This operator automates database backup operations by watching for
DatabaseBackup custom resources and creating corresponding CronJobs
to perform scheduled backups to cloud storage.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

# Import main components for easier access
from operator.handlers import (
    create_backup_job,
    update_backup_job,
    delete_backup_job,
    check_backup_status
)
from operator.templates import ManifestTemplates
from operator.config import OperatorConfig

__all__ = [
    'create_backup_job',
    'update_backup_job',
    'delete_backup_job',
    'check_backup_status',
    'ManifestTemplates',
    'OperatorConfig',
]