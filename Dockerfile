# Use the official Python image with your exact requested version
FROM python:3.14.4-slim

# Force Python output to be unbuffered so logs appear immediately
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for psycopg2 and asyncpg
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project files into the container
COPY . .

# Command to run the bot when the container starts
CMD ["python", "main.py"]