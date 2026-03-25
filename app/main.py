# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.api import users, chains, messages, validation, attachments, websocket

app = FastAPI(
    title="Chaos Messenger API",
    description="P2P mesh messenger with blockchain-style encryption",
    version="0.2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for frontend
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# API routers
app.include_router(users.router)
app.include_router(chains.router)
app.include_router(messages.router)
app.include_router(validation.router)
app.include_router(attachments.router)
app.include_router(websocket.router)

@app.get("/")
async def root():
    """Serve the main HTML page."""
    from fastapi.responses import FileResponse
    return FileResponse("index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.2.0"}
