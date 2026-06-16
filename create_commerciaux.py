"""
Création des 4 commerciaux manquants.
Lancer avec : python manage.py shell < create_commerciaux.py
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'boisandco.settings')
django.setup()

from apps.users.models import User

commerciaux = [
    {'first_name': 'Bruno',    'last_name': 'Commercial', 'username': 'bruno',    'email': 'bruno@boisandco.ma'},
    {'first_name': 'Amine',    'last_name': 'Commercial', 'username': 'amine',    'email': 'amine@boisandco.ma'},
    {'first_name': 'Ibtissam', 'last_name': 'Commercial', 'username': 'ibtissam', 'email': 'ibtissam@boisandco.ma'},
    {'first_name': 'Hassan',   'last_name': 'Commercial', 'username': 'hassan',   'email': 'hassan@boisandco.ma'},
]

for data in commerciaux:
    if User.objects.filter(username=data['username']).exists():
        print(f"[EXISTE DEJA] {data['username']}")
        continue
    user = User.objects.create_user(
        username   = data['username'],
        email      = data['email'],
        password   = 'Boisandco2026!',
        first_name = data['first_name'],
        last_name  = data['last_name'],
        role       = User.Role.COMMERCIAL,
        is_active  = True,
    )
    print(f"[CREE] {user.get_full_name()} / {user.username} / role={user.role}")

print("\nMot de passe par defaut : Boisandco2026!")
print("A changer a la premiere connexion.")
