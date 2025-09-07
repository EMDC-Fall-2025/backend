# # Use an official Python runtime as a parent image
# FROM python:3.8

# # Set the working directory in the container
# WORKDIR /backend

# Install dependencies
# RUN pip install --upgrade pip
# RUN pip install django
# RUN pip install mysqlclient
# RUN pip install django-autoreload
# RUN pip install python-dotenv
# RUN pip install django-cors-headers
# RUN pip install djangorestframework

# # Copy the backend code into the container at /backend
# COPY /emdcbackend/ /backend/

# # Expose port 7012 to allow external access
# EXPOSE 7004

# # Run the Django application with auto-reload
# CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:7004"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Workdir is where manage.py will be (we’ll bind-mount here too)
WORKDIR /backend

# Install deps early to leverage layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# Optional: copy source for first build (bind mount will override at runtime)
COPY emdcbackend /backend

EXPOSE 7004

# Run Django on all interfaces
CMD ["python", "manage.py", "runserver", "0.0.0.0:7004"]
