#!/usr/bin/python3 -u
"""
Description: Home Assistant module that generates UI from a Lovelace dashboard
Author: thnikk
"""

import weakref
import requests
import common as c
import gi
import asyncio
import aiohttp

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa


class HASSLovelace(c.BaseModule):
    SCHEMA = {
        "server": {
            "type": "string",
            "default": "",
            "label": "Server",
            "description": "Home Assistant server address "
            "(e.g. 10.0.0.3:8123)",
        },
        "bearer_token": {
            "type": "string",
            "default": "",
            "label": "Bearer Token",
            "description": "Long-lived access token from Home Assistant",
        },
        "dashboard_id": {
            "type": "string",
            "default": "lovelace",
            "label": "Dashboard ID",
            "description": "Dashboard ID (e.g. lovelace)",
        },
        "interval": {
            "type": "integer",
            "default": 30,
            "label": "Update Interval",
            "description": "Polling interval (seconds)",
            "min": 5,
            "max": 600,
        },
    }

    def _get_session(self):
        if not hasattr(self, "_session") or self._session is None:
            self._session = requests.Session()
        return self._session

    async def _fetch_config_ws(self, base_url, token, dash_id):
        """Fetch Lovelace config via WebSocket (supports YAML mode)"""
        ws_url = (
            base_url.replace("http://", "ws://").replace("https://", "wss://")
            + "/api/websocket"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    # 1. Auth
                    msg = await ws.receive_json()
                    if msg.get("type") != "auth_required":
                        return None

                    await ws.send_json(
                        {
                            "type": "auth",
                            "access_token": token.replace("Bearer ", "")
                            if token.startswith("Bearer ")
                            else token,
                        }
                    )

                    msg = await ws.receive_json()
                    if msg.get("type") != "auth_ok":
                        c.print_debug(
                            f"HASS Lovelace: WS Auth failed: {msg}",
                            color="red"
                        )
                        return None

                    # 2. Get Config
                    cmd = {
                        "id": 1,
                        "type": "lovelace/config",
                    }
                    if dash_id != "lovelace":
                        cmd["url_path"] = dash_id

                    await ws.send_json(cmd)

                    msg = await ws.receive_json()
                    if msg.get("success"):
                        return msg.get("result")
                    else:
                        c.print_debug(
                            f"HASS Lovelace: WS Config fetch failed: {msg}",
                            color="red"
                        )
                        return None
        except Exception as e:
            c.print_debug(f"HASS Lovelace: WS Error: {e}", color="red")
            return None

    def fetch_data(self):
        server = self.config.get("server")
        token = self.config.get("bearer_token")
        dash_id = self.config.get("dashboard_id", "lovelace")

        if not server or not token:
            return None

        if "://" in server:
            base_url = server.rstrip("/")
        else:
            base_url = f"http://{server}"

        bearer_token = f"Bearer {token}" if not token.startswith(
            "Bearer ") else token
        headers = {"Authorization": bearer_token,
                   "content-type": "application/json"}

        config = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            config = loop.run_until_complete(
                self._fetch_config_ws(base_url, bearer_token, dash_id)
            )
            loop.close()
        except Exception as e:
            c.print_debug(
                f"HASS Lovelace: Failed to fetch via WS: {e}", color="yellow")

        if config is None:
            url_config = f"{base_url}/api/config/lovelace/config"
            if dash_id != "lovelace":
                url_config = f"{base_url}/api/config/lovelace/config/{dash_id}"

            try:
                with self._get_session().get(
                    url_config, headers=headers, timeout=5
                ) as r:
                    if r.status_code == 200:
                        config = r.json()
            except Exception:
                pass

        if config is None:
            c.print_debug(
                f"HASS Lovelace: Could not fetch config for "
                f"'{dash_id}' via any method.",
                color="red",
            )
            return None

        try:
            with self._get_session().get(
                f"{base_url}/api/states", headers=headers, timeout=5
            ) as r:
                if r.status_code != 200:
                    return None
                states = {s["entity_id"]: s for s in r.json()}

            return {
                "config": config,
                "states": states,
                "server": base_url,
                "token": bearer_token,
            }
        except Exception as e:
            c.print_debug(
                f"HASS Lovelace: Error fetching states: {e}", color="red")
            return None

    def build_popover(self, data):
        server = data["server"]
        token = data["token"]
        config = data.get("config", {})
        states = data.get("states", {})

        main_box = c.box("v", spacing=15)

        # Dashboard Title (Main Widget Heading)
        title = config.get("title", "Home Assistant")
        main_box.append(c.label(title, style="heading"))

        views = config.get("views", [])
        if not views:
            cards = config.get("cards", [])
            if cards:
                ibox = c.box("v", style="box")
                for card in cards:
                    self.build_card_rows(card, states, server, token, ibox)
                if ibox.get_first_child():
                    main_box.append(ibox)
        else:
            for view in views:
                # 20px gap between sections
                view_box = c.box("v", spacing=20)

                cards = view.get("cards", [])
                sections = view.get("sections", [])

                if not cards and sections:
                    for section in sections:
                        sec_cards = section.get("cards", [])
                        self._render_cards_with_headings(
                            sec_cards, states, server, token, view_box
                        )

                else:
                    self._render_cards_with_headings(
                        cards, states, server, token, view_box
                    )

                if view_box.get_first_child():
                    main_box.append(view_box)

        scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=False)
        scrolled.set_overflow(Gtk.Overflow.HIDDEN)
        scrolled.set_max_content_height(600)
        scrolled.set_propagate_natural_width(True)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(main_box)
        return scrolled

    def _extract_entities(self, card):
        entities = []
        ctype = card.get("type")
        if ctype in ["grid", "horizontal-stack", "vertical-stack"]:
            for c_info in card.get("cards", []):
                entities.extend(self._extract_entities(c_info))
        elif ctype in ["entities", "glance"]:
            for ent in card.get("entities", []):
                if isinstance(ent, dict):
                    entities.append(ent.get("entity"))
                else:
                    entities.append(ent)
        elif ctype in ["button", "sensor"]:
            entities.append(card.get("entity"))
        return [e for e in entities if e]

    def group_toggle_ha(self, server, token, eids, state, switch_widgets):
        service = "turn_on" if state else "turn_off"

        # Optimistically update the local UI switches immediately
        for sw in switch_widgets:
            if sw.get_active() != state:
                # We use a custom property to prevent the individual toggle_ha
                # from sending redundant requests when triggered by
                # group toggle
                sw._by_group = True
                sw.set_active(state)
                delattr(sw, "_by_group")

        try:
            with self._get_session().post(
                f"{server}/api/services/homeassistant/{service}",
                headers={"Authorization": token,
                         "content-type": "application/json"},
                json={"entity_id": eids},
                timeout=3,
            ):
                pass
        except Exception:
            pass
        return False

    def toggle_ha(self, server, token, eid, switch=None):
        # If this was triggered by a group toggle, don't send
        # individual request
        if switch and getattr(switch, "_by_group", False):
            return False

        try:
            domain = eid.split(".")[0]
            with self._get_session().post(
                f"{server}/api/services/{domain}/toggle",
                headers={"Authorization": token,
                         "content-type": "application/json"},
                json={"entity_id": eid},
                timeout=3,
            ):
                pass
        except Exception:
            pass
        return False

    def _update_group_switch(self, group_sw, eids, states):
        """Update the group switch state based on individual entity states."""
        if not group_sw:
            return
        any_on = any(states.get(eid, {}).get("state") == "on" for eid in eids)
        if group_sw.get_active() != any_on:
            # We don't want to trigger the group_sw signal here
            # but setting active programmatically usually doesn't trigger
            # 'state-set'
            # if changed via user it does.
            # In GTK4, set_active() emits 'notify::active'.
            # 'state-set' is specifically for user interaction usually.
            group_sw.set_active(any_on)

    def _render_cards_with_headings(
            self, cards, states, server, token, parent):
        """Render a list of cards into parent, grouping by heading cards."""
        groups = []
        current_group = {"heading": None, "cards": []}

        for card in cards:
            if card.get("type") == "heading":
                if current_group["heading"] or current_group["cards"]:
                    groups.append(current_group)
                current_group = {"heading": card, "cards": []}
            else:
                current_group["cards"].append(card)
        if current_group["heading"] or current_group["cards"]:
            groups.append(current_group)

        for group in groups:
            current_section = c.box("v", spacing=10)

            # Find all toggleable entities in this section
            toggleable_eids = []
            for card in group["cards"]:
                for eid in self._extract_entities(card):
                    if not eid or eid not in states:
                        continue
                    domain = eid.split(".")[0]
                    if domain in [
                        "switch",
                        "light",
                        "input_boolean",
                        "automation",
                        "script",
                    ]:
                        if eid not in toggleable_eids:
                            toggleable_eids.append(eid)

            # Dictionary to collect the created switch widgets for local
            # optimistic update
            switch_widgets_dict = {}
            group_sw = None

            # Render heading if present (create group_sw if needed)
            if group["heading"]:
                card = group["heading"]
                heading = card.get("heading") or card.get(
                    "text") or card.get("title")
                if heading:
                    header_box = c.box("h", spacing=10)
                    header_box.append(
                        c.label(heading, style="title", ha="start", he=True)
                    )

                    if toggleable_eids:
                        any_on = any(
                            states[eid].get("state") == "on"
                            for eid in toggleable_eids
                        )
                        group_sw = Gtk.Switch.new()
                        group_sw.set_active(any_on)
                        group_sw.set_valign(Gtk.Align.CENTER)
                        header_box.append(group_sw)

                    current_section.append(header_box)
            else:
                if toggleable_eids and len(toggleable_eids) > 1:
                    header_box = c.box("h", spacing=10)
                    header_box.append(c.label("", ha="start", he=True))
                    any_on = any(
                        states[eid].get("state") == "on"
                        for eid in toggleable_eids
                    )
                    group_sw = Gtk.Switch.new()
                    group_sw.set_active(any_on)
                    group_sw.set_valign(Gtk.Align.CENTER)
                    header_box.append(group_sw)
                    current_section.append(header_box)

            # Render cards
            ibox = c.box("v", style="box")
            if group["cards"]:
                for card in group["cards"]:
                    self.build_card_rows(
                        card, states, server, token, ibox, switch_widgets_dict
                    )

            # Connect group switch now that we have all individual switches
            if group_sw:

                def on_group_switch_set(
                    _sw,
                    state,
                    s=server,
                    t=token,
                    e=toggleable_eids,
                    w=switch_widgets_dict.values(),
                ):
                    # If this change is coming from the individual switches
                    # sync, don't trigger HA
                    if getattr(_sw, "_by_sync", False):
                        return False
                    self.group_toggle_ha(s, t, e, state, list(w))
                    return False

                group_sw.connect("state-set", on_group_switch_set)

                # Add listeners to individual switches to update the group
                # switch state
                def on_individual_switch_change(
                    _sw, _new_state, gsw=group_sw, sw_dict=switch_widgets_dict
                ):
                    # If this change was triggered by the group toggle, don't
                    # update back
                    if getattr(_sw, "_by_group", False):
                        return False

                    # Calculate if ANY switch will be on after this change
                    # We use the new state of the current switch and current
                    # state of others
                    any_on = any(
                        _new_state if s == _sw else s.get_active()
                        for s in sw_dict.values()
                    )

                    if gsw.get_active() != any_on:
                        # Set a flag so the group switch knows this is a sync,
                        # not a user action
                        gsw._by_sync = True
                        gsw.set_active(any_on)
                        # We use GLib.idle_add or similar if needed, but
                        # delattr here is fine if set_active is synchronous
                        delattr(gsw, "_by_sync")
                    return False

                for sw in switch_widgets_dict.values():
                    sw.connect("state-set", on_individual_switch_change)

            # Now append the cards box if it has children
            if ibox.get_first_child():
                current_section.append(ibox)

            if current_section.get_first_child():
                parent.append(current_section)

    def build_card_rows(
            self, card, states, server, token, container, switch_dict=None):
        ctype = card.get("type")
        if ctype in ["grid", "horizontal-stack", "vertical-stack"]:
            cards = card.get("cards", [])
            for c_info in cards:
                self.build_card_rows(
                    c_info, states, server, token, container, switch_dict
                )
            return

        if ctype in ["entities", "glance"]:
            entities = card.get("entities", [])
            for ent in entities:
                row = self._create_entity_row(
                    ent, states, server, token, switch_dict)
                if row:
                    if container.get_first_child():
                        container.append(c.sep("h"))
                    container.append(row)
        elif ctype in ["button", "sensor"]:
            row = self._create_entity_row(
                card, states, server, token, switch_dict)
            if row:
                if container.get_first_child():
                    container.append(c.sep("h"))
                container.append(row)

    def _create_entity_row(self, ent, states, server, token, switch_dict=None):

        if isinstance(ent, dict):
            eid = ent.get("entity")
        else:
            eid = ent

        if not eid or eid not in states:
            return None

        state_data = states[eid]
        name = (
            ent.get("name") if isinstance(ent, dict) else None
        ) or state_data.get(
            "attributes", {}
        ).get("friendly_name")

        if not name:
            name = eid.split(".")[-1].replace("_", " ").title()

        row = c.box("h", spacing=20, style="inner-box")
        row.append(c.label(name, ha="start", he=True))

        domain = eid.split(".")[0]
        if domain in ["sensor", "binary_sensor"]:
            val = state_data.get("state", "unknown")
            try:
                val = f"{float(val):.1f}"
            except (ValueError, TypeError):
                pass
            unit = state_data.get("attributes", {}).get(
                "unit_of_measurement", "")
            row.append(c.label(f"{val}{unit}", ha="end"))
        elif domain in [
                "switch", "light", "input_boolean", "automation", "script"]:
            sw = Gtk.Switch.new()
            sw.set_active(state_data.get("state") == "on")
            sw.set_valign(Gtk.Align.CENTER)
            sw.connect(
                "state-set", self._make_toggle_handler(server, token, eid))
            if switch_dict is not None:
                switch_dict[eid] = sw
            row.append(sw)
        else:
            val = state_data.get("state", "unknown")
            row.append(c.label(val, ha="end"))

        return row

    def _make_toggle_handler(self, server, token, eid):
        return lambda sw, _st: self.toggle_ha(server, token, eid, sw)

    def create_widget(self, bar):
        m = c.Module(True, False)
        m.set_position(bar.position)
        m.set_icon("")
        m.set_visible(False)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data or "config" not in data:
            return
        widget.set_visible(True)

        if not widget.get_active():
            states = data.get("states", {})
            fingerprint = tuple(
                (eid, s.get("state")) for eid, s in sorted(states.items())
            )
            if getattr(widget, "_popover_fingerprint", None) == fingerprint:
                return
            widget._popover_fingerprint = fingerprint

            widget.set_widget(self.build_popover(data))


module_map = {"hass_lovelace": HASSLovelace}
