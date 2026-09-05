from fastapi import FastAPI

app = FastAPI(title="City Camera Network ANPR Service")


@app.get("/health")
def health_check():
    return {"status": "ok"}
