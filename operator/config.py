"""
Configuration management for the Database Backup Operator
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    """Configuration for supported database types"""
    supported_types: List[str] = field(default_factory=lambda: [
        'postgres',
        'mysql',
        'mongodb'
    ])
    
    default_ports: Dict[str, int] = field(default_factory=lambda: {
        'postgres': 5432,
        'mysql': 3306,
        'mongodb': 27017
    })
    
    images: Dict[str, str] = field(default_factory=lambda: {
        'postgres': 'postgres:15-alpine',
        'mysql': 'mysql:8.0',
        'mongodb': 'mongo:7.0'
    })


@dataclass
class StorageConfig:
    """Configuration for supported storage backends"""
    supported_types: List[str] = field(default_factory=lambda: [
        's3',
        'gcs',
        'azure'
    ])
    
    default_regions: Dict[str, str] = field(default_factory=lambda: {
        's3': 'us-east-1',
        'gcs': 'us-central1',
        'azure': 'eastus'
    })


@dataclass
class BackupConfig:
    """General backup configuration"""
    default_schedule: str = '0 2 * * *'  # Daily at 2 AM
    default_retention_days: int = 7
    successful_jobs_history_limit: int = 3
    failed_jobs_history_limit: int = 1
    backup_timeout_seconds: int = 3600  # 1 hour
    
    # Resource limits for backup jobs
    memory_request: str = '256Mi'
    memory_limit: str = '512Mi'
    cpu_request: str = '100m'
    cpu_limit: str = '500m'
    
    # Backup storage
    temp_storage_size: str = '10Gi'


@dataclass
class OperatorConfig:
    """Main operator configuration"""
    
    # Operator metadata
    name: str = 'db-backup-operator'
    version: str = '0.1.0'
    
    # Kubernetes API configuration
    namespace: Optional[str] = None  # None means watch all namespaces
    
    # Component configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    
    # Operator behavior
    reconciliation_interval: int = 300  # Status check every 5 minutes
    
    # Logging
    log_level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    
    # Feature flags
    enable_webhooks: bool = field(default_factory=lambda: 
        os.getenv('ENABLE_WEBHOOKS', 'false').lower() == 'true'
    )
    enable_metrics: bool = field(default_factory=lambda: 
        os.getenv('ENABLE_METRICS', 'false').lower() == 'true'
    )
    
    @classmethod
    def from_env(cls) -> 'OperatorConfig':
        """
        Create configuration from environment variables
        
        Environment variables:
        - OPERATOR_NAMESPACE: Namespace to watch (default: all)
        - LOG_LEVEL: Logging level (default: INFO)
        - ENABLE_WEBHOOKS: Enable admission webhooks (default: false)
        - ENABLE_METRICS: Enable Prometheus metrics (default: false)
        - DEFAULT_BACKUP_SCHEDULE: Default cron schedule (default: 0 2 * * *)
        - DEFAULT_RETENTION_DAYS: Default retention period (default: 7)
        """
        config = cls()
        
        # Override from environment
        if namespace := os.getenv('OPERATOR_NAMESPACE'):
            config.namespace = namespace
        
        if schedule := os.getenv('DEFAULT_BACKUP_SCHEDULE'):
            config.backup.default_schedule = schedule
        
        if retention := os.getenv('DEFAULT_RETENTION_DAYS'):
            try:
                config.backup.default_retention_days = int(retention)
            except ValueError:
                pass  # Use default if invalid
        
        return config
    
    def validate(self) -> None:
        """
        Validate configuration
        
        Raises:
            ValueError: If configuration is invalid
        """
        if self.reconciliation_interval < 60:
            raise ValueError("Reconciliation interval must be at least 60 seconds")
        
        if self.backup.default_retention_days < 1:
            raise ValueError("Retention days must be at least 1")
        
        if self.backup.backup_timeout_seconds < 60:
            raise ValueError("Backup timeout must be at least 60 seconds")
    
    def get_database_image(self, db_type: str) -> str:
        """Get Docker image for a database type"""
        return self.database.images.get(db_type, self.database.images['postgres'])
    
    def get_default_port(self, db_type: str) -> int:
        """Get default port for a database type"""
        return self.database.default_ports.get(db_type, 5432)
    
    def get_default_region(self, storage_type: str) -> str:
        """Get default region for a storage type"""
        return self.storage.default_regions.get(storage_type, 'us-east-1')
    
    def is_database_supported(self, db_type: str) -> bool:
        """Check if database type is supported"""
        return db_type in self.database.supported_types
    
    def is_storage_supported(self, storage_type: str) -> bool:
        """Check if storage type is supported"""
        return storage_type in self.storage.supported_types


# Global configuration instance
_config: Optional[OperatorConfig] = None


def get_config() -> OperatorConfig:
    """
    Get the global configuration instance (singleton pattern)
    
    Returns:
        OperatorConfig: The global configuration
    """
    global _config
    if _config is None:
        _config = OperatorConfig.from_env()
        _config.validate()
    return _config


def set_config(config: OperatorConfig) -> None:
    """
    Set the global configuration instance
    
    Args:
        config: New configuration instance
    """
    global _config
    config.validate()
    _config = config