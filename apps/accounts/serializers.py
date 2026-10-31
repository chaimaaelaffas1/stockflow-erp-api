from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class MeSerializer(serializers.ModelSerializer):
    """
    Informations non sensibles de l'utilisateur connecté.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_active",
        ]

        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "password",
            "date_joined",
        ]

        read_only_fields = [
            "id",
            "date_joined",
            "username",
        ]

        extra_kwargs = {
            "email": {"required": True},
        }

    def validate_password(self, value):
        validate_password(value, user=getattr(self, "instance", None))
        return value

    def validate(self, attrs):
        """
        Empêche le dernier ADMIN actif de se retirer ses propres droits.
        """

        request = self.context.get("request")
        instance = getattr(self, "instance", None)

        if request is None or instance is None:
            return attrs

        current_user = request.user

        # La règle concerne la modification de son propre compte.
        if instance.pk != current_user.pk:
            return attrs

        UserModel = instance.__class__

        is_current_admin = instance.role == UserModel.Role.ADMIN and instance.is_active

        new_role = attrs.get("role", instance.role)
        new_is_active = attrs.get("is_active", instance.is_active)

        removes_admin_access = new_role != UserModel.Role.ADMIN or not new_is_active

        if is_current_admin and removes_admin_access:
            active_admin_count = UserModel.objects.filter(
                role=UserModel.Role.ADMIN,
                is_active=True,
            ).count()

            if active_admin_count <= 1:
                raise serializers.ValidationError({"role": ("The last active administrator cannot remove their own admin access.")})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance
