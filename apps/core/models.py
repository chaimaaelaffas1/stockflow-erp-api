from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # Empêche Django de créer la table 'timestampedmodel'


class ImmutableQuerySet(models.QuerySet):
    """Empêche la modification et la suppression des audits."""

    def update(self, **kwargs):
        raise ValidationError("Audit logs cannot be modified.")

    def delete(self):
        raise ValidationError("Audit logs cannot be deleted.")


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(
        max_length=100,
    )

    object_type = models.CharField(
        max_length=100,
    )

    object_id = models.PositiveBigIntegerField()

    payload = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["object_type", "object_id"],
                name="audit_object_idx",
            ),
            models.Index(
                fields=["action", "created_at"],
                name="audit_action_created_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit logs cannot be modified.")

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit logs cannot be deleted.")

    def __str__(self):
        return f"{self.action} - {self.object_type} #{self.object_id}"
