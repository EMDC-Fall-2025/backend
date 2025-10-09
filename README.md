# EMDC Backend

## Prerequisites
- Python 3.10+
- pip / venv
- PostgreSQL (or your configured DB)

## Setup
1) Install dependencies
```
pip install -r requirements.txt
```

2) Environment (example)
```
export DJANGO_SETTINGS_MODULE=emdcbackend.settings
export DEBUG=1
# export DATABASE_URL=postgres://user:pass@localhost:5432/emdc
```

3) Database migrations
```
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations auth
python manage.py migrate auth
python manage.py makemigrations emdcbackend
python manage.py migrate emdcbackend
```

4) Create superuser (optional)
```
python manage.py createsuperuser
```

5) Run server
```
python manage.py runserver
```

## Environment (.env)
Create a `.env` file with these variables (fill in as needed):
```
DEBUG=1
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=
ALLOWED_HOSTS=127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

## Auth
This API uses Token authentication. Include the header in requests:
```
Authorization: Token <your_token>
```
