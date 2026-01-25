#!/usr/bin/python3 -u
"""
Description: System tray module for GTK4 with collapsible feature
Author: thnikk (ported and enhanced)
"""
import os
import typing
import gi
import logging
import threading

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio

import common as c
from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver
from dasbus.client.proxy import disconnect_proxy
from dasbus.error import DBusError
from dasbus.server.interface import accepts_additional_arguments
from dasbus.signal import Signal
import dasbus.typing

# SNI Constants
WATCHER_SERVICE_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"
HOST_SERVICE_NAME_TEMPLATE = "org.kde.StatusNotifierHost-{}-{}"
HOST_OBJECT_PATH_TEMPLATE = "/StatusNotifierHost/{}"

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

class StatusNotifierItem:
    def __init__(self, service_name, object_path):
        self.service_name = service_name
        self.object_path = object_path
        self.on_loaded_callback: typing.Optional[typing.Callable] = None
        self.on_updated_callback: typing.Optional[typing.Callable] = None
        self.session_bus = SessionMessageBus()
        self.properties = {"ItemIsMenu": True}
        self.item_proxy = None

        self.item_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=self.service_name
        )
        self.item_observer.service_available.connect(self.item_available_handler)
        self.item_observer.service_unavailable.connect(self.item_unavailable_handler)
        self.item_observer.connect_once_available()

    def item_available_handler(self, _observer):
        try:
            c.print_debug(f"SNI Item available: {self.service_name}{self.object_path}")
            self.item_proxy = self.session_bus.get_proxy(self.service_name, self.object_path)
            
            # Connect signals if they exist
            for signal_name, prop_names in [
                ('NewTitle', ["Title"]),
                ('NewIcon', ["IconName", "IconPixmap"]),
                ('NewAttentionIcon', ["AttentionIconName", "AttentionIconPixmap"]),
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
                    # c.print_debug(f"  Property {name}: {val}")
                except (AttributeError, DBusError):
                    pass
            
            if self.on_loaded_callback:
                GLib.idle_add(self.on_loaded_callback, self)
        except Exception as e:
            c.print_debug(f"Error in item_available_handler: {e}", color='red')

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
                c.print_debug(f"Failed to activate item: {e}")

    def context_menu(self, x, y):
        if self.item_proxy:
            try:
                self.item_proxy.ContextMenu(x, y)
            except Exception as e:
                c.print_debug(f"Failed to show context menu: {e}")

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
            c.print_debug(f"StatusNotifierWatcher: Registering item {full_name}")
            self._items.append(full_name)
            self.StatusNotifierItemRegistered.emit(full_name)
            self._emit_properties_changed("RegisteredStatusNotifierItems", 
                dasbus.typing.get_variant(typing.List[str], self._items))
            
            # Watch for service disappearance
            observer = DBusObserver(self.session_bus, sender)
            observer.service_unavailable.connect(
                lambda _: self._unregister_item(full_name)
            )
            observer.connect_once_available()

    def _unregister_item(self, full_name):
        if full_name in self._items:
            c.print_debug(f"StatusNotifierWatcher: Unregistering item {full_name}")
            self._items.remove(full_name)
            self.StatusNotifierItemUnregistered.emit(full_name)
            self._emit_properties_changed("RegisteredStatusNotifierItems", 
                dasbus.typing.get_variant(typing.List[str], self._items))

    def _emit_properties_changed(self, prop_name, variant):
        self.PropertiesChanged.emit(
            WATCHER_SERVICE_NAME,
            {prop_name: variant},
            []
        )

    @accepts_additional_arguments
    def RegisterStatusNotifierHost(self, service, call_info):
        sender = call_info["sender"]
        c.print_debug(f"StatusNotifierWatcher: Registering host {sender} ({service})")
        if sender not in self._hosts:
            self._hosts.append(sender)
            self.StatusNotifierHostRegistered.emit()
            self._emit_properties_changed("IsStatusNotifierHostRegistered",
                dasbus.typing.get_variant(bool, True))
            
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

    def __init__(self):
        self.modules = []
        self._items = []
        self.session_bus = SessionMessageBus()
        self.host_id = f"pybar-{os.getpid()}"
        
        # Try to register watcher if not present
        self.watcher_proxy = None
        self._setup_watcher()

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
        host_service_name = HOST_SERVICE_NAME_TEMPLATE.format(os.getpid(), self.host_id)
        host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
        try:
            self.session_bus.register_service(host_service_name)
        except Exception:
            pass

        # Check if watcher exists
        self.watcher_observer = DBusObserver(self.session_bus, WATCHER_SERVICE_NAME)
        self.watcher_observer.service_available.connect(self._watcher_available)
        self.watcher_observer.service_unavailable.connect(self._watcher_unavailable)
        self.watcher_observer.connect_once_available()
        
        if not self.watcher_observer.is_service_available:
            c.print_debug("SNI Watcher not found, starting internal watcher")
            try:
                self.watcher_interface = StatusNotifierWatcherInterface()
                # Connect directly to internal interface signals to avoid proxy issues in same process
                self.watcher_interface.StatusNotifierItemRegistered.connect(self._item_registered)
                self.watcher_interface.StatusNotifierItemUnregistered.connect(self._item_unregistered)
                
                self.session_bus.publish_object(WATCHER_OBJECT_PATH, self.watcher_interface)
                self.session_bus.register_service(WATCHER_SERVICE_NAME)
            except Exception as e:
                c.print_debug(f"Failed to start internal SNI watcher: {e}")

    def _watcher_available(self, _observer):
        # If we are the watcher, we've already connected signals in _setup_watcher
        if hasattr(self, 'watcher_interface'):
            c.print_debug("Using internal SNI watcher")
            # We still need to register as a host on our own watcher
            host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
            self.watcher_interface.RegisterStatusNotifierHost(host_object_path, call_info={})
            return

        c.print_debug("External SNI Watcher service available, connecting proxy")
        self.watcher_proxy = self.session_bus.get_proxy(WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH)
        self.watcher_proxy.StatusNotifierItemRegistered.connect(self._item_registered)
        self.watcher_proxy.StatusNotifierItemUnregistered.connect(self._item_unregistered)
        
        host_object_path = HOST_OBJECT_PATH_TEMPLATE.format(self.host_id)
        try:
            c.print_debug(f"Registering host: {host_object_path}")
            self.watcher_proxy.RegisterStatusNotifierHost(host_object_path)
        except Exception as e:
            c.print_debug(f"Failed to register host: {e}", color='red')

        try:
            items = self.watcher_proxy.RegisteredStatusNotifierItems
            c.print_debug(f"Already registered items: {items}")
            for full_name in items:
                self._item_registered(full_name)
        except Exception as e:
            c.print_debug(f"Failed to get existing items: {e}")

    def _watcher_unavailable(self, _observer):
        self.watcher_proxy = None
        for item in self._items[:]:
            self._item_unregistered(f"{item.service_name}{item.object_path}")

    def _item_registered(self, full_name):
        c.print_debug(f"TrayHost._item_registered: {full_name}")
        service, path = get_service_name_and_object_path(full_name)
        if not any(i.service_name == service and i.object_path == path for i in self._items):
            item = StatusNotifierItem(service, path)
            item.on_loaded_callback = self._on_item_loaded
            item.on_updated_callback = self._on_item_updated
            self._items.append(item)
            c.print_debug(f"  Created StatusNotifierItem for {full_name}")
        else:
            c.print_debug(f"  StatusNotifierItem for {full_name} already in self._items")

    def _on_item_loaded(self, item):
        for module in self.modules:
            module.add_item(item)

    def _on_item_updated(self, item, changed):
        for module in self.modules:
            module.update_item(item, changed)

    def _item_unregistered(self, full_name):
        service, path = get_service_name_and_object_path(full_name)
        item = next((i for i in self._items if i.service_name == service and i.object_path == path), None)
        if item:
            self._items.remove(item)
            for module in self.modules:
                module.remove_item(item)

class TrayIcon(Gtk.Box):
    def __init__(self, item, icon_size):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.item = item
        self.icon_size = icon_size
        self.image = Gtk.Image()
        self.append(self.image)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer", None))
        
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.update()

    def _on_click(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        if button == 1:
            # -1, -1 is often used to signify "default position" or "don't know"
            self.item.activate(-1, -1)
        elif button == 3:
            # Try SNI context menu
            self.item.context_menu(-1, -1)
            # Since we don't have dbusmenu yet, if the app doesn't show its own window,
            # it might feel like nothing happened.

    def update(self, changed=None):
        props = self.item.properties
        icon_name = props.get("IconName")
        pixmap = props.get("IconPixmap")
        theme_path = props.get("IconThemePath")
        
        # c.print_debug(f"Updating tray icon: {icon_name}, theme: {theme_path}")
        
        if icon_name:
            if theme_path and os.path.exists(theme_path):
                # Temporary add search path if not there
                theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
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
            # Fallback if no icon or pixmap
            self.image.set_from_icon_name("image-missing")
            self.image.set_pixel_size(self.icon_size)
        
        tooltip = props.get("ToolTip")
        if tooltip and isinstance(tooltip, (list, tuple)) and len(tooltip) >= 3:
            title = tooltip[2]
            desc = tooltip[3] if len(tooltip) > 3 else ""
            self.set_tooltip_markup(f"<b>{title}</b>\n{desc}" if desc else title)
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
        return GdkPixbuf.Pixbuf.new_from_data(ba, GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)

class TrayModule(Gtk.Box):
    def __init__(self, bar, config):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.bar = bar
        self.config = config
        self.icon_size = config.get("icon_size", 18)
        self.get_style_context().add_class("tray-module")
        
        # Direction and expansion logic
        # Default to 'left' as tray is usually on the right
        self.direction = config.get("direction", "left")
        
        self.revealer = Gtk.Revealer()
        self.icons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.icons_box.get_style_context().add_class("tray-icons")
        self.revealer.set_child(self.icons_box)
        
        self.toggle_btn = Gtk.Button()
        self.toggle_btn.get_style_context().add_class("tray-toggle")
        self.toggle_btn.connect("clicked", self._on_toggle)
        
        # Order and transition based on direction
        if self.direction == "left":
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.append(self.revealer)
            self.append(self.toggle_btn)
        else:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.append(self.toggle_btn)
            self.append(self.revealer)
            
        # Start collapsed by default (unless explicitly set otherwise)
        is_collapsed = config.get("collapsed", True)
        self.revealer.set_reveal_child(not is_collapsed)
        self._update_ui_state()
        
        self.icons = {}
        TrayHost.get_instance().add_module(self)

    def _on_toggle(self, btn):
        revealed = not self.revealer.get_reveal_child()
        self.revealer.set_reveal_child(revealed)
        self._update_ui_state()

    def _update_ui_state(self):
        revealed = self.revealer.get_reveal_child()
        
        # Update arrows based on direction and state
        # User requested: < to open, > to close (for left expansion)
        if self.direction == "left":
            self.toggle_btn.set_label("" if revealed else "")
        else:
            self.toggle_btn.set_label("" if revealed else "")
            
        # Toggle collapsed class for padding
        if revealed:
            self.get_style_context().remove_class("collapsed")
        else:
            self.get_style_context().add_class("collapsed")


    def add_item(self, item):
        full_name = f"{item.service_name}{item.object_path}"
        c.print_debug(f"TrayModule.add_item: {full_name}")
        if full_name not in self.icons:
            icon = TrayIcon(item, self.icon_size)
            self.icons[full_name] = icon
            self.icons_box.append(icon)
            c.print_debug(f"  Icon widget created and appended for {full_name}")
        else:
            c.print_debug(f"  Icon for {full_name} already exists")

    def update_item(self, item, changed):
        full_name = f"{item.service_name}{item.object_path}"
        if full_name in self.icons:
            self.icons[full_name].update(changed)

    def remove_item(self, item):
        full_name = f"{item.service_name}{item.object_path}"
        if full_name in self.icons:
            icon = self.icons.pop(full_name)
            self.icons_box.remove(icon)

def create_widget(bar, config):
    return TrayModule(bar, config)
