FROM python:3.11-slim

# تثبيت مكتبات النظام التي يعتمد عليها Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح Chromium الخاص بـ Playwright
RUN playwright install chromium

COPY . .

EXPOSE 10000
CMD ["python", "app.py"]
