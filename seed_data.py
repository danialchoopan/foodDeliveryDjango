import os
import django
import random
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User, Address
from apps.restaurants.models import Restaurant, MenuCategory, MenuItem, RestaurantReview, FavoriteRestaurant
from apps.orders.models import Order, OrderItem
from apps.delivery.models import DeliveryZone, PeakTimeSetting

def seed_data():
    print("Seeding data...")

    # Create Admin
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@example.com',
            'role': User.Role.ADMIN,
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin.set_password('admin123')
        admin.save()
    print(f"Admin created: {admin.username}")

    # Create Restaurant Owners
    owners = []
    for i in range(1, 4):
        owner, created = User.objects.get_or_create(
            username=f'owner{i}',
            defaults={
                'email': f'owner{i}@example.com',
                'role': User.Role.RESTAURANT_OWNER,
                'is_verified': True
            }
        )
        if created:
            owner.set_password('owner123')
            owner.save()
        owners.append(owner)
    print(f"{len(owners)} Restaurant owners created.")

    # Create Customers
    customers = []
    for i in range(1, 6):
        customer, created = User.objects.get_or_create(
            username=f'customer{i}',
            defaults={
                'email': f'customer{i}@example.com',
                'role': User.Role.CUSTOMER
            }
        )
        if created:
            customer.set_password('customer123')
            customer.save()

            # Add a sample address for each customer
            Address.objects.create(
                user=customer,
                title='خانه',
                city='تهران' if i % 2 == 0 else 'شیراز',
                address_text=f'خیابان {i}، پلاک {i*10}',
                latitude=35.7 + (i * 0.01),
                longitude=51.3 + (i * 0.01),
                is_default=True,
                is_active=True
            )
        customers.append(customer)
    print(f"{len(customers)} Customers created.")

    # Create Riders
    riders = []
    for i in range(1, 4):
        rider, created = User.objects.get_or_create(
            username=f'rider{i}',
            defaults={
                'email': f'rider{i}@example.com',
                'role': User.Role.DELIVERY_RIDER,
                'rider_status': User.RiderStatus.AVAILABLE,
                'current_latitude': 35.7 + (random.random() * 0.1),
                'current_longitude': 51.3 + (random.random() * 0.1),
                'last_location_update': timezone.now()
            }
        )
        if created:
            rider.set_password('rider123')
            rider.save()
        riders.append(rider)
    print(f"{len(riders)} Riders created.")

    # Create Restaurants
    restaurant_data = [
        {"name": "پیتزا قصر", "city": "تهران", "type": Restaurant.CuisineType.FAST_FOOD},
        {"name": "برگر کینگ", "city": "تهران", "type": Restaurant.CuisineType.FAST_FOOD},
        {"name": "سوشی سنتر", "city": "شیراز", "type": Restaurant.CuisineType.JAPANESE},
        {"name": "کباب دانیال", "city": "اصفهان", "type": Restaurant.CuisineType.PERSIAN},
        {"name": "رستوران سنتی", "city": "مشهد", "type": Restaurant.CuisineType.PERSIAN},
    ]
    restaurants = []
    for i, data in enumerate(restaurant_data):
        res, created = Restaurant.objects.get_or_create(
            name=data["name"],
            defaults={
                'owner': owners[i % len(owners)],
                'address': f'خیابان اصلی، {data["city"]}',
                'city': data["city"],
                'phone_number': f'0218888000{i}',
                'latitude': 35.7 + (i * 0.01),
                'longitude': 51.3 + (i * 0.01),
                'cuisine_type': data["type"],
                'is_active': True,
                'is_open': True,
                'is_verified': True
            }
        )
        if created or not res.is_verified:
            res.is_verified = True
            res.save()
        restaurants.append(res)
    print(f"{len(restaurants)} Restaurants created.")

    # Create Menus
    categories = ["Main Dish", "Drinks", "Dessert"]
    for res in restaurants:
        for cat_name in categories:
            cat, _ = MenuCategory.objects.get_or_create(restaurant=res, name=cat_name)
            for j in range(1, 4):
                MenuItem.objects.get_or_create(
                    category=cat,
                    name=f"{cat_name} Item {j}",
                    defaults={
                        'restaurant': res,
                        'description': f'Delicious {cat_name}',
                        'price': random.randint(50000, 200000),
                        'is_available': True
                    }
                )
    print("Menus created.")

    # Create Reviews
    comments = ["Very good!", "Excellent food", "Highly recommended", "The best in town", "Good service"]
    for res in restaurants:
        for cust in customers:
            RestaurantReview.objects.get_or_create(
                restaurant=res,
                user=cust,
                defaults={
                    'rating': random.randint(3, 5),
                    'comment': random.choice(comments)
                }
            )
    print("Reviews created.")

    # Create Favorites
    for cust in customers:
        FavoriteRestaurant.objects.get_or_create(
            user=cust,
            restaurant=random.choice(restaurants)
        )
    print("Favorites created.")

    # Create Delivery Zones
    DeliveryZone.objects.get_or_create(
        name="Central Tehran",
        defaults={
            'center_latitude': 35.7,
            'center_longitude': 51.3,
            'radius_km': 10,
            'extra_fee': 2000,
            'is_active': True
        }
    )
    print("Delivery zones created.")

    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()
