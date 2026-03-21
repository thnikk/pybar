"""
Description: BaseModule — base class for all data-fetching modules
Author: thnikk
"""
import os
import json
import time
import weakref
from datetime import datetime
from common.state import state_manager
from common.helpers import print_debug, add_style


class BaseModule:
    """
    Base class providing a standard worker loop with caching and
    state_manager integration.
    """

    def __init__(self, name, config):
        self.name = name
        self.config = config
        module_default = getattr(self.__class__, 'DEFAULT_INTERVAL', None)
        self.interval = config.get('interval', module_default or 60)
        self.cache_path = os.path.expanduser(
            f"~/.cache/pybar/{name}.json")
        self.last_data = None
        import module
        resolved_type = module.resolve_type(config.get('type', name))
        self.is_hass = (
            name.startswith('hass') or
            resolved_type.startswith('hass') or
            resolved_type.startswith('homeassistant')
        )
        self.empty_is_error = getattr(
            self.__class__, 'EMPTY_IS_ERROR', True)
        # Single shared subscription; widgets register weak callbacks here.
        self._widget_callbacks = []
        self._state_sub_id = None

    def cleanup(self):
        """Override in subclass if cleanup is needed."""
        pass

    def fetch_data(self):
        """Override to fetch data; return a dict or None."""
        return {}

    def run_worker(self):
        """Standard worker loop with caching and stop/wake support."""
        import module
        stop_event = module._worker_stop_flags.get(self.name)
        wake_event = module._worker_wake_flags.get(self.name)
        first_run = True

        while True:
            data = None

            # Load from cache on first run (non-hass modules only).
            # If the cache is still fresh (age < interval), skip the
            # first fetch and sleep out the remaining interval instead.
            skip_fetch = False
            sleep_time = None
            if first_run and not self.is_hass and \
                    os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, 'r') as f:
                        cached = json.load(f)
                    if cached:
                        self.last_data = cached
                        stale_init = cached.copy()
                        cache_age = 0
                        if 'timestamp' in cached:
                            cache_age = time.time() - cached['timestamp']
                            if cache_age > self.interval * 2:
                                stale_init['stale'] = True
                        stale_init['timestamp'] = (
                            datetime.now().timestamp())
                        state_manager.update(self.name, stale_init)
                        print_debug(
                            f"Loaded {self.name} from cache",
                            color='green')
                        if cache_age < self.interval:
                            # Cache is fresh; defer the first real fetch
                            skip_fetch = True
                            sleep_time = max(
                                0, self.interval - cache_age)
                            print_debug(
                                f"{self.name} cache is fresh, "
                                f"skipping first fetch",
                                color='green')
                except Exception as e:
                    print_debug(
                        f"Failed to load cache for {self.name}: {e}",
                        color='red')

            start_time = time.time()
            try:
                if not skip_fetch:
                    new_data = self.fetch_data()
                    if new_data is not None:
                        if new_data == {} and self.last_data \
                                and self.empty_is_error:
                            # Use stale cache when fetch returns empty
                            data = self.last_data.copy()
                            if 'timestamp' in self.last_data:
                                cache_age = (
                                    time.time() -
                                    self.last_data['timestamp'])
                                if cache_age > self.interval * 2:
                                    data['stale'] = True
                            else:
                                data['stale'] = True
                            print_debug(
                                f"{self.name} returned empty, "
                                f"using stale cache",
                                color='yellow')
                        else:
                            data = new_data
                            self.last_data = data
                            if not self.is_hass:
                                try:
                                    os.makedirs(
                                        os.path.dirname(self.cache_path),
                                        exist_ok=True)
                                    with open(self.cache_path, 'w') as f:
                                        json.dump(data, f)
                                except Exception as e:
                                    print_debug(
                                        f"Failed to save cache for "
                                        f"{self.name}: {e}", color='red')
                    else:
                        if self.last_data:
                            data = self.last_data.copy()
                            data['stale'] = True
            except Exception as e:
                print_debug(
                    f"Worker {self.name} failed: {e}", color='red')
                if self.last_data:
                    data = self.last_data.copy()
                    data['stale'] = True

            execution_time = time.time() - start_time

            if data is not None:
                if isinstance(data, dict):
                    data['timestamp'] = datetime.now().timestamp()
                state_manager.update(self.name, data)

            first_run = False
            if self.interval <= 0:
                break

            # Use the remaining interval from cache skip, or subtract
            # the time spent fetching from the full interval.
            if sleep_time is None:
                sleep_time = max(0, self.interval - execution_time)

            if stop_event:
                if wake_event:
                    woken = wake_event.wait(timeout=sleep_time)
                    if stop_event.is_set():
                        break
                    if woken:
                        wake_event.clear()
                else:
                    if stop_event.wait(timeout=sleep_time):
                        break
            else:
                time.sleep(sleep_time)

    def _ensure_subscription(self):
        """Register one shared state subscription for all widgets."""
        if self._state_sub_id is not None:
            return

        def _fan_out(data):
            # Iterate over a snapshot so removals during iteration are safe.
            for cb_ref in list(self._widget_callbacks):
                cb = cb_ref()
                if cb is not None:
                    cb(data)
            # Prune dead references.
            self._widget_callbacks = [
                r for r in self._widget_callbacks if r() is not None
            ]

        self._state_sub_id = state_manager.subscribe(
            self.name, _fan_out
        )

    def _unregister_subscription(self):
        """Unsubscribe the shared state subscription."""
        if self._state_sub_id is not None:
            state_manager.unsubscribe(self._state_sub_id)
            self._state_sub_id = None
        self._widget_callbacks.clear()

    def create_widget(self, bar):
        """Create and return the GTK widget for the bar."""
        from common.widgets import Module

        m = Module()
        m.set_position(bar.position)

        # Ensure one shared subscription exists before adding the callback.
        self._ensure_subscription()

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        # Store a weak reference to the bound callback so the widget
        # can be garbage-collected without holding it alive here.
        self._widget_callbacks.append(weakref.ref(update_callback))

        # Keep a strong reference on the widget so the callback stays
        # alive for as long as the widget does.
        m._update_callback = update_callback
        return m

    def update_ui(self, widget, data):
        """Update the bar widget with new data from state_manager."""
        if not data:
            return
        if 'text' in data:
            widget.set_label(data['text'])
            widget.set_visible(bool(data['text']))
        if 'icon' in data:
            widget.set_icon(data['icon'])
        if 'tooltip' in data:
            widget.set_tooltip_text(str(data['tooltip']))

        widget.reset_style()
        if 'class' in data:
            add_style(widget, data['class'])
        if data.get('stale'):
            add_style(widget, 'stale')
