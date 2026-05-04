# 🍔 SnapFood - API دلیوری غذا (Restaurant & Delivery System)

یک سیستم تحویل غذای پیشرفته با قابلیت‌های چندنقشی، مدیریت همزمانی، موقعیت‌یابی جغرافیایی و قیمت‌گذاری پویا.

[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.14-red.svg)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://www.docker.com/)

---

## 📋 فهرست مطالب

- [ویژگی‌ها](#-ویژگی‌ها)
- [نقش‌های کاربری](#-نقش‌های-کاربری)
- [تکنولوژی‌های استفاده شده](#-تکنولوژی‌های-استفاده-شده)
- [نصب و راه‌اندازی](#-نصب-و-راه‌اندازی)
- [راه‌اندازی با Docker](#-راه‌اندازی-با-docker)
---

## ✨ ویژگی‌ها

### سیستم چندنقشی (Multi-role)
- **مشتری (Customer)**: ثبت سفارش، مشاهده رستوران‌های نزدیک، ردیابی سفارش
- **صاحب رستوران (RestaurantOwner)**: مدیریت رستوران، منو، مشاهده سفارشات و گزارش فروش
- **راننده (DeliveryRider)**: مشاهده سفارش‌های نزدیک، قبول سفارش، آپدیت موقعیت
- **ادمین (Admin)**: مدیریت کامل همه بخش‌ها

### قابلیت‌های پیشرفته
- 📍 **موقعیت‌یابی جغرافیایی**: فیلتر رستوران‌های نزدیک، محاسبه مسافت، تخمین زمان تحویل
- 🔒 **مدیریت همزمانی**: استفاده از `select_for_update()` برای جلوگیری از تداخل سفارشات همزمان
- 💰 **قیمت‌گذاری پویا**: هزینه ارسال بر اساس مسافت و زمان شلوغی (Peak Time)
- 🚦 **صف سفارش**: بسته شدن خودکار رستوران در صورت ازدحام سفارش (سیستم Busy)
- 📊 **گزارشات**: گزارش فروش روزانه برای رستورانداران
- 🔐 **احراز هویت JWT**: امنیت بالا با توکن‌های دسترسی
- 📝 **مستندات خودکار**: Swagger/OpenAPI با drf-spectacular

---

## 👥 نقش‌های کاربری

| نقش | وظایف اصلی | دسترسی‌ها |
|------|------------|-----------|
| **مشتری** | ثبت سفارش، مشاهده رستوران‌ها، ردیابی | ایجاد و مشاهده سفارشات خود |
| **صاحب رستوران** | مدیریت رستوران و منو، گزارشات | مدیریت رستوران‌های خود |
| **راننده** | قبول سفارش، آپدیت موقعیت | مشاهده و قبول سفارش‌های نزدیک |
| **ادمین** | مدیریت همه چیز | دسترسی کامل به تمام APIها |

---

## 🛠 تکنولوژی‌های استفاده شده

- **Backend**: Django 4.2, Django REST Framework 3.14
- **Database**: PostgreSQL 15
- **Cache & Message Broker**: Redis 7
- **Task Queue**: Celery 5.3
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Documentation**: drf-spectacular (Swagger/OpenAPI)
- **Geolocation**: GeoPy (محاسبه فاصله)
- **Containerization**: Docker & Docker Compose
- **Testing**: Pytest, pytest-django

---

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها
- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (اختیاری، برای Celery)
- Docker & Docker Compose (اختیاری)

---

### 🐳 راه‌اندازی با Docker (توصیه شده)

```bash
# 1. کلون کردن پروژه
git clone https://github.com/yourusername/snapfood.git
cd snapfood

# 2. کپی فایل محیطی
cp .env.example .env

# 3. ویرایش فایل .env (در صورت نیاز)
nano .env

# 4. ساخت و اجرای کانتینرها
docker-compose up --build

# 5. اجرای migrations (به صورت خودکار در entrypoint انجام می‌شود)
docker-compose exec django python manage.py migrate

# 6. دسترسی به پروژه
# API: http://localhost:8000
# Swagger Docs: http://localhost:8000/api/docs/
# Admin Panel: http://localhost:8000/admin/
