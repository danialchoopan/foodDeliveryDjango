# SnapFood API Documentation (READMEAPI)

این مستندات برای راهنمایی توسعه‌دهندگان اپلیکیشن اندروید و وب تهیه شده است. تمامی APIها با فرمت JSON کار می‌کنند و نیاز به توکن Bearer برای احراز هویت دارند (به جز موارد عمومی).

## 🔐 احراز هویت (Authentication)

برای دسترسی به APIهای محافظت شده، باید ابتدا لاگین کرده و توکن JWT دریافت کنید.

- **ثبت نام**: `POST /api/auth/register/`
- **ورود**: `POST /api/auth/login/`
- **رفرش توکن**: `POST /api/auth/token/refresh/`

**مثال ورود:**
```json
{
    "username": "customer1",
    "password": "customer123"
}
```
پاسخ شامل `access` و `refresh` خواهد بود. در درخواست‌های بعدی، هدر زیر را اضافه کنید:
`Authorization: Bearer <your_access_token>`

---

## 🍴 رستوران‌ها (Restaurants)

- **لیست رستوران‌ها**: `GET /api/restaurants/` (قابلیت فیلتر بر اساس نام، نوع غذا و وضعیت باز بودن)
- **جزییات رستوران و منو**: `GET /api/restaurants/{id}/`
- **مشاهده منو به تفکیک دسته**: `GET /api/restaurants/{id}/menu/`

---

## 🛒 سفارشات (Orders)

- **ایجاد/مشاهده سبد خرید**: `GET/POST /api/orders/cart/`
- **افزودن به سبد**: `POST /api/orders/cart/add_item/`
- **ثبت نهایی سفارش**: `POST /api/orders/cart/checkout/`
- **لیست سفارشات کاربر**: `GET /api/orders/`
- **جزییات سفارش**: `GET /api/orders/{id}/`

---

## 🚴 پیک و ارسال (Delivery)

- **ردیابی لحظه‌ای**: `GET /api/delivery/tracking/{id}/live-location/`
- **محاسبه هزینه ارسال**: `POST /api/delivery/fee/`
    - ورودی: مختصات مبدا و مقصد

---

## 👨‍💼 پنل مدیریت رستوران (Owner Panel)

- **مدیریت منو**: `POST/PUT /api/restaurants/categories/` و `POST/PUT /api/restaurants/items/`
- **مشاهده سفارشات رستوران**: `GET /api/restaurants/my-restaurant/orders/`
- **تغییر وضعیت سفارش**: `PATCH /api/orders/{id}/status/`

---

## 🛠 ابزارها و داکیومنت تعاملی

- **Swagger UI**: `/api/docs/` (توصیه شده برای تست آنلاین)
- **Redoc**: `/api/redoc/`

## 📊 دیتای نمونه (Seed Data)
برای تست اولیه می‌توانید از یوزرهای زیر استفاده کنید:
- ادمین: `admin` / `admin123`
- مشتری: `customer1` / `customer123`
- صاحب رستوران: `owner1` / `owner123`
- پیک: `rider1` / `rider123`
