"""
Management command to seed the database with sample data.
Usage: python manage.py seed_data [--clear]
"""
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User, Address
from apps.restaurants.models import Restaurant, MenuCategory, MenuItem, RestaurantReview, FavoriteRestaurant
from apps.orders.models import Order, OrderItem
from apps.delivery.models import DeliveryZone, PeakTimeSetting


class Command(BaseCommand):
    help = 'Seed the database with sample data for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            RestaurantReview.objects.all().delete()
            FavoriteRestaurant.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            MenuItem.objects.all().delete()
            MenuCategory.objects.all().delete()
            Restaurant.objects.all().delete()
            Address.objects.all().delete()
            DeliveryZone.objects.all().delete()
            PeakTimeSetting.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS('Data cleared.'))

        self.stdout.write('Seeding data...')

        # Create Admin
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
        self.stdout.write(f'  Admin: {admin.username}')

        # Create Restaurant Owners
        owners = []
        owner_data = [
            {'username': 'owner1', 'email': 'owner1@example.com'},
            {'username': 'owner2', 'email': 'owner2@example.com'},
            {'username': 'owner3', 'email': 'owner3@example.com'},
        ]
        for data in owner_data:
            owner, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'role': User.Role.RESTAURANT_OWNER,
                    'is_verified': True,
                }
            )
            if created:
                owner.set_password('owner123')
                owner.save()
            owners.append(owner)
        self.stdout.write(f'  Owners: {len(owners)}')

        # Create Customers
        customers = []
        customer_cities = ['تهران', 'شیراز', 'تهران', 'اصفهان', 'مشهد']
        for i in range(1, 6):
            customer, created = User.objects.get_or_create(
                username=f'customer{i}',
                defaults={
                    'email': f'customer{i}@example.com',
                    'role': User.Role.CUSTOMER,
                }
            )
            if created:
                customer.set_password('customer123')
                customer.save()

                city = customer_cities[i - 1]
                lat_offset = random.uniform(-0.05, 0.05)
                lng_offset = random.uniform(-0.05, 0.05)
                Address.objects.create(
                    user=customer,
                    title='خانه',
                    city=city,
                    address_text=f'خیابان {i}، پلاک {i * 10}',
                    latitude=35.6892 + lat_offset,
                    longitude=51.3890 + lng_offset,
                    is_default=True,
                    is_active=True,
                )
            customers.append(customer)
        self.stdout.write(f'  Customers: {len(customers)}')

        # Create Riders
        riders = []
        for i in range(1, 4):
            rider, created = User.objects.get_or_create(
                username=f'rider{i}',
                defaults={
                    'email': f'rider{i}@example.com',
                    'role': User.Role.DELIVERY_RIDER,
                    'rider_status': User.RiderStatus.AVAILABLE,
                    'current_latitude': 35.6892 + random.uniform(-0.1, 0.1),
                    'current_longitude': 51.3890 + random.uniform(-0.1, 0.1),
                    'last_location_update': timezone.now(),
                }
            )
            if created:
                rider.set_password('rider123')
                rider.save()
            riders.append(rider)
        self.stdout.write(f'  Riders: {len(riders)}')

        # Create Restaurants
        restaurant_data = [
            {'name': 'پیتزا قصر', 'city': 'تهران', 'cuisine': Restaurant.CuisineType.FAST_FOOD,
             'desc': 'بهترین پیتزا با مواد تازه', 'min_order': 80000, 'delivery_time': 30},
            {'name': 'برگر کینگ', 'city': 'تهران', 'cuisine': Restaurant.CuisineType.FAST_FOOD,
             'desc': 'برگرهای خوشمزه و تازه', 'min_order': 60000, 'delivery_time': 25},
            {'name': 'سوشی سنتر', 'city': 'شیراز', 'cuisine': Restaurant.CuisineType.JAPANESE,
             'desc': 'سوشی و غذاهای ژاپنی اصیل', 'min_order': 100000, 'delivery_time': 40},
            {'name': 'کباب دانیال', 'city': 'اصفهان', 'cuisine': Restaurant.CuisineType.PERSIAN,
             'desc': 'کباب‌های سنتی ایرانی', 'min_order': 70000, 'delivery_time': 35},
            {'name': 'رستوران سنتی', 'city': 'مشهد', 'cuisine': Restaurant.CuisineType.PERSIAN,
             'desc': 'غذاهای سنتی و خانگی', 'min_order': 50000, 'delivery_time': 45},
            {'name': 'چینی دراگون', 'city': 'تهران', 'cuisine': Restaurant.CuisineType.CHINESE,
             'desc': 'غذاهای چینی اصیل', 'min_order': 90000, 'delivery_time': 35},
            {'name': 'ایتالیایی لاپلاچا', 'city': 'تهران', 'cuisine': Restaurant.CuisineType.ITALIAN,
             'desc': 'پاستا و پیتزا ایتالیایی', 'min_order': 85000, 'delivery_time': 40},
            {'name': 'فست فود بیگ برگر', 'city': 'شیراز', 'cuisine': Restaurant.CuisineType.FAST_FOOD,
             'desc': 'همبرگر و ساندویچ‌های خاص', 'min_order': 55000, 'delivery_time': 20},
        ]

        restaurants = []
        for i, data in enumerate(restaurant_data):
            lat_offset = random.uniform(-0.05, 0.05)
            lng_offset = random.uniform(-0.05, 0.05)
            res, created = Restaurant.objects.get_or_create(
                name=data['name'],
                defaults={
                    'owner': owners[i % len(owners)],
                    'description': data['desc'],
                    'address': f'خیابان اصلی، {data["city"]}',
                    'city': data['city'],
                    'phone_number': f'0218888{i:04d}',
                    'latitude': 35.6892 + lat_offset,
                    'longitude': 51.3890 + lng_offset,
                    'cuisine_type': data['cuisine'],
                    'minimum_order': data['min_order'],
                    'delivery_time': data['delivery_time'],
                    'is_active': True,
                    'is_open': True,
                    'is_verified': True,
                }
            )
            restaurants.append(res)
        self.stdout.write(f'  Restaurants: {len(restaurants)}')

        # Create Menu Categories and Items
        categories_data = {
            Restaurant.CuisineType.FAST_FOOD: [
                ('غذاهای اصلی', ['پیتза مargarita', 'پیتزا پپرونی', 'سیب زمینی سرخ شده', 'ساندویچ مرغ']),
                ('نوشیدنی‌ها', ['کولا', 'آب پرتقال', 'شیر Shake']),
                ('دسرها', ['بستنی وانیلی', 'کیک شکلاتی', 'چیزکیک']),
            ],
            Restaurant.CuisineType.JAPANESE: [
                ('غذاهای اصلی', ['سالمون رول', 'تونا مکی', 'اودون', 'رامن']),
                ('نوشیدنی‌ها', ['چای سبز', 'ساکی', 'آب']),
                ('دسرها', ['موچی', 'دسر ماتچا']),
            ],
            Restaurant.CuisineType.PERSIAN: [
                ('غذاهای اصلی', ['کباب کوبیده', 'چلو کباب', 'قورمه سبزی', 'زرشک پلو با مرغ']),
                ('نوشیدنی‌ها', ['دوغ', 'آب انار', 'چای']),
                ('دسرها', ['بستنی سنتی', 'حلوا']),
            ],
            Restaurant.CuisineType.CHINESE: [
                ('غذاهای اصلی', ['نودل سویا', 'برنج سرخ شده', 'دیم سام']),
                ('نوشیدنی‌ها', ['چای', 'آب معدنی']),
                ('دسرها', ['مانگو پودینگ']),
            ],
            Restaurant.CuisineType.ITALIAN: [
                ('غذاهای اصلی', ['پاستا بولونیز', 'ریزوتو', 'لازانیا']),
                ('نوشیدنی‌ها', ['آب گازدار', 'اسپرسو']),
                ('دسرها', ['تیرامیسو', 'پاناکوتا']),
            ],
        }

        for res in restaurants:
            cats = categories_data.get(res.cuisine_type, categories_data[Restaurant.CuisineType.FAST_FOOD])
            for cat_name, items in cats:
                cat, _ = MenuCategory.objects.get_or_create(
                    restaurant=res, name=cat_name,
                    defaults={'order': cats.index((cat_name, items))}
                )
                for item_name in items:
                    MenuItem.objects.get_or_create(
                        category=cat, name=item_name,
                        defaults={
                            'restaurant': res,
                            'description': f'{item_name} خوشمزه و تازه',
                            'price': random.randint(40000, 180000),
                            'stock': random.randint(10, 50),
                            'is_available': True,
                            'is_featured': random.choice([True, False]),
                        }
                    )
        self.stdout.write('  Menus created.')

        # Create Reviews
        review_comments = [
            'عالی بود، حتماً دوباره سفارش می‌دم!',
            'غذا خیلی خوشمزه بود',
            'تحویل سریع بود',
            'کیفیت عالی، قیمت مناسب',
            'پیشنهاد می‌کنم',
            'متوسط بود',
            'خوب بود ولی جای بهبود داره',
        ]
        for res in restaurants:
            for cust in random.sample(customers, min(3, len(customers))):
                RestaurantReview.objects.get_or_create(
                    restaurant=res, user=cust,
                    defaults={
                        'rating': random.randint(3, 5),
                        'comment': random.choice(review_comments),
                    }
                )
        self.stdout.write('  Reviews created.')

        # Create Favorites
        for cust in customers:
            fav_restaurants = random.sample(restaurants, min(2, len(restaurants)))
            for res in fav_restaurants:
                FavoriteRestaurant.objects.get_or_create(user=cust, restaurant=res)
        self.stdout.write('  Favorites created.')

        # Create Sample Orders
        order_statuses = [
            Order.Status.DELIVERED, Order.Status.DELIVERED, Order.Status.DELIVERED,
            Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PREPARING,
        ]
        for i, cust in enumerate(customers[:3]):
            res = random.choice(restaurants)
            menu_items = list(res.menu_items.filter(is_available=True)[:3])
            if not menu_items:
                continue

            subtotal = sum(mi.price * random.randint(1, 3) for mi in menu_items)
            delivery_fee = random.choice([15000, 20000, 25000])

            order = Order.objects.create(
                customer=cust,
                restaurant=res,
                delivery_address=cust.addresses.first().address_text if cust.addresses.exists() else 'آدرس نمونه',
                customer_latitude=float(cust.addresses.first().latitude) if cust.addresses.exists() else 35.6892,
                customer_longitude=float(cust.addresses.first().longitude) if cust.addresses.exists() else 51.3890,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total_amount=subtotal + delivery_fee,
                status=order_statuses[i % len(order_statuses)],
                payment_method=random.choice(Order.PaymentMethod.choices)[0],
            )

            for mi in menu_items:
                qty = random.randint(1, 3)
                OrderItem.objects.create(
                    order=order, menu_item=mi, quantity=qty,
                    price=mi.price, item_name=mi.name,
                    item_description=mi.description,
                )
        self.stdout.write('  Sample orders created.')

        # Create Delivery Zones
        zones = [
            ('مرکز تهران', 35.6892, 51.3890, 10, 2000),
            ('شمال تهران', 35.75, 51.40, 8, 3000),
            ('شیراز مرکز', 29.5918, 52.5836, 12, 2500),
        ]
        for name, lat, lng, radius, fee in zones:
            DeliveryZone.objects.get_or_create(
                name=name,
                defaults={
                    'center_latitude': lat, 'center_longitude': lng,
                    'radius_km': radius, 'extra_fee': fee, 'is_active': True,
                }
            )
        self.stdout.write('  Delivery zones created.')

        # Create Peak Time Settings
        peak_times = [
            (0, 12, 14, 1.5),   # Monday lunch rush
            (1, 12, 14, 1.5),   # Tuesday
            (2, 12, 14, 1.5),   # Wednesday
            (3, 12, 14, 1.5),   # Thursday
            (4, 12, 14, 2.0),   # Friday (highest)
            (5, 19, 22, 1.8),   # Saturday dinner
            (6, 19, 22, 1.8),   # Sunday dinner
        ]
        for dow, start, end, mult in peak_times:
            PeakTimeSetting.objects.get_or_create(
                day_of_week=dow, start_hour=start, end_hour=end,
                defaults={'multiplier': mult, 'is_active': True},
            )
        self.stdout.write('  Peak time settings created.')

        self.stdout.write(self.style.SUCCESS('\nSeeding completed successfully!'))
        self.stdout.write(f'\n  Users: {User.objects.count()}')
        self.stdout.write(f'  Restaurants: {Restaurant.objects.count()}')
        self.stdout.write(f'  Menu Items: {MenuItem.objects.count()}')
        self.stdout.write(f'  Orders: {Order.objects.count()}')
        self.stdout.write(f'  Reviews: {RestaurantReview.objects.count()}')
        self.stdout.write(f'  Delivery Zones: {DeliveryZone.objects.count()}')
