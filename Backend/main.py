from fastapi import FastAPI

app = FastAPI(
    title="Result Processing System",
    description="University Result Processing System API",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Result Processing System API",
        "status": "running"
    }