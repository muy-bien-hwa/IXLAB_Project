from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter(
    prefix="/stream",
    tags=["stream video"]
)

streaming_active = False
connections: List[WebSocket] = []  # 연결된 WebSocket 클라이언트 리스트


@router.get("/start")
def streaming_start():
    global streaming_active
    streaming_active = True
    return {"message": "streaming started"}    
    

@router.post("/stop")  # sendBeacon 이라 post로 받음
def streaming_stop():
    global streaming_active
    streaming_active = False 
    return {"message": "streaming stopped"}  

@router.get("/status")
def get_streaming_status():
    return {"streaming_active": streaming_active}  


@router.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)  # 클라이언트 추가
    print(connections)
    try:
        while True:
            # 프레임 데이터를 바이너리로 수신 (live_camera.py에서 전송)
            data = await websocket.receive_bytes()
            # 연결된 모든 클라이언트(프론트)에게 브로드캐스트
            for conn in connections:
                if conn != websocket:  # 송신자 제외 (필요 시)
                    await conn.send_bytes(data)
    except WebSocketDisconnect:
        connections.remove(websocket)