from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, UpdateView, View
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden

from .models import User


class ManagerRequiredMixin(LoginRequiredMixin):
    """Réserve l'accès aux managers et directeurs."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_manager_or_above and not request.user.is_superuser:
            return HttpResponseForbidden("Accès réservé aux managers.")
        return super().dispatch(request, *args, **kwargs)


class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        show_inactive = (
            self.request.GET.get('inactifs') == '1'
            and (self.request.user.is_manager_or_above or self.request.user.is_superuser)
        )
        self._show_inactive = show_inactive
        qs = User.objects.filter(is_active_employee=not show_inactive).order_by('last_name', 'first_name')
        role = self.request.GET.get('role', '')
        if role:
            qs = qs.filter(role=role)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        show_inactive = getattr(self, '_show_inactive', False)
        ctx['selected_role'] = self.request.GET.get('role', '')
        ctx['show_inactive'] = show_inactive
        ctx['total'] = User.objects.filter(is_active_employee=not show_inactive).count()
        ctx['inactive_count'] = User.objects.filter(is_active_employee=False).count()
        ctx['role_stats'] = [
            (r, label, User.objects.filter(is_active_employee=not show_inactive, role=r).count())
            for r, label in User.Role.choices
        ]
        return ctx


class UserCreateView(ManagerRequiredMixin, View):
    template_name = 'users/user_form.html'

    def get(self, request):
        return render(request, self.template_name, self._ctx())

    def post(self, request):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', '')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        avatar = request.FILES.get('avatar')

        errors = {}
        if not first_name:
            errors['first_name'] = 'Le prénom est obligatoire.'
        if not last_name:
            errors['last_name'] = 'Le nom est obligatoire.'
        if not email:
            errors['email'] = "L'adresse e-mail est obligatoire."
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'Cette adresse e-mail est déjà utilisée.'
        if not role:
            errors['role'] = 'Veuillez sélectionner un rôle.'
        if not password1:
            errors['password1'] = 'Le mot de passe est obligatoire.'
        elif len(password1) < 8:
            errors['password1'] = 'Le mot de passe doit contenir au moins 8 caractères.'
        elif password1 != password2:
            errors['password2'] = 'Les mots de passe ne correspondent pas.'

        if errors:
            return render(request, self.template_name, {
                **self._ctx(),
                'errors': errors,
                'post': request.POST,
            })

        # Générer un username depuis prénom + nom
        base = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            role=role,
            is_active_employee=True,
            is_superuser=(role == User.Role.ADMIN),
            is_staff=(role == User.Role.ADMIN),
        )
        user.set_password(password1)
        if avatar:
            user.avatar = avatar
        user.save()

        messages.success(request, f'Membre « {user.get_full_name()} » créé avec succès.')
        return redirect('users:list')

    def _ctx(self):
        return {
            'roles': User.Role.choices,
            'errors': {},
            'post': {},
            'is_create': True,
        }


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'users/user_detail.html'
    context_object_name = 'profile_user'


class UserUpdateView(LoginRequiredMixin, View):
    template_name = 'users/user_form.html'

    def get_user(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if not request.user.is_staff and not request.user.is_manager_or_above:
            if request.user.pk != user.pk:
                return None
        return user

    def get(self, request, pk):
        member = self.get_user(request, pk)
        if member is None:
            return HttpResponseForbidden()
        return render(request, self.template_name, {
            **self._ctx(member),
            'is_create': False,
        })

    def post(self, request, pk):
        member = self.get_user(request, pk)
        if member is None:
            return HttpResponseForbidden()

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', '')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        avatar = request.FILES.get('avatar')

        errors = {}
        if not first_name:
            errors['first_name'] = 'Le prénom est obligatoire.'
        if not last_name:
            errors['last_name'] = 'Le nom est obligatoire.'
        if not email:
            errors['email'] = "L'adresse e-mail est obligatoire."
        elif User.objects.filter(email=email).exclude(pk=pk).exists():
            errors['email'] = 'Cette adresse e-mail est déjà utilisée.'
        if password1 and len(password1) < 8:
            errors['password1'] = 'Le mot de passe doit contenir au moins 8 caractères.'
        elif password1 and password1 != password2:
            errors['password2'] = 'Les mots de passe ne correspondent pas.'

        if errors:
            return render(request, self.template_name, {
                **self._ctx(member),
                'errors': errors,
                'post': request.POST,
                'is_create': False,
            })

        member.first_name = first_name
        member.last_name = last_name
        member.email = email
        member.phone = phone
        if request.user.is_manager_or_above and role:
            member.role = role
            member.is_superuser = (role == User.Role.ADMIN)
            member.is_staff = (role == User.Role.ADMIN)
        if password1:
            member.set_password(password1)
        if avatar:
            member.avatar = avatar
        member.save()

        messages.success(request, f'Profil de « {member.get_full_name()} » mis à jour.')
        return redirect('users:list')

    def _ctx(self, member):
        return {
            'member': member,
            'roles': User.Role.choices,
            'errors': {},
            'post': {
                'first_name': member.first_name,
                'last_name': member.last_name,
                'email': member.email,
                'phone': member.phone,
                'role': member.role,
            },
        }


class UserToggleActiveView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        if member.pk == request.user.pk:
            messages.error(request, 'Vous ne pouvez pas désactiver votre propre compte.')
            return redirect('users:list')
        if member.is_superuser and not request.user.is_superuser:
            messages.error(request, 'Action non autorisée.')
            return redirect('users:list')
        member.is_active_employee = not member.is_active_employee
        member.is_active = member.is_active_employee
        member.save(update_fields=['is_active_employee', 'is_active'])
        action = 'réactivé' if member.is_active_employee else 'désactivé'
        messages.success(request, f'Compte de « {member.get_full_name()} » {action}.')
        return redirect(request.META.get('HTTP_REFERER', 'users:list'))
