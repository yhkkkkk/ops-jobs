from django.contrib import admin
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord, AgentPackage, AgentServer


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['id', 'host', 'status', 'version', 'last_heartbeat_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['host__name', 'host__ip_address', 'version']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AgentToken)
class AgentTokenAdmin(admin.ModelAdmin):
    list_display = ['id', 'agent', 'token_last4', 'issued_by', 'created_at', 'expired_at', 'revoked_at']
    list_filter = ['revoked_at', 'created_at']
    search_fields = ['agent__host__name', 'token_last4']
    readonly_fields = ['created_at']


@admin.register(AgentInstallRecord)
class AgentInstallRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'host', 'agent', 'status', 'install_mode', 'installed_by', 'installed_at']
    list_filter = ['status', 'install_mode', 'installed_at']
    search_fields = ['host__name', 'host__ip_address']
    readonly_fields = ['installed_at']


@admin.register(AgentUninstallRecord)
class AgentUninstallRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'host', 'agent', 'status', 'uninstalled_by', 'uninstalled_at']
    list_filter = ['status', 'uninstalled_at']
    search_fields = ['host__name', 'host__ip_address']
    readonly_fields = ['uninstalled_at']


@admin.register(AgentPackage)
class AgentPackageAdmin(admin.ModelAdmin):
    list_display = ['version', 'os_type', 'arch', 'file_size', 'is_default', 'is_active', 'created_by', 'created_at']
    list_filter = ['os_type', 'arch', 'is_default', 'is_active', 'created_at']
    search_fields = ['version', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AgentServer)
class AgentServerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'base_url', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at']
