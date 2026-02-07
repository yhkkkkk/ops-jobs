"""
统一的存储后端接口
支持多种存储后端：本地、OSS、S3、COS、MinIO、RustFS
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import IO, Optional, Tuple
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from apps.system_config.models import ConfigManager

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """存储后端基类"""
    
    @abstractmethod
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """
        上传文件到存储
        
        Args:
            file_obj: 上传的文件对象
            storage_path: 存储路径（不包含bucket/endpoint等）
        
        Returns:
            (success, error_message)
        """
        pass
    
    @abstractmethod
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        生成下载URL
        
        Args:
            storage_path: 存储路径
            expires_in: URL过期时间（秒），用于私有存储的预签名URL
        
        Returns:
            下载URL，如果失败返回None
        """
        pass
    
    @abstractmethod
    def delete_file(self, storage_path: str) -> bool:
        """
        删除文件
        
        Args:
            storage_path: 存储路径
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            storage_path: 存储路径
        
        Returns:
            是否存在
        """
        pass

    @abstractmethod
    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """
        获取文件内容用于下载或校验

        Args:
            storage_path: 存储路径

        Returns:
            文件对象或字节流；不存在或失败时返回None
        """
        pass


class LocalStorageBackend(StorageBackend):
    """本地文件系统存储后端"""

    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """写入到MEDIA_ROOT"""
        try:
            file_obj.seek(0)
            file_path = os.path.join(settings.MEDIA_ROOT, storage_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as dest:
                if hasattr(file_obj, "chunks"):
                    for chunk in file_obj.chunks():
                        dest.write(chunk)
                else:
                    dest.write(file_obj.read())
            return True, None
        except Exception as e:
            logger.error(f"写入本地文件失败: {e}", exc_info=True)
            return False, str(e)
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成本地文件URL"""
        # 本地存储使用Django的MEDIA_URL
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        if not media_url.endswith('/'):
            media_url += '/'
        return f"{media_url}{storage_path}"
    
    def delete_file(self, storage_path: str) -> bool:
        """删除本地文件"""
        try:
            file_path = os.path.join(settings.MEDIA_ROOT, storage_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"删除本地文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查本地文件是否存在"""
        try:
            file_path = os.path.join(settings.MEDIA_ROOT, storage_path)
            return os.path.exists(file_path)
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """读取本地文件"""
        try:
            file_path = os.path.join(settings.MEDIA_ROOT, storage_path)
            if not os.path.exists(file_path):
                return None
            return open(file_path, "rb")
        except Exception as e:
            logger.error(f"读取本地文件失败: {e}", exc_info=True)
            return None


class OSSStorageBackend(StorageBackend):
    """阿里云OSS存储后端"""
    
    def __init__(self):
        self.endpoint = ConfigManager.get('storage.oss.endpoint', '')
        self.bucket_name = ConfigManager.get('storage.oss.bucket', '')
        self.access_key_id = ConfigManager.get('storage.oss.access_key_id', '')
        self.access_key_secret = ConfigManager.get('storage.oss.access_key_secret', '')
        self._client = None
    
    def _get_client(self):
        """获取OSS客户端"""
        if self._client is None:
            try:
                import oss2
            except ImportError:
                raise ImportError("请安装 oss2 库: pip install oss2")
            
            if not all([self.endpoint, self.bucket_name, self.access_key_id, self.access_key_secret]):
                raise ValueError("OSS配置不完整，请在系统配置中设置")
            
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self._client = oss2.Bucket(auth, self.endpoint, self.bucket_name)
        
        return self._client
    
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """上传文件到OSS"""
        try:
            bucket = self._get_client()
            file_obj.seek(0)
            result = bucket.put_object(storage_path, file_obj.read())
            
            if result.status == 200:
                return True, None
            else:
                return False, f"OSS上传失败，状态码: {result.status}"
        except Exception as e:
            logger.error(f"OSS上传失败: {e}", exc_info=True)
            return False, f"OSS上传失败: {str(e)}"
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成OSS下载URL"""
        try:
            bucket = self._get_client()
            # 检查bucket是否为公开读取
            # 如果是公开，直接返回URL；如果是私有，生成签名URL
            url = bucket.sign_url('GET', storage_path, expires_in)
            return url
        except Exception as e:
            logger.error(f"生成OSS URL失败: {e}", exc_info=True)
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """删除OSS文件"""
        try:
            bucket = self._get_client()
            bucket.delete_object(storage_path)
            return True
        except Exception as e:
            logger.error(f"删除OSS文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查OSS文件是否存在"""
        try:
            bucket = self._get_client()
            return bucket.object_exists(storage_path)
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """下载OSS文件"""
        try:
            bucket = self._get_client()
            return bucket.get_object(storage_path)
        except Exception as e:
            logger.error(f"获取OSS文件失败: {e}", exc_info=True)
            return None


class S3StorageBackend(StorageBackend):
    """AWS S3存储后端"""
    
    def __init__(self):
        self.bucket_name = ConfigManager.get('storage.s3.bucket', '')
        self.region = ConfigManager.get('storage.s3.region', 'us-east-1')
        self.endpoint = ConfigManager.get('storage.s3.endpoint', '')
        self.access_key = ConfigManager.get('cloud.aws.access_key', '')
        self.secret_key = ConfigManager.get('cloud.aws.secret_key', '')
        self._client = None
    
    def _get_client(self):
        """获取S3客户端"""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise ImportError("请安装 boto3 库: pip install boto3")
            
            if not all([self.bucket_name, self.access_key, self.secret_key]):
                raise ValueError("S3配置不完整，请在系统配置中设置")
            
            s3_config = {
                'region_name': self.region,
                'aws_access_key_id': self.access_key,
                'aws_secret_access_key': self.secret_key,
            }
            if self.endpoint:
                s3_config['endpoint_url'] = self.endpoint
            
            self._client = boto3.client('s3', **s3_config)
        
        return self._client
    
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """上传文件到S3"""
        try:
            s3_client = self._get_client()
            file_obj.seek(0)
            s3_client.upload_fileobj(file_obj, self.bucket_name, storage_path)
            return True, None
        except Exception as e:
            logger.error(f"S3上传失败: {e}", exc_info=True)
            return False, f"S3上传失败: {str(e)}"
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成S3下载URL（预签名URL）"""
        try:
            s3_client = self._get_client()
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': storage_path},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"生成S3 URL失败: {e}", exc_info=True)
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """删除S3文件"""
        try:
            s3_client = self._get_client()
            s3_client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception as e:
            logger.error(f"删除S3文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查S3文件是否存在"""
        try:
            s3_client = self._get_client()
            s3_client.head_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """下载S3文件"""
        try:
            s3_client = self._get_client()
            response = s3_client.get_object(Bucket=self.bucket_name, Key=storage_path)
            return response.get("Body")
        except Exception as e:
            logger.error(f"获取S3文件失败: {e}", exc_info=True)
            return None


class COSStorageBackend(StorageBackend):
    """腾讯云COS存储后端"""
    
    def __init__(self):
        self.region = ConfigManager.get('storage.cos.region', 'ap-guangzhou')
        self.bucket_name = ConfigManager.get('storage.cos.bucket', '')
        self.secret_id = ConfigManager.get('storage.cos.secret_id', '')
        self.secret_key = ConfigManager.get('storage.cos.secret_key', '')
        self._client = None
    
    def _get_client(self):
        """获取COS客户端"""
        if self._client is None:
            try:
                from qcloud_cos import CosConfig, CosS3Client
            except ImportError:
                raise ImportError("请安装 cos-python-sdk-v5 库: pip install cos-python-sdk-v5")
            
            if not all([self.bucket_name, self.secret_id, self.secret_key]):
                raise ValueError("COS配置不完整，请在系统配置中设置")
            
            config = CosConfig(Region=self.region, SecretId=self.secret_id, SecretKey=self.secret_key)
            self._client = CosS3Client(config)
        
        return self._client
    
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """上传文件到COS"""
        try:
            cos_client = self._get_client()
            file_obj.seek(0)
            response = cos_client.put_object(
                Bucket=self.bucket_name,
                Body=file_obj.read(),
                Key=storage_path
            )
            
            if response.get('ETag'):
                return True, None
            else:
                return False, "COS上传失败"
        except Exception as e:
            logger.error(f"COS上传失败: {e}", exc_info=True)
            return False, f"COS上传失败: {str(e)}"
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成COS下载URL（预签名URL）"""
        try:
            cos_client = self._get_client()
            url = cos_client.get_presigned_download_url(
                Bucket=self.bucket_name,
                Key=storage_path,
                Expired=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"生成COS URL失败: {e}", exc_info=True)
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """删除COS文件"""
        try:
            cos_client = self._get_client()
            cos_client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception as e:
            logger.error(f"删除COS文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查COS文件是否存在"""
        try:
            cos_client = self._get_client()
            cos_client.head_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """下载COS文件"""
        try:
            cos_client = self._get_client()
            response = cos_client.get_object(Bucket=self.bucket_name, Key=storage_path)
            return response.get("Body")
        except Exception as e:
            logger.error(f"获取COS文件失败: {e}", exc_info=True)
            return None


class MinIOStorageBackend(StorageBackend):
    """MinIO存储后端（兼容S3协议）"""
    
    def __init__(self):
        self.endpoint = ConfigManager.get('storage.minio.endpoint', '')
        self.bucket_name = ConfigManager.get('storage.minio.bucket', '')
        self.access_key = ConfigManager.get('storage.minio.access_key', '')
        self.secret_key = ConfigManager.get('storage.minio.secret_key', '')
        self.secure = ConfigManager.get('storage.minio.secure', True)
        self._client = None
    
    def _get_client(self):
        """获取MinIO客户端"""
        if self._client is None:
            try:
                from minio import Minio
            except ImportError:
                raise ImportError("请安装 minio 库: pip install minio")
            
            if not all([self.endpoint, self.bucket_name, self.access_key, self.secret_key]):
                raise ValueError("MinIO配置不完整，请在系统配置中设置")
            
            # 解析endpoint，移除协议前缀
            endpoint = self.endpoint.replace('http://', '').replace('https://', '')
            self._client = Minio(
                endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
        
        return self._client
    
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """上传文件到MinIO"""
        try:
            client = self._get_client()
            file_obj.seek(0)
            file_size = file_obj.size
            result = client.put_object(
                self.bucket_name,
                storage_path,
                file_obj,
                length=file_size
            )
            return True, None
        except Exception as e:
            logger.error(f"MinIO上传失败: {e}", exc_info=True)
            return False, f"MinIO上传失败: {str(e)}"
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成MinIO下载URL（预签名URL）"""
        try:
            from datetime import timedelta
            client = self._get_client()
            url = client.presigned_get_object(
                self.bucket_name,
                storage_path,
                expires=timedelta(seconds=expires_in)
            )
            return url
        except Exception as e:
            logger.error(f"生成MinIO URL失败: {e}", exc_info=True)
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """删除MinIO文件"""
        try:
            client = self._get_client()
            client.remove_object(self.bucket_name, storage_path)
            return True
        except Exception as e:
            logger.error(f"删除MinIO文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查MinIO文件是否存在"""
        try:
            client = self._get_client()
            client.stat_object(self.bucket_name, storage_path)
            return True
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """下载MinIO文件"""
        try:
            client = self._get_client()
            return client.get_object(self.bucket_name, storage_path)
        except Exception as e:
            logger.error(f"获取MinIO文件失败: {e}", exc_info=True)
            return None


class RustFSStorageBackend(StorageBackend):
    """RustFS存储后端（兼容S3协议，使用boto3）"""
    
    def __init__(self):
        self.endpoint = ConfigManager.get('storage.rustfs.endpoint', '')
        self.bucket_name = ConfigManager.get('storage.rustfs.bucket', '')
        self.access_key = ConfigManager.get('storage.rustfs.access_key', '')
        self.secret_key = ConfigManager.get('storage.rustfs.secret_key', '')
        self.region = ConfigManager.get('storage.rustfs.region', 'us-east-1')
        self._client = None
    
    def _get_client(self):
        """获取RustFS客户端（使用boto3，兼容S3协议）"""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise ImportError("请安装 boto3 库: pip install boto3")
            
            if not all([self.endpoint, self.bucket_name, self.access_key, self.secret_key]):
                raise ValueError("RustFS配置不完整，请在系统配置中设置")
            
            # 使用boto3创建S3兼容客户端
            s3_config = {
                'region_name': self.region,
                'aws_access_key_id': self.access_key,
                'aws_secret_access_key': self.secret_key,
                'endpoint_url': self.endpoint,  # RustFS的endpoint
            }
            
            self._client = boto3.client('s3', **s3_config)
        
        return self._client
    
    def upload_file(self, file_obj: UploadedFile, storage_path: str) -> Tuple[bool, Optional[str]]:
        """上传文件到RustFS"""
        try:
            s3_client = self._get_client()
            file_obj.seek(0)
            s3_client.upload_fileobj(file_obj, self.bucket_name, storage_path)
            return True, None
        except Exception as e:
            logger.error(f"RustFS上传失败: {e}", exc_info=True)
            return False, f"RustFS上传失败: {str(e)}"
    
    def generate_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """生成RustFS下载URL（预签名URL）"""
        try:
            s3_client = self._get_client()
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': storage_path},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"生成RustFS URL失败: {e}", exc_info=True)
            return None
    
    def delete_file(self, storage_path: str) -> bool:
        """删除RustFS文件"""
        try:
            s3_client = self._get_client()
            s3_client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception as e:
            logger.error(f"删除RustFS文件失败: {e}", exc_info=True)
            return False
    
    def exists(self, storage_path: str) -> bool:
        """检查RustFS文件是否存在"""
        try:
            s3_client = self._get_client()
            s3_client.head_object(Bucket=self.bucket_name, Key=storage_path)
            return True
        except Exception:
            return False

    def get_file(self, storage_path: str) -> Optional[IO[bytes]]:
        """下载RustFS文件"""
        try:
            s3_client = self._get_client()
            response = s3_client.get_object(Bucket=self.bucket_name, Key=storage_path)
            return response.get("Body")
        except Exception as e:
            logger.error(f"获取RustFS文件失败: {e}", exc_info=True)
            return None
