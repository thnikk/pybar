#!/usr/bin/python3 -u
"""
Description: System tray module for GTK4 with collapsible feature
Author: thnikk (ported and enhanced)
"""
import dasbus.typing
from dasbus.signal import Signal
from dasbus.server.interface import accepts_additional_arguments
from dasbus.error import DBusError
from dasbus.specification import DBusSpecification
from dasbus.client.handler import ClientObjectHandler
from dasbus.client.proxy import disconnect_proxy
from dasbus.client.observer import DBusObserver
from dasbus.connection import SessionMessageBus
import common as c
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
import os
import typing
import gi
import logging
import time

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')


# SNI Constants
WATCHER_SERVICE_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"
HOST_SERVICE_NAME_TEMPLATE = "org.kde.StatusNotifierHost-{}-{}"
HOST_OBJECT_PATH_TEMPLATE = "/StatusNotifierHost/{}"

# Configure dasbus logging
logging.getLogger("dasbus.connection").setLevel(logging.WARNING)

PROPERTIES = [
    "Id", "Category", "Title", "Status", "WindowId", "IconName", "IconPixmap",
    "OverlayIconName", "OverlayIconPixmap", "AttentionIconName",
    "AttentionIconPixmap", "AttentionMovieName", "ToolTip", "IconThemePath",
    "ItemIsMenu", "Menu"
]


def get_service_name_and_object_path(service: str) -> typing.Tuple[str, str]:
    index = service.find("/")
    if index != -1:
        return service[0:index], service[index:]
    return service, "/StatusNotifierItem"


def debug_print(msg, *args, **kwargs):
    try:
        c.print_debug(msg, *args, **kwargs)
    except Exception:
        pass


class StatusNotifierItemInterface:
    __dbus_xml__ = """
    <node>
        <interface name="org.kde.StatusNotifierItem">
            <method name="ContextMenu">
                <arg name="x" type="i" direction="in"/>
                <arg name="y" type="i" direction="in"/>
            </method>
            <method name="Activate">
                <arg name="x" type="i" direction="in"/>
                <arg name="y" type="i" direction="in"/>
            </method>
            <method name="SecondaryAction">
                <arg name="x" type="i" direction="in"/>
                <arg name="y" type="i" direction="in"/>
            </method>
            <method name="Scroll">
                <arg name="delta" type="i" direction="in"/>
                <arg name="orientation" type="s" direction="in"/>
            </method>
            <property name="Category" type="s" access="read"/>
            <property name="Id" type="s" access="read"/>
            <property name="Title" type="s" access="read"/>
            <property name="Status" type="s" access="read"/>
            <property name="WindowId" type="i" access="read"/>
            <property name="IconThemePath" type="s" access="read"/>
            <property name="Menu" type="o" access="read"/>
            <property name="ItemIsMenu" type="b" access="read"/>
            <property name="IconName" type="s" access="read"/>
            <property name="IconPixmap" type="a(iiay)" access="read"/>
            <property name="OverlayIconName" type="s" access="read"/>
            <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
            <property name="AttentionIconName" type="s" access="read"/>
            <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
            <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
            <signal name="NewTitle"/>
            <signal name="NewIcon"/>
            <signal name="NewAttentionIcon"/>
            <signal name="NewOverlayIcon"/>
            <signal name="NewToolTip"/>
            <signal name="NewStatus">
                <arg name="status" type="s" direction="out"/>
            </signal>
            <signal name="NewIconThemePath">
                <arg name="icon_theme_path" type="s" direction="out"/>
            </signal>
        </interface>
    </node>
    """


class SNIClientHandler(ClientObjectHandler):
    def _get_specification(self):
        return DBusSpecification.from_xml(
                StatusNotifierItemInterface.__dbus_xml__)


class StatusNotifierItem:
    def __init__(self, service_name, object_path):
        self.service_name = service_name
        self.object_path = object_path
        self.on_loaded_callback: typing.Optional[typing.Callable] = None
        self.on_updated_callback: typing.Optional[typing.Callable] = None
        self.session_bus = SessionMessageBus()
        self.properties = {"ItemIsMenu": True}
        self.item_proxy = None
        self.pid = 0
        self.proc_name = ""

        self.item_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=self.service_name
        )
        self.item_observer.service_available.connect(
            self.item_available_handler)
        self.item_observer.service_unavailable.connect(
            self.item_unavailable_handler)
        self.item_observer.connect_once_available()

    def item_available_handler(self, _observer):
        try:
            debug_print(
                f"SNI Item available: {self.service_name}{self.object_path}")

            # Resolve PID and Process Name for identification
            try:
                self.pid = self.session_bus.proxy.GetConnectionUnixProcessID(
                    self.service_name)
                if os.path.exists(f"/proc/{self.pid}/cmdline"):
                    with open(f"/proc/{self.pid}/cmdline", "r") as f:
                        self.proc_name = f.read().replace('\0', ' ').lower()
                debug_print(
                    f"  Identified process: PID={self.pid}, "
                    f"Name='{self.proc_name[:50]}...'")
            except Exception as e:
                debug_print(
                    f"  Failed to resolve process info (non-fatal): {e}")

            self.item_proxy = self.session_bus.get_proxy(
                self.service_name,
                self.object_path,
                handler_factory=SNIClientHandler
            )

            # Connect signals if they exist
            for signal_name, prop_names in [
                ('NewTitle', ["Title"]),
                ('NewIcon', ["IconName", "IconPixmap"]),
                ('NewAttentionIcon', [
                 "AttentionIconName", "AttentionIconPixmap"]),
                ('NewStatus', ["Status"])
            ]:
                if hasattr(self.item_proxy, signal_name):
                    getattr(self.item_proxy, signal_name).connect(
                        lambda *args, p=prop_names: self.change_handler(p)
                    )

            if hasattr(self.item_proxy, "NewIconThemePath"):
                self.item_proxy.NewIconThemePath.connect(
                    lambda path: self.change_handler(["IconThemePath"])
                )

            # Initial properties fetch
            for name in PROPERTIES:
                try:
                    val = getattr(self.item_proxy, name)
                    self.properties[name] = val
                except (AttributeError, DBusError):
                    pass

            if self.on_loaded_callback:
                GLib.idle_add(self.on_loaded_callback, self)
        except Exception as e:
            debug_print(f"Error in item_available_handler: {e}", color='red')

    def item_unavailable_handler(self, _observer):
        if self.item_proxy:
            disconnect_proxy(self.item_proxy)
            self.item_proxy = None

    def change_handler(self, changed_properties):
        actual_changed = []
        for name in changed_properties:
            try:
                self.properties[name] = getattr(self.item_proxy, name)
                actual_changed.append(name)
            except (AttributeError, DBusError):
                pass

        if actual_changed and self.on_updated_callback:
            GLib.idle_add(self.on_updated_callback, self, actual_changed)

    def activate(self, x, y):
        if self.item_proxy:
            try:
                self.item_proxy.Activate(x, y)
            except Exception as e:
                debug_print(f"Failed to activate item: {e}")

    def context_menu(self, x, y):
        if self.item_proxy:
            try:
                if hasattr(self.item_proxy, 'ContextMenu'):
                    self.item_proxy.ContextMenu(x, y)
                    return True
            except Exception as e:
                debug_print(f"Failed to call ContextMenu: {e}")

            if "Menu" in self.properties:
                return False
            else:
                debug_print(
                    f"Item {self.service_name} has no context menu support.")
        return False

    def secondary_action(self, x, y):
        if self.item_proxy:
            if hasattr(self.item_proxy, 'SecondaryAction'):
                try:
                    self.item_proxy.SecondaryAction(x, y)
                except Exception as e:
                    debug_print(f"Failed to call SecondaryAction: {e}")


class DBusMenuInterface:
    __dbus_xml__ = """
    <node>
        <interface name="com.canonical.dbusmenu">
            <method name="GetLayout">
                <arg name="parentId" type="i" direction="in"/>
                <arg name="recursionDepth" type="i" direction="in"/>
                <arg name="propertyNames" type="as" direction="in"/>
                <arg name="revision" type="u" direction="out"/>
                <arg name="layout" type="(ia{sv}av)" direction="out"/>
            </method>
            <method name="GetGroupProperties">
                <arg name="ids" type="ai" direction="in"/>
                <arg name="propertyNames" type="as" direction="in"/>
                <arg name="properties" type="a(ia{sv})" direction="out"/>
            </method>
            <method name="GetProperty">
                <arg name="id" type="i" direction="in"/>
                <arg name="name" type="s" direction="in"/>
                <arg name="value" type="v" direction="out"/>
            </method>
            <method name="Event">
                <arg name="id" type="i" direction="in"/>
                <arg name="eventId" type="s" direction="in"/>
                <arg name="data" type="v" direction="in"/>
                <arg name="timestamp" type="u" direction="in"/>
            </method>
            <method name="AboutToShow">
                <arg name="id" type="i" direction="in"/>
                <arg name="needUpdate" type="b" direction="out"/>
            </method>
            <signal name="ItemsPropertiesUpdated">
                <arg name="updatedProps" type="a(ia{sv})" direction="out"/>
                <arg name="removedProps" type="a(ias)" direction="out"/>
            </signal>
            <signal name="LayoutUpdated">
                <arg name="revision" type="u" direction="out"/>
                <arg name="parent" type="i" direction="out"/>
            </signal>
            <signal name="ItemActivationRequested">
                <arg name="id" type="i" direction="out"/>
                <arg name="timestamp" type="u" direction="out"/>
            </signal>
            <property name="Version" type="u" access="read"/>
            <property name="Status" type="s" access="read"/>
        </interface>
    </node>
    """


class DBusMenuClientHandler(ClientObjectHandler):
    def _get_specification(self):
        return DBusSpecification.from_xml(DBusMenuInterface.__dbus_xml__)


class StatusNotifierWatcherInterface:
    __dbus_xml__ = """
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
                    <arg type="s" direction="out" name="service" />
                </signal>
                <signal name="StatusNotifierItemUnregistered">
                    <arg type="s" direction="out" name="service" />
                </signal>
                <signal name="StatusNotifierHostRegistered"/>
                <signal name="StatusNotifierHostUnregistered"/>
            </interface>
        </node>
    """

    def __init__(self):
        self._items = []
        self._hosts = []
        self.StatusNotifierItemRegistered = Signal()
        self.StatusNotifierItemUnregistered = Signal()
        self.StatusNotifierHostRegistered = Signal()
        self.StatusNotifierHostUnregistered = Signal()
        self.PropertiesChanged = Signal()
        self.session_bus = SessionMessageBus()

    @accepts_additional_arguments
    def RegisterStatusNotifierItem(self, service, call_info):
        sender = call_info["sender"]
        if service.startswith("/"):
            full_name = f"{sender}{service}"
        elif service.startswith(":"):
            full_name = f"{service}/StatusNotifierItem"
        else:
            full_name = f"{sender}/StatusNotifierItem"

        if full_name not in self._items:
            debug_print(f"StatusNotifierWatcher: Registering item {full_name}")
            self._items.append(full_name)
            self.StatusNotifierItemRegistered.emit(full_name)
            self._emit_properties_changed("RegisteredStatusNotifierItems",
                                          dasbus.typing.get_variant(
                                              typing.List[str], self._items))

            # Watch for service disappearance
            observer = DBusObserver(self.session_bus, sender)
            observer.service_unavailable.connect(
                lambda _: self._unregister_item(full_name)
            )
            observer.connect_once_available()

    def _unregister_item(self, full_name):
        if full_name in self._items:
            debug_print(
                f"StatusNotifierWatcher: Unregistering item {full_name}")
            self._items.remove(full_name)
            self.StatusNotifierItemUnregistered.emit(full_name)
            self._emit_properties_changed(
                    "RegisteredStatusNotifierItems",
                    dasbus.typing.get_variant(typing.List[str], self._items))

    def _emit_properties_changed(self, prop_name, variant):
        self.PropertiesChanged.emit(
            WATCHER_SERVICE_NAME,
            {prop_name: variant},
            []
        )

    @accepts_additional_arguments
    def RegisterStatusNotifierHost(self, service, call_info):
        sender = call_info.get("sender", "internal")
        debug_print(
            f"StatusNotifierWatcher: Registering host {sender} ({service})")
        if sender not in self._hosts:
            self._hosts.append(sender)
            self.StatusNotifierHostRegistered.emit()
            self._emit_properties_changed(
                    "IsStatusNotifierHostRegistered",
                    dasbus.typing.get_variant(bool, True))

            if sender != "internal":
                observer = DBusObserver(self.session_bus, sender)
                observer.service_unavailable.connect(
                    lambda _: self._unregister_host(sender)
                )
                observer.connect_once_available()

    def _unregister_host(self, sender):
        if sender in self._hosts:
            self._hosts.remove(sender)
            self.StatusNotifierHostUnregistered.emit()

    @property
    def RegisteredStatusNotifierItems(self) -> typing.List[str]:
        return self._items

    @property
    def IsStatusNotifierHostRegistered(self) -> bool:
        return len(self._hosts) > 0

    @property
    def ProtocolVersion(self) -> int:
        return 0


class TrayHost:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (for reload)"""
        if cls._instance:
            cls._instance.cleanup()
            cls._instance = None

    def __init__(self):
        self.modules = []
        self._items = []
        self.session_bus = SessionMessageBus()
        self.host_id = f"pybar-{os.getpid()}"
        self.watcher_interface = None

        # Try to register watcher if not present
        self.watcher_proxy = None
        self._setup_watcher()

    def cleanup(self):
        """Cleanup DBus registrations and connections"""
        debug_print("TrayHost cleanup starting")
        
        # Disconnect all items
        for item in self._items[:]:
            if item.item_observer:
                item.item_observer.disconnect()
            if item.item_proxy:
                disconnect_proxy(item.item_proxy)
        self._items.clear()
        
        # Unregister DBus services
        try:
            if hasattr(self, 'watcher_interface') and self.watcher_interface:
                self.session_bus.unpublish_object(WATCHER_OBJECT_PATH)
                self.watcher_interface = None
        except Exception as e:
            debug_print(f"Failed to unpublish watcher: {e}")
        
        try:
            self.session_bus.unregister_service(WATCHER_SERVICE_NAME)
        except Exception as e:
            debug_print(f"Failed to unregister watcher service: {e}")
        
        try:
            host_service_name = HOST_SERVICE_NAME_TEMPLATE.format(
                os.getpid(), self.host_id)
            self.session_bus.unregister_service(host_service_name)
        except Exception as e:
            debug_print(f"Failed to unregister host service: {e}")
        
        # Disconnect observers
        if hasattr(self, 'watcher_observer') and self.watcher_observer:
            self.watcher_observer.disconnect()
        
        if self.watcher_proxy:
            disconnect_proxy(self.watcher_proxy)
            self.watcher_proxy = None
        
        debug_print("TrayHost cleanup complete")

    def add_module(self, module):
        self.modules.append(module)
        # Add existing items to new module
        for item in self._items:
            module.add_item(item)

    def remove_module(self, module):
        if module in self.modules:
            self.modules.remove(module)

    def _setup_watcher(self):
        # Register as a host
        host_service_name = HOST_SERVICE_NAME_TEMPLATE.format(
            os.getpid(), self.host_id)
        try:
            self.session_bus.register_service(host_service_name)
        except Exception:
            pass

        # Check if watcher exists
        self.watcher_observer = DBusObserver(
            self.session_bus, WATCHER_SERVICE_NAME)
        self.watcher_observer.service_available.connect(
            self._watcher_available)
        self.watcher_observer.service_unavailable.connect(
            self._watcher_unavailable)
        self.watcher_observer.connect_once_available()

        if not self.watcher_observer.is_service_available:
            debug_print("SNI Watcher not found, starting internal watcher")
            try:
                self.watcher_interface = StatusNotifierWatcherInterface()
                # Connect directly to internal interface signals
                self.watcher_interface.StatusNotifierItemRegistered.connect(
                    self._item_registered)
                self.watcher_interface.StatusNotifierItemUnregistered.connect(
                    self._item_unregistered)

                self.session_bus.publish_object(
                    WATCHER_OBJECT_PATH, self.watcher_interface)
                self.session_bus.register_service(WATCHER_SERVICE_NAME)
            except Exception as e:
                c.print_debug(
                    f"Failed to start internal SNI watcher: {e}", color='red')

    def _watcher_available(self, _observer):
        if hasattr(self, 'watcher_interface'):
            debug_print("Using internal SNI watcher")
            # We still need to register as a host on our own watcher
            host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
            self.watcher_interface.RegisterStatusNotifierHost(
                host_object_path, call_info={})
            return

        debug_print("External SNI Watcher service available, connecting proxy")
        self.watcher_proxy = self.session_bus.get_proxy(
            WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH)
        self.watcher_proxy.StatusNotifierItemRegistered.connect(
            self._item_registered)
        self.watcher_proxy.StatusNotifierItemUnregistered.connect(
            self._item_unregistered)

        host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
        try:
            debug_print(f"Registering host: {host_object_path}")
            self.watcher_proxy.RegisterStatusNotifierHost(host_object_path)
        except Exception as e:
            c.print_debug(f"Failed to register host: {e}", color='red')

        try:
            items = self.watcher_proxy.RegisteredStatusNotifierItems
            debug_print(f"Already registered items: {items}")
            for full_name in items:
                self._item_registered(full_name)
        except Exception as e:
            c.print_debug(f"Failed to get existing items: {e}")

    def _watcher_unavailable(self, _observer):
        self.watcher_proxy = None
        for item in self._items[:]:
            self._item_unregistered(f"{item.service_name}{item.object_path}")

    def _item_registered(self, full_name):
        debug_print(f"TrayHost._item_registered: {full_name}")
        service, path = get_service_name_and_object_path(full_name)

        if not any(
                i.service_name == service and
                i.object_path == path for i in self._items):
            item = StatusNotifierItem(service, path)
            item.on_loaded_callback = self._on_item_loaded
            item.on_updated_callback = self._on_item_updated
            self._items.append(item)
            debug_print(f"  Created StatusNotifierItem for {full_name}")

    def _on_item_loaded(self, item):
        for module in self.modules:
            module.add_item(item)

    def _on_item_updated(self, item, changed):
        for module in self.modules:
            module.update_item(item, changed)

    def _item_unregistered(self, full_name):
        service, path = get_service_name_and_object_path(full_name)
        item = next((i for i in self._items if i.service_name ==
                    service and i.object_path == path), None)
        if item:
            self._items.remove(item)
            for module in self.modules:
                module.remove_item(item)


class DBusMenuClient:
    def __init__(self, service, path):
        self.service = service
        self.path = path
        self.bus = SessionMessageBus()
        self.proxy = self.bus.get_proxy(
            service,
            path,
            handler_factory=DBusMenuClientHandler
        )

    def get_layout(self, parent_id=0, recursion_depth=-1, property_names=None):
        if property_names is None:
            property_names = []
        try:
            _revision, layout = self.proxy.GetLayout(
                parent_id, recursion_depth, property_names)
            return layout
        except Exception as e:
            debug_print(f"Failed to get dbusmenu layout: {e}")
            return None

    def event(self, item_id, event_id, data, timestamp):
        try:
            self.proxy.Event(item_id, event_id, data, timestamp)
        except Exception as e:
            debug_print(f"Failed to send dbusmenu event: {e}")


class TrayIcon(Gtk.Box):
    def __init__(self, item, icon_size, module):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.item = item
        self.icon_size = icon_size
        self.module = module

        self.stack = Gtk.Stack()
        self.append(self.stack)

        self.image = Gtk.Image()
        self.stack.add_named(self.image, "image")

        self.label = Gtk.Label()
        self.label.get_style_context().add_class("custom-tray-icon")
        self.stack.add_named(self.label, "label")

        self.set_cursor(Gdk.Cursor.new_from_name("pointer", None))

        self.menu_client = None
        self.popover_menu = None

        click = Gtk.GestureClick()
        click.set_button(0)  # Handle all buttons
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.update()

    def _get_custom_icon(self):
        custom_icons = self.module.config.get("custom_icons", {})
        if not custom_icons:
            return None

        # Gather identifiers (consistent with add_item blacklist logic)
        candidates = []
        candidates.append(self.item.properties.get("Id", ""))
        candidates.append(self.item.properties.get("Title", ""))
        candidates.append(self.item.service_name)
        candidates.append(getattr(self.item, "proc_name", ""))

        tooltip = self.item.properties.get("ToolTip")
        if tooltip and isinstance(tooltip, (list, tuple)) and len(tooltip) >= 3:
            candidates.append(tooltip[2])  # Tooltip title

        # Filter empty and lowercase
        candidates = [c.lower() for c in candidates if c]

        for match_string, icon_char in custom_icons.items():
            match_string = match_string.lower()
            for candidate in candidates:
                if match_string in candidate:
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
            bar_pos = self.module.config.get("position", "bottom")
            margin = self.module.config.get("margin", 0)

            if bar_pos == "bottom":
                height = native.get_height()
                global_y = geo.y + geo.height - height + win_y - margin
                global_x = geo.x + win_x + margin
            else:
                global_y = geo.y + win_y + margin
                global_x = geo.x + win_x + margin

            return int(global_x), int(global_y)

        except Exception as e:
            debug_print(f"Failed to calculate coords: {e}")
            return 0, 0

    def _on_click(self, gesture, _n_press, x, y):
        button = gesture.get_current_button()
        
        proc = getattr(self.item, "proc_name", "")
        item_id = self.item.properties.get("Id", "")
        title = self.item.properties.get("Title", "")
        debug_print(
            f"TrayIcon._on_click: button {button} for {self.item.service_name}\n"
            f"  Details: proc='{proc}', id='{item_id}', title='{title}'")

        if self.popover_menu and self.popover_menu.get_visible():
            debug_print("  Hiding existing popover")
            self.popover_menu.popdown()
            if button == 3:
                return

        global_x, global_y = self._get_global_coordinates(x, y)

        item_id = self.item.properties.get("Id", "").lower()
        item_title = self.item.properties.get("Title", "").lower()
        proc_name = getattr(self.item, "proc_name", "")

        is_discord = (
            "discord" in item_id or
            "discord" in item_title or
            "discord" in self.item.service_name.lower() or
            "discord" in proc_name
        )

        if is_discord:
            try:
                native = self.get_native()
                surface = native.get_surface()
                display = Gdk.Display.get_default()
                monitor = display.get_monitor_at_surface(surface)
                geo = monitor.get_geometry()
                global_x = global_x - geo.x
                global_y = global_y - geo.y
            except Exception:
                pass

        if button == 1:
            self.item.activate(global_x, global_y)
        elif button == 2:
            self.item.secondary_action(global_x, global_y)
        elif button == 3:
            if "telegram" in item_id or "telegram" in item_title:
                self._show_dbus_menu()
                return

            menu_path = self.item.properties.get("Menu")
            if menu_path and menu_path != "/":
                self._show_dbus_menu()
                return

            if self.item.context_menu(global_x, global_y):
                return

            self._show_dbus_menu()

    def _show_dbus_menu(self):
        menu_path = self.item.properties.get("Menu")
        if not menu_path:
            return

        if not self.menu_client:
            self.menu_client = DBusMenuClient(
                self.item.service_name, menu_path)

        layout = self.menu_client.get_layout(
            0, -1, [
                "label", "enabled", "visible", "type",
                "toggle-type", "toggle-state"])
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
        self.popover_menu.add_css_class("tray-popover")
        self.popover_menu.set_parent(self)
        self.popover_menu.insert_action_group("menu", action_group)
        self.popover_menu.set_has_arrow(True)
        self.popover_menu.connect("map", lambda p: c.handle_popover_edge(p))

        if self.module.config.get("position", "bottom") == "bottom":
            self.popover_menu.set_position(Gtk.PositionType.TOP)
        else:
            self.popover_menu.set_position(Gtk.PositionType.BOTTOM)

        self.popover_menu.popup()

    def _build_menu_model(self, children, action_group):
        menu_model = Gio.Menu()

        for child in children:
            child_id = child[0]
            props = child[1]
            subchildren = child[2]

            label = props.get("label", "")
            visible = props.get("visible", True)
            enabled = props.get("enabled", True)
            item_type = props.get("type", "standard")
            toggle_type = props.get("toggle-type", "")
            toggle_state = props.get("toggle-state", 0)

            if not visible:
                continue

            if item_type == "separator":
                pass
            elif subchildren:
                submenu = self._build_menu_model(subchildren, action_group)
                if label:
                    label = label.replace("_", "")
                item = Gio.MenuItem.new(label, None)
                item.set_submenu(submenu)
                menu_model.append_item(item)
            elif label:
                label = label.replace("_", "")
                action_name = f"item_{child_id}"

                if toggle_type in ["checkmark", "radio"]:
                    state = GLib.Variant.new_boolean(bool(toggle_state))
                    action = Gio.SimpleAction.new_stateful(
                        action_name, None, state)

                    def on_toggle(act, _, cid=child_id, mc=self.menu_client):
                        new_state = not act.get_state().get_boolean()
                        act.set_state(GLib.Variant.new_boolean(new_state))
                        data = GLib.Variant("s", "")
                        if mc:
                            mc.event(cid, "clicked", data, int(time.time()))

                    action.connect("activate", on_toggle)
                else:
                    action = Gio.SimpleAction.new(action_name, None)
                    action.set_enabled(enabled)

                    def on_activated(_, __, cid=child_id, mc=self.menu_client):
                        data = GLib.Variant("s", "")
                        if mc:
                            mc.event(cid, "clicked", data, int(time.time()))

                    action.connect("activate", on_activated)

                action_group.add_action(action)
                menu_item = Gio.MenuItem.new(label, f"menu.{action_name}")
                menu_model.append_item(menu_item)

        return menu_model

    def update(self, _changed=None):
        props = self.item.properties
        custom_icon = self._get_custom_icon()

        if custom_icon:
            self.label.set_label(custom_icon)
            self.stack.set_visible_child_name("label")
        else:
            self.stack.set_visible_child_name("image")
            icon_name = props.get("IconName")
            pixmap = props.get("IconPixmap")
            theme_path = props.get("IconThemePath")

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
                self.image.set_from_icon_name("image-missing")
                self.image.set_pixel_size(self.icon_size)

        tooltip = props.get("ToolTip")
        if tooltip and isinstance(tooltip, (list, tuple)) and len(tooltip) >= 3:
            title = tooltip[2]
            desc = tooltip[3] if len(tooltip) > 3 else ""
            self.set_tooltip_markup(
                f"<b>{title}</b>\n{desc}" if desc else title)
        elif props.get("Title"):
            self.set_tooltip_text(props.get("Title"))

        status = props.get("Status", "Active")
        self.set_visible(status != "Passive")

    def _pixmap_to_pixbuf(self, pixmap_data):
        if not pixmap_data:
            return None
        best = max(pixmap_data, key=lambda x: x[0] * x[1])
        w, h, data = best
        ba = bytearray(data)
        for i in range(0, len(ba), 4):
            a, r, g, b = ba[i], ba[i+1], ba[i+2], ba[i+3]
            ba[i], ba[i+1], ba[i+2], ba[i+3] = r, g, b, a
        return GdkPixbuf.Pixbuf.new_from_data(
            ba, GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)


class TrayModuleWidget(Gtk.Box):
    def __init__(self, tray_instance, config):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.tray = tray_instance
        self.config = config
        self.icon_size = config.get("icon_size", 18)
        self.get_style_context().add_class("tray-module")

        self.direction = config.get("direction", "left")

        self.revealer = Gtk.Revealer()
        self.icons_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.icons_box.get_style_context().add_class("tray-icons")
        self.revealer.set_child(self.icons_box)

        self.toggle_btn = Gtk.Button()
        self.toggle_btn.get_style_context().add_class("tray-toggle")

        self.toggle_label = Gtk.Label()
        self.toggle_label.set_halign(Gtk.Align.CENTER)
        self.toggle_label.set_valign(Gtk.Align.CENTER)
        self.toggle_btn.set_child(self.toggle_label)

        self.toggle_btn.connect("clicked", self._on_toggle)

        if self.direction == "left":
            self.revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.append(self.revealer)
            self.append(self.toggle_btn)
        else:
            self.revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.append(self.toggle_btn)
            self.append(self.revealer)

        is_collapsed = config.get("collapsed", True)
        self.revealer.set_reveal_child(not is_collapsed)
        self._update_ui_state()

        self.icons = {}
        TrayHost.get_instance().add_module(self)
        self.connect("destroy", self._on_destroy)

    def cleanup(self):
        """Cleanup resources"""
        TrayHost.get_instance().remove_module(self)
        self.icons.clear()
        # Clean up icons
        child = self.icons_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.icons_box.remove(child)
            child = next_child

    def _on_destroy(self, _widget):
        self.cleanup()

    def _on_toggle(self, _btn):
        revealed = not self.revealer.get_reveal_child()
        self.revealer.set_reveal_child(revealed)
        self._update_ui_state()

    def _update_ui_state(self):
        revealed = self.revealer.get_reveal_child()
        self.set_spacing(5 if revealed else 0)

        label_text = ""
        if self.direction == "right":
            label_text = "" if revealed else ""
        else:
            label_text = "" if revealed else ""

        self.toggle_label.set_text(label_text)

        if revealed:
            self.get_style_context().remove_class("collapsed")
        else:
            self.get_style_context().add_class("collapsed")

    def add_item(self, item):
        full_name = f"{item.service_name}{item.object_path}"

        # Gather all possible identifiers
        identifiers = {
            "proc": getattr(item, "proc_name", ""),
            "id": item.properties.get("Id", ""),
            "title": item.properties.get("Title", ""),
            "tooltip": ""
        }

        # Extract tooltip title if available
        tooltip = item.properties.get("ToolTip")
        if tooltip and isinstance(tooltip, (list, tuple)) and len(tooltip) >= 3:
            identifiers["tooltip"] = tooltip[2]

        # Log identification info for user debugging
        id_str = ", ".join(f"{k}='{v}'" for k, v in identifiers.items() if v)
        debug_print(f"Tray Item Candidates: {id_str}")

        # Check for minimum requirements (ghost icon protection)
        has_id = bool(identifiers["id"])
        has_title = bool(identifiers["title"])
        has_proc = bool(identifiers["proc"])
        
        icon_name = item.properties.get("IconName")
        icon_pixmap = item.properties.get("IconPixmap")
        has_icon = bool(icon_name or icon_pixmap)

        if not (has_id or has_title or has_proc or has_icon):
            debug_print(f"Skipping empty item: {full_name}")
            return

        # Check blacklist
        blacklist = self.config.get("blacklist", [])
        if blacklist:
            # Normalize identifiers for case-insensitive comparison
            check_values = [v.lower() for v in identifiers.values() if v]
            
            for entry in blacklist:
                entry_lower = entry.lower()
                for val in check_values:
                    if entry_lower in val:
                        debug_print(f"Blacklisted item matched '{entry}': {val} ({full_name})")
                        return

        if full_name not in self.icons:
            icon = TrayIcon(item, self.icon_size, self)
            self.icons[full_name] = icon
            self.icons_box.append(icon)

    def update_item(self, item, changed):
        full_name = f"{item.service_name}{item.object_path}"
        if full_name in self.icons:
            self.icons[full_name].update(changed)

    def remove_item(self, item):
        full_name = f"{item.service_name}{item.object_path}"
        if full_name in self.icons:
            icon = self.icons.pop(full_name)
            self.icons_box.remove(icon)


class Tray(c.BaseModule):
    SCHEMA = {
        'icon_size': {
            'type': 'integer',
            'default': 18,
            'label': 'Icon Size',
            'description': 'Size of tray icons in pixels',
            'min': 12,
            'max': 48
        },
        'direction': {
            'type': 'choice',
            'default': 'left',
            'label': 'Expand Direction',
            'description': 'Direction the tray expands when opened',
            'choices': ['left', 'right']
        },
        'collapsed': {
            'type': 'boolean',
            'default': True,
            'label': 'Start Collapsed',
            'description': 'Start with tray icons hidden'
        },
        'custom_icons': {
            'type': 'dict',
            'default': {},
            'label': 'Custom Icons',
            'description': 'Set custom icons for tray programs'
        },
        'blacklist': {
            'type': 'list',
            'default': [],
            'label': 'Blacklist',
            'description': 'List of partial process names to hide from tray',
            'element_type': 'string'
        }
    }

    def run_worker(self):
        """ Tray uses D-Bus, no periodic fetch needed """
        pass

    def create_widget(self, bar):
        return TrayModuleWidget(self, self.config)


module_map = {
    'tray': Tray
}
