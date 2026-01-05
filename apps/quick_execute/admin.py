"""
快速执行Admin配置

注意：快速执行模块不需要自己的模型，
它直接使用executor模块的ExecutionTask和TaskExecution模型。
这里只是为了保持模块完整性而创建的文件。
"""
from django.contrib import admin

# 快速执行模块不需要注册自己的模型
# 所有的执行记录都在executor模块中管理
