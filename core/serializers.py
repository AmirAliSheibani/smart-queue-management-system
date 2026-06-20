from rest_framework import serializers
from .models import Center, Visitor, Queue, Notification, Rating


class CenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Center
        fields = '__all__'
        read_only_fields = ['user', 'avg_wait_seconds','phone']


class VisitorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    user = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Visitor
        fields = '__all__'


class QueueSerializer(serializers.ModelSerializer):
    visitor_id = serializers.PrimaryKeyRelatedField(
        queryset=Visitor.objects.all(), source='visitor'
    )
    center_id = serializers.PrimaryKeyRelatedField(
        queryset=Center.objects.all(), source='center', required=False
    )

    class Meta:
        model = Queue
        fields = ['id', 'visitor_id', 'center_id', 'status', 'position', 'created_at', 'access_token']
        read_only_fields = ['id', 'position', 'created_at']

    def validate(self, attrs):
        visitor = attrs.get('visitor')
        center = self.context.get('center') or attrs.get('center')

        if not center:
            raise serializers.ValidationError("Center is required.")

        exists = Queue.objects.filter(visitor=visitor, center=center, status='waiting').exists()
        if exists:
            raise serializers.ValidationError("این مراجعه‌کننده قبلاً در صف این مرکز ثبت شده است.")

        return attrs


class QueueStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Queue._meta.get_field('status').choices)

    class Meta:
        model = Queue
        fields = ['status']


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'center', 'visitor', 'score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'visitor']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'center', 'phone', 'name']
        read_only_fields = ['id']

