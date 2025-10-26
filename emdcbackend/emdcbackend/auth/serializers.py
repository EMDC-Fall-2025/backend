from django.contrib.auth.models import User
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "password", "has_password"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def get_has_password(self, obj):
        return obj.has_usable_password()
