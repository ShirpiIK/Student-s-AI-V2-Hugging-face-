# Use python 3.9 image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create cache directory for Hugging Face
RUN mkdir -p /.cache/huggingface && chmod -R 777 /.cache

# Expose port 7860 (Hugging Face default)
EXPOSE 7860

# Command to run the app
CMD ["python", "app.py"]