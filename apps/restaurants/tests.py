from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.restaurants.models import Restaurant, MenuCategory, MenuItem, RestaurantReview, FavoriteRestaurant
from django.urls import reverse

User = get_user_model()

class DanialFoodTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123', role='customer')
        self.owner = User.objects.create_user(username='owneruser', password='password123', role='restaurant_owner')
        self.admin = User.objects.create_user(username='adminuser', password='password123', role='admin', is_staff=True)

        self.restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            owner=self.owner,
            address="123 Test St",
            latitude=35.6892,
            longitude=51.3890,
            phone_number="02188880000",
            is_active=True
        )
        # Bypassing the 'is_verified = False' in save() for new objects
        Restaurant.objects.filter(id=self.restaurant.id).update(is_verified=True)
        self.restaurant.refresh_from_db()

    def test_login(self):
        # The URL name is 'web_login' in config/urls.py
        response = self.client.post(reverse('web_login'), {'username': 'testuser', 'password': 'password123'})
        self.assertEqual(response.status_code, 302)

    def test_customer_dashboard_access(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Restaurant")

    def test_owner_dashboard_access(self):
        self.client.login(username='owneruser', password='password123')
        response = self.client.get(reverse('owner_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پنل مدیریت رستوران")

    def test_admin_dashboard_access(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "داشبورد مدیریتی دانیال فود")

    def test_favorite_toggle(self):
        self.client.login(username='testuser', password='password123')
        # toggle_favorite redirects to restaurant_detail
        response = self.client.post(reverse('toggle_favorite', args=[self.restaurant.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(FavoriteRestaurant.objects.filter(user=self.user, restaurant=self.restaurant).exists())

        # Toggle off
        response = self.client.post(reverse('toggle_favorite', args=[self.restaurant.id]))
        self.assertFalse(FavoriteRestaurant.objects.filter(user=self.user, restaurant=self.restaurant).exists())

    def test_restaurant_review(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('restaurant_detail', args=[self.restaurant.id]), {
            'rating': 5,
            'comment': 'Great food!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RestaurantReview.objects.filter(user=self.user, restaurant=self.restaurant, rating=5).exists())
