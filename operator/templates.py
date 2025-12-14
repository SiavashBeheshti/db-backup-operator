from typing import Dict, Any
from operator.config import get_config


class ManifestTemplates:
    """
    Templates for Kubernetes manifests used by the operator
    """
    
    @staticmethod
    def get_backup_commands() -> Dict[str, str]:
        """
        Database-specific backup commands
        """
        return {
            'postgres': "pg_dump -h {host} -U $DB_USER -d {database} | gzip > /backup/backup-$(date +%Y%m%d-%H%M%S).sql.gz",
            'mysql': "mysqldump -h {host} -u $DB_USER -p$DB_PASSWORD {database} | gzip > /backup/backup-$(date +%Y%m%d-%H%M%S).sql.gz",
            'mongodb': "mongodump --host {host} --db {database} --archive=/backup/backup-$(date +%Y%m%d-%H%M%S).archive --gzip"
        }
    
    @staticmethod
    def get_upload_command(bucket: str, namespace: str, name: str, retention: int) -> str:
        """
        Generate S3 upload and retention cleanup command
        """
        return f"""
        aws s3 cp /backup/*.gz s3://{bucket}/{namespace}/{name}/ && \
        aws s3 ls s3://{bucket}/{namespace}/{name}/ | sort -r | tail -n +{retention + 1} | awk '{{print $4}}' | xargs -I {{}} aws s3 rm s3://{bucket}/{namespace}/{name}/{{}}
        """
    
    @staticmethod
    def cronjob_manifest(
        name: str,
        namespace: str,
        schedule: str,
        database: Dict[str, Any],
        storage: Dict[str, Any],
        retention: int
    ) -> Dict[str, Any]:
        """
        Generate CronJob manifest for database backup
        """
        config = get_config()
        
        db_type = database['type']
        db_host = database['host']
        db_name = database['name']
        db_creds_secret = database.get('credentialsSecret', f'{name}-db-creds')
        
        storage_bucket = storage['bucket']
        storage_region = storage.get('region', config.get_default_region(storage['type']))
        storage_creds_secret = storage.get('credentialsSecret', f'{name}-storage-creds')
        
        # Get backup command template
        backup_commands = ManifestTemplates.get_backup_commands()
        backup_cmd = backup_commands.get(db_type, backup_commands['postgres'])
        backup_cmd = backup_cmd.format(host=db_host, database=db_name)
        
        # Get upload command
        upload_cmd = ManifestTemplates.get_upload_command(
            bucket=storage_bucket,
            namespace=namespace,
            name=name,
            retention=retention
        )
        
        # Build complete command
        full_command = f"{backup_cmd} && {upload_cmd}"
        
        return {
            'apiVersion': 'batch/v1',
            'kind': 'CronJob',
            'metadata': {
                'name': f'{name}-backup',
                'namespace': namespace,
                'labels': {
                    'app': 'database-backup',
                    'backup-name': name,
                    'managed-by': config.name,
                    'version': config.version
                }
            },
            'spec': {
                'schedule': schedule,
                'successfulJobsHistoryLimit': config.backup.successful_jobs_history_limit,
                'failedJobsHistoryLimit': config.backup.failed_jobs_history_limit,
                'concurrencyPolicy': 'Forbid',
                'jobTemplate': {
                    'spec': {
                        'backoffLimit': 2,
                        'activeDeadlineSeconds': config.backup.backup_timeout_seconds,
                        'template': {
                            'metadata': {
                                'labels': {
                                    'app': 'database-backup',
                                    'backup-name': name
                                }
                            },
                            'spec': {
                                'restartPolicy': 'OnFailure',
                                'containers': [{
                                    'name': 'backup',
                                    'image': config.get_database_image(db_type),
                                    'command': ['/bin/sh', '-c'],
                                    'args': [full_command],
                                    'env': ManifestTemplates._get_container_env(
                                        db_type=db_type,
                                        db_creds_secret=db_creds_secret,
                                        storage_creds_secret=storage_creds_secret,
                                        storage_region=storage_region
                                    ),
                                    'volumeMounts': [{
                                        'name': 'backup-storage',
                                        'mountPath': '/backup'
                                    }],
                                    'resources': {
                                        'requests': {
                                            'memory': config.backup.memory_request,
                                            'cpu': config.backup.cpu_request
                                        },
                                        'limits': {
                                            'memory': config.backup.memory_limit,
                                            'cpu': config.backup.cpu_limit
                                        }
                                    }
                                }],
                                'volumes': [{
                                    'name': 'backup-storage',
                                    'emptyDir': {
                                        'sizeLimit': config.backup.temp_storage_size
                                    }
                                }]
                            }
                        }
                    }
                }
            }
        }
    
    @staticmethod
    def _get_container_env(
        db_type: str,
        db_creds_secret: str,
        storage_creds_secret: str,
        storage_region: str
    ) -> list:
        """
        Generate environment variables for the backup container
        """
        env_vars = [
            {
                'name': 'DB_USER',
                'valueFrom': {
                    'secretKeyRef': {
                        'name': db_creds_secret,
                        'key': 'username'
                    }
                }
            },
            {
                'name': 'AWS_ACCESS_KEY_ID',
                'valueFrom': {
                    'secretKeyRef': {
                        'name': storage_creds_secret,
                        'key': 'access-key'
                    }
                }
            },
            {
                'name': 'AWS_SECRET_ACCESS_KEY',
                'valueFrom': {
                    'secretKeyRef': {
                        'name': storage_creds_secret,
                        'key': 'secret-key'
                    }
                }
            },
            {
                'name': 'AWS_DEFAULT_REGION',
                'value': storage_region
            }
        ]
        
        # Add password for MySQL/Postgres (MongoDB uses different auth)
        if db_type in ['postgres', 'mysql']:
            env_vars.insert(1, {
                'name': 'DB_PASSWORD',
                'valueFrom': {
                    'secretKeyRef': {
                        'name': db_creds_secret,
                        'key': 'password'
                    }
                }
            })
        
        return env_vars