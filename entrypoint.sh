echo "Starting Google Ads Pipeline API & Scheduler..."

# Run the FastAPI application using uvicorn
# The scheduler is started within the app's startup event
exec uvicorn main:app --host 0.0.0.0 --port 8000
