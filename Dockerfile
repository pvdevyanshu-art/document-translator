# Step 1: Start with a modern Python operating system
FROM python:3.9-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Install the Tesseract OCR engine
# This is the part that solves the "Read-only" error
RUN apt-get update && apt-get install -y tesseract-ocr

# Step 4: Copy the requirements file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy all of our application code into the container
COPY . .

# Step 6: Tell Docker what command to run when the container starts
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "1"]
