from rest_framework import serializers

from .models import StepComment, ProjectComment, ProjectStep


class StepCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = StepComment
        fields = ['id', 'step', 'author', 'author_name', 'text', 'attachment', 'created_at']
        read_only_fields = ['id', 'author', 'author_name', 'created_at']

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username if obj.author else ''

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class ProjectCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectComment
        fields = ['id', 'project', 'author', 'author_name', 'text', 'attachment', 'audio', 'created_at']
        read_only_fields = ['id', 'author', 'author_name', 'created_at']

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username if obj.author else ''

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class ProjectStepSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectStep
        fields = [
            'id', 'project', 'order', 'name', 'description', 'responsables_roles',
            'due_date', 'is_completed', 'completed_at', 'completed_by', 'completed_by_name',
        ]
        read_only_fields = ['id', 'is_completed', 'completed_at', 'completed_by', 'completed_by_name']

    def get_completed_by_name(self, obj):
        return obj.completed_by.get_full_name() or obj.completed_by.username if obj.completed_by else ''
