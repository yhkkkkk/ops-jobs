"""
基于Fabric的SSH管理器
提供更稳定的SSH连接和命令执行功能
"""
import logging
import time
import tempfile
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from io import StringIO
from contextlib import contextmanager

try:
    from fabric import Connection, Config
    from invoke import Responder, UnexpectedExit, CommandTimedOut
    from paramiko.ssh_exception import AuthenticationException, NoValidConnectionsError
    FABRIC_AVAILABLE = True
except ImportError:
    FABRIC_AVAILABLE = False
    Connection = None
    Config = None
    Responder = None
    UnexpectedExit = None
    AuthenticationException = Exception
    NoValidConnectionsError = Exception

from utils.realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


class FabricSSHError(Exception):
    """Fabric SSH异常"""
    pass


class FileTransferProgressMonitor:
    """文件传输进度监控器"""

    def __init__(self, task_id: str, host_id: int, host_name: str, host_ip: str,
                 file_size: int, local_path: str, remote_path: str, bandwidth_limit: int = 0):
        self.task_id = task_id
        self.host_id = host_id
        self.host_name = host_name
        self.host_ip = host_ip
        self.file_size = file_size
        self.local_path = local_path
        self.remote_path = remote_path
        self.bandwidth_limit = bandwidth_limit * 1024 if bandwidth_limit > 0 else 0  # 转换为字节/秒

        # 进度跟踪
        self.transferred = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_transferred = 0

        # 速度计算
        self.speed_samples = []  # 存储最近的速度样本
        self.max_samples = 10   # 最多保留10个样本用于平均速度计算

        # 限速相关
        self.last_throttle_time = self.start_time

        # 推送开始日志
        limit_text = f"，限速: {bandwidth_limit} KB/s" if bandwidth_limit > 0 else ""
        self._push_progress_log(f"开始上传文件{limit_text}", 0, 0)

    def progress_callback(self, transferred: int, total: int):
        """Paramiko SFTP进度回调函数"""
        current_time = time.time()
        self.transferred = transferred

        # 实现带宽限制
        if self.bandwidth_limit > 0:
            self._apply_bandwidth_limit(current_time)

        # 计算进度百分比
        progress_percent = (transferred / total * 100) if total > 0 else 0

        # 计算瞬时速度（每秒字节数）
        time_diff = current_time - self.last_update_time
        if time_diff >= 1.0:  # 每秒更新一次
            bytes_diff = transferred - self.last_transferred
            speed = bytes_diff / time_diff if time_diff > 0 else 0

            # 添加速度样本
            self.speed_samples.append(speed)
            if len(self.speed_samples) > self.max_samples:
                self.speed_samples.pop(0)

            # 计算平均速度
            avg_speed = sum(self.speed_samples) / len(self.speed_samples)

            # 估算剩余时间
            remaining_bytes = total - transferred
            eta_seconds = remaining_bytes / avg_speed if avg_speed > 0 else 0

            # 推送进度日志
            limit_info = f" (限速: {self.bandwidth_limit // 1024} KB/s)" if self.bandwidth_limit > 0 else ""
            self._push_progress_log(
                f"上传进度: {progress_percent:.1f}% ({self._format_bytes(transferred)}/{self._format_bytes(total)}){limit_info}",
                progress_percent,
                avg_speed,
                eta_seconds
            )

            self.last_update_time = current_time
            self.last_transferred = transferred

    def _apply_bandwidth_limit(self, current_time: float):
        """应用带宽限制"""
        if self.bandwidth_limit <= 0:
            return

        # 计算从上次限速检查到现在的时间差
        time_since_last_throttle = current_time - self.last_throttle_time

        # 计算在这个时间段内允许传输的最大字节数
        max_bytes_allowed = self.bandwidth_limit * time_since_last_throttle

        # 计算实际传输的字节数
        bytes_transferred_since_throttle = self.transferred - self.last_transferred

        # 如果传输速度超过限制，则暂停
        if bytes_transferred_since_throttle > max_bytes_allowed:
            # 计算需要暂停的时间
            excess_bytes = bytes_transferred_since_throttle - max_bytes_allowed
            sleep_time = excess_bytes / self.bandwidth_limit

            if sleep_time > 0.001:  # 只有当暂停时间大于1毫秒时才暂停
                time.sleep(sleep_time)

        self.last_throttle_time = current_time

    def complete(self):
        """标记传输完成"""
        total_time = time.time() - self.start_time
        avg_speed = self.file_size / total_time if total_time > 0 else 0

        self._push_progress_log(
            f"文件上传完成，总耗时: {total_time:.2f}秒，平均速度: {self._format_speed(avg_speed)}",
            100,
            avg_speed
        )

    def _push_progress_log(self, message: str, progress: float, speed: float = 0, eta: float = 0):
        """推送进度日志"""
        try:
            log_data = {
                'host_name': self.host_name,
                'host_ip': self.host_ip,
                'log_type': 'info',
                'content': message,
                'step_name': '文件传输',
                'step_order': 1,
                # 扩展字段用于前端显示
                'progress_percent': progress,
                'transfer_speed': speed,
                'eta_seconds': eta,
                'file_size': self.file_size,
                'transferred': self.transferred,
                'local_path': self.local_path,
                'remote_path': self.remote_path
            }

            realtime_log_service.push_log(self.task_id, self.host_id, log_data)
        except Exception as e:
            logger.error(f"推送进度日志失败: {e}")

    def _format_bytes(self, bytes_count: int) -> str:
        """格式化字节数为可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} PB"

    def _format_speed(self, speed: float) -> str:
        """格式化传输速度"""
        return f"{self._format_bytes(speed)}/s"


class SimpleOutputHandler:
    """简化的输出处理器，用于调试"""

    def __init__(self, name):
        self.name = name
        self.lines = []

    def write(self, data):
        if data:
            # 处理编码
            if isinstance(data, bytes):
                try:
                    data = data.decode('utf-8')
                except UnicodeDecodeError:
                    data = data.decode('utf-8', errors='replace')

            print(f"[{self.name}] 收到: {repr(data)}")
            self.lines.append(data)

    def flush(self):
        print(f"[{self.name}] flush() 调用")

    def close(self):
        print(f"[{self.name}] close() 调用")


class RealTimeOutputHandler:
    """实时输出处理器，用于捕获并推送命令执行过程中的实时输出"""

    def __init__(self, task_id: str, host_id: int, host_name: str, host_ip: str, stream_type: str = "stdout"):
        self.task_id = task_id
        self.host_id = host_id
        self.host_name = host_name
        self.host_ip = host_ip
        self.stream_type = stream_type
        self.buffer = ""
        self.lock = threading.Lock()
        self.closed = False

    def write(self, data):
        """处理写入的数据"""
        if not data or self.closed:
            return

        try:
            # 处理编码问题
            if isinstance(data, bytes):
                try:
                    data = data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        data = data.decode('gbk')
                    except UnicodeDecodeError:
                        data = data.decode('utf-8', errors='replace')

            # 使用线程锁保护缓冲区操作
            with self.lock:
                if self.closed:
                    return

                # 将数据添加到缓冲区
                self.buffer += data

                # 处理完整的行
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.rstrip('\r')  # 移除回车符

                    if line.strip():
                        self._push_log_safe(line.strip())

        except Exception as e:
            logger.error(f"RealTimeOutputHandler.write失败: {e}")

    def _push_log_safe(self, content):
        """安全地推送日志，避免阻塞"""
        try:
            # 临时改为同步推送，确保日志能正常推送
            logger.info(f"[实时日志] 推送: {self.host_name} - {content[:50]}...")
            realtime_log_service.push_log(self.task_id, self.host_id, {
                'host_name': self.host_name,
                'host_ip': self.host_ip,
                'log_type': self.stream_type,
                'content': content,
                'step_name': '脚本执行',
                'step_order': 1
            })
            logger.info(f"[实时日志] 推送成功: {self.host_name}")
        except Exception as e:
            logger.error(f"推送日志失败: {e}")

    def flush(self):
        """刷新缓冲区"""
        try:
            with self.lock:
                if self.buffer.strip() and not self.closed:
                    self._push_log_safe(self.buffer.strip())
                    self.buffer = ""
        except Exception as e:
            logger.error(f"RealTimeOutputHandler.flush失败: {e}")

    def close(self):
        """关闭处理器"""
        try:
            with self.lock:
                self.closed = True
                # 推送剩余的缓冲区内容
                if self.buffer.strip():
                    self._push_log_safe(self.buffer.strip())
                    self.buffer = ""
        except Exception as e:
            logger.error(f"RealTimeOutputHandler.close失败: {e}")


class ConnectionPool:
    """SSH连接池管理器"""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.pool: Dict[str, list] = {}  # key: connection_key, value: list of connections
        self.lock = threading.Lock()
        self._enabled = False

    def enable(self):
        """启用连接池"""
        self._enabled = True

    def disable(self):
        """禁用连接池"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """检查连接池是否启用"""
        return self._enabled

    def _get_connection_key(self, conn_info: Dict[str, Any]) -> str:
        """生成连接键"""
        return f"{conn_info['host']}:{conn_info['port']}:{conn_info['user']}"

    def get_connection(self, conn_info: Dict[str, Any], create_func):
        """从连接池获取连接，如果没有则创建"""
        if not self._enabled:
            return None

        connection_key = self._get_connection_key(conn_info)

        with self.lock:
            if connection_key not in self.pool:
                self.pool[connection_key] = []

            pool = self.pool[connection_key]

            # 尝试从池中获取可用连接
            while pool:
                conn = pool.pop()
                try:
                    # 检查连接是否仍然有效（通过检查底层transport）
                    if hasattr(conn, 'client') and conn.client and hasattr(conn.client, 'get_transport'):
                        transport = conn.client.get_transport()
                        if transport and transport.is_active():
                            return conn
                    # 连接无效，关闭它
                    try:
                        conn.close()
                    except:
                        pass
                except:
                    # 连接无效，继续尝试下一个
                    try:
                        conn.close()
                    except:
                        pass
                    continue

            # 池中没有可用连接，返回None让调用者创建新连接
            return None

    def return_connection(self, conn_info: Dict[str, Any], conn):
        """归还连接到池中"""
        if not self._enabled or not conn:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return

        connection_key = self._get_connection_key(conn_info)

        with self.lock:
            if connection_key not in self.pool:
                self.pool[connection_key] = []

            pool = self.pool[connection_key]

            # 检查池是否已满
            if len(pool) < self.max_size:
                try:
                    # 检查连接是否仍然有效（通过检查底层transport）
                    if hasattr(conn, 'client') and conn.client and hasattr(conn.client, 'get_transport'):
                        transport = conn.client.get_transport()
                        if transport and transport.is_active():
                            pool.append(conn)
                            return
                except:
                    pass

            # 池已满或连接无效，关闭连接
            try:
                conn.close()
            except:
                pass

    def clear(self):
        """清空连接池"""
        with self.lock:
            for pool in self.pool.values():
                for conn in pool:
                    try:
                        conn.close()
                    except:
                        pass
            self.pool.clear()


class FabricSSHManager:
    """基于Fabric的SSH管理器"""

    def __init__(self):
        if not FABRIC_AVAILABLE:
            raise ImportError("Fabric未安装，请运行: uv add fabric")

        # 初始化连接池
        self.connection_pool = ConnectionPool(max_size=10)
        self._init_connection_pool()

    def _init_connection_pool(self):
        """初始化连接池配置"""
        try:
            from apps.system_config.models import ConfigManager
            enable_pool = ConfigManager.get('fabric.enable_connection_pool', False)
            if enable_pool:
                self.connection_pool.enable()
                logger.info("SSH连接池已启用")
            else:
                self.connection_pool.disable()
        except Exception as e:
            logger.warning(f"初始化连接池配置失败: {e}，默认禁用连接池")
            self.connection_pool.disable()

    def execute_script(self, host, script_content: str, script_type: str = 'shell',
                      timeout: int = None, task_id: Optional[str] = None,
                      account_id: Optional[int] = None) -> Dict[str, Any]:
        """
        在远程主机上执行脚本

        Args:
            host: 主机对象
            script_content: 脚本内容
            script_type: 脚本类型 (shell, python, powershell等)
            timeout: 超时时间(秒)，如果为None则使用配置的默认值
            task_id: 任务ID，用于实时日志
            account_id: 可选的账号ID，如果提供则使用账号管理的认证信息

        Returns:
            执行结果字典
        """
        start_time = time.time()
        start_datetime = datetime.now()

        try:
            # 如果没有指定超时时间，使用系统配置的默认值
            if timeout is None:
                from apps.system_config.models import ConfigManager
                timeout = ConfigManager.get('fabric.command_timeout', 300)

            # 获取主机连接信息（支持使用账号管理的认证信息）
            conn_info = self._get_connection_info(host, account_id=account_id)

            # 创建Fabric连接
            with self._create_connection(conn_info, timeout) as conn:

                # 推送开始执行日志
                if task_id:
                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info',
                        'content': f'开始执行{script_type}脚本',
                        'step_name': '脚本执行',
                        'step_order': 1
                    })

                # 根据脚本类型执行
                if script_type.lower() == 'python':
                    result = self._execute_python_script(conn, script_content, timeout, host, task_id)
                elif script_type.lower() == 'powershell':
                    result = self._execute_powershell_script(conn, script_content, timeout, host, task_id)
                else:  # shell
                    result = self._execute_shell_script(conn, script_content, timeout, host, task_id)

                # 计算执行时间
                end_datetime = datetime.now()
                execution_time = time.time() - start_time
                result['execution_time'] = execution_time
                result['start_time'] = start_datetime.isoformat()
                result['end_time'] = end_datetime.isoformat()

                # 推送完成日志
                if task_id:
                    status = '成功' if result['success'] else '失败'
                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info' if result['success'] else 'error',
                        'content': f'脚本执行{status}，耗时: {execution_time:.2f}秒',
                        'step_name': '脚本执行',
                        'step_order': 1
                    })

                return result

        except Exception as e:
            end_datetime = datetime.now()
            execution_time = time.time() - start_time
            error_msg = str(e)

            logger.error(f"Fabric执行脚本失败 - 主机: {host.name}, 错误: {error_msg}")

            # 推送错误日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'error',
                    'content': f'脚本执行异常: {error_msg}',
                    'step_name': '脚本执行',
                    'step_order': 1
                })

            return {
                'success': False,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'stdout': '',
                'stderr': error_msg,
                'exit_code': -1,
                'message': f'执行失败: {error_msg}',
                'execution_time': execution_time,
                'start_time': start_datetime.isoformat(),
                'end_time': end_datetime.isoformat()
            }

    def _get_connection_info(self, host, account_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取主机连接信息

        Args:
            host: 主机对象
            account_id: 可选的账号ID，如果提供则使用该账号，否则使用主机配置的账号

        Returns:
            连接信息字典
        """
        from .models import ServerAccount

        # 确定使用哪个账号
        account = None
        if account_id:
            # 如果提供了account_id，使用指定的账号
            try:
                account = ServerAccount.objects.get(id=account_id)
            except ServerAccount.DoesNotExist:
                raise FabricSSHError(f"账号ID {account_id} 不存在")
        elif host.account:
            # 使用主机配置的账号
            account = host.account
        else:
            raise FabricSSHError(f"主机 {host.name} 没有配置服务器账号，请在主机设置中指定账号或在执行时提供账号ID")

        # 获取IP地址（优先使用内网IP）
        host_ip = host.internal_ip or host.public_ip
        if not host_ip:
            raise FabricSSHError(f"主机 {host.name} 没有配置IP地址（内网IP或外网IP）")

        username = account.username

        # 解密密码（如果使用密码认证）
        password = None
        if account.password:
            try:
                password = self._decrypt_password(account.password)
            except Exception as e:
                logger.warning(f"解密账号 {account.name} 密码失败: {e}")
                password = account.password  # 如果解密失败，使用原始值

        # 处理私钥（如果使用密钥认证）
        key_filename = None
        if account.private_key:
            # 创建临时私钥文件
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                    f.write(account.private_key)
                    key_filename = f.name
                # 设置私钥文件权限
                os.chmod(key_filename, 0o600)
            except Exception as e:
                logger.error(f"创建账号私钥文件失败: {e}")
                raise FabricSSHError(f"账号私钥处理失败: {str(e)}")

        logger.info(f"使用账号认证信息: 账号={account.name}, 用户名={username}, 主机={host.name}, IP={host_ip}")

        return {
            'host': host_ip,
            'port': host.port or 22,
            'user': username,
            'password': password,
            'key_filename': key_filename,
        }

    def _decrypt_password(self, encrypted_password: str) -> str:
        """解密密码"""
        from .utils import decrypt_password
        return decrypt_password(encrypted_password)

    def _create_connection_config(self, conn_info: Dict[str, Any], timeout: int) -> Config:
        """创建Fabric连接配置"""
        from apps.system_config.models import ConfigManager

        # 获取连接超时配置
        connection_timeout = ConfigManager.get('fabric.connection_timeout', 30)

        return Config(overrides={
            'connect_kwargs': {
                'timeout': connection_timeout,  # 使用配置的连接超时时间
                'auth_timeout': connection_timeout,
                'banner_timeout': connection_timeout,
            },
            'timeouts': {
                'connect': connection_timeout,
            },
            'run': {
                'warn': True,  # 不要因为非零退出码抛异常
                'timeout': timeout,  # 设置命令执行超时
                'encoding': 'utf-8',  # 设置输出编码为UTF-8
                'env': {
                    'LC_ALL': 'C.UTF-8',  # 设置UTF-8编码环境
                    'LANG': 'C.UTF-8',
                    'PYTHONIOENCODING': 'utf-8'  # Python输出编码
                }
            }
        })

    def _create_new_connection(self, conn_info: Dict[str, Any], config: Config) -> Connection:
        """创建新的Fabric连接"""
        # 准备连接参数
        connect_kwargs = {}
        if conn_info['password']:
            connect_kwargs['password'] = conn_info['password']
        if conn_info['key_filename']:
            connect_kwargs['key_filename'] = conn_info['key_filename']

        conn = Connection(
            host=conn_info['host'],
            port=conn_info['port'],
            user=conn_info['user'],
            config=config,
            connect_kwargs=connect_kwargs
        )

        # 测试连接
        conn.open()
        logger.info(f"Fabric SSH连接成功: {conn_info['host']}:{conn_info['port']}")

        return conn

    def _is_connection_pool_enabled(self) -> bool:
        """动态检查连接池是否启用"""
        try:
            from apps.system_config.models import ConfigManager
            return ConfigManager.get('fabric.enable_connection_pool', False)
        except Exception as e:
            logger.warning(f"检查连接池配置失败: {e}，默认禁用连接池")
            return False

    @contextmanager
    def _create_connection(self, conn_info: Dict[str, Any], timeout: int):
        """创建Fabric连接（支持连接池）"""
        config = self._create_connection_config(conn_info, timeout)

        # 动态检查连接池是否启用
        pool_enabled = self._is_connection_pool_enabled()

        # 尝试从连接池获取连接
        conn = None
        from_pool = False

        if pool_enabled:
            conn = self.connection_pool.get_connection(conn_info, self._create_new_connection)
            if conn:
                from_pool = True
                logger.debug(f"从连接池获取连接: {conn_info['host']}:{conn_info['port']}")

        # 如果连接池中没有可用连接，创建新连接
        if not conn:
            try:
                conn = self._create_new_connection(conn_info, config)
            except (AuthenticationException, NoValidConnectionsError) as e:
                raise FabricSSHError(f"SSH认证失败: {str(e)}")
            except Exception as e:
                raise FabricSSHError(f"SSH连接失败: {str(e)}")

        try:
            yield conn
        finally:
            # 归还连接到池中或关闭连接
            if pool_enabled and from_pool:
                # 从池中获取的连接，归还到池中
                self.connection_pool.return_connection(conn_info, conn)
            else:
                # 新创建的连接，如果连接池启用则归还，否则关闭
                if pool_enabled:
                    self.connection_pool.return_connection(conn_info, conn)
                else:
                    if conn:
                        try:
                            conn.close()
                        except:
                            pass

    def _execute_shell_script(self, conn, script_content: str, timeout: int,
                             host, task_id: Optional[str]) -> Dict[str, Any]:
        """执行Shell脚本"""
        try:
            # 推送开始执行日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': '开始执行shell脚本',
                    'step_name': '脚本执行',
                    'step_order': 1
                })

            # 创建实时输出处理器
            stdout_handler = None
            stderr_handler = None

            if task_id:
                # 使用改进的实时输出处理器
                stdout_handler = RealTimeOutputHandler(
                    task_id, host.id, host.name, host.ip_address, "stdout"
                )
                stderr_handler = RealTimeOutputHandler(
                    task_id, host.id, host.name, host.ip_address, "stderr"
                )

            # 直接执行脚本内容，避免文件上传的复杂性
            # 使用bash -c来执行多行脚本，并设置UTF-8编码环境
            escaped_script = script_content.replace("'", "'\"'\"'")  # 转义单引号
            # 在脚本前添加编码设置
            command = f"export LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONIOENCODING=utf-8; bash -c '{escaped_script}'"

            logger.info(f"执行命令: {command}")

            # 执行脚本，使用实时输出处理器
            logger.info(f"开始执行命令: {command}")
            result = conn.run(
                command,
                out_stream=stdout_handler,  # 使用实时输出处理器
                err_stream=stderr_handler,  # 使用实时错误处理器
                warn=True,  # 命令失败时不抛出异常
                pty=False,  # 不使用伪终端，避免缓冲问题
                timeout=timeout,
                encoding='utf-8',  # 明确指定编码
                env={
                    'PYTHONUNBUFFERED': '1',  # 确保Python输出不缓冲
                    'LC_ALL': 'C.UTF-8',      # 设置UTF-8编码
                    'LANG': 'C.UTF-8',        # 设置语言环境
                    'PYTHONIOENCODING': 'utf-8'  # Python输出编码
                }
            )
            logger.info(f"命令执行完成，退出码: {result.exited}")

            # 确保输出处理器正确关闭
            if stdout_handler:
                stdout_handler.flush()
                stdout_handler.close()
            if stderr_handler:
                stderr_handler.flush()
                stderr_handler.close()

            return {
                'success': result.ok,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'stdout': result.stdout or '',
                'stderr': result.stderr or '',
                'exit_code': result.exited,
                'message': '执行成功' if result.ok else f'执行失败，退出码: {result.exited}'
            }



        except Exception as e:
            raise FabricSSHError(f"Shell脚本执行失败: {str(e)}")


    def _execute_python_script(self, conn, script_content: str, timeout: int,
                              host, task_id: Optional[str]) -> Dict[str, Any]:
        """执行Python脚本"""
        try:
            # 创建临时脚本文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                local_script_path = f.name

            try:
                # 上传脚本到远程主机
                remote_script_path = f'/tmp/script_{int(time.time())}.py'
                conn.put(local_script_path, remote_script_path)

                # 创建实时输出处理器
                stdout_handler = None
                stderr_handler = None

                if task_id:
                    stdout_handler = RealTimeOutputHandler(
                        task_id, host.id, host.name, host.ip_address, "stdout"
                    )
                    stderr_handler = RealTimeOutputHandler(
                        task_id, host.id, host.name, host.ip_address, "stderr"
                    )

                # 执行Python脚本，使用Fabric原生的实时输出流
                # 注意：不使用pty=True，因为它可能导致输出缓冲问题
                result = conn.run(
                    f'python3 -u {remote_script_path}',  # -u 参数确保输出不缓冲
                    out_stream=stdout_handler,
                    err_stream=stderr_handler,
                    warn=True,  # 命令失败时不抛出异常
                    pty=False,  # 不使用伪终端，避免缓冲问题
                    timeout=timeout,
                    env={'PYTHONUNBUFFERED': '1'}  # 确保Python输出不缓冲
                )

                # 确保所有输出都已推送
                if stdout_handler:
                    stdout_handler.close()
                if stderr_handler:
                    stderr_handler.close()

                # 清理远程脚本文件
                try:
                    conn.run(f'rm -f {remote_script_path}', timeout=10)
                except:
                    pass

                return {
                    'success': result.ok,
                    'host_id': host.id,
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'stdout': result.stdout or '',
                    'stderr': result.stderr or '',
                    'exit_code': result.exited,
                    'message': '执行成功' if result.ok else f'执行失败，退出码: {result.exited}'
                }

            finally:
                # 清理本地临时文件
                try:
                    os.unlink(local_script_path)
                except:
                    pass

        except Exception as e:
            raise FabricSSHError(f"Python脚本执行失败: {str(e)}")

    def _execute_powershell_script(self, conn, script_content: str, timeout: int,
                                  host, task_id: Optional[str]) -> Dict[str, Any]:
        """执行PowerShell脚本"""
        try:
            # PowerShell脚本需要在Windows主机上执行
            # 这里简化处理，实际可能需要更复杂的逻辑
            result = conn.run(f'powershell -Command "{script_content}"', timeout=timeout, hide=False)

            return {
                'success': result.return_code == 0,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'stdout': result.stdout or '',
                'stderr': result.stderr or '',
                'exit_code': result.return_code,
                'message': '执行成功' if result.return_code == 0 else f'执行失败，退出码: {result.return_code}'
            }

        except Exception as e:
            raise FabricSSHError(f"PowerShell脚本执行失败: {str(e)}")

    def transfer_file(self, host, transfer_type: str, local_path: str, remote_path: str,
                     timeout: int = None, task_id: Optional[str] = None,
                     source_server_host: Optional[str] = None, source_server_user: Optional[str] = None,
                     source_server_path: Optional[str] = None, account_id: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        在远程主机上执行文件传输

        Args:
            host: 主机对象
            transfer_type: 传输类型 ('local_upload', 'server_upload')
            local_path: 本地路径（local_upload时使用）
            remote_path: 远程路径
            timeout: 超时时间(秒)，如果为None则使用配置的默认值
            task_id: 任务ID，用于实时日志
            source_server_host: 源服务器地址（server_upload时使用）
            source_server_user: 源服务器用户名（server_upload时使用）
            source_server_path: 源服务器文件路径（server_upload时使用）
            account_id: 可选的账号ID，如果提供则使用账号管理的认证信息
            **kwargs: 其他参数，如overwrite_policy等

        Returns:
            传输结果字典
        """
        start_time = time.time()
        start_datetime = datetime.now()

        try:
            # 如果没有指定超时时间，使用系统配置的默认值
            if timeout is None:
                from apps.system_config.models import ConfigManager
                timeout = ConfigManager.get('fabric.command_timeout', 300)

            # 获取主机连接信息（支持使用账号管理的认证信息）
            conn_info = self._get_connection_info(host, account_id=account_id)

            # 创建Fabric连接
            with self._create_connection(conn_info, timeout) as conn:

                # 推送开始传输日志
                if task_id:
                    if transfer_type == 'local_upload':
                        log_content = f'开始从本地上传文件: {local_path} -> {remote_path}'
                    elif transfer_type == 'server_upload':
                        log_content = f'开始从服务器传输文件: {source_server_user}@{source_server_host}:{source_server_path} -> {remote_path}'
                    else:
                        log_content = f'开始传输文件: {remote_path}'

                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info',
                        'content': log_content,
                        'step_name': '文件传输',
                        'step_order': 1
                    })

                # 根据传输类型执行
                if transfer_type == 'local_upload':
                    result = self._upload_file(conn, local_path, remote_path, host, task_id, **kwargs)
                elif transfer_type == 'server_upload':
                    result = self._server_upload_file(conn, source_server_host, source_server_user, source_server_path,
                                                    remote_path, host, task_id, **kwargs)
                else:
                    raise FabricSSHError(f"不支持的传输类型: {transfer_type}")

                # 计算执行时间
                execution_time = time.time() - start_time
                result['execution_time'] = execution_time
                result['start_time'] = start_datetime.isoformat()
                result['end_time'] = datetime.now().isoformat()

                # 推送完成日志
                if task_id:
                    status = '成功' if result['success'] else '失败'
                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info' if result['success'] else 'error',
                        'content': f'文件传输{status}，耗时: {execution_time:.2f}秒',
                        'step_name': '文件传输',
                        'step_order': 1
                    })

                return result

        except FabricSSHError:
            raise
        except Exception as e:
            raise FabricSSHError(f"文件传输失败: {str(e)}")

    def _upload_file(self, conn, local_path: str, remote_path: str, host, task_id: Optional[str], **kwargs) -> Dict[str, Any]:
        """上传文件到远程主机"""
        try:
            overwrite_policy = kwargs.get('overwrite_policy', 'overwrite')

            # 检查远程文件是否存在
            if overwrite_policy != 'overwrite':
                try:
                    result = conn.run(f'test -f {remote_path}', warn=True, hide=True)
                    if result.ok:  # 文件存在
                        if overwrite_policy == 'skip':
                            return {
                                'success': True,
                                'host_id': host.id,
                                'host_name': host.name,
                                'host_ip': host.ip_address,
                                'message': '文件已存在，跳过上传',
                                'skipped': True
                            }
                        elif overwrite_policy == 'backup':
                            # 备份现有文件
                            backup_path = f"{remote_path}.backup.{int(time.time())}"
                            conn.run(f'cp {remote_path} {backup_path}')
                        elif overwrite_policy == 'fail':
                            return {
                                'success': False,
                                'host_id': host.id,
                                'host_name': host.name,
                                'host_ip': host.ip_address,
                                'message': '文件已存在，上传失败',
                            }
                except:
                    pass  # 文件不存在，继续上传

            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                conn.run(f'mkdir -p {remote_dir}', warn=True)

            # 获取文件大小用于进度计算
            file_size = 0
            try:
                file_size = os.path.getsize(local_path)
            except:
                pass

            # 创建进度监控器
            progress_monitor = None
            if task_id and file_size > 0:
                bandwidth_limit = kwargs.get('bandwidth_limit', 0)
                progress_monitor = FileTransferProgressMonitor(
                    task_id=task_id,
                    host_id=host.id,
                    host_name=host.name,
                    host_ip=host.ip_address,
                    file_size=file_size,
                    local_path=local_path,
                    remote_path=remote_path,
                    bandwidth_limit=bandwidth_limit
                )

            # 上传文件，使用进度回调
            if progress_monitor:
                conn.put(local_path, remote_path, callback=progress_monitor.progress_callback)
            else:
                conn.put(local_path, remote_path)

            # 推送完成进度
            if progress_monitor:
                progress_monitor.complete()

            return {
                'success': True,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'message': '文件上传成功',
                'local_path': local_path,
                'remote_path': remote_path,
                'file_size': file_size
            }

        except Exception as e:
            raise FabricSSHError(f"文件上传失败: {str(e)}")

    def _server_upload_file(self, conn, source_server_host: str, source_server_user: str, source_server_path: str,
                           remote_path: str, host, task_id: Optional[str], **kwargs) -> Dict[str, Any]:
        """
        从另一台服务器传输文件到目标主机（三跳模式：Job平台中转）
        1. Job平台从源服务器下载文件到临时目录
        2. Job平台将文件上传到目标服务器
        3. 删除临时文件
        """
        temp_file_path = None
        source_conn = None
        try:
            from apps.hosts.models import Host
            
            overwrite_policy = kwargs.get('overwrite_policy', 'overwrite')
            timeout = kwargs.get('timeout', 300)

            # 推送三跳传输开始日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'开始三跳传输: {source_server_user}@{source_server_host}:{source_server_path} -> {host.name}:{remote_path}',
                    'step_name': '文件传输',
                    'step_order': 1
                })

            # 步骤1: 查找源服务器Host对象（源服务器必须在系统中，以便获取认证信息）
            source_host = None
            try:
                # 尝试通过IP地址查找
                source_host = Host.objects.filter(ip_address=source_server_host).first()
                # 如果找不到，尝试通过hostname查找
                if not source_host:
                    source_host = Host.objects.filter(hostname=source_server_host).first()
                # 如果还是找不到，尝试通过name查找
                if not source_host:
                    source_host = Host.objects.filter(name=source_server_host).first()
            except Exception as e:
                logger.error(f"查找源服务器Host对象失败: {e}")
                raise FabricSSHError(f"查找源服务器失败: {str(e)}")

            # 如果找不到Host对象，报错（源服务器必须在系统中才能进行三跳传输）
            if not source_host:
                error_msg = f"源服务器 {source_server_host} 不在主机列表中，无法进行三跳传输。请先将源服务器添加到系统中。"
                logger.error(error_msg)
                if task_id:
                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'error',
                        'content': error_msg,
                        'step_name': '文件传输',
                        'step_order': 1
                    })
                raise FabricSSHError(error_msg)
            
            # 如果源服务器用户名不匹配，使用提供的用户名（但使用源服务器的认证信息）
            if source_host.username != source_server_user:
                logger.info(f"源服务器用户名不匹配，使用提供的用户名: {source_server_user} (原用户名: {source_host.username})")

            # 步骤2: 创建临时文件路径
            import uuid
            temp_dir = tempfile.gettempdir()
            file_name = os.path.basename(source_server_path) or f"transfer_{uuid.uuid4().hex[:8]}"
            temp_file_path = os.path.join(temp_dir, f"ops_job_transfer_{uuid.uuid4().hex}_{file_name}")

            # 推送下载开始日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'步骤1/3: 从源服务器 {source_server_host} 下载文件到临时目录',
                    'step_name': '文件传输',
                    'step_order': 2
                })

            # 步骤3: 从源服务器下载文件到临时目录
            try:
                source_conn_info = self._get_connection_info(source_host)
                # 如果提供了不同的用户名，使用提供的用户名（但使用源服务器的认证信息）
                if source_host.username != source_server_user:
                    source_conn_info['user'] = source_server_user
                
                with self._create_connection(source_conn_info, timeout) as source_conn:
                    download_result = self._download_file(
                        source_conn, 
                        temp_file_path, 
                        source_server_path, 
                        source_host, 
                        task_id, 
                        **kwargs
                    )
                    
                    if not download_result.get('success'):
                        return {
                            'success': False,
                            'host_id': host.id,
                            'host_name': host.name,
                            'host_ip': host.ip_address,
                            'message': f'从源服务器下载文件失败: {download_result.get("message", "未知错误")}',
                        }
            except Exception as e:
                error_msg = f'从源服务器下载文件失败: {str(e)}'
                logger.error(error_msg)
                if task_id:
                    realtime_log_service.push_log(task_id, host.id, {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'error',
                        'content': error_msg,
                        'step_name': '文件传输',
                        'step_order': 2
                    })
                return {
                    'success': False,
                    'host_id': host.id,
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'message': error_msg,
                }

            # 推送上传开始日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'步骤2/3: 上传文件到目标服务器 {host.name}',
                    'step_name': '文件传输',
                    'step_order': 3
                })

            # 步骤4: 上传文件到目标服务器
            upload_result = self._upload_file(conn, temp_file_path, remote_path, host, task_id, **kwargs)
            
            if not upload_result.get('success'):
                return {
                    'success': False,
                    'host_id': host.id,
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'message': f'上传文件到目标服务器失败: {upload_result.get("message", "未知错误")}',
                }

            # 步骤5: 删除临时文件
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    if task_id:
                        realtime_log_service.push_log(task_id, host.id, {
                            'host_name': host.name,
                            'host_ip': host.ip_address,
                            'log_type': 'info',
                            'content': f'步骤3/3: 清理临时文件完成',
                            'step_name': '文件传输',
                            'step_order': 4
                        })
            except Exception as e:
                logger.warning(f"删除临时文件失败: {temp_file_path}, 错误: {e}")
                # 临时文件删除失败不影响传输结果

            return {
                'success': True,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'message': '三跳传输成功',
                'source_server': f'{source_server_user}@{source_server_host}:{source_server_path}',
                'remote_path': remote_path,
                'transfer_mode': 'three_hop'  # 标记为三跳模式
            }

        except Exception as e:
            error_msg = f"三跳传输失败: {str(e)}"
            logger.error(error_msg)
            
            # 确保清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            raise FabricSSHError(error_msg)

    def _download_file(self, conn, local_path: str, remote_path: str, host, task_id: Optional[str], **kwargs) -> Dict[str, Any]:
        """从远程主机下载文件"""
        try:
            overwrite_policy = kwargs.get('overwrite_policy', 'overwrite')

            # 检查本地文件是否存在
            if overwrite_policy != 'overwrite' and os.path.exists(local_path):
                if overwrite_policy == 'skip':
                    return {
                        'success': True,
                        'host_id': host.id,
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'message': '本地文件已存在，跳过下载',
                        'skipped': True
                    }
                elif overwrite_policy == 'backup':
                    # 备份现有文件
                    backup_path = f"{local_path}.backup.{int(time.time())}"
                    os.rename(local_path, backup_path)
                elif overwrite_policy == 'fail':
                    return {
                        'success': False,
                        'host_id': host.id,
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'message': '本地文件已存在，下载失败',
                    }

            # 确保本地目录存在
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)

            # 下载文件
            conn.get(remote_path, local_path)

            return {
                'success': True,
                'host_id': host.id,
                'host_name': host.name,
                'host_ip': host.ip_address,
                'message': '文件下载成功',
                'local_path': local_path,
                'remote_path': remote_path
            }

        except Exception as e:
            raise FabricSSHError(f"文件下载失败: {str(e)}")


# 全局实例
fabric_ssh_manager = FabricSSHManager() if FABRIC_AVAILABLE else None
