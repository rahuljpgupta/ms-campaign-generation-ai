"""
FastAPI server for Campaign Generator with WebSocket support

This is the main entry point for the campaign generation API.
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.api import websocket_endpoint

# Initialize FastAPI app
app = FastAPI(
    title="Campaign Generator API",
    description="AI-powered marketing campaign generation using LangChain and LangGraph",
    version="1.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Campaign Generator API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "components": {
            "api": "operational",
            "websocket": "operational",
            "llm": "operational"
        }
    }


@app.websocket("/ws/{client_id}")
async def websocket_route(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time campaign generation
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier
    """
    await websocket_endpoint(websocket, client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
