"""
存储服务工厂类
根据存储类型返回对应的存储后端
"""
import logging
from typing import Optional
from .storage_backends import (
    StorageBackend,
    LocalStorageBackend,
    OSSStorageBackend,
    S3StorageBackend,
    COSStorageBackend,
    MinIOStorageBackend,
    RustFSStorageBackend,
)

logger = logging.getLogger(__name__)


class StorageService:
    """存储服务工厂类"""
    
    _backends = {
        'local': LocalStorageBackend,
        'oss': OSSStorageBackend,
        's3': S3StorageBackend,
        'cos': COSStorageBackend,
        'minio': MinIOStorageBackend,
        'rustfs': RustFSStorageBackend,
    }
    # 缓存已创建的后端实例，避免每次请求都初始化底层客户端（例如 COS/S3 客户端会绑定连接池）
    _instances: dict[str, StorageBackend] = {}
    _lock = __import__('threading').Lock()

    @classmethod
    def get_backend(cls, storage_type: str) -> Optional[StorageBackend]:
        """
        根据存储类型获取存储后端实例（单例复用）
        
        Args:
            storage_type: 存储类型 (local, oss, s3, cos, minio, rustfs)
        
        Returns:
            存储后端实例，如果类型不支持返回None
        """
        # 快速路径：已有实例直接返回
        inst = cls._instances.get(storage_type)
        if inst is not None:
            return inst

        backend_class = cls._backends.get(storage_type)
        if backend_class is None:
            logger.error(f"不支持的存储类型: {storage_type}")
            return None

        # 加锁创建实例，防止并发重复创建
        try:
            with cls._lock:
                # 可能在等待锁的过程中已经创建好了
                inst = cls._instances.get(storage_type)
                if inst is not None:
                    return inst
                instance = backend_class()
                cls._instances[storage_type] = instance
                return instance
        except Exception as e:
            logger.error(f"初始化存储后端失败 ({storage_type}): {e}", exc_info=True)
            return None
    
    @classmethod
    def generate_storage_path(cls, version: str, os_type: str, arch: str, filename: str) -> str:
        """
        生成统一的存储路径
        
        Args:
            version: 版本号
            os_type: 操作系统类型
            arch: 架构
            filename: 文件名
        
        Returns:
            存储路径，格式: agent_packages/{version}/{os_type}/{arch}/{filename}
        """
        return f"agent_packages/{version}/{os_type}/{arch}/{filename}"
