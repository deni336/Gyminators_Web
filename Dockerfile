FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DJANGO_DEBUG=false
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY gyminators ./gyminators
COPY website ./website
RUN mkdir -p /app/data /app/staticfiles /app/media && \
    DJANGO_SECRET_KEY=build-only-static-collection-key python manage.py collectstatic --noinput && \
    chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/api/health', headers={'Host':os.environ.get('DOMAIN','localhost'),'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=3)" || exit 1
CMD ["/bin/sh", "-c", "python manage.py migrate --noinput && python manage.py setup_roles && exec gunicorn gyminators.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --access-logfile - --error-logfile -"]
