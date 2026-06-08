from apps.hosts.models import Host, HostGroup


def get_file_source_errors(file_sources):
    errors = []
    for index, source in enumerate(file_sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"file source {index} must be an object")
            continue
        if source.get("type") not in (None, "artifact"):
            errors.append(f"unsupported file source type: {source.get('type')}")
        if not source.get("download_url"):
            errors.append(f"artifact file source {index} requires download_url")
        if not source.get("remote_path"):
            errors.append(f"artifact file source {index} requires remote_path")
    return errors


def get_execution_plan_resource_permission_error(execution_plan, user):
    """Return a permission error if a plan references resources outside user's ownership."""
    if user.is_superuser:
        return ""

    host_ids = set()
    group_ids = set()

    plan_steps = execution_plan.planstep_set.select_related("step").prefetch_related(
        "step__target_hosts",
        "step__target_groups",
    )
    for plan_step in plan_steps:
        host_ids.update(plan_step.step_target_host_ids or [])
        group_ids.update(plan_step.step_target_group_ids or [])
        if plan_step.step_id:
            host_ids.update(plan_step.step.target_hosts.values_list("id", flat=True))
            group_ids.update(plan_step.step.target_groups.values_list("id", flat=True))

    denied_host_ids = sorted(
        Host.objects.filter(id__in=host_ids).exclude(created_by=user).values_list("id", flat=True)
    )
    missing_host_ids = sorted(host_ids - set(Host.objects.filter(id__in=host_ids).values_list("id", flat=True)))
    if denied_host_ids or missing_host_ids:
        return f"permission denied for execution plan target host ids: {denied_host_ids + missing_host_ids}"

    groups = list(HostGroup.objects.filter(id__in=group_ids).prefetch_related("host_set"))
    found_group_ids = {group.id for group in groups}
    denied_group_ids = sorted(group.id for group in groups if group.created_by_id != user.id)
    missing_group_ids = sorted(group_ids - found_group_ids)
    if denied_group_ids or missing_group_ids:
        return f"permission denied for execution plan target group ids: {denied_group_ids + missing_group_ids}"

    denied_group_host_ids = sorted(
        {
            host.id
            for group in groups
            for host in group.host_set.all()
            if host.created_by_id != user.id
        }
    )
    if denied_group_host_ids:
        return f"permission denied for execution plan target host ids: {denied_group_host_ids}"

    return ""
