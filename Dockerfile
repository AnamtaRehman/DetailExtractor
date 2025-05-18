# Use the official Python image as the base
FROM python:3.10.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the FastAPI default port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

#RUN ngrok config add-authtoken 2xHGs7DvENfeYTjN2evQOTtjpv2_6LLFfYB6wkFP8yW3bfb84
