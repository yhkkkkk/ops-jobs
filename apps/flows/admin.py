from django.contrib import admin

from .models import FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowTemplate


class FlowNodeInline(admin.TabularInline):
    model = FlowNode
    extra = 0


class FlowEdgeInline(admin.TabularInline):
    model = FlowEdge
    fk_name = "template"
    extra = 0


@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "created_by", "created_at")
    search_fields = ("name",)
    inlines = [FlowNodeInline, FlowEdgeInline]


@admin.register(FlowRun)
class FlowRunAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "status", "started_by", "created_at", "finished_at")
    list_filter = ("status", "trigger_type")


@admin.register(FlowNodeRun)
class FlowNodeRunAdmin(admin.ModelAdmin):
    list_display = ("id", "flow_run", "node", "status", "execution_record", "created_at")
    list_filter = ("status",)
