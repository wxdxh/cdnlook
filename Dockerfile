# Use the official Python image
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start Flask with Gunicorn
# Cloud Run backend processing can take a long time, adjust timeout accordingly
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 3600 main:app
