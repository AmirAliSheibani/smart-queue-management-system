# Smart Queue Management System (WaIT Core API)

A backend system built with Django REST Framework for managing service center queues, visitor flow, notifications, and rating systems.

This project simulates real-world queue handling systems used in service centers, clinics, and customer support environments.

It supports both authenticated and public access flows with secure token-based operations.

---

## 🚀 Features

### 👥 User & Access Control
- Role-based system (Center Manager / Visitor)
- Authentication-based permissions
- Visitor isolation per center

---

### 🏢 Center Management
- Create and manage service centers
- Owner-restricted access control
- Center-level statistics and analytics

---

### 🎟 Queue System
- Add visitors to queue
- FIFO-based queue ordering
- Queue status tracking:
  - waiting
  - in_progress
  - done

- Next-customer automation system
- Queue reordering (move to first / last)

---

### 📊 Analytics & Statistics
- Real-time queue stats per center
- Average waiting time calculation
- Center-level performance tracking

---

### ⭐ Rating System
- Token-based secure rating system
- Only available after queue completion
- Automatic token expiration
- Average score calculation per center

---

### 📲 Notifications & SMS
- SMS integration using Ghasedak API
- Status notifications for visitors
- Queue token delivery via SMS

---

### 🌐 Public APIs
- Public queue status endpoint (token-based)
- Public rating endpoint without authentication
- Secure access via time-limited tokens

---

## 🧱 Tech Stack

- Python
- Django
- Django REST Framework (DRF)
- PostgreSQL / SQLite
- Requests (SMS API integration)
- drf-yasg (Swagger documentation)

---

## 🏗 Architecture Overview

```
Client Request
      ↓
DRF API Layer
      ↓
Service Layer (queue_service)
      ↓
Database (Queue, Visitor, Center)
      ↓
External Services (SMS API)
```

The system follows a **service-oriented backend architecture**, separating business logic from API views.

---

## 🔐 Security Design

- Token-based access for public endpoints
- Expiring queue access tokens
- Ownership-based permissions
- Role validation (manager vs visitor)
- Atomic database transactions for queue operations

---

## 📡 Main API Endpoints

### Centers
- `POST /centers/` → Create center
- `GET /centers/<id>/` → Get center
- `DELETE /centers/<id>/` → Delete center

---

### Visitors
- `GET /visitors/`
- `POST /visitors/`
- `PATCH /visitors/<id>/`
- `DELETE /visitors/<id>/`

---

### Queue
- `GET /queue/<center_id>/`
- `POST /queue/<center_id>/`
- `DELETE /queue/<id>/delete`
- `PATCH /queue/<id>/status/`
- `POST /queue/<center_id>/next/`
- `POST /queue/<id>/reorder/`

---

### Public APIs
- `GET /public/queue/<token>/stats/`
- `POST /public/queue/rate/`

---

### Notifications
- `GET /notification/<center_id>/`
- `DELETE /notification/<center_id>/delete/`

---

## ⚙️ Queue Flow Logic

1. Visitor joins queue
2. System assigns position automatically
3. Manager processes queue:
   - current → `done`
   - next → `in_progress`
4. Visitor receives SMS with access token
5. After completion:
   - visitor submits rating using token
   - token is invalidated

---

## ⭐ Rating System Logic

- Rating only allowed if:
  - queue status = `done`
  - token is valid and not expired

- After submission:
  - rating is saved
  - token is invalidated
  - center average is recalculated

---

## 📦 Installation

```bash
git clone https://github.com/AmirAliSheibani/smart-queue-management-system.git
cd smart-queue-management-system

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

---

## 🔐 Environment Variables

Create `.env` file:

```env
SECRET_KEY=your-secret
DEBUG=True

GHASEDAK_API_KEY=your-sms-key
FRONTEND_URL=https://yourdomain.com
```

---

## 🧠 Key Design Highlights

- Service-layer architecture (`queue_service`)
- Atomic queue operations (transaction-safe)
- Token-based stateless public access
- SMS-driven user interaction
- Clean separation of roles and permissions
- Scalable queue logic suitable for real-world systems

---

## 📈 Possible Improvements

- WebSocket real-time queue updates
- Redis caching for queue positions
- Admin dashboard (React/Vue)
- Dockerization
- Rate limiting (DRF throttling)
- Event-driven architecture (Celery + RabbitMQ)
- Multi-center analytics dashboard

---

## 👨‍💻 Author

Developed by **Amir Ali Sheibani**

GitHub:  
https://github.com/AmirAliSheibani

---
