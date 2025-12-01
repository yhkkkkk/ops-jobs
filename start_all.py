#!/usr/bin/env python
"""
一键启动所有后端服务
同时启动 WSGI、ASGI 和 Celery 服务
"""
import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

class ServiceManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        
    def start_service(self, name, command, cwd=None):
        """启动一个服务"""
        print(f"Starting {name}...")
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd or os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.processes[name] = process
            
            # 启动日志监控线程
            log_thread = threading.Thread(
                target=self._monitor_logs,
                args=(name, process),
                daemon=True
            )
            log_thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to start {name}: {e}")
            return False
    
    def _monitor_logs(self, name, process):
        """监控服务日志输出"""
        while self.running and process.poll() is None:
            try:
                line = process.stdout.readline()
                if line:
                    # 添加服务名前缀
                    print(f"[{name}] {line.rstrip()}")
            except:
                break
    
    def stop_all(self):
        """停止所有服务"""
        print("\nStopping all services...")
        self.running = False
        
        for name, process in self.processes.items():
            if process.poll() is None:
                print(f"Stopping {name}...")
                try:
                    # Windows 使用 CTRL_BREAK_EVENT，Unix 使用 SIGTERM
                    if os.name == 'nt':
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    
                    # 等待进程结束
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"Force killing {name}...")
                        process.kill()
                        process.wait()

                except Exception as e:
                    print(f"Error stopping {name}: {e}")

        print("All services stopped")
    
    def wait_for_services(self):
        """等待所有服务运行"""
        try:
            while self.running:
                # 检查是否有服务异常退出
                for name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        print(f"Service {name} exited unexpectedly (exit code: {process.returncode})")
                        if self.running:
                            print("Attempting to restart service...")
                            # 这里可以添加重启逻辑
                
                time.sleep(1)
        except KeyboardInterrupt:
            pass

def check_dependencies():
    """检查依赖是否安装"""
    print("Checking dependencies...")

    # 检查 Redis
    try:
        import redis
        r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
        r.ping()
        print("Redis connection OK")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        print("Please ensure Redis service is running")
        return False

    # 检查必要的包
    required_packages = ['django', 'celery', 'daphne']
    for package in required_packages:
        try:
            __import__(package)
            print(f"{package} installed")
        except ImportError:
            print(f"{package} not installed")
            return False
    
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("Django Multi-Service Launcher")
    print("=" * 60)
    
    # 设置环境变量
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ops_job.settings')
    
    # 检查依赖
    if not check_dependencies():
        print("\nDependency check failed, please resolve the above issues first")
        return 1
    
    # 创建服务管理器
    manager = ServiceManager()
    
    # 注册信号处理器
    def signal_handler(signum, frame):
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    print("\nStarting services...")

    # 启动服务
    services = [
        {
            'name': 'WSGI',
            'command': [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000'],
            'description': 'Django WSGI Server (port 8000)'
        },
        {
            'name': 'ASGI',
            'command': [sys.executable, '-m', 'daphne', '-b', '127.0.0.1', '-p', '8001', 'ops_job.asgi:application'],
            'description': 'Django ASGI Server (port 8001)'
        },
        {
            'name': 'Celery',
            'command': [sys.executable, '-m', 'celery', '-A', 'ops_job', 'worker', '--loglevel=debug', '--pool=solo', '--concurrency=1', '--without-gossip', '--without-mingle', '--without-heartbeat', '--events'],
            'description': 'Celery Background Task Processor (Debug Mode)'
        }
    ]
    
    # 启动所有服务
    success_count = 0
    for service in services:
        print(f"\n{service['description']}")
        if manager.start_service(service['name'], service['command']):
            success_count += 1
            time.sleep(2)  # 给服务一些启动时间
        else:
            print(f"Failed to start {service['name']}")

    if success_count == 0:
        print("\nNo services started successfully")
        return 1

    print(f"\nSuccessfully started {success_count}/{len(services)} services")
    print("\n" + "=" * 60)
    print("Service Status:")
    print("  - WSGI Server: http://127.0.0.1:8000")
    print("  - ASGI Server: http://127.0.0.1:8001")
    print("  - Admin Panel: http://127.0.0.1:8000/admin/")
    print("  - API Docs: http://127.0.0.1:8000/docs/swagger/")
    print("  - Celery Worker: Running in background")
    print("=" * 60)
    print("\nTips:")
    print("  - Frontend dev server needs to be started separately: cd frontend && npm run dev")
    print("  - Press Ctrl+C to stop all services")
    print("  - Log output format: [ServiceName] log content")
    print("\nServices are running...")
    
    # 等待服务运行
    try:
        manager.wait_for_services()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
