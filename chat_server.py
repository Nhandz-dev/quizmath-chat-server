from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- Khởi tạo Firebase ---
cred = credentials.Certificate("quiz-app-ab1d4-firebase-adminsdk-fbsvc-921454d508.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI()
clients: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    # --- Gửi lịch sử chat ---
    messages_ref = db.collection("messages").order_by("timestamp", direction=firestore.Query.ASCENDING).limit(30)
    docs = messages_ref.stream()
    for doc in docs:
        data = doc.to_dict()
        sender = data.get("sender", "???")
        message = data.get("message", "")
        await ws.send_text(f"[{sender}]: {message}")

    try:
        while True:
            data = await ws.receive_text()
            print("New message:", data)

            # Gửi đến các client khác
            for client in clients:
                if client != ws:
                    await client.send_text(data)

            # Lưu vào Firestore
            if "]:" in data:
                name, msg = data.split("]:", 1)
                name = name[1:]  # bỏ dấu [
                msg = msg.strip()
                db.collection("messages").add({
                    "sender": name,
                    "message": msg,
                    "timestamp": datetime.now()
                })

    except WebSocketDisconnect:
        clients.remove(ws)
