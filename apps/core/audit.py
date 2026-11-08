from apps.core.models import AuditLog


def record_audit(*, user, action, obj, payload=None):
    return AuditLog.objects.create(
        actor=user,
        action=action,
        object_type=obj._meta.label,
        object_id=obj.pk,
        payload=payload or {},
    )
