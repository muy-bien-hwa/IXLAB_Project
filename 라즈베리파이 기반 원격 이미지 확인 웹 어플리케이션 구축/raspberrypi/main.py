# main.py
# 라즈베리파이 FastAPI 서버

from fastapi import FastAPI
from controller import stream

app = FastAPI()

app.include_router(stream.router)

@app.get("/")
def running_check():
    return {"status": "ok", "message": "Raspberry Pi server is running"}
