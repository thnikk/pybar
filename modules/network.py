#!/usr/bin/python3 -u
"""
Description: Network module refactored for unified state
Author: thnikk
"""
from subprocess import run
import common as c
import gi
import socket
import threading
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib  # noqa


class Network(c.BaseModule):
    def get_devices(self):
        """ Get active NetworkManager connections """
        try:
            res = run(
                ['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'd'],
                check=True, capture_output=True).stdout.decode('utf-8')
            devices = []
            for line in res.splitlines():
                parts = line.split(':')
                if len(parts) >= 4:
                    dev_type = parts[1]
                    if dev_type in ['loopback', 'bridge', 'wifi-p2p']:
                        continue
                    dev = {
                        'GENERAL.DEVICE': parts[0],
                        'GENERAL.TYPE': dev_type,
                        'GENERAL.STATE': parts[2],
                        'GENERAL.CONNECTION': parts[3]
                    }
                    devices.append(dev)

            # Also get IPs for connected devices
            res_ip = run(
                ['nmcli', '-t', '-f', 'GENERAL.DEVICE,IP4.ADDRESS', 'd', 'show'],
                check=True, capture_output=True).stdout.decode('utf-8')
            curr_dev = None
            for line in res_ip.splitlines():
                if 'GENERAL.DEVICE:' in line:
                    curr_dev = line.split(':', 1)[1]
                elif 'IP4.ADDRESS[1]' in line and curr_dev:
                    ip = line.split(':', 1)[1]
                    for d in devices:
                        if d['GENERAL.DEVICE'] == curr_dev:
                            d['IP4.ADDRESS[1]'] = ip
                            break
            return devices
        except Exception as e:
            c.print_debug(f"Error fetching network devices: {e}", color='red')
            return []

    def check_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            pass
        return False

    def get_remembered_ssids(self):
        """ Get SSIDs of saved Wi-Fi connections """
        try:
            res = run(
                ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                check=True, capture_output=True
            ).stdout.decode('utf-8')
            ssids = []
            for line in res.splitlines():
                parts = line.split(':')
                if len(parts) == 2 and parts[1] == '802-11-wireless':
                    ssids.append(parts[0])
            return ssids
        except Exception:
            return []

    def get_wifi_networks(self):
        """ Scan for available Wi-Fi networks """
        try:
            res = run(
                ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BARS,IN-USE',
                    'dev', 'wifi', 'list'],
                check=True, capture_output=True
            ).stdout.decode('utf-8')

            remembered = self.get_remembered_ssids()
            networks = []
            for line in res.splitlines():
                parts = line.rsplit(':', 4)
                if len(parts) == 5 and parts[0]:
                    ssid = parts[0]
                    networks.append({
                        'SSID': ssid,
                        'SIGNAL': parts[1],
                        'SECURITY': parts[2],
                        'BARS': parts[3],
                        'IN-USE': parts[4] == '*',
                        'REMEMBERED': ssid in remembered
                    })
            # Sort by signal strength
            networks.sort(key=lambda x: int(
                x['SIGNAL']) if x['SIGNAL'].isdigit() else 0, reverse=True)
            return networks
        except Exception as e:
            c.print_debug(f"Error scanning Wi-Fi: {e}", color='red')
            return []

    def fetch_data(self):
        """ Fetch network data """
        has_internet = self.check_internet()
        devices = self.get_devices()
        wifi_networks = self.get_wifi_networks()
        icons = {"ethernet": "", "wifi": "", "wifi-p2p": ""}
        connection_type = None
        connection_ip = None

        for device in devices:
            state = device.get('GENERAL.STATE', '').lower()
            if 'connected' in state:
                connection_type = device.get('GENERAL.TYPE')
                connection_ip = device.get('IP4.ADDRESS[1]', '').split(
                    '/')[0] if 'IP4.ADDRESS[1]' in device else None
                if connection_type in icons:
                    break

        always_show = self.config.get('always_show', True)

        if connection_type:
            text = icons.get(connection_type, "") if always_show else ""
            tooltip = f"{connection_type}\n{connection_ip}"
        elif has_internet:
            text = "" if always_show else ""
            tooltip = "Connected (Unknown device)"
        else:
            text = ""
            tooltip = "No connection"

        return {
            "text": text,
            "tooltip": tooltip,
            "devices": devices,
            "wifi_networks": wifi_networks,
            "connection_type": connection_type,
        }

    def get_wifi_device(self):
        """ Get the name of the Wi-Fi device """
        try:
            res = run(['nmcli', '-t', '-f', 'DEVICE,TYPE', 'd'],
                      check=True, capture_output=True).stdout.decode('utf-8')
            for line in res.splitlines():
                parts = line.split(':')
                if len(parts) == 2 and parts[1] == 'wifi':
                    return parts[0]
        except Exception:
            pass
        return None

    def wifi_action(
            self, ssid, password=None, disconnect=False, forget=False,
            button=None):
        """ Connect, disconnect, or forget Wi-Fi in background """
        def run_nmcli():
            try:
                wifi_dev = self.get_wifi_device()
                if forget:
                    if button:
                        GLib.idle_add(button.set_label, "Forgetting...")
                    if wifi_dev:
                        res = run(
                            ['nmcli', '-t', '-f', 'CONNECTION', 'd', 'show',
                                wifi_dev], capture_output=True, text=True)
                        if ssid in res.stdout:
                            run(
                                ['nmcli', 'device', 'disconnect', wifi_dev],
                                check=False)
                    run(['nmcli', 'connection', 'delete', ssid], check=True)
                elif disconnect:
                    if button:
                        GLib.idle_add(button.set_label, "Disconnecting...")
                    if wifi_dev:
                        run(
                            ['nmcli', 'device', 'disconnect', wifi_dev],
                            check=True)
                    else:
                        run(['nmcli', 'connection', 'down', ssid], check=True)
                else:
                    if button:
                        GLib.idle_add(button.set_label, "Connecting...")

                    cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
                    if password:
                        cmd += ['password', password]

                    result = run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        c.print_debug(
                            f"Wi-Fi connection failed: {result.stderr}",
                            color='red')
                        if button:
                            GLib.idle_add(button.set_label, "Failed")
                    else:
                        if button:
                            GLib.idle_add(button.set_label, "Connected")

                # Real-time update
                new_data = self.fetch_data()
                c.state_manager.update(self.name, new_data)

            except Exception as e:
                c.print_debug(f"Wi-Fi action failed: {e}", color='red')
                if button:
                    GLib.idle_add(button.set_label, "Error")

        threading.Thread(target=run_nmcli, daemon=True).start()

    def toggle_wifi_details(self, _btn, details_box, indicator):
        visible = not details_box.get_visible()
        details_box.set_visible(visible)
        indicator.set_text('' if visible else '')

    def build_popover(self, widget, data):
        """ Build popover for network """
        widget.popover_widgets = {}

        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Network', style='heading'))

        # Active Connections
        names = {
            'GENERAL.DEVICE': 'Device', "GENERAL.CONNECTION": "SSID",
            'IP4.ADDRESS[1]': 'IP'
        }

        connected_any = False
        for device in data.get('devices', []):
            state = device.get('GENERAL.STATE', '').lower()
            if 'connected' not in state:
                continue

            connected_any = True
            dev_name = device.get('GENERAL.DEVICE', 'unknown')
            network_box = c.box('v', spacing=10)
            network_box.append(
                c.label(device.get(
                    'GENERAL.TYPE', 'unknown'), style='title', ha='start'))
            device_box = c.box('v', style='box')

            widget.popover_widgets[dev_name] = {}

            items = []
            for long, short in names.items():
                if short == 'SSID' and device.get('GENERAL.TYPE') != 'wifi':
                    continue
                if long in device:
                    items.append((short, device[long], long))

            for i, (short, val, long) in enumerate(items):
                line = c.box('h', style='inner-box')
                line.append(c.label(short))
                val_label = c.label(val, ha='end', he=True)
                line.append(val_label)
                device_box.append(line)

                if long == 'IP4.ADDRESS[1]':
                    widget.popover_widgets[dev_name]['ip_label'] = val_label

                if i != len(items) - 1:
                    device_box.append(c.sep('h'))

            network_box.append(device_box)
            main_box.append(network_box)

        if not connected_any:
            main_box.append(c.label("No active connections", style='gray'))

        # Available networks
        if data.get('wifi_networks'):
            main_box.append(c.sep('h'))
            wifi_section = c.box('v', spacing=10)
            wifi_section.append(
                c.label('Available networks', style='title', ha='start'))

            scroll = c.scroll(height=300, style='scroll')
            wifi_list = c.box('v', style='box')

            for i, net in enumerate(data['wifi_networks']):
                item_con = c.box('v')

                # SSID Row
                ssid_btn = c.button()
                c.add_style(ssid_btn, ['minimal', 'inner-box'])

                ssid_content = c.box('h', spacing=10)
                indicator = c.label('', style='gray')
                ssid_label = c.label(net['SSID'], ha='start', he=True)
                signal_label = c.label(
                    f"{net['SIGNAL']}%", style='gray', ha='end')

                ssid_content.append(indicator)
                ssid_content.append(ssid_label)
                ssid_content.append(signal_label)
                ssid_btn.set_child(ssid_content)

                # Details Box
                details_box = c.box('v')
                details_box.set_visible(False)
                c.add_style(details_box, 'expanded-status')
                details_box.append(c.sep('h'))

                details_inner = c.box('v', spacing=10, style='inner-box')

                # Info line
                info_line = c.box('h')
                info_line.append(c.label("Security", style='gray'))
                info_line.append(c.label(net['SECURITY'], ha='end', he=True))
                details_inner.append(info_line)

                # Actions
                if net['IN-USE'] or net['REMEMBERED']:
                    # Grouped buttons [ Action | Forget ]
                    btn_box = c.box('h', spacing=0)
                    btn_box.set_homogeneous(True)

                    if net['IN-USE']:
                        action_btn = c.button(
                            "Disconnect", style='red', ha='fill')
                        action_btn.connect(
                            'clicked', lambda b, s=net['SSID']: self.wifi_action(
                                s, disconnect=True, button=b))
                    else:
                        action_btn = c.button(
                            "Connect", style='blue', ha='fill')
                        action_btn.connect(
                            'clicked', lambda b, s=net['SSID']: self.wifi_action(
                                s, button=b))

                    c.add_style(action_btn, 'group-button')
                    action_btn.set_hexpand(True)
                    btn_box.append(action_btn)

                    forget_btn = c.button("Forget", style='normal', ha='fill')
                    c.add_style(forget_btn, 'group-button')
                    forget_btn.set_hexpand(True)
                    forget_btn.connect(
                        'clicked', lambda b, s=net['SSID']: self.wifi_action(
                            s, forget=True, button=b))
                    btn_box.append(forget_btn)

                    details_inner.append(btn_box)
                else:
                    # Password and Connect
                    pass_entry = Gtk.Entry()
                    pass_entry.set_placeholder_text('Password...')
                    pass_entry.set_visibility(False)
                    pass_entry.set_hexpand(True)
                    c.add_style(pass_entry, 'normal')

                    connect_btn = c.button("Connect", style='blue', ha='fill')
                    connect_btn.set_hexpand(True)

                    def on_connect(b, s=net['SSID'], e=pass_entry):
                        self.wifi_action(s, e.get_text(), button=b)

                    connect_btn.connect('clicked', on_connect)
                    pass_entry.connect(
                        'activate', lambda _e: on_connect(connect_btn))

                    details_inner.append(pass_entry)
                    details_inner.append(connect_btn)

                details_box.append(details_inner)

                ssid_btn.connect(
                    'clicked', self.toggle_wifi_details,
                    details_box, indicator)

                item_con.append(ssid_btn)
                item_con.append(details_box)
                wifi_list.append(item_con)

                if i < len(data['wifi_networks']) - 1:
                    wifi_list.append(c.sep('h'))

            scroll.set_child(wifi_list)
            wifi_section.append(scroll)
            main_box.append(wifi_section)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_label('...')
        m.popover_widgets = {}

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))
        widget.set_tooltip_text(data.get('tooltip', ''))

        if not widget.get_active():
            widget.set_widget(self.build_popover(widget, data))
        else:
            # Live update IP labels if they exist
            devices = {d['GENERAL.DEVICE']: d for d in data.get('devices', [])}
            for dev_name, widgets in getattr(
                widget, 'popover_widgets', {}
            ).items():
                if dev_name in devices:
                    dev = devices[dev_name]
                    if 'ip_label' in widgets:
                        ip = dev.get('IP4.ADDRESS[1]', 'None')
                        widgets['ip_label'].set_text(ip)


module_map = {
    'network': Network
}
