FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root
RUN useradd -m appuser
USER appuser

# Set HOME explicitly so boto3 finds ~/.aws when credentials are mounted for
# local development. In the cluster there is no credentials file: Pod Identity
# injects credentials through the environment instead.
ENV HOME=/home/appuser

CMD ["python", "main.py"]
