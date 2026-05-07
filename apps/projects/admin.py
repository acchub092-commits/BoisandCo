from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ProjectTemplate, PhaseTemplate, TaskTemplate,
    Project, Phase, Task, TaskAssignment,
    ProjectMember, TaskComment,
)


# ---------------------------------------------------------------------------
# Gabarits
# ---------------------------------------------------------------------------

class TaskTemplateInline(admin.TabularInline):
    model = TaskTemplate
    extra = 1
    fields = ('order', 'name', 'required_role', 'estimated_hours')


class PhaseTemplateInline(admin.StackedInline):
    model = PhaseTemplate
    extra = 1
    fields = ('order', 'name', 'estimated_days')
    show_change_link = True


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'phases_count', 'tasks_count', 'is_active', 'created_by')
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [PhaseTemplateInline]


@admin.register(PhaseTemplate)
class PhaseTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'order', 'estimated_days')
    list_filter = ('template',)
    inlines = [TaskTemplateInline]


# ---------------------------------------------------------------------------
# Projets
# ---------------------------------------------------------------------------

class TaskAssignmentInline(admin.TabularInline):
    model = TaskAssignment
    extra = 0
    fields = ('user', 'is_primary', 'assigned_by', 'assigned_at')
    readonly_fields = ('assigned_at',)


class TaskInline(admin.StackedInline):
    model = Task
    extra = 0
    fields = ('order', 'name', 'status', 'progress', 'required_role', 'due_date')
    show_change_link = True


class PhaseInline(admin.StackedInline):
    model = Phase
    extra = 0
    fields = ('order', 'name', 'is_active', 'is_completed', 'estimated_days')
    show_change_link = True


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    fields = ('user', 'added_by', 'added_at')
    readonly_fields = ('added_at',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'name', 'client_name', 'status_badge',
        'progress_bar', 'manager', 'created_at',
    )
    list_filter = ('status', 'manager')
    search_fields = ('reference', 'name', 'client_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'created_by')
    inlines = [PhaseInline, ProjectMemberInline]
    fieldsets = (
        ('Identité', {
            'fields': ('reference', 'name', 'status', 'template'),
        }),
        ('Client', {
            'fields': ('client_name', 'client_email', 'client_phone', 'address'),
        }),
        ('Équipe', {
            'fields': ('manager', 'estimator'),
        }),
        ('Dates & Budget', {
            'fields': ('start_date', 'end_date', 'actual_end_date', 'budget'),
        }),
        ('Documents', {
            'fields': ('initial_order',),
        }),
        ('Méta', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Statut')
    def status_badge(self, obj):
        colors = {
            'AVANT_VENTE': '#94a3b8',
            'ETUDE':       '#60a5fa',
            'PRODUCTION':  '#f59e0b',
            'LOGISTIQUE':  '#a78bfa',
            'POSE':        '#34d399',
            'CLOTURE':     '#6b7280',
        }
        color = colors.get(obj.status, '#94a3b8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )

    @admin.display(description='Avancement')
    def progress_bar(self, obj):
        p = obj.progress
        return format_html(
            '<div style="width:120px;background:#e5e7eb;border-radius:4px;height:8px">'
            '<div style="width:{}%;background:#c9821f;border-radius:4px;height:8px"></div>'
            '</div> {}%',
            p, p
        )


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'order', 'is_active', 'is_completed', 'progress')
    list_filter = ('is_active', 'is_completed')
    search_fields = ('name', 'project__reference')
    inlines = [TaskInline]


class TaskCommentInline(admin.StackedInline):
    model = TaskComment
    extra = 0
    fields = ('author', 'text', 'attachment', 'audio', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'phase', 'status', 'progress', 'required_role', 'due_date')
    list_filter = ('status', 'required_role')
    search_fields = ('name', 'phase__project__reference')
    inlines = [TaskAssignmentInline, TaskCommentInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'added_by', 'added_at')
    list_filter = ('project',)
    search_fields = ('project__reference', 'user__last_name')


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'author', 'created_at', 'has_attachment', 'has_audio')
    list_filter = ('created_at',)
    search_fields = ('task__name', 'author__last_name')

    @admin.display(boolean=True, description='Fichier')
    def has_attachment(self, obj):
        return bool(obj.attachment)

    @admin.display(boolean=True, description='Audio')
    def has_audio(self, obj):
        return bool(obj.audio)
