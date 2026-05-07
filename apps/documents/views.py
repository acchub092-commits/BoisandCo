from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db.models import Sum, Q

from .models import Document, DocumentCategory
from apps.projects.models import Project


def _human_size(size_bytes):
    """Taille lisible pour les stats globales."""
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} To'


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        qs = Document.objects.filter(is_latest=True).select_related(
            'project', 'category', 'uploaded_by'
        )
        project_id = self.request.GET.get('project', '')
        category_id = self.request.GET.get('category', '')
        file_type = self.request.GET.get('file_type', '')
        search = self.request.GET.get('q', '').strip()

        if project_id:
            qs = qs.filter(project_id=project_id)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if file_type:
            qs = qs.filter(file_type=file_type)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(project__reference__icontains=search)
                | Q(project__name__icontains=search)
                | Q(description__icontains=search)
            )

        sort = self.request.GET.get('sort', '-uploaded_at')
        allowed_sorts = {
            'name', '-name',
            'uploaded_at', '-uploaded_at',
            'file_size', '-file_size',
            'project__reference', '-project__reference',
        }
        if sort not in allowed_sorts:
            sort = '-uploaded_at'
        return qs.order_by(sort)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['projects'] = Project.objects.order_by('reference')
        ctx['categories'] = (
            DocumentCategory.objects
            .filter(parent__isnull=True)
            .prefetch_related('children')
        )
        ctx['selected_project'] = self.request.GET.get('project', '')
        ctx['selected_category'] = self.request.GET.get('category', '')
        ctx['selected_file_type'] = self.request.GET.get('file_type', '')
        ctx['search'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '-uploaded_at')
        ctx['file_types'] = Document.FileType.choices

        # Stats globales (tous documents, pas juste le filtre courant)
        all_docs = Document.objects.filter(is_latest=True)
        ctx['total_docs'] = all_docs.count()
        total_bytes = all_docs.aggregate(s=Sum('file_size'))['s'] or 0
        ctx['total_size_human'] = _human_size(total_bytes)

        return ctx


class DocumentUploadView(LoginRequiredMixin, View):
    template_name = 'documents/document_upload.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._ctx(request))

    def post(self, request, *args, **kwargs):
        project_id = request.POST.get('project', '').strip()
        category_id = request.POST.get('category') or None
        name = request.POST.get('name', '').strip()
        version = request.POST.get('version', '1.0').strip() or '1.0'
        description = request.POST.get('description', '').strip()
        file = request.FILES.get('file')

        errors = {}
        if not project_id:
            errors['project'] = 'Veuillez sélectionner un projet.'
        if not name:
            errors['name'] = 'Le nom est obligatoire.'
        if not file:
            errors['file'] = 'Veuillez choisir un fichier.'

        if errors:
            return render(request, self.template_name, {
                **self._ctx(request),
                'errors': errors,
                'post': request.POST,
            })

        doc = Document(
            project_id=project_id,
            category_id=category_id,
            name=name,
            version=version,
            description=description,
            file=file,
            uploaded_by=request.user,
            is_latest=True,
        )
        doc.save()
        messages.success(request, f'Document « {doc.name} » déposé avec succès.')

        next_url = request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('documents:list')

    def _ctx(self, request):
        return {
            'projects': Project.objects.order_by('reference'),
            'categories': (
                DocumentCategory.objects
                .filter(parent__isnull=True)
                .prefetch_related('children')
            ),
            'errors': {},
            'post': {'project': request.GET.get('project', '')},
        }


class DocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)
        name = doc.name
        try:
            doc.file.delete(save=False)
        except Exception:
            pass
        doc.delete()
        messages.success(request, f'Document « {name} » supprimé.')
        next_url = request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('documents:list')
