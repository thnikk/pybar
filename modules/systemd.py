#!/usr/bin/python3 -u
"""
Description: Systemd module refactored for unified state
Author: thnikk
"""
import re
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Systemd(c.BaseModule):
    SCHEMA = {
        'blacklist': {
            'type': 'list',
            'item_type': 'string',
            'default': [],
            'label': 'Blacklist',
            'description': 'Service prefixes to ignore'
        },
        'interval': {
            'type': 'integer',
            'default': 60,
            'label': 'Update Interval',
            'description': 'How often to check for failed services (seconds)',
            'min': 10,
            'max': 600
        }
    }

    def get_failed(self, user=False):
        cmd = ['systemctl', '--failed', '--legend=no']
        if user:
            cmd.insert(1, '--user')
        try:
            res = run(cmd, check=True, capture_output=True).stdout.decode(
                'utf-8').strip().splitlines()
            return [line.split()[1] for line in res if len(line.split()) > 1]
        except Exception:
            return []

    def fetch_data(self):
        blacklist = self.config.get('blacklist', [])

        failed_sys = [
            s for s in self.get_failed()
            if s.split('.')[0] not in blacklist]
        failed_user = [
            s for s in self.get_failed(user=True)
            if s.split('.')[0] not in blacklist]

        total = len(failed_sys) + len(failed_user)
        return {
            "text": f' {total}' if total else "",
            "failed_system": failed_sys,
            "failed_user": failed_user
        }

    def get_status(self, service, user=False):
        # Mapping systemd results to human-friendly strings
        result_map = {
            "exit-code": "Program quit with an error",
            "timeout": "Took too long to respond",
            "resources": "Out of memory or resource limit",
            "core-dump": "Program crashed",
            "start-limit-hit": "Failed too often (start limit)",
            "signal": "Program was killed by a signal",
            "protocol": "Communication error",
        }

        show_cmd = [
            'systemctl', 'show', service, '-p',
            'Description,Result,StateChangeTimestamp,'
            'ExecMainStatus,ExecMainCode']
        if user:
            show_cmd.insert(1, '--user')

        try:
            # Fetch properties
            res = run(
                show_cmd, capture_output=True).stdout.decode('utf-8').strip()
            props = dict(line.split('=', 1)
                         for line in res.splitlines() if '=' in line)

            desc = props.get('Description', 'No description')
            result = props.get('Result', 'unknown')
            reason = result_map.get(result, result)
            timestamp = props.get('StateChangeTimestamp', 'unknown')
            exit_code = props.get('ExecMainStatus', '0')

            # Format the summary
            summary = [
                f"<b>Description:</b> {desc}",
                f"<b>Failed at:</b> {timestamp}",
                f"<b>Reason:</b> {reason} (status={exit_code})"
            ]

            # Special handling for coredumps to find what process crashed
            if service.startswith('systemd-coredump@'):
                log_cmd = ['systemctl', 'status', service, '-l', '--no-pager']
                if user:
                    log_cmd.insert(1, '--user')
                status_output = run(
                    log_cmd, capture_output=True).stdout.decode('utf-8')
                pid_match = re.search(
                    r'Started Process Core Dump \(PID (\d+)', status_output)
                if pid_match:
                    coredump_pid = pid_match.group(1)
                    journal_cmd = [
                        'journalctl', f'_PID={coredump_pid}',
                        '--no-pager', '-b']
                    journal_res = run(
                        journal_cmd, capture_output=True).stdout.decode(
                            'utf-8')
                    crash_match = re.search(
                        r'Process \d+ \(([^)]+)\)', journal_res)
                    if crash_match:
                        summary.insert(
                            1,
                            f"<b>Crashed Process:</b> {crash_match.group(1)}")

            # Fetch logs
            log_cmd = ['systemctl', 'status', service, '-n', '3', '--no-pager']
            if user:
                log_cmd.insert(1, '--user')
            logs = run(log_cmd, capture_output=True).stdout.decode(
                'utf-8').splitlines()

            # Filter for actual log lines
            months = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            actual_logs = [log.strip() for log in logs if any(
                log.strip().startswith(month) for month in months)]

            if actual_logs:
                summary.append("\n<b>Recent Logs:</b>")
                summary.extend(actual_logs[:3])

            return "\n".join(summary)
        except Exception as e:
            return f"Failed to fetch details: {e}"

    def toggle_status(
            self, _btn, status_box, status_label, indicator, service, is_user):
        visible = not status_box.get_visible()
        if visible:
            status = self.get_status(service, is_user)
            status_label.set_markup(status)
            indicator.set_text('')
        else:
            indicator.set_text('')
        status_box.set_visible(visible)

    def reset_failed(self, _btn, user=False):
        cmd = ['systemctl', 'reset-failed']
        if user:
            cmd.insert(1, '--user')
        try:
            run(cmd, check=True)
        except Exception:
            pass

    def build_popover(self, data):
        try:
            main_box = c.box('v', spacing=20, style='small-widget')
            main_box.append(c.label('Failed Services', style='heading'))

            scroll_box = c.scroll(height=400, style='scroll')
            scroll_box.set_hexpand(True)
            scroll_box.set_vexpand(False)

            content_box = c.box('v', spacing=20)

            sections = [("System", data['failed_system'], False),
                        ("User", data['failed_user'], True)]
            for name, failed, is_user in sections:
                if not failed:
                    continue
                sec_box = c.box('v', spacing=10)

                header_box = c.box('h', spacing=10)
                header_box.append(c.label(name, style='title', ha='start'))

                reset_btn = c.button(' Reset', style='orange', ha='end')
                reset_btn.set_hexpand(True)
                reset_btn.connect('clicked', self.reset_failed, is_user)
                header_box.append(reset_btn)

                sec_box.append(header_box)

                items_box = c.box('v', style='box')
                for i, s in enumerate(failed):
                    item_con = c.box('v')

                    btn = c.button()
                    c.add_style(btn, ['minimal', 'inner-box'])

                    btn_content = c.box('h', spacing=10)
                    indicator = c.label('', style='gray')
                    btn_label = c.label(s, ha='start', he=True)
                    btn_content.append(indicator)
                    btn_content.append(btn_label)
                    btn.set_child(btn_content)

                    # Container for details
                    status_box = c.box('v')
                    status_box.set_visible(False)
                    c.add_style(status_box, 'expanded-status')

                    status_box.append(c.sep('h'))

                    text_wrapper = c.box('v', style='inner-box')
                    status_label = c.label(
                        "", style='small', ha='start', wrap=50)
                    c.add_style(status_label, 'gray')
                    text_wrapper.append(status_label)
                    status_box.append(text_wrapper)

                    btn.connect(
                        'clicked', self.toggle_status, status_box,
                        status_label, indicator, s, is_user)

                    item_con.append(btn)
                    item_con.append(status_box)

                    items_box.append(item_con)
                    if i < len(failed) - 1:
                        items_box.append(c.sep('h'))

                sec_box.append(items_box)
                content_box.append(sec_box)

            scroll_box.set_child(content_box)
            main_box.append(scroll_box)

            return main_box
        except Exception as e:
            c.print_debug(f"Error building systemd popover: {e}", color='red')
            return c.box('v')

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_visible(False)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))
        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'systemd': Systemd
}
