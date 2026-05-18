from django.contrib import admin
from .models import DocumentCategory, Document


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'slug', 'order')
    list_filter = ('parent',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'project', 'category', 'file_type',
        'version', 'is_latest', 'file_size_human', 'uploaded_by', 'uploaded_at',
    )
    list_filter = ('file_type', 'is_latest', 'category')
    search_fields = ('name', 'project__reference', 'project__name')
    readonly_fields = ('uploaded_at', 'file_size', 'file_type')
    raw_id_fields = ('project', 'previous_version')
