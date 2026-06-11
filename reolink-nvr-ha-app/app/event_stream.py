"""
event_stream.py

Persistent event listener for Reolink NVR.
Maintains WebSocket connections and broadcasts events to subscribers.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types from NVR."""
    MOTION = "motion"
    PERSON = "person"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    DOORBELL = "doorbell"
    VISITOR = "visitor"


@dataclass
class Event:
    """Represents a single event from the NVR."""
    timestamp: datetime
    channel: int
    event_type: EventType
    event_id: str
    metadata: dict


class EventStream:
    """
    Maintains persistent connection to NVR event stream.
    Allows subscribers to receive events in real-time.
    """

    def __init__(self, nvr_client):
        self.nvr_client = nvr_client
        self._subscribers: list[Callable] = []
        self._running = False
        self._task: Any = None
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_delay = 5

    def subscribe(self, callback: Callable[[Event], None]) -> Callable:
        """
        Subscribe to events.
        Callback receives an Event object.
        Returns unsubscribe function.
        """
        self._subscribers.append(callback)
        logger.debug(f"New subscriber. Total: {len(self._subscribers)}")

        def unsubscribe():
            self._subscribers.remove(callback)
            logger.debug(f"Unsubscribed. Total: {len(self._subscribers)}")

        return unsubscribe

    async def start(self):
        """Start the event stream listener."""
        if self._running:
            logger.warning("Event stream already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Event stream started")

    async def stop(self):
        """Stop the event stream listener."""
        self._running = False
        if self._task:
            await self._task
        logger.info("Event stream stopped")

    async def _listen_loop(self):
        """Main listen loop with reconnect logic."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Event stream error: %s", e)
                await self._handle_reconnect()

    async def _connect_and_listen(self):
        """Connect to NVR and listen for events."""
        # Note: This is a placeholder implementation.
        # Real implementation would use reolink_aio's event channel capabilities
        # or implement polling as fallback.

        logger.debug("Attempting to connect to event stream")

        # Simulate event stream listening
        while self._running:
            try:
                # In a real implementation, we would listen to the NVR's
                # event channel (if available) or poll periodically
                await asyncio.sleep(30)

                # Health check
                if not await self.nvr_client.ping():
                    logger.warning("NVR ping failed, reconnecting")
                    break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Error in listen loop: %s", e)
                raise

    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff."""
        if not self._running:
            return

        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_reconnect_attempts:
            logger.error("Max reconnect attempts reached, stopping event stream")
            self._running = False
            return

        delay = min(self._reconnect_delay * (2 ** self._reconnect_attempts), 300)
        logger.info(
            "Reconnecting in %d seconds (attempt %d/%d)",
            delay,
            self._reconnect_attempts,
            self._max_reconnect_attempts,
        )
        await asyncio.sleep(delay)

    async def emit_event(self, event: Event):
        """
        Emit an event to all subscribers.
        Called internally or by clip generator when events are detected.
        """
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping event")

        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error("Error in event subscriber: %s", e)

    def get_stats(self) -> dict:
        """Return event stream statistics."""
        return {
            "running": self._running,
            "subscribers": len(self._subscribers),
            "queue_size": self._event_queue.qsize(),
            "reconnect_attempts": self._reconnect_attempts,
        }
