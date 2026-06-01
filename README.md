# 🍔 SnapFood - Food Delivery System (Restaurant & Delivery)

SnapFood is an advanced food delivery system with multi-role capabilities, geolocation tracking, and dynamic pricing. This project includes both a powerful REST API and a simplified Web Panel for Customers, Restaurant Owners, and Admins.

---

## 🚀 Getting Started

Follow these steps to set up and run the project on your local machine.

### 1. Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/snapfood.git
cd snapfood

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/base.txt
pip install -r requirements/dev.txt
```

### 3. Configuration
Copy the example environment file and adjust if necessary:
```bash
cp .env.example .env
```
*Note: The project is pre-configured to use SQLite for easy local setup.*

### 4. Database Setup & Migrations
```bash
python manage.py makemigrations accounts restaurants orders delivery
python manage.py migrate
```

### 5. Seed Initial Data
Run the following script to create sample users (Admin, Customers, Owners, Riders), restaurants, and menus:
```bash
python seed_data.py
```

### 6. Run the Server
```bash
python manage.py runserver
```
- **Web Panels**: [http://localhost:8000](http://localhost:8000)
- **Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **API Documentation**: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)

---

## 👥 User Roles & Features

| Role | Key Features |
|------|--------------|
| **Customer** | Browse restaurants, Favorite shops, Order food, Rate & Review, Track deliveries. |
| **Restaurant Owner**| Manage Menu (Categories/Items), View orders, Sales reports, Toggle open status. |
| **Delivery Rider** | Accept nearby orders, Update live location, Update delivery status. |
| **Admin** | Full system overview, Verify new restaurants, Manage users and zones. |

---

## 📖 API Documentation

For detailed information on how to connect your Android application to this backend, please refer to the dedicated API guide:

👉 **[READMEAPI.md (Persian)](READMEAPI.md)**

---

## 🛠 Tech Stack
- **Backend**: Django 4.2 & Django REST Framework
- **Database**: SQLite (Dev) / PostgreSQL (Prod)
- **Auth**: JWT & Session-based
- **Styling**: Plain HTML/CSS (Responsive & RTL support)
