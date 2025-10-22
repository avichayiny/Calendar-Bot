# Dockerfile

# --- Step 1: Start from an official Python base image ---
# We use the "slim" version so our image will be small and efficient
FROM python:3.11-slim

# --- Step 2: Set the working directory inside the container ---
# All subsequent commands will run inside a folder named /app
WORKDIR /app

# --- Step 3: Copy the requirements file and install dependencies ---
# Copying this file separately leverages Docker's caching mechanism and speeds up future builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Step 4: Copy the rest of the project files ---
# The first dot means "all files in the current directory on my machine"
# The second dot means "the current directory inside the container" (/app)
COPY . .

# --- Step 5: Define the command that will start the server ---
# This command will run automatically when Google starts our container
# It runs the gunicorn server and listens for requests from anywhere on port 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--log-level", "debug", "app:app"]