from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

app = FastAPI()
clients: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            for client in clients:
                if client != ws:
                    await client.send_text(data)
    except WebSocketDisconnect:
        clients.remove(ws)

@app.get("/")
def root():
    return {"message": "QuizMath Chat Server is running!"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)

