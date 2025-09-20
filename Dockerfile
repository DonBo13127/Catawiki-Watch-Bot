FROM mcr.microsoft.com/playwright/python:v1.37.1-focal

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Installer les navigateurs Playwright
RUN playwright install

CMD ["python", "main.py"]
