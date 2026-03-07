#!/usr/bin/python3 -u
"""
Description: System tray module for GTK4 with collapsible feature
Author: thnikk (ported and enhanced)
"""
import common as c
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
import os
import typing
import gi
import time

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

# SNI constants
WATCHER_SERVICE = 'org.kde.StatusNotifierWatcher'
WATCHER_PATH = '/StatusNotifierWatcher'
SNI_IFACE = 'org.kde.StatusNotifierItem'
SNI_PATH = '/StatusNotifierItem'
DBUSMENU_IFACE = 'com.canonical.dbusmenu'
PROPS_IFACE = 'org.freedesktop.DBus.Properties'
DBUS_SERVICE = 'org.freedesktop.DBus'
DBUS_PATH = '/org/freedesktop/DBus'
DBUS_IFACE = 'org.freedesktop.DBus'
HOST_NAME_TPL = 'org.kde.StatusNotifierHost-{}-{}'
HOST_PATH_TPL = '/StatusNotifierHost/{}'

# SNI properties to fetch on item load
PROPERTIES = [
    'Id', 'Category', 'Title', 'Status', 'WindowId', 'IconName',
    'IconPixmap', 'OverlayIconName', 'OverlayIconPixmap',
    'AttentionIconName', 'AttentionIconPixmap', 'AttentionMovieName',
    'ToolTip', 'IconThemePath', 'ItemIsMenu', 'Menu'
]

# SNI watcher DBus XML spec
_WATCHER_XML = """
<node>
  <interface name="org.kde.StatusNotifierWatcher">
    <method name="RegisterStatusNotifierItem">
      <arg name="service" type="s" direction="in"/>
    </method>
    <method name="RegisterStatusNotifierHost">
      <arg name="service" type="s" direction="in"/>
    </method>
    <property name="RegisteredStatusNotifierItems" type="as" access="read"/>
    <property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
    <property name="ProtocolVersion" type="i" access="read"/>
    <signal name="StatusNotifierItemRegistered">
      <arg type="s" name="service"/>
    </signal>
    <signal name="StatusNotifierItemUnregistered">
      <arg type="s" name="service"/>
    </signal>
    <signal name="StatusNotifierHostRegistered"/>
    <signal name="StatusNotifierHostUnregistered"/>
  </interface>
</node>
"""


def debug_print(msg, *args, **kwargs):
    """ Log debug messages via common module """
    try:
        c.print_debug(msg, *args, **kwargs)
    except Exception:
        pass


def _get_bus():
    """ Return the session DBus connection """
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def _bus_call(conn, service, path, iface, method, params, reply_type=None):
    """ Synchronous DBus method call; returns unpacked result or None """
    try:
        result = conn.call_sync(
            service, path, iface, method, params,
            GLib.VariantType.new(reply_type) if reply_type else None,
            Gio.DBusCallFlags.NONE, 3000, None
        )
        return result
    except Exception as e:
        debug_print(f'DBus call {iface}.{method} failed: {e}')
        return None


def _request_name(conn, name):
    """ Request a well-known DBus name; returns True on success """
    # flags=0x4 → DBUS_NAME_FLAG_DO_NOT_QUEUE
    result = _bus_call(
        conn, DBUS_SERVICE, DBUS_PATH, DBUS_IFACE, 'RequestName',
        GLib.Variant('(su)', (name, 0x4)), '(u)'
    )
    return result is not None and result[0] == 1


def _release_name(conn, name):
    """ Release a well-known DBus name """
    _bus_call(
        conn, DBUS_SERVICE, DBUS_PATH, DBUS_IFACE, 'ReleaseName',
        GLib.Variant('(s)', (name,)), '(u)'
    )


def _deep_unpack(v):
    """ Recursively unpack GLib.Variant objects to Python primitives """
    if isinstance(v, GLib.Variant):
        return _deep_unpack(v.unpack())
    if isinstance(v, dict):
        return {k: _deep_unpack(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return type(v)(_deep_unpack(i) for i in v)
    return v


def _get_service_and_path(service: str) -> typing.Tuple[str, str]:
    """ Split a SNI registration string into (bus_name, object_path) """
    idx = service.find('/')
    if idx != -1:
        return service[:idx], service[idx:]
    return service, SNI_PATH


# ---------------------------------------------------------------------------
# SNI Watcher server — exposes org.kde.StatusNotifierWatcher on the session bus
# ---------------------------------------------------------------------------

class WatcherServer:
    """
    Pure-Gio implementation of the StatusNotifierWatcher DBus service.
    Registers a DBus object via Gio.DBusConnection.register_object().
    """

    def __init__(self, conn):
        self._conn = conn
        self._items = []      # registered full_name strings
        self._hosts = []      # registered sender strings
        self._watches = {}    # sender → watch_id (to detect disappearance)

        # Callbacks set by TrayHost
        self.on_item_registered = None
        self.on_item_unregistered = None

        node = Gio.DBusNodeInfo.new_for_xml(_WATCHER_XML)
        iface = node.interfaces[0]
        self._reg_id = conn.register_object(
            WATCHER_PATH, iface,
            self._on_method_call,
            self._on_get_property,
            None  # set_property not needed
        )
        debug_print('WatcherServer: registered at ' + WATCHER_PATH)

    def unregister(self):
        """ Remove the DBus object registration """
        if self._reg_id:
            self._conn.unregister_object(self._reg_id)
            self._reg_id = None
        for watch_id in self._watches.values():
            Gio.bus_unwatch_name(watch_id)
        self._watches.clear()

    # -- DBus dispatch -------------------------------------------------------

    def _on_method_call(
            self, conn, sender, _obj_path, _iface, method, params,
            invocation):
        """ Dispatch incoming DBus method calls """
        if method == 'RegisterStatusNotifierItem':
            self._register_item(conn, sender, params[0], invocation)
        elif method == 'RegisterStatusNotifierHost':
            self._register_host(conn, sender, params[0], invocation)
        else:
            invocation.return_error_literal(
                Gio.io_error_quark(), Gio.IOErrorEnum.NOT_SUPPORTED,
                f'Unknown method: {method}'
            )

    def _on_get_property(
            self, _conn, _sender, _path, _iface, prop_name):
        """ Return current property values as GLib.Variant """
        if prop_name == 'RegisteredStatusNotifierItems':
            return GLib.Variant('as', self._items)
        if prop_name == 'IsStatusNotifierHostRegistered':
            return GLib.Variant('b', len(self._hosts) > 0)
        if prop_name == 'ProtocolVersion':
            return GLib.Variant('i', 0)
        return None

    # -- Item registration ---------------------------------------------------

    def _register_item(self, conn, sender, service, invocation):
        """ Handle RegisterStatusNotifierItem method call """
        invocation.return_value(None)  # void return

        if service.startswith('/'):
            full_name = f'{sender}{service}'
        elif service.startswith(':'):
            full_name = f'{service}/StatusNotifierItem'
        else:
            full_name = f'{sender}/StatusNotifierItem'

        if full_name in self._items:
            return

        debug_print(f'WatcherServer: registering {full_name}')
        self._items.append(full_name)
        self._emit_signal(
            'StatusNotifierItemRegistered', GLib.Variant('(s)', (full_name,))
        )
        self._emit_props_changed(
            'RegisteredStatusNotifierItems', GLib.Variant('as', self._items)
        )

        # Watch for the sender vanishing so we can auto-unregister
        if sender not in self._watches:
            watch_id = Gio.bus_watch_name_on_connection(
                conn, sender, Gio.BusNameWatcherFlags.NONE,
                None,
                lambda c, n, fn=full_name: self._on_sender_vanished(fn)
            )
            self._watches[sender] = watch_id

        if self.on_item_registered:
            self.on_item_registered(full_name)

    def _on_sender_vanished(self, full_name):
        """ Called when a registered item's bus name disappears """
        if full_name not in self._items:
            return
        debug_print(f'WatcherServer: unregistering vanished {full_name}')
        self._items.remove(full_name)
        self._emit_signal(
            'StatusNotifierItemUnregistered',
            GLib.Variant('(s)', (full_name,))
        )
        self._emit_props_changed(
            'RegisteredStatusNotifierItems', GLib.Variant('as', self._items)
        )
        if self.on_item_unregistered:
            self.on_item_unregistered(full_name)

    # -- Host registration ---------------------------------------------------

    def _register_host(self, _conn, sender, _service, invocation):
        """ Handle RegisterStatusNotifierHost method call """
        invocation.return_value(None)
        if sender not in self._hosts:
            debug_print(f'WatcherServer: registering host {sender}')
            self._hosts.append(sender)
            self._emit_signal('StatusNotifierHostRegistered', None)
            self._emit_props_changed(
                'IsStatusNotifierHostRegistered', GLib.Variant('b', True)
            )

    def register_host_internal(self):
        """ Register pybar itself as a host (no invocation object needed) """
        sentinel = '__internal__'
        if sentinel not in self._hosts:
            self._hosts.append(sentinel)
            self._emit_signal('StatusNotifierHostRegistered', None)
            self._emit_props_changed(
                'IsStatusNotifierHostRegistered', GLib.Variant('b', True)
            )

    # -- Signal / property helpers -------------------------------------------

    def _emit_signal(self, signal_name, params):
        try:
            self._conn.emit_signal(
                None, WATCHER_PATH, WATCHER_SERVICE, signal_name, params
            )
        except Exception as e:
            debug_print(f'WatcherServer emit {signal_name} error: {e}')

    def _emit_props_changed(self, prop_name, variant):
        try:
            self._conn.emit_signal(
                None, WATCHER_PATH, PROPS_IFACE, 'PropertiesChanged',
                GLib.Variant(
                    '(sa{sv}as)',
                    (WATCHER_SERVICE, {prop_name: variant}, [])
                )
            )
        except Exception as e:
            debug_print(f'WatcherServer PropertiesChanged error: {e}')


# ---------------------------------------------------------------------------
# SNI item client — wraps a single system-tray item
# ---------------------------------------------------------------------------

class StatusNotifierItem:
    """
    Represents one status notifier item on the bus.
    Uses Gio.DBusProxy and bus_watch_name for lifecycle management.
    """

    def __init__(self, service_name, object_path, conn):
        self.service_name = service_name
        self.object_path = object_path
        self._conn = conn
        self.on_loaded_callback: typing.Optional[typing.Callable] = None
        self.on_updated_callback: typing.Optional[typing.Callable] = None
        self.properties: dict = {'ItemIsMenu': True}
        self._proxy = None
        self.pid = 0
        self.proc_name = ''

        # Watch for the item's bus name to appear/vanish
        self._watch_id = Gio.bus_watch_name_on_connection(
            conn, service_name, Gio.BusNameWatcherFlags.NONE,
            self._on_available,
            self._on_unavailable
        )

    def disconnect(self):
        """ Stop watching and release the proxy """
        if self._watch_id:
            Gio.bus_unwatch_name(self._watch_id)
            self._watch_id = None
        self._proxy = None

    # -- Lifecycle -----------------------------------------------------------

    def _on_available(self, conn, _name, _owner):
        """ Called when the item's bus name appears """
        try:
            debug_print(
                f'SNI: available {self.service_name}{self.object_path}')
            self._resolve_process(conn)
            self._proxy = Gio.DBusProxy.new_sync(
                conn, Gio.DBusProxyFlags.NONE, None,
                self.service_name, self.object_path, SNI_IFACE, None
            )
            self._proxy.connect('g-signal', self._on_signal)
            self._fetch_all_properties()
            if self.on_loaded_callback:
                GLib.idle_add(self.on_loaded_callback, self)
        except Exception as e:
            debug_print(
                f'SNI available handler error: {e}', color='red')

    def _on_unavailable(self, _conn, _name):
        """ Called when the item's bus name vanishes """
        self._proxy = None

    def _resolve_process(self, conn):
        """ Attempt to resolve the bus name to a PID and cmdline """
        try:
            result = _bus_call(
                conn, DBUS_SERVICE, DBUS_PATH, DBUS_IFACE,
                'GetConnectionUnixProcessID',
                GLib.Variant('(s)', (self.service_name,)), '(u)'
            )
            if result:
                self.pid = result[0]
                cmdline = f'/proc/{self.pid}/cmdline'
                if os.path.exists(cmdline):
                    with open(cmdline) as f:
                        self.proc_name = f.read().replace('\0', ' ').lower()
                debug_print(
                    f'  PID={self.pid} proc={self.proc_name[:50]}')
        except Exception as e:
            debug_print(f'  PID resolve failed (non-fatal): {e}')

    # -- Properties ----------------------------------------------------------

    def _fetch_all_properties(self):
        """ Populate self.properties from the proxy cache or via GetAll """
        for name in PROPERTIES:
            val = self._get_property(name)
            if val is not None:
                self.properties[name] = val

    def _get_property(self, name):
        """ Read one property; cache first, then explicit Get call """
        if self._proxy is None:
            return None
        # Try the proxy's cache (populated by Gio during proxy creation)
        var = self._proxy.get_cached_property(name)
        if var is not None:
            return _deep_unpack(var)
        # Fall back to an explicit Properties.Get call
        try:
            result = self._conn.call_sync(
                self.service_name, self.object_path,
                PROPS_IFACE, 'Get',
                GLib.Variant('(ss)', (SNI_IFACE, name)),
                GLib.VariantType.new('(v)'),
                Gio.DBusCallFlags.NONE, 3000, None
            )
            return _deep_unpack(result[0]) if result else None
        except Exception:
            return None

    # -- Signal handler ------------------------------------------------------

    def _on_signal(self, _proxy, _sender, signal_name, _params):
        """ Handle SNI signals by refreshing affected properties """
        prop_map = {
            'NewTitle': ['Title', 'ToolTip'],
            'NewIcon': ['IconName', 'IconPixmap', 'ToolTip', 'Title'],
            'NewAttentionIcon': [
                'AttentionIconName', 'AttentionIconPixmap', 'ToolTip'],
            'NewOverlayIcon': ['OverlayIconName', 'OverlayIconPixmap'],
            'NewToolTip': ['ToolTip', 'Title'],
            'NewStatus': ['Status', 'ToolTip'],
            'NewIconThemePath': ['IconThemePath'],
        }
        if signal_name not in prop_map:
            return
        changed = []
        for name in prop_map[signal_name]:
            val = self._get_property(name)
            if val is not None:
                self.properties[name] = val
                changed.append(name)
        if changed and self.on_updated_callback:
            GLib.idle_add(self.on_updated_callback, self, changed)

    # -- Actions -------------------------------------------------------------

    def activate(self, x, y):
        """ Send Activate to the item """
        if self._proxy:
            try:
                self._proxy.call_sync(
                    'Activate', GLib.Variant('(ii)', (x, y)),
                    Gio.DBusCallFlags.NONE, -1, None
                )
            except Exception as e:
                debug_print(f'Activate error: {e}')

    def context_menu(self, x, y):
        """ Send ContextMenu; returns True if the call succeeded """
        if not self._proxy:
            return False
        try:
            self._proxy.call_sync(
                'ContextMenu', GLib.Variant('(ii)', (x, y)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            return True
        except Exception as e:
            debug_print(f'ContextMenu error: {e}')
        return False

    def secondary_action(self, x, y):
        """ Send SecondaryAction to the item """
        if self._proxy:
            try:
                self._proxy.call_sync(
                    'SecondaryAction', GLib.Variant('(ii)', (x, y)),
                    Gio.DBusCallFlags.NONE, -1, None
                )
            except Exception as e:
                debug_print(f'SecondaryAction error: {e}')


# ---------------------------------------------------------------------------
# DBusMenu client — fetches and activates context menus
# ---------------------------------------------------------------------------

class DBusMenuClient:
    """ Pure-Gio client for com.canonical.dbusmenu """

    def __init__(self, service, path):
        self._conn = _get_bus()
        self._service = service
        self._path = path

    def get_layout(
            self, parent_id=0, recursion_depth=-1, property_names=None):
        """ Fetch the menu layout tree; returns (id, props, children) """
        if property_names is None:
            property_names = []
        result = _bus_call(
            self._conn, self._service, self._path,
            DBUSMENU_IFACE, 'GetLayout',
            GLib.Variant('(iias)', (parent_id, recursion_depth,
                                    property_names)),
            '(u(ia{sv}av))'
        )
        if result is None:
            return None
        _revision, layout = result.unpack()
        return _deep_unpack(layout)

    def event(self, item_id, event_id, data, timestamp):
        """ Send a menu event (e.g. 'clicked') to the item """
        _bus_call(
            self._conn, self._service, self._path,
            DBUSMENU_IFACE, 'Event',
            GLib.Variant('(isvu)', (item_id, event_id, data, timestamp)),
            None
        )


# ---------------------------------------------------------------------------
# TrayHost — singleton that manages the watcher and all SNI items
# ---------------------------------------------------------------------------

class TrayHost:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """ Reset the singleton (for reload) """
        if cls._instance:
            cls._instance.cleanup()
            cls._instance = None

    def __init__(self):
        self.modules = []
        self._items: list = []
        self._conn = _get_bus()
        self.host_id = f'pybar-{os.getpid()}'
        self._watcher_server = None
        self._watcher_proxy = None
        self._watcher_watch_id = None
        self._setup_watcher()

    def cleanup(self):
        """ Release all DBus resources """
        debug_print('TrayHost: cleanup')
        for item in self._items[:]:
            item.disconnect()
        self._items.clear()

        if self._watcher_server:
            self._watcher_server.unregister()
            self._watcher_server = None

        if self._watcher_watch_id:
            Gio.bus_unwatch_name(self._watcher_watch_id)
            self._watcher_watch_id = None

        _release_name(self._conn, WATCHER_SERVICE)
        _release_name(
            self._conn,
            HOST_NAME_TPL.format(os.getpid(), self.host_id)
        )
        self._watcher_proxy = None

    # -- Module registration -------------------------------------------------

    def add_module(self, module):
        self.modules.append(module)
        for item in self._items:
            module.add_item(item)

    def remove_module(self, module):
        if module in self.modules:
            self.modules.remove(module)

    # -- Watcher setup -------------------------------------------------------

    def _setup_watcher(self):
        """ Own the host name, then watch for the SNI watcher service """
        host_name = HOST_NAME_TPL.format(os.getpid(), self.host_id)
        _request_name(self._conn, host_name)

        self._watcher_watch_id = Gio.bus_watch_name_on_connection(
            self._conn, WATCHER_SERVICE, Gio.BusNameWatcherFlags.NONE,
            self._on_watcher_available,
            self._on_watcher_unavailable
        )

        # If no external watcher exists, start our own
        try:
            result = _bus_call(
                self._conn, DBUS_SERVICE, DBUS_PATH, DBUS_IFACE,
                'NameHasOwner',
                GLib.Variant('(s)', (WATCHER_SERVICE,)), '(b)'
            )
            has_owner = result[0] if result else False
        except Exception:
            has_owner = False

        if not has_owner:
            debug_print('TrayHost: no external watcher, starting internal')
            self._start_internal_watcher()

    def _start_internal_watcher(self):
        """ Register pybar's own SNI watcher on the bus """
        try:
            self._watcher_server = WatcherServer(self._conn)
            self._watcher_server.on_item_registered = self._item_registered
            self._watcher_server.on_item_unregistered = self._item_unregistered
            if _request_name(self._conn, WATCHER_SERVICE):
                self._watcher_server.register_host_internal()
            else:
                debug_print(
                    'TrayHost: could not own watcher name', color='red')
        except Exception as e:
            c.print_debug(
                f'TrayHost: failed to start internal watcher: {e}',
                color='red')

    # -- External watcher proxy events ---------------------------------------

    def _on_watcher_available(self, conn, _name, _owner):
        """ External watcher appeared; connect a proxy to it """
        if self._watcher_server:
            # We are the watcher — nothing to do
            return
        debug_print('TrayHost: external watcher appeared')
        try:
            self._watcher_proxy = Gio.DBusProxy.new_sync(
                conn, Gio.DBusProxyFlags.NONE, None,
                WATCHER_SERVICE, WATCHER_PATH, WATCHER_SERVICE, None
            )
            self._watcher_proxy.connect(
                'g-signal', self._on_watcher_signal)

            host_path = HOST_PATH_TPL.format(self.host_id)
            _bus_call(
                conn, WATCHER_SERVICE, WATCHER_PATH,
                WATCHER_SERVICE, 'RegisterStatusNotifierHost',
                GLib.Variant('(s)', (host_path,)), None
            )

            # Enumerate already-registered items
            var = self._watcher_proxy.get_cached_property(
                'RegisteredStatusNotifierItems')
            if var:
                for full_name in var.unpack():
                    self._item_registered(full_name)
        except Exception as e:
            c.print_debug(
                f'TrayHost: watcher proxy error: {e}', color='red')

    def _on_watcher_unavailable(self, _conn, _name):
        """ External watcher disappeared """
        if self._watcher_server:
            return
        debug_print('TrayHost: external watcher vanished')
        self._watcher_proxy = None
        for item in self._items[:]:
            self._item_unregistered(
                f'{item.service_name}{item.object_path}')

    def _on_watcher_signal(
            self, _proxy, _sender, signal_name, params):
        """ Handle signals from an external SNI watcher """
        if signal_name == 'StatusNotifierItemRegistered':
            self._item_registered(params[0])
        elif signal_name == 'StatusNotifierItemUnregistered':
            self._item_unregistered(params[0])

    # -- Item lifecycle ------------------------------------------------------

    def _item_registered(self, full_name):
        service, path = _get_service_and_path(full_name)
        already = any(
            i.service_name == service and i.object_path == path
            for i in self._items
        )
        if already:
            return
        debug_print(f'TrayHost: new item {full_name}')
        item = StatusNotifierItem(service, path, self._conn)
        item.on_loaded_callback = self._on_item_loaded
        item.on_updated_callback = self._on_item_updated
        self._items.append(item)

    def _item_unregistered(self, full_name):
        service, path = _get_service_and_path(full_name)
        item = next(
            (i for i in self._items
             if i.service_name == service and i.object_path == path),
            None
        )
        if not item:
            return
        self._items.remove(item)
        item.disconnect()
        for module in self.modules:
            module.remove_item(item)

    def _on_item_loaded(self, item):
        for module in self.modules:
            module.add_item(item)

    def _on_item_updated(self, item, changed):
        for module in self.modules:
            module.update_item(item, changed)


# ---------------------------------------------------------------------------
# UI — TrayIcon, TrayModuleWidget, Tray (no dasbus dependencies)
# ---------------------------------------------------------------------------

class TrayIcon(Gtk.Box):
    def __init__(self, item, icon_size, module):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.item = item
        self.icon_size = icon_size
        self.module = module

        self.stack = Gtk.Stack()
        self.append(self.stack)

        self.image = Gtk.Image()
        self.stack.add_named(self.image, 'image')

        self.label = Gtk.Label()
        self.label.get_style_context().add_class('custom-tray-icon')
        self.stack.add_named(self.label, 'label')

        self.set_cursor(Gdk.Cursor.new_from_name('pointer', None))

        self.menu_client = None
        self.popover_menu = None

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect('released', self._on_click)
        self.add_controller(click)

        self.set_has_tooltip(False)
        self._tooltip_text = ''
        c.set_hover_popover(self, lambda: self._tooltip_text, delay=200)

        self.update()

    def _get_identifiers(self):
        """ Return lowercase identifier strings for this tray item """
        props = self.item.properties
        candidates = [
            props.get('Id', ''),
            props.get('Title', ''),
            self.item.service_name,
            getattr(self.item, 'proc_name', ''),
        ]
        tooltip = props.get('ToolTip')
        if tooltip and isinstance(tooltip, (list, tuple)) and len(tooltip) >= 3:
            candidates.append(tooltip[2])
        return [s.lower() for s in candidates if s]

    def _get_custom_icon(self):
        custom_icons = self.module.config.get('custom_icons', {})
        if not custom_icons:
            return None
        candidates = self._get_identifiers()
        for match_string, icon_char in custom_icons.items():
            match_lower = match_string.lower()
            for candidate in candidates:
                if match_lower in candidate:
                    return icon_char
        return None

    def _get_global_coordinates(self, x_local, y_local):
        try:
            native = self.get_native()
            if not native:
                return 0, 0
            surface = native.get_surface()
            if not surface:
                return 0, 0
            display = Gdk.Display.get_default()
            monitor = display.get_monitor_at_surface(surface)
            if not monitor:
                return 0, 0
            geo = monitor.get_geometry()
            point = self.translate_coordinates(native, x_local, y_local)
            if not point:
                return 0, 0
            win_x, win_y = point
            bar_pos = self.module.config.get('position', 'bottom')
            margin = self.module.config.get('margin', 0)
            if bar_pos == 'bottom':
                height = native.get_height()
                global_y = geo.y + geo.height - height + win_y - margin
                global_x = geo.x + win_x + margin
            else:
                global_y = geo.y + win_y + margin
                global_x = geo.x + win_x + margin
            return int(global_x), int(global_y)
        except Exception as e:
            debug_print(f'Coordinate calculation failed: {e}')
            return 0, 0

    def _on_click(self, gesture, _n_press, x, y):
        button = gesture.get_current_button()
        item_id = self.item.properties.get('Id', '')
        title = self.item.properties.get('Title', '')
        debug_print(
            f'TrayIcon click button={button} '
            f'id={item_id!r} title={title!r}')

        if self.popover_menu and self.popover_menu.get_visible():
            self.popover_menu.popdown()
            if button == 3:
                return

        global_x, global_y = self._get_global_coordinates(x, y)

        if button == 1:
            self.item.activate(global_x, global_y)
        elif button == 2:
            self.item.secondary_action(global_x, global_y)
        elif button == 3:
            if 'telegram' in item_id or 'telegram' in title:
                self._show_dbus_menu()
                return
            menu_path = self.item.properties.get('Menu')
            if menu_path and menu_path != '/':
                self._show_dbus_menu()
                return
            if self.item.context_menu(global_x, global_y):
                return
            self._show_dbus_menu()

    def _show_dbus_menu(self):
        menu_path = self.item.properties.get('Menu')
        if not menu_path:
            return

        if not self.menu_client:
            self.menu_client = DBusMenuClient(
                self.item.service_name, menu_path)

        layout = self.menu_client.get_layout(
            0, -1,
            ['label', 'enabled', 'visible', 'type',
             'toggle-type', 'toggle-state'])
        if not layout:
            return

        children = layout[2]
        if not children:
            return

        action_group = Gio.SimpleActionGroup.new()
        menu_model = self._build_menu_model(children, action_group)

        if self.popover_menu:
            self.popover_menu.unparent()
            self.popover_menu = None

        self.popover_menu = Gtk.PopoverMenu.new_from_model(menu_model)
        self.popover_menu.add_css_class('tray-popover')
        self.popover_menu.set_parent(self)
        self.popover_menu.set_can_focus(False)
        self.popover_menu.insert_action_group('menu', action_group)
        self.popover_menu.set_has_arrow(True)
        self.popover_menu.connect('map', lambda p: c.handle_popover_edge(p))

        if hasattr(self.module, 'notify_menu_opened'):
            self.module.notify_menu_opened()
            self.popover_menu.connect(
                'closed', lambda _: self.module.notify_menu_closed())

        pos = (Gtk.PositionType.TOP
               if self.module.config.get('position', 'bottom') == 'bottom'
               else Gtk.PositionType.BOTTOM)
        self.popover_menu.set_position(pos)
        self.popover_menu.popup()

    def _build_menu_model(self, children, action_group):
        menu_model = Gio.Menu()
        for child in children:
            child_id = child[0]
            props = child[1]
            subchildren = child[2]

            label = props.get('label', '')
            visible = props.get('visible', True)
            enabled = props.get('enabled', True)
            item_type = props.get('type', 'standard')
            toggle_type = props.get('toggle-type', '')
            toggle_state = props.get('toggle-state', 0)

            if not visible:
                continue
            if item_type == 'separator':
                continue

            if subchildren:
                submenu = self._build_menu_model(subchildren, action_group)
                label = label.replace('_', '')
                item = Gio.MenuItem.new(label, None)
                item.set_submenu(submenu)
                menu_model.append_item(item)
            elif label:
                label = label.replace('_', '')
                action_name = f'item_{child_id}'

                if toggle_type in ('checkmark', 'radio'):
                    state = GLib.Variant.new_boolean(bool(toggle_state))
                    action = Gio.SimpleAction.new_stateful(
                        action_name, None, state)

                    def on_toggle(act, _, cid=child_id, mc=self.menu_client):
                        new_state = not act.get_state().get_boolean()
                        act.set_state(GLib.Variant.new_boolean(new_state))
                        if mc:
                            mc.event(cid, 'clicked',
                                     GLib.Variant('s', ''),
                                     int(time.time()))

                    action.connect('activate', on_toggle)
                else:
                    action = Gio.SimpleAction.new(action_name, None)
                    action.set_enabled(enabled)

                    def on_activated(
                            _, __, cid=child_id, mc=self.menu_client):
                        if mc:
                            mc.event(cid, 'clicked',
                                     GLib.Variant('s', ''),
                                     int(time.time()))

                    action.connect('activate', on_activated)

                action_group.add_action(action)
                menu_item = Gio.MenuItem.new(label, f'menu.{action_name}')
                menu_model.append_item(menu_item)

        return menu_model

    def update(self, _changed=None):
        props = self.item.properties
        custom_icon = self._get_custom_icon()

        if custom_icon:
            self.label.set_label(custom_icon)
            self.stack.set_visible_child_name('label')
        else:
            self.stack.set_visible_child_name('image')
            icon_name = props.get('IconName')
            pixmap = props.get('IconPixmap')
            theme_path = props.get('IconThemePath')

            if icon_name:
                if theme_path and os.path.exists(theme_path):
                    theme = Gtk.IconTheme.get_for_display(
                        Gdk.Display.get_default())
                    if theme_path not in theme.get_search_path():
                        theme.add_search_path(theme_path)
                self.image.set_from_icon_name(icon_name)
                self.image.set_pixel_size(self.icon_size)
            elif pixmap:
                pixbuf = self._pixmap_to_pixbuf(pixmap)
                if pixbuf:
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    self.image.set_from_paintable(texture)
            else:
                self.image.set_from_icon_name('image-missing')
                self.image.set_pixel_size(self.icon_size)

        tooltip = props.get('ToolTip')
        if (tooltip and isinstance(tooltip, (list, tuple))
                and len(tooltip) >= 3):
            title = tooltip[2]
            desc = tooltip[3] if len(tooltip) > 3 else ''
            self._tooltip_text = f'{title}\n{desc}' if desc else title
        elif props.get('Title'):
            self._tooltip_text = props.get('Title')
        else:
            self._tooltip_text = ''

        if (hasattr(self, '_hover_popover') and self._hover_popover
                and self._hover_popover.get_visible()):
            if self._tooltip_text:
                self._hover_popover.label.set_text(self._tooltip_text)
            else:
                self._hover_popover.popdown()

        status = props.get('Status', 'Active')
        self.set_visible(status != 'Passive')

    def _pixmap_to_pixbuf(self, pixmap_data):
        if not pixmap_data:
            return None
        best = max(pixmap_data, key=lambda x: x[0] * x[1])
        w, h, data = best
        ba = bytearray(data)
        for i in range(0, len(ba), 4):
            a, r, g, b = ba[i], ba[i + 1], ba[i + 2], ba[i + 3]
            ba[i], ba[i + 1], ba[i + 2], ba[i + 3] = r, g, b, a
        return GdkPixbuf.Pixbuf.new_from_data(
            ba, GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)


class TrayModuleWidget(Gtk.Box):
    def __init__(self, tray_instance, config):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.tray = tray_instance
        self.config = config
        self.icon_size = config.get('icon_size', 18)
        self.get_style_context().add_class('tray-module')
        self.direction = config.get('direction', 'left')

        self.revealer = Gtk.Revealer()
        self.icons_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.icons_box.get_style_context().add_class('tray-icons')
        self.revealer.set_child(self.icons_box)

        self.toggle_btn = Gtk.Button()
        self.toggle_btn.get_style_context().add_class('tray-toggle')
        self.toggle_label = Gtk.Label()
        self.toggle_label.set_halign(Gtk.Align.CENTER)
        self.toggle_label.set_valign(Gtk.Align.CENTER)
        self.toggle_btn.set_child(self.toggle_label)
        self.toggle_btn.connect('clicked', self._on_toggle)

        if self.direction == 'left':
            self.revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.append(self.revealer)
            self.append(self.toggle_btn)
        else:
            self.revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.append(self.toggle_btn)
            self.append(self.revealer)

        is_collapsed = config.get('collapsed', True)
        self.user_wants_expanded = not is_collapsed
        self.revealer.set_reveal_child(not is_collapsed)

        self._is_hovering = False
        self._open_menus = 0
        self._auto_revealed = False

        self.icons = {}
        self._update_ui_state()

        if config.get('auto_reveal', False):
            self._setup_auto_reveal()

        TrayHost.get_instance().add_module(self)
        self.connect('destroy', self._on_destroy)

    def cleanup(self):
        TrayHost.get_instance().remove_module(self)
        self.icons.clear()
        child = self.icons_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.icons_box.remove(child)
            child = next_child

    def _on_destroy(self, _widget):
        self.cleanup()

    def _setup_auto_reveal(self):
        self.toggle_btn.set_sensitive(False)
        motion = Gtk.EventControllerMotion.new()
        motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        motion.connect('enter', self._on_hover_enter)
        motion.connect('leave', self._on_hover_leave)
        self.add_controller(motion)

    def _on_hover_enter(self, _ctrl, _x, _y):
        self._is_hovering = True
        self._set_auto_revealed(True)

    def _on_hover_leave(self, _ctrl):
        self._is_hovering = False
        if self._open_menus == 0:
            self._set_auto_revealed(False)

    def _set_auto_revealed(self, revealed):
        has_icons = len(self.icons) > 0
        self._auto_revealed = revealed and has_icons
        self.revealer.set_visible(has_icons)
        self.revealer.set_reveal_child(self._auto_revealed)
        self.set_spacing(5 if self._auto_revealed else 0)
        self._update_ui_state()

    def notify_menu_opened(self):
        self._open_menus += 1

    def notify_menu_closed(self):
        self._open_menus = max(0, self._open_menus - 1)
        if self._open_menus == 0 and not self._is_hovering:
            self._set_auto_revealed(False)

    def _on_toggle(self, _btn):
        self.user_wants_expanded = not self.user_wants_expanded
        self._update_ui_state()

    def _update_ui_state(self):
        has_icons = len(self.icons) > 0
        self.revealer.set_visible(has_icons)

        auto_reveal = self.config.get('auto_reveal', False)
        if auto_reveal:
            if not self._auto_revealed:
                self.set_spacing(0)
            expanded = self._auto_revealed
        else:
            should_reveal = self.user_wants_expanded and has_icons
            self.revealer.set_reveal_child(should_reveal)
            self.set_spacing(5 if should_reveal else 0)
            expanded = self.user_wants_expanded

        if self.direction == 'right':
            label_text = '' if expanded else ''
        else:
            label_text = '' if expanded else ''
        self.toggle_label.set_text(label_text)

        if has_icons:
            if expanded:
                self.get_style_context().remove_class('collapsed')
            else:
                self.get_style_context().add_class('collapsed')
        else:
            self.get_style_context().add_class('collapsed')

    def add_item(self, item):
        full_name = f'{item.service_name}{item.object_path}'

        identifiers = {
            'proc': getattr(item, 'proc_name', ''),
            'id': item.properties.get('Id', ''),
            'title': item.properties.get('Title', ''),
            'tooltip': ''
        }
        tooltip = item.properties.get('ToolTip')
        if (tooltip and isinstance(tooltip, (list, tuple))
                and len(tooltip) >= 3):
            identifiers['tooltip'] = tooltip[2]

        id_str = ', '.join(
            f"{k}='{v}'" for k, v in identifiers.items() if v)
        debug_print(f'Tray add_item: {id_str}')

        has_id = bool(identifiers['id'])
        has_title = bool(identifiers['title'])
        has_proc = bool(identifiers['proc'])
        icon_name = item.properties.get('IconName')
        icon_pixmap = item.properties.get('IconPixmap')
        has_icon = bool(icon_name or icon_pixmap)

        if not (has_id or has_title or has_proc or has_icon):
            debug_print(f'Skipping empty item: {full_name}')
            return

        blacklist = self.config.get('blacklist', [])
        if blacklist:
            check_values = [v.lower() for v in identifiers.values() if v]
            for entry in blacklist:
                entry_lower = entry.lower()
                for val in check_values:
                    if entry_lower in val:
                        debug_print(
                            f"Blacklisted '{entry}' matched '{val}'")
                        return

        if full_name not in self.icons:
            icon = TrayIcon(item, self.icon_size, self)
            self.icons[full_name] = icon
            self.icons_box.append(icon)
            self._update_ui_state()

    def update_item(self, item, changed):
        full_name = f'{item.service_name}{item.object_path}'
        if full_name in self.icons:
            self.icons[full_name].update(changed)

    def remove_item(self, item):
        full_name = f'{item.service_name}{item.object_path}'
        if full_name in self.icons:
            icon = self.icons.pop(full_name)
            self.icons_box.remove(icon)
            self._update_ui_state()


class Tray(c.BaseModule):
    SCHEMA = {
        'icon_size': {
            'type': 'integer', 'default': 18, 'label': 'Icon Size',
            'description': 'Size of tray icons in pixels',
            'min': 12, 'max': 48
        },
        'direction': {
            'type': 'choice', 'default': 'left',
            'label': 'Expand Direction',
            'description': 'Direction the tray expands when opened',
            'choices': ['left', 'right']
        },
        'collapsed': {
            'type': 'boolean', 'default': True,
            'label': 'Start Collapsed',
            'description': 'Start with tray icons hidden'
        },
        'custom_icons': {
            'type': 'dict', 'default': {},
            'label': 'Custom Icons',
            'description': 'Set custom icons for tray programs'
        },
        'blacklist': {
            'type': 'list', 'default': [], 'label': 'Blacklist',
            'description': 'Partial process names to hide from tray',
            'element_type': 'string'
        },
        'auto_reveal': {
            'type': 'boolean', 'default': False, 'label': 'Auto Reveal',
            'description': (
                'Reveal tray icons on hover and hide on leave; '
                'disables the toggle button'
            )
        }
    }

    def run_worker(self):
        """ Tray uses D-Bus signals; no polling required """
        pass

    def create_widget(self, bar):
        return TrayModuleWidget(self, self.config)


module_map = {
    'tray': Tray
}
