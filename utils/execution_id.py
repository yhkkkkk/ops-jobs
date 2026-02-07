"""
统一的执行ID生成服务
"""
import time
import threading
from django.core.cache import cache
from django.conf import settings


class ExecutionIDGenerator:
    """执行ID生成器 - 生成全局唯一的数字ID"""
    
    _lock = threading.Lock()
    _last_timestamp = 0
    _sequence = 0
    
    # 配置参数
    TIMESTAMP_BITS = 41  # 时间戳位数 (可用到2109年)
    SEQUENCE_BITS = 12   # 序列号位数 (每毫秒可生成4096个ID)
    WORKER_BITS = 10     # 工作节点位数 (支持1024个节点)
    
    # 位移量
    SEQUENCE_SHIFT = 0
    WORKER_SHIFT = SEQUENCE_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_BITS
    
    # 最大值
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
    MAX_WORKER_ID = (1 << WORKER_BITS) - 1
    
    # 起始时间戳 (2024-01-01 00:00:00 UTC)
    EPOCH = 1704067200000
    
    def __init__(self, worker_id=None):
        """
        初始化执行ID生成器
        
        Args:
            worker_id: 工作节点ID，如果不指定则自动获取
        """
        if worker_id is None:
            worker_id = self._get_worker_id()
        
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError(f"Worker ID必须在0-{self.MAX_WORKER_ID}之间")
        
        self.worker_id = worker_id
    
    def _get_worker_id(self):
        """获取工作节点ID"""
        # 尝试从配置中获取
        worker_id = getattr(settings, 'EXECUTION_ID_WORKER_ID', None)
        if worker_id is not None:
            return worker_id
        
        # 使用缓存生成唯一的worker_id
        cache_key = 'execution_id_worker_counter'
        try:
            # 原子性地获取并递增worker_id
            worker_id = cache.get(cache_key, 0)
            cache.set(cache_key, (worker_id + 1) % (self.MAX_WORKER_ID + 1), timeout=None)
            return worker_id
        except Exception:
            # 如果缓存不可用，使用进程ID的后10位
            import os
            return os.getpid() % (self.MAX_WORKER_ID + 1)
    
    def generate(self):
        """生成执行ID"""
        with self._lock:
            timestamp = self._get_timestamp()
            
            # 如果时间戳相同，递增序列号
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self.MAX_SEQUENCE
                if self._sequence == 0:
                    # 序列号溢出，等待下一毫秒
                    timestamp = self._wait_next_millis(timestamp)
            else:
                self._sequence = 0
            
            if timestamp < self._last_timestamp:
                raise RuntimeError("系统时钟回退，无法生成执行ID")
            
            self._last_timestamp = timestamp
            
            # 组装ID: 时间戳 + 工作节点ID + 序列号
            execution_id = (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT) |
                (self.worker_id << self.WORKER_SHIFT) |
                self._sequence
            )
            
            return execution_id
    
    def _get_timestamp(self):
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    def _wait_next_millis(self, last_timestamp):
        """等待下一毫秒"""
        timestamp = self._get_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_timestamp()
        return timestamp
    
    def parse(self, execution_id):
        """解析执行ID"""
        timestamp = ((execution_id >> self.TIMESTAMP_SHIFT) + self.EPOCH)
        worker_id = (execution_id >> self.WORKER_SHIFT) & self.MAX_WORKER_ID
        sequence = execution_id & self.MAX_SEQUENCE
        
        return {
            'timestamp': timestamp,
            'worker_id': worker_id,
            'sequence': sequence,
            'datetime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp / 1000))
        }


# 全局执行ID生成器实例
_execution_id_generator = None


def get_execution_id_generator():
    """获取执行ID生成器实例"""
    global _execution_id_generator
    if _execution_id_generator is None:
        _execution_id_generator = ExecutionIDGenerator()
    return _execution_id_generator


def generate_execution_id():
    """生成执行ID - 便捷函数"""
    return get_execution_id_generator().generate()


def parse_execution_id(execution_id):
    """解析执行ID - 便捷函数"""
    return get_execution_id_generator().parse(execution_id)


# 兼容性函数
def generate_job_execution_id():
    """生成作业执行ID"""
    return generate_execution_id()


def generate_script_execution_id():
    """生成脚本执行ID"""
    return generate_execution_id()


def generate_scheduled_execution_id():
    """生成定时任务执行ID"""
    return generate_execution_id()
