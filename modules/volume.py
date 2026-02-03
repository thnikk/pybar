#!/usr/bin/python3 -u
"""
Description: Pulse module refactored for unified state
Author: thnikk
"""
import common as c
import pulsectl
import threading
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Pango  # noqa


class Volume(c.BaseModule):
    SCHEMA = {
        'icons': {
            'type': 'dict',
            'default': {},
            'label': 'Custom Icons',
            'description': 'Custom icons to use for devices (name: icon)'
        }
    }

    def get_volume_data(self, pulse, blacklist=None):
        """ Get current pulse data """
        if blacklist is None:
            blacklist = {}
        try:
            default_sink = pulse.sink_default_get()
            sinks = pulse.sink_list()
            sources = pulse.source_list()
            sink_inputs = pulse.sink_input_list()

            # Filter blacklisted devices
            sink_bl = blacklist.get('sinks', [])
            source_bl = blacklist.get('sources', [])

            def is_allowed(device, blocklist):
                if not blocklist:
                    return True
                name = getattr(device, 'name', '') or ''
                desc = getattr(device, 'description', '') or ''
                return not any(b in name or b in desc for b in blocklist)

            sinks = [s for s in sinks if is_allowed(s, sink_bl)]
            sources = [s for s in sources if is_allowed(s, source_bl)]

            def serialize_device(d):
                # For programs (sink inputs), we often need to look at proplist
                # for a name
                name = getattr(d, 'name', None)
                description = getattr(d, 'description', None)
                proplist = dict(d.proplist) if hasattr(d, 'proplist') else {}

                if not description:
                    description = proplist.get(
                        'application.name',
                        proplist.get('media.name', name or 'Unknown'))
                if not name:
                    name = proplist.get(
                        'application.process.binary', description)

                return {
                    'index': d.index,
                    'name': name,
                    'description': description,
                    'volume': d.volume.value_flat,
                    'mute': bool(d.mute),
                    'proplist': proplist
                }

            return {
                'default_sink': serialize_device(default_sink)
                if default_sink else None,
                'outputs': [serialize_device(s) for s in sinks],
                'inputs': [serialize_device(s) for s in sources],
                'programs': [serialize_device(s) for s in sink_inputs]
            }
        except Exception as e:
            c.print_debug(f"Error fetching volume data: {e}", color='red')
            return None

    def run_worker(self):
        """ Background worker for volume """
        blacklist = self.config.get('blacklist', {})
        while True:
            try:
                with pulsectl.Pulse('pybar-volume-worker') as pulse:
                    def update():
                        try:
                            data = self.get_volume_data(pulse, blacklist)
                            if data:
                                c.state_manager.update(self.name, data)
                        except Exception as e:
                            c.print_debug(
                                f"Volume update failed: {e}", color='red')

                    # Initial update
                    update()

                    def event_callback(ev):
                        raise pulsectl.PulseLoopStop

                    pulse.event_mask_set('sink', 'sink_input', 'source')
                    pulse.event_callback_set(event_callback)

                    while True:
                        pulse.event_listen()
                        update()
            except Exception as e:
                c.print_debug(f"Volume worker error: {e}", color='red')
                time.sleep(5)

    def handle_scroll(self, widget, dx, dy):
        """ Handle scroll on module """
        with pulsectl.Pulse('volume-action') as pulse:
            default = pulse.sink_default_get()
            if dy > 0:
                pulse.volume_change_all_chans(default, -0.01)
            elif dy < 0:
                if default.volume.value_flat < 1:
                    pulse.volume_change_all_chans(default, 0.01)
                else:
                    pulse.volume_set_all_chans(default, 1)

    def toggle_default_mute(self):
        """ Toggle default sink mute """
        with pulsectl.Pulse('volume-action') as pulse:
            default = pulse.sink_default_get()
            if default:
                pulse.mute(default, not default.mute)

    def cycle_output_device(self, blacklist=None):
        """ Cycle through output devices """
        if blacklist is None:
            blacklist = {}
        with pulsectl.Pulse('volume-action') as pulse:
            sinks = pulse.sink_list()
            if not sinks:
                return

            current = pulse.sink_default_get()
            if not current:
                return

            # Filter out monitors and blacklisted devices
            sink_bl = blacklist.get('sinks', [])
            valid_sinks = []
            for s in sinks:
                desc = getattr(s, 'description', '') or ''
                name = getattr(s, 'name', '') or ''
                if 'Monitor of' in desc:
                    continue
                if any(b in desc or b in name for b in sink_bl):
                    continue
                valid_sinks.append(s)

            if not valid_sinks:
                return

            # Find current index
            idx = -1
            for i, s in enumerate(valid_sinks):
                if s.name == current.name:
                    idx = i
                    break

            # Set next
            next_sink = valid_sinks[(idx + 1) % len(valid_sinks)]
            pulse.default_set(next_sink)

    def toggle_mute(self, section, index, state):
        with pulsectl.Pulse('volume-action') as pulse:
            dev = None
            if section == 'Outputs':
                dev = next((s for s in pulse.sink_list()
                           if s.index == index), None)
            elif section == 'Inputs':
                dev = next((s for s in pulse.source_list()
                           if s.index == index), None)
            elif section == 'Programs':
                dev = next((s for s in pulse.sink_input_list()
                           if s.index == index), None)

            if dev:
                pulse.mute(dev, not state)
        return True

    def set_dev_volume(self, section, index, value):
        with pulsectl.Pulse('volume-action') as pulse:
            dev = None
            if section == 'Outputs':
                dev = next((s for s in pulse.sink_list()
                           if s.index == index), None)
            elif section == 'Inputs':
                dev = next((s for s in pulse.source_list()
                           if s.index == index), None)
            elif section == 'Programs':
                dev = next((s for s in pulse.sink_input_list()
                           if s.index == index), None)

            if dev:
                pulse.volume_set_all_chans(dev, value / 100)

    def set_default(self, section, name):
        with pulsectl.Pulse('volume-action') as pulse:
            if section == 'Outputs':
                sink = next(
                    (s for s in pulse.sink_list() if s.name == name), None)
                if sink:
                    pulse.default_set(sink)
            elif section == 'Inputs':
                source = next((s for s in pulse.source_list()
                              if s.name == name), None)
                if source:
                    pulse.default_set(source)

    def build_device_row(self, section, device):
        """ Build a row for a single pulse device """
        row = c.box('v', spacing=5, style='inner-box')

        top = c.box('h', spacing=10)

        # Mute switch
        mute_switch = Gtk.Switch()
        mute_switch.set_active(not device.get('mute', False))
        mute_switch.set_valign(Gtk.Align.CENTER)
        mute_switch.connect(
            'state-set', lambda _s, state: self.toggle_mute(
                section, device['index'], state))
        top.append(mute_switch)

        # Label
        label_text = device.get('proplist', {}).get(
            'application.process.binary', device.get('description', 'Unknown'))
        btn = c.button(label_text, ha='start', style='minimal', length=25)
        if section != 'Programs':
            btn.connect(
                'clicked', lambda _b: self.set_default(
                    section, device['name']))
        btn.set_hexpand(True)
        top.append(btn)

        row.append(top)

        # Volume slider - disable scroll to allow container to scroll
        slider = c.slider(round(device.get('volume', 0) * 100), scrollable=False)
        slider.connect(
            'value-changed', lambda s: self.set_dev_volume(
                section, device['index'], s.get_value()))
        if device.get('mute'):
            c.add_style(slider, 'muted')
        row.append(slider)

        return row

    def build_popover_content(self, data):
        """ Build popover for volume """
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Volume', style='heading'))

        content_box = c.box('v', spacing=20)

        sections = [
            ('Outputs', data.get('outputs', [])),
            ('Inputs', data.get('inputs', [])),
            ('Programs', data.get('programs', []))
        ]

        for name, devices in sections:
            if not devices:
                continue

            section_box = c.box('v', spacing=10)
            section_box.append(c.label(name, style='title', ha='start'))
            devices_box = c.box('v', style='box')

            for i, device in enumerate(devices):
                # Skip monitors
                if name != 'Programs' and 'Monitor of' in device.get(
                        'description', ''):
                    continue

                dev_row = self.build_device_row(name, device)
                devices_box.append(dev_row)
                if i != len(devices) - 1:
                    devices_box.append(c.sep('h'))

            section_box.append(devices_box)
            content_box.append(section_box)

        scroll = c.scroll(height=400, style='scroll')
        scroll.set_overflow(Gtk.Overflow.HIDDEN)
        scroll.set_child(content_box)
        main_box.append(scroll)
        return main_box

    def create_widget(self, bar):
        """ Create volume module widget """
        m = c.Module()
        m.set_position(bar.position)
        c.add_style(m, 'module-fixed')
        m.icons = self.config.get('icons', {})
        m.set_label('...')
        m.set_icon('')

        # Add scroll controller
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_controller.connect(
            'scroll', lambda _c, dx, dy: self.handle_scroll(m, dx, dy))
        m.add_controller(scroll_controller)

        # Add right-click for mute
        click_controller = Gtk.GestureClick.new()
        click_controller.set_button(3)  # Right click
        click_controller.connect(
            'released', lambda _c, _n, _x, _y: self.toggle_default_mute())
        m.add_controller(click_controller)

        # Add middle-click for cycling outputs
        middle_click_controller = Gtk.GestureClick.new()
        middle_click_controller.set_button(2)  # Middle click
        middle_click_controller.connect(
            'released', lambda _c, _n, _x, _y: self.cycle_output_device(
                self.config.get('blacklist', {})))
        m.add_controller(middle_click_controller)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Update volume UI """
        default = data.get('default_sink')
        widget.set_visible(True)
        if not default:
            widget.set_label('ERR')
            widget.set_icon('')
            return

        volume = round(default['volume'] * 100)
        widget.set_label(f'{volume}%')

        # Set icon
        if default['mute']:
            widget.set_icon('')
        else:
            found = False
            for name, icon in widget.icons.items():
                if name.lower() in default['name'].lower():
                    widget.set_icon(icon)
                    found = True
                    break
            if not found:
                widget.set_icon('')

        # Update popover content
        if not widget.get_active():
            # Optimization: Don't rebuild popover if data hasn't changed
            compare_data = data.copy()
            compare_data.pop('timestamp', None)
            
            if getattr(widget, 'last_popover_data', None) == compare_data:
                return

            widget.last_popover_data = compare_data
            widget.set_widget(self.build_popover_content(data))


module_map = {
    'volume': Volume
}
