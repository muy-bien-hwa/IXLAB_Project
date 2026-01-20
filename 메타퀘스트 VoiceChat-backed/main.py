from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controller import analyze


app = FastAPI()

app.include_router(analyze.router)

# Unity용 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def running_check():
    return {"status": "ok", "message": "Backend server is running"}
