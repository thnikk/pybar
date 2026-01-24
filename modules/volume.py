#!/usr/bin/python3 -u
"""
Description: Pulse module
Author: thnikk
"""
import common as c
import pulsectl
import threading
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Pango  # noqa


class Volume(c.Module):
    def __init__(self, bar, config):
        super().__init__()
        self.set_position(bar.position)
        self.alive = True

        c.add_style(self, 'module-fixed')

        self.icons = config['icons']

        # Storage for persistent widget references
        self.section_boxes = {}  # {'Outputs': box, 'Inputs': box, 'Programs': box}
        self.device_widgets = {}  # {(section, index): (row_box, label, slider, mute_btn)}
        self.widget_instance = None

        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_controller.connect('scroll', self.scroll)
        self.add_controller(scroll_controller)

        # Try a different approach for right-click - connect to the text label
        button_controller = Gtk.EventControllerLegacy.new()
        button_controller.connect('event', self.handle_button_event)
        self.text.add_controller(button_controller)

        # Connect to pulse and get default sink
        while True:
            try:
                self.pulse = pulsectl.Pulse()
                default = self.pulse.sink_default_get()
                break
            except pulsectl.pulsectl.PulseIndexError:
                c.print_debug(
                    "Couldn't connect to pulse server, retrying...",
                    color='red', name='modules-volume')
                time.sleep(1)
                continue

        volume = round(default.volume.value_flat * 100)
        self.set_icon(default)
        self.text.set_label(f'{volume}%')

        self.make_widget()

        thread = threading.Thread(target=self.pulse_thread)
        thread.daemon = True
        thread.start()

        self.connect('destroy', self.destroy)

    def destroy(self, _):
        """ Clean up thread """
        self.alive = False

    def set_volume(self, slider, sink_key):
        """ Set volume for sink/source/sink-input """
        section, index = sink_key
        sink = self._get_sink_by_key(section, index)
        if sink:
            self.pulse.volume_set_all_chans(sink, slider.get_value()/100)

    def _get_sink_by_key(self, section, index):
        """ Get sink object by section and index """
        try:
            if section == 'Outputs':
                for sink in self.pulse.sink_list():
                    if sink.index == index:
                        return sink
            elif section == 'Inputs':
                for source in self.pulse.source_list():
                    if source.index == index:
                        return source
            elif section == 'Programs':
                for sink_input in self.pulse.sink_input_list():
                    if sink_input.index == index:
                        return sink_input
        except Exception:
            pass
        return None

    def toggle_mute(self, switch, state, sink_key):
        """ Toggle mute for a device """
        section, index = sink_key
        sink = self._get_sink_by_key(section, index)
        if sink:
            self.pulse.mute(sink, not state)  # Invert: ON=unmuted, OFF=muted
            # Immediate visual update
            GLib.idle_add(self.update_widget)

    def set_default(self, button, sink):
        """ Set default sink/source """
        self.pulse.default_set(sink)

    def _get_device_label(self, section, sink):
        """ Get display label for a device """
        if section == 'Programs':
            try:
                return sink.proplist['application.process.binary']
            except KeyError:
                return sink.name
        else:
            return sink.description

    def _create_device_row(self, section, sink):
        """ Create a row widget for a device """
        sink_box = c.box('v', spacing=10, style='inner-box')

        # Top row: mute button + label
        top_row = c.box('h', spacing=10)

        # Mute toggle switch (vertically centered)
        switch_container = c.box('v')
        switch_container.set_valign(Gtk.Align.CENTER)
        mute_switch = Gtk.Switch()
        mute_switch.set_active(not sink.mute)
        c.add_style(mute_switch, 'switch')
        mute_switch.set_tooltip_text("Toggle mute")
        sink_key = (section, sink.index)
        mute_switch.connect('state_set', self.toggle_mute, sink_key)
        switch_container.append(mute_switch)
        top_row.append(switch_container)

        # Device label
        label_text = self._get_device_label(section, sink)
        if section == 'Programs':
            sink_label = c.button(label_text, ha='start', style='minimal')
        else:
            sink_label = c.button(label_text, ha='start', style='minimal')
            sink_label.connect('clicked', self.set_default, sink)
        sink_label.set_hexpand(True)
        top_row.append(sink_label)

        sink_box.append(top_row)

        # Volume slider
        level = c.slider(round(sink.volume.value_flat * 100))
        level.connect('value-changed', self.set_volume, sink_key)
        if sink.mute:
            c.add_style(level, 'muted')
        sink_box.append(level)

        return sink_box, sink_label, level, mute_switch

    def handle_content_scroll(self, controller, dx, dy):
        """ Redirect scroll events to ScrolledWindow instead of letting sliders handle them """
        if not hasattr(self, 'scroll_window') or not self.scroll_window:
            return False

        vadjustment = self.scroll_window.get_vadjustment()
        hadjustment = self.scroll_window.get_hadjustment()

        # Vertical scrolling
        if dy != 0:
            current = vadjustment.get_value()
            step = vadjustment.get_step_increment()
            new_value = current + (dy * step)
            # Clamp to valid range
            lower = vadjustment.get_lower()
            upper = vadjustment.get_upper() - vadjustment.get_page_size()
            new_value = max(lower, min(new_value, upper))
            vadjustment.set_value(new_value)

        # Horizontal scrolling (if needed)
        if dx != 0:
            current = hadjustment.get_value()
            step = hadjustment.get_step_increment()
            new_value = current + (dx * step)
            # Clamp to valid range
            lower = hadjustment.get_lower()
            upper = hadjustment.get_upper() - hadjustment.get_page_size()
            new_value = max(lower, min(new_value, upper))
            hadjustment.set_value(new_value)

        return True  # Stop event propagation to prevent sliders from handling

    def _update_device_row(self, sink_key, sink):
        """ Update an existing device row """
        if sink_key not in self.device_widgets:
            return False

        row_box, label, slider, mute_switch = self.device_widgets[sink_key]
        section = sink_key[0]

        # Update mute switch state (without triggering signal)
        mute_switch.handler_block_by_func(self.toggle_mute)
        mute_switch.set_active(not sink.mute)
        mute_switch.handler_unblock_by_func(self.toggle_mute)

        # Update slider value (without triggering signal)
        slider.handler_block_by_func(self.set_volume)
        slider.set_value(round(sink.volume.value_flat * 100))
        slider.handler_unblock_by_func(self.set_volume)

        # Update muted style
        if sink.mute:
            c.add_style(slider, 'muted')
        else:
            c.del_style(slider, 'muted')

        # Update label text
        label_text = self._get_device_label(section, sink)
        label.set_label(label_text)

        return True

    def build_widget_structure(self):
        """ Build the persistent widget structure """
        main_box = c.box('v', style='widget', spacing=20)
        c.add_style(main_box, 'small-widget')
        main_box.append(c.label('Volume', style='heading'))

        # Content box that will be scrollable
        content_box = c.box('v', spacing=20)

        # Create section boxes for each type
        for name in ["Outputs", "Inputs", "Programs"]:
            section_box = c.box('v', spacing=10)
            section_box.append(c.label(name, style='title', ha='start'))
            devices_box = c.box('v', style='box')
            section_box.append(devices_box)
            self.section_boxes[name] = {
                'section': section_box,
                'devices': devices_box
            }
            content_box.append(section_box)

        # Add scroll redirection controller to content box
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        scroll_controller.connect('scroll', self.handle_content_scroll)
        content_box.add_controller(scroll_controller)

        # Wrap in scrolled window with fixed height
        scroll_window = c.scroll(height=500)
        scroll_window.set_child(content_box)

        # Store reference for scroll handler
        self.scroll_window = scroll_window

        main_box.append(scroll_window)

        return main_box

    def update_widget(self):
        """ Update widget contents in-place """
        if not self.widget_instance:
            return

        try:
            current_devices = {
                'Outputs': self.pulse.sink_list(),
                'Inputs': self.pulse.source_list(),
                'Programs': self.pulse.sink_input_list()
            }
        except Exception:
            return

        # Track which devices we've seen
        seen_keys = set()

        for section_name, device_list in current_devices.items():
            section_data = self.section_boxes.get(section_name)
            if not section_data:
                continue

            devices_box = section_data['devices']
            section_box = section_data['section']

            for sink in device_list:
                # Skip monitor devices
                if section_name != 'Programs' and 'Monitor of' in sink.description:
                    continue

                sink_key = (section_name, sink.index)
                seen_keys.add(sink_key)

                if sink_key in self.device_widgets:
                    # Update existing row
                    self._update_device_row(sink_key, sink)
                else:
                    # Create new row
                    row_box, label, slider, mute_btn = self._create_device_row(section_name, sink)
                    self.device_widgets[sink_key] = (row_box, label, slider, mute_btn)

                    # Add separator if not first device
                    existing_children = []
                    child = devices_box.get_first_child()
                    while child:
                        existing_children.append(child)
                        child = child.get_next_sibling()

                    if existing_children:
                        devices_box.append(c.sep('v'))

                    devices_box.append(row_box)

            # Show/hide section based on content
            has_visible_devices = any(
                k[0] == section_name and k in seen_keys
                for k in self.device_widgets.keys()
            )
            section_box.set_visible(has_visible_devices)

        # Remove departed devices
        departed_keys = set(self.device_widgets.keys()) - seen_keys
        for sink_key in departed_keys:
            row_box, label, slider, mute_switch = self.device_widgets[sink_key]
            section_name = sink_key[0]
            devices_box = self.section_boxes[section_name]['devices']

            # Get siblings to handle separator removal
            prev_sibling = row_box.get_prev_sibling()
            next_sibling = row_box.get_next_sibling()

            # Remove the row
            devices_box.remove(row_box)

            # Remove adjacent separator
            if prev_sibling and isinstance(prev_sibling, Gtk.Separator):
                devices_box.remove(prev_sibling)
            elif next_sibling and isinstance(next_sibling, Gtk.Separator):
                devices_box.remove(next_sibling)

            del self.device_widgets[sink_key]

    def pulse_listen(self):
        """ Listen for events """
        while True:
            try:
                with pulsectl.Pulse('event-listener') as pulse:
                    def print_events(ev):
                        raise pulsectl.PulseLoopStop
                    pulse.event_mask_set('sink', 'sink_input', 'source')
                    pulse.event_callback_set(print_events)
                    pulse.event_listen()
                    break
            except pulsectl.pulsectl.PulseDisconnected:
                c.print_debug(
                    'Reconnecting to pulse', name='volume-listener',
                    color='red')
                time.sleep(0.1)
                pass

    def pulse_thread(self):
        """ Seperate thread for listening for events """
        while self.alive:
            self.pulse_listen()
            GLib.idle_add(self.update)
        c.print_debug('thread killed')

    def handle_button_event(self, controller, event):
        """ Handle button events for mute toggle """
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:  # Right-click
            default = self.pulse.sink_default_get()
            if default:
                self.pulse.mute(default, not default.mute)
                self.update()
            return True  # Stop event propagation
        return False  # Allow other handlers

    def scroll(self, controller, dx, dy):
        """ Scroll action for volume control """
        default = self.pulse.sink_default_get()

        # Handle vertical scrolling (dy)
        if dy > 0:  # Scroll down = volume down
            self.pulse.volume_change_all_chans(default, -0.01)
        elif dy < 0:  # Scroll up = volume up
            if default.volume.value_flat < 1:
                self.pulse.volume_change_all_chans(default, 0.01)
            else:
                self.pulse.volume_set_all_chans(default, 1)

        # Handle horizontal scrolling (dx) - could switch outputs or adjust balance
        # For now, ignore horizontal scrolling

    def update(self):
        """ Update """
        while True:
            try:
                default = self.pulse.sink_default_get()
                break
            except (
                    pulsectl.pulsectl.PulseIndexError,
                    pulsectl.pulsectl.PulseOperationFailed
            ):
                c.print_debug(
                    'Reconnecting to pulse', name='volume-updater',
                    color='red')
                time.sleep(0.1)
                self.pulse = pulsectl.Pulse()
                pass
        volume = round(default.volume.value_flat * 100)
        self.text.set_label(f"{volume}%")

        self.set_icon(default)

        # Always update widget contents (live updates)
        self.update_widget()

    def set_icon(self, sink):
        """ Set icon for module """
        if sink.mute:
            self.icon.set_label('')
            return
        found = False
        for name, icon in self.icons.items():
            if name.lower() in sink.name.lower():
                self.icon.set_label(icon)
                found = True
        if not found:
            self.icon.set_label('')

    def make_widget(self):
        """ Make widget for module """
        # Reset stored references
        self.section_boxes = {}
        self.device_widgets = {}

        widget = c.Widget()
        widget.box.append(self.build_widget_structure())
        widget.draw()
        self.widget_instance = widget
        self.set_popover(widget)

        # Populate initial content
        self.update_widget()


def module(bar, config=None):
    """ PulseAudio module """
    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    module = Volume(bar, config)

    return module
