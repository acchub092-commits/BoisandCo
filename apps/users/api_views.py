"""
API d'authentification par token — point d'entrée commun à toute app mobile
consommant l'API DRF (actuellement : PWA Chiffrage terrain).
"""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user):
    return {
        'id': user.pk,
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'email': user.email,
        'role': user.role,
        'role_display': user.get_role_display(),
    }


class LoginView(APIView):
    """POST {username, password} -> {token, user}. Pas d'authentification requise."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        if not username or not password:
            return Response(
                {'detail': "Nom d'utilisateur et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            return Response(
                {'detail': 'Identifiants incorrects.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': _user_payload(user)})


class MeView(APIView):
    """GET -> profil de l'utilisateur authentifié (vérifie la validité du token côté app mobile)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))


class LogoutView(APIView):
    """POST -> invalide le token courant (déconnexion explicite depuis l'app mobile)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
