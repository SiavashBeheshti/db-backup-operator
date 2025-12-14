import kopf
import kubernetes
from typing import Dict, Any
from operator.templates import ManifestTemplates
from operator.config import get_config


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """
    Configure operator on startup
    """
    config = get_config()
    
    # Configure Kopf settings
    settings.persistence.finalizer = f'{config.name}/finalizer'
    settings.posting.level = getattr(kopf.config, config.log_level.upper(), kopf.config.INFO)
    
    print(f"Starting {config.name} v{config.version}")
    print(f"Watching namespace: {config.namespace or 'all namespaces'}")
    print(f"Supported databases: {', '.join(config.database.supported_types)}")
    print(f"Supported storage: {', '.join(config.storage.supported_types)}")


@kopf.on.create('backup.example.com', 'v1', 'databasebackups')
def create_backup_job(spec, name, namespace, logger, **kwargs):
    """
    Handler called when a DatabaseBackup resource is created
    """
    config = get_config()
    logger.info(f"Creating backup job for {name}")
    
    # Extract configuration with defaults from config
    schedule = spec.get('schedule', config.backup.default_schedule)
    database = spec['database']
    storage = spec['storage']
    retention = spec.get('retention', {}).get('keepLast', config.backup.default_retention_days)
    
    # Validate configuration
    _validate_spec(database, storage, logger)
    
    # Generate CronJob manifest using template
    cronjob = ManifestTemplates.cronjob_manifest(
        name=name,
        namespace=namespace,
        schedule=schedule,
        database=database,
        storage=storage,
        retention=retention
    )
    
    # Apply CronJob to cluster
    api = kubernetes.client.BatchV1Api()
    kopf.adopt(cronjob)  # Set owner reference for garbage collection
    
    try:
        api.create_namespaced_cron_job(
            namespace=namespace,
            body=cronjob
        )
        logger.info(f"CronJob {name}-backup created successfully with schedule: {schedule}")
        
        return {
            'message': f'Backup CronJob created with schedule: {schedule}',
            'cronjob': f'{name}-backup',
            'retention': retention
        }
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to create CronJob: {e}")
        raise kopf.PermanentError(f"Cannot create CronJob: {e}")


@kopf.on.update('backup.example.com', 'v1', 'databasebackups')
def update_backup_job(spec, name, namespace, logger, **kwargs):
    """
    Handler called when a DatabaseBackup resource is updated
    """
    config = get_config()
    logger.info(f"Updating backup job for {name}")
    
    api = kubernetes.client.BatchV1Api()
    
    try:
        # Delete existing CronJob
        api.delete_namespaced_cron_job(
            name=f'{name}-backup',
            namespace=namespace,
            propagation_policy='Foreground'
        )
        logger.info(f"Deleted old CronJob {name}-backup")
        
        # Extract updated configuration with defaults
        schedule = spec.get('schedule', config.backup.default_schedule)
        database = spec['database']
        storage = spec['storage']
        retention = spec.get('retention', {}).get('keepLast', config.backup.default_retention_days)
        
        # Validate configuration
        _validate_spec(database, storage, logger)
        
        # Recreate with new configuration
        cronjob = ManifestTemplates.cronjob_manifest(
            name=name,
            namespace=namespace,
            schedule=schedule,
            database=database,
            storage=storage,
            retention=retention
        )
        
        kopf.adopt(cronjob)
        api.create_namespaced_cron_job(
            namespace=namespace,
            body=cronjob
        )
        
        logger.info(f"CronJob {name}-backup updated successfully")
        
        return {'message': 'Backup job updated successfully'}
        
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to update CronJob: {e}")
        raise kopf.TemporaryError(f"Cannot update CronJob: {e}", delay=30)


@kopf.on.delete('backup.example.com', 'v1', 'databasebackups')
def delete_backup_job(name, namespace, logger, **kwargs):
    """
    Handler called when a DatabaseBackup resource is deleted
    CronJob will be automatically deleted due to owner reference
    """
    logger.info(f"DatabaseBackup {name} deleted - associated CronJob will be cleaned up automatically")
    return {'message': f'Backup job {name} deleted'}


@kopf.timer('backup.example.com', 'v1', 'databasebackups', interval=300)
def check_backup_status(spec, name, namespace, status, patch, logger, **kwargs):
    """
    Periodic check to update backup status
    """
    config = get_config()
    api = kubernetes.client.BatchV1Api()
    
    try:
        cronjob = api.read_namespaced_cron_job(
            name=f'{name}-backup',
            namespace=namespace
        )
        
        # Update status with last backup time and job count
        if cronjob.status.last_schedule_time:
            patch.status['lastBackup'] = cronjob.status.last_schedule_time.isoformat()
            patch.status['phase'] = 'Active'
        else:
            patch.status['phase'] = 'Pending'
        
        # Count active jobs
        if cronjob.status.active:
            patch.status['activeJobs'] = len(cronjob.status.active)
        else:
            patch.status['activeJobs'] = 0
            
    except kubernetes.client.exceptions.ApiException as e:
        logger.warning(f"Could not read CronJob status: {e}")
        patch.status['phase'] = 'Error'
        patch.status['error'] = str(e)


def _validate_spec(database: Dict[str, Any], storage: Dict[str, Any], logger) -> None:
    """
    Validate DatabaseBackup spec using configuration
    """
    config = get_config()
    
    # Validate database type
    if not config.is_database_supported(database['type']):
        raise kopf.PermanentError(
            f"Unsupported database type: {database['type']}. "
            f"Supported types: {', '.join(config.database.supported_types)}"
        )
    
    # Validate storage type
    if not config.is_storage_supported(storage['type']):
        raise kopf.PermanentError(
            f"Unsupported storage type: {storage['type']}. "
            f"Supported types: {', '.join(config.storage.supported_types)}"
        )
    
    # Validate required fields
    if not database.get('host'):
        raise kopf.PermanentError("Database host is required")
    
    if not database.get('name'):
        raise kopf.PermanentError("Database name is required")
    
    if not storage.get('bucket'):
        raise kopf.PermanentError("Storage bucket is required")
    
    logger.info("Spec validation passed")