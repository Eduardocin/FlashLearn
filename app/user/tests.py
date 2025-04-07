from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class AuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
    
    def test_login_success(self):
        """Testa se um usuário consegue fazer login com credenciais corretas."""
        response = self.client.post(reverse('login'), {'username': 'testuser', 'password': 'testpass'})
        self.assertEqual(response.status_code, 302)  # Redireciona ao sucesso
        self.assertTrue(User.objects.get(username='testuser').is_authenticated)
    
    def test_register_user(self):
        """Testa o registro de um novo usuário."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com', 
            'password1': 'ComplexPass123!',  
            'password2': 'ComplexPass123!',
        })
        
        # Verifica redirecionamento após sucesso
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())