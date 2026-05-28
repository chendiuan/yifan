# 新生兒照護紀錄

Django newborn care tracker for feeding, sleep, diaper, health, growth, and notes.

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

## PythonAnywhere Setup

1. Create a PythonAnywhere account and open a Bash console.

2. Clone the repository:

```bash
git clone https://github.com/chendiuan/yifan.git ~/yifan
cd ~/yifan
```

3. Create a virtualenv and install dependencies:

```bash
python3.11 -m venv ~/.virtualenvs/yifan
source ~/.virtualenvs/yifan/bin/activate
pip install -r requirements.txt
```

4. Create `.env` from the example:

```bash
cp .env.example .env
nano .env
```

Set:

```text
DJANGO_SECRET_KEY=<a long random secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<yourusername>.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://<yourusername>.pythonanywhere.com
```

5. Prepare the database and static files:

```bash
python manage.py migrate
python manage.py collectstatic
```

6. In the PythonAnywhere Web tab:

- Add a new manual web app.
- Choose the same Python version as the virtualenv.
- Set virtualenv path to `/home/<yourusername>/.virtualenvs/yifan`.
- Edit the WSGI file and copy the contents of `pythonanywhere_wsgi.py`.
- Replace `YOUR_USERNAME` with your PythonAnywhere username.

7. Static files mapping on the Web tab:

```text
URL: /static/
Directory: /home/<yourusername>/yifan/staticfiles
```

8. Reload the web app.

Your app should be available at:

```text
https://<yourusername>.pythonanywhere.com/
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
