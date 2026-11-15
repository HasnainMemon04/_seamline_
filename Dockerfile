FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib PORT=8080
COPY requirements.lock.txt requirements.deploy.txt ./
RUN pip install --no-cache-dir -r requirements.deploy.txt
COPY . .
RUN useradd --uid 10001 --create-home seamline && chown -R seamline:seamline /app
USER seamline
EXPOSE 8080
HEALTHCHECK --start-period=180s --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/healthz',timeout=4)"
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 180 --access-logfile - --error-logfile - wsgi:app"]
