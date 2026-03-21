"""Real-time updates via WebSocket for collaborative features."""

import json
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""
    user_id: str
    username: str
    websocket: Any  # FastAPI WebSocket
    subscribed_projects: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.now)


class RealtimeManager:
    """Manages WebSocket connections and broadcasts for real-time updates."""

    def __init__(self):
        self.clients: Dict[str, WebSocketClient] = {}  # connection_id -> client
        self.project_subscribers: Dict[str, Set[str]] = {}  # project_id -> {connection_ids}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: Any, user_id: str, username: str) -> str:
        """Register a new WebSocket connection. Returns connection ID."""
        connection_id = str(uuid.uuid4())
        async with self._lock:
            self.clients[connection_id] = WebSocketClient(
                user_id=user_id,
                username=username,
                websocket=websocket,
            )
        logger.info("WebSocket connected: user=%s conn=%s", user_id, connection_id)
        return connection_id

    async def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            client = self.clients.pop(connection_id, None)
            if client:
                for project_id in list(client.subscribed_projects):
                    subs = self.project_subscribers.get(project_id)
                    if subs:
                        subs.discard(connection_id)
                        if not subs:
                            del self.project_subscribers[project_id]
        logger.info("WebSocket disconnected: conn=%s", connection_id)

    async def subscribe_project(self, connection_id: str, project_id: str):
        """Subscribe a client to project updates."""
        async with self._lock:
            client = self.clients.get(connection_id)
            if not client:
                return
            client.subscribed_projects.add(project_id)
            if project_id not in self.project_subscribers:
                self.project_subscribers[project_id] = set()
            self.project_subscribers[project_id].add(connection_id)
        logger.info("Subscribed conn=%s to project=%s", connection_id, project_id)

    async def unsubscribe_project(self, connection_id: str, project_id: str):
        """Unsubscribe from project updates."""
        async with self._lock:
            client = self.clients.get(connection_id)
            if client:
                client.subscribed_projects.discard(project_id)
            subs = self.project_subscribers.get(project_id)
            if subs:
                subs.discard(connection_id)
                if not subs:
                    del self.project_subscribers[project_id]

    async def broadcast_to_project(self, project_id: str, event_type: str,
                                   data: Dict[str, Any],
                                   exclude_user: Optional[str] = None):
        """Broadcast an event to all subscribers of a project."""
        message = json.dumps({
            "type": event_type,
            "project_id": project_id,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
        subscriber_ids = self.project_subscribers.get(project_id, set()).copy()
        for conn_id in subscriber_ids:
            client = self.clients.get(conn_id)
            if not client:
                continue
            if exclude_user and client.user_id == exclude_user:
                continue
            try:
                await client.websocket.send_text(message)
            except Exception:
                logger.warning("Failed to send to conn=%s, removing", conn_id)
                await self.disconnect(conn_id)

    async def send_to_user(self, user_id: str, event_type: str,
                           data: Dict[str, Any]):
        """Send a message to a specific user (all their connections)."""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
        for conn_id, client in list(self.clients.items()):
            if client.user_id == user_id:
                try:
                    await client.websocket.send_text(message)
                except Exception:
                    logger.warning("Failed to send to user conn=%s", conn_id)
                    await self.disconnect(conn_id)

    def get_online_users(self, project_id: Optional[str] = None) -> List[Dict]:
        """Get list of online users, optionally filtered by project."""
        seen = set()
        users = []
        if project_id:
            conn_ids = self.project_subscribers.get(project_id, set())
        else:
            conn_ids = set(self.clients.keys())
        for conn_id in conn_ids:
            client = self.clients.get(conn_id)
            if client and client.user_id not in seen:
                seen.add(client.user_id)
                users.append({
                    "user_id": client.user_id,
                    "username": client.username,
                    "connected_at": client.connected_at.isoformat(),
                })
        return users


# Global instance
realtime_manager = RealtimeManager()
