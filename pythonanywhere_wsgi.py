"""
PythonAnywhere WSGI template for this project.

Copy the contents of this file into the WSGI file shown on the
PythonAnywhere Web tab, then replace YOUR_USERNAME with your account name.
"""

import os
import sys

project_home = "/home/YOUR_USERNAME/yifan"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

env_file = os.path.join(project_home, ".env")
if os.path.exists(env_file):
    with open(env_file, encoding="utf-8") as env:
        for line in env:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "babylog.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
