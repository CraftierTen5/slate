from fastapi import FastAPI
from dotenv import load_dotenv
import os

# Load the .env file that contains your DATABASE_URL
load_dotenv()

app = FastAPI(title="Slate API")

@app.get("/")
def read_root():
    db_url = os.getenv("DATABASE_URL")
    # Masking the password for safety in the response
    safe_url = db_url.replace("slate_password", "****") if db_url else "Not found"
    return {"message": "Backend is running", "database_url": safe_url}