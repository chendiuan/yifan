# 新生兒照護紀錄

Django-based newborn care tracker for feeding, sleep, diaper, health, growth, and notes.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8001
```

Open:

```text
http://127.0.0.1:8001/
```

## NAS / LAN Preview

For testing on another device in the same network:

```powershell
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8001
```

Then open:

```text
http://<NAS-or-PC-IP>:8001/
```

Before exposing this publicly, update `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, HTTPS, and deployment settings.
