# 🛠 Installation

### 1. Clone the repository
```bash
git clone https://github.com/bomberman2099/WaIT.git
cd your-repo-name
```

### 2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # For Linux/Mac
venv\Scripts\activate     # For Windows
```
### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply migrations
```bash
python manage.py migrate
```

### 5. Create a superuser
```bash
python manage.py createsuperuser
```
### 1. Run the development server
```bash
python manage.py runserver
```
#### Then open your browser and go to:
```bash
http://127.0.0.1:8000/api/v1/swagger/
```
