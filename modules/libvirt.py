#!/usr/bin/python3 -u
"""
Description: VM module refactored for unified state
Author: thnikk
"""
import subprocess
import weakref
import threading
import time
import gi
import common as c
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib  # noqa


class VM(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 10,
            'label': 'Update Interval',
            'description': 'How often to check for running VMs (seconds)',
            'min': 5,
            'max': 60
        },
        'hide_when_inactive': {
            'type': 'boolean',
            'default': False,
            'label': 'Hide when inactive',
            'description': 'Hide the module when no VMs are running'
        },
        'hide_count_when_zero': {
            'type': 'boolean',
            'default': False,
            'label': 'Hide count when zero',
            'description': 'Hide the number of running VMs when none are active'
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.busy_actions = set()

    def fetch_data(self):
        try:
            res = subprocess.run(
                ["virsh", "list", "--all"],
                capture_output=True, text=True, check=True
            )
            lines = res.stdout.strip().splitlines()
            running = []
            inactive = []
            for line in lines[2:]:  # Skip header
                parts = line.split()
                if not parts:
                    continue
                # parts[0] is Id, parts[1] is Name, parts[2:] is State
                name = parts[1]
                state = " ".join(parts[2:])
                if state == "running":
                    running.append(name)
                else:
                    inactive.append(name)

            return {
                "running": running,
                "inactive": inactive,
                "busy": list(self.busy_actions),
                "text": f" {len(running)}"
            }
        except Exception:
            return {}

    def vm_action(self, _btn, action, name):
        busy_key = (name, action)
        if busy_key in self.busy_actions:
            return

        def run_action():
            try:
                subprocess.run(
                    ["virsh", action, name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                # Poll for state change (up to 10s) to keep spinner accurate
                target = "running" if action == "start" else "shut off"
                for _ in range(20):
                    time.sleep(0.5)
                    res = subprocess.run(
                        ["virsh", "domstate", name],
                        capture_output=True, text=True
                    )
                    if res.stdout.strip() == target:
                        break
            except Exception as e:
                c.print_debug(f"Failed to {action} VM {name}: {e}", color='red')
            finally:
                self.busy_actions.discard(busy_key)
                import module
                GLib.idle_add(module.force_update, self.name)

        self.busy_actions.add(busy_key)
        import module
        module.force_update(self.name)
        threading.Thread(target=run_action, daemon=True).start()

    def build_section(self, data, title, domains, is_running=False):
        if not domains:
            return None

        # Convert busy list items to tuples for consistent comparison
        busy_list = [tuple(b) for b in data.get('busy', [])]
        box = c.box('v', spacing=10)
        box.append(c.label(f"{title} ({len(domains)})", style='title', ha='start'))

        ibox = c.box('v')
        for i, d in enumerate(domains):
            item_box = c.box('h', spacing=10, style='inner-box')
            item_box.append(c.label(d, ha='start', he=True))

            actions = c.box('h', spacing=10)

            def get_action_widget(action_name, icon, tooltip, name=d):
                if (name, action_name) in busy_list:
                    s = Gtk.Spinner()
                    s.start()
                    s.set_size_request(24, 24)
                    return s
                btn = c.button(icon, style='minimal')
                btn.connect('clicked', self.vm_action, action_name, name)
                c.set_hover_popover(btn, tooltip)
                return btn

            if is_running:
                actions.append(get_action_widget('shutdown', '', 'Shutdown'))
                actions.append(get_action_widget('destroy', '', 'Force Stop'))
            else:
                actions.append(get_action_widget('start', '', 'Start'))

            item_box.append(actions)
            ibox.append(item_box)
            if i < len(domains) - 1:
                ibox.append(c.sep('h'))

        # Use scroll box if list is long
        large = len(domains) > 5
        vsgb = c.VScrollGradientBox(
            ibox, gradient_size=60,
            max_height=180 if large else None)
        c.add_style(vsgb, 'box')
        box.append(vsgb)
        return box

    def launch_virt_manager(self, _btn):
        subprocess.Popen(
            ["virt-manager"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    def build_popover(self, data):
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Virtual Machines', style='heading'))

        content_box = c.box('v', spacing=20)

        running_section = self.build_section(
            data, "Running", data.get('running', []), is_running=True)
        if running_section:
            content_box.append(running_section)

        inactive_section = self.build_section(
            data, "Inactive", data.get('inactive', []), is_running=False)
        if inactive_section:
            content_box.append(inactive_section)

        if not running_section and not inactive_section:
            content_box.append(c.label("No VMs found", style='dim-label'))

        main_box.append(content_box)

        # Launch virt-manager button
        vm_btn = c.button(' Open Virt-Manager', style='normal')
        vm_btn.connect('clicked', self.launch_virt_manager)
        main_box.append(vm_btn)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return

        running_count = len(data.get('running', []))
        hide_count = self.config.get('hide_count_when_zero', False)

        if running_count == 0 and hide_count:
            widget.set_label('')
        else:
            widget.set_label(data.get('text', ' 0'))

        # Visibility logic
        hide_inactive = self.config.get('hide_when_inactive', False)
        widget.set_visible(not hide_inactive or running_count > 0)

        # Optimization: Don't rebuild popover if data hasn't changed
        compare_data = data.copy()
        compare_data.pop('timestamp', None)
        if getattr(widget, 'last_popover_data', None) == compare_data:
            return

        widget.last_popover_data = compare_data

        if widget.get_active():
            popover = widget.get_popover()
            if popover and hasattr(popover, 'box'):
                # Clear and rebuild existing popover content
                while (child := popover.box.get_first_child()):
                    popover.box.remove(child)
                popover.box.append(self.build_popover(data))
        else:
            widget.set_widget(self.build_popover(data))



module_map = {
    'libvirt': VM
}
alias_map = {
    'vm': VM
}
