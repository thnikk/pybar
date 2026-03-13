"""
Description: StateManager and singleton state_manager instance
Author: thnikk
"""
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib  # noqa


class StateManager:
    """Pub/sub state store that dispatches updates on the GLib main loop."""

    def __init__(self):
        self.data = {'debug': False}
        self.subscribers = {}
        self._next_id = 0
        # Track sub IDs with a pending idle callback to avoid double-queuing.
        self._pending = set()

    def _generate_id(self):
        """Generate a unique subscription ID."""
        self._next_id += 1
        return self._next_id

    def _dispatch(self, sub_id, name, callback):
        """Fire callback with latest data; called from GLib main loop."""
        self._pending.discard(sub_id)
        # No-op if the subscription was removed while idle was waiting.
        if sub_id not in self.subscribers.get(name, {}):
            return False
        data = self.data.get(name)
        if data is not None:
            try:
                callback(data)
            except Exception as e:
                # Avoid importing print_debug here to prevent circular imports
                print(f"[StateManager] Callback failed for {name}: {e}")
        return False

    def update(self, name, new_data):
        """Update state and notify subscribers."""
        self.data[name] = new_data
        if name not in self.subscribers:
            return
        for sub_id, callback in list(self.subscribers[name].items()):
            if sub_id in self._pending:
                continue
            self._pending.add(sub_id)
            GLib.idle_add(
                self._dispatch, sub_id, name, callback,
                priority=GLib.PRIORITY_DEFAULT_IDLE
            )

    def subscribe(self, name, callback):
        """Subscribe to updates for name; returns subscription ID."""
        sub_id = self._generate_id()
        if name not in self.subscribers:
            self.subscribers[name] = {}
        self.subscribers[name][sub_id] = callback
        # Fire immediately with current value if one exists.
        if name in self.data and sub_id not in self._pending:
            self._pending.add(sub_id)
            GLib.idle_add(
                self._dispatch, sub_id, name, callback,
                priority=GLib.PRIORITY_DEFAULT_IDLE
            )
        return sub_id

    def unsubscribe(self, sub_id):
        """Unsubscribe using the ID returned by subscribe()."""
        self._pending.discard(sub_id)
        for name, subs in list(self.subscribers.items()):
            if sub_id in subs:
                del subs[sub_id]
                if not subs:
                    del self.subscribers[name]
                return True
        return False

    def clear(self):
        """Clear all data and subscribers."""
        self.data.clear()
        self.subscribers.clear()
        self._pending.clear()

    def get(self, name):
        """Return current value for name, or None."""
        return self.data.get(name)

    def debug_info(self):
        """Return subscription counts per name."""
        return {name: len(subs) for name, subs in self.subscribers.items()}


# Module-level singleton
state_manager = StateManager()
