#!/usr/bin/python3 -u
"""
Description: Home Assistant module that generates UI from a Lovelace dashboard
Author: thnikk
"""

import json
import os
import weakref
import requests
import common as c
import gi
import asyncio
import aiohttp
import logging

logging.getLogger("asyncio").setLevel(logging.WARNING)

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa


class HASSLovelace(c.BaseModule):
    SCHEMA = {
        "server": {
            "type": "string",
            "default": "",
            "label": "Server",
            "description": (
                "Home Assistant server address (e.g. 10.0.0.3:8123)"
            ),
        },
        "bearer_token": {
            "type": "string",
            "default": "",
            "label": "Bearer Token",
            "description": (
                "Long-lived access token from Home Assistant"
            ),
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

    # --- Pin helpers ---------------------------------------------------

    @property
    def _pin_cache_path(self):
        """Path to the JSON file that persists the pinned entity ID."""
        return os.path.expanduser(
            f"~/.cache/pybar/{self.name}_pin.json"
        )

    def _load_pinned(self):
        """Return the pinned entity ID, or None if nothing is pinned."""
        try:
            with open(self._pin_cache_path) as f:
                return json.load(f).get("pinned_eid")
        except Exception:
            return None

    def _save_pinned(self, eid):
        """Persist the pinned entity ID (pass None to clear)."""
        try:
            os.makedirs(
                os.path.dirname(self._pin_cache_path), exist_ok=True
            )
            with open(self._pin_cache_path, "w") as f:
                json.dump({"pinned_eid": eid}, f)
        except Exception:
            pass

    def _format_pinned_label(self, states, eid):
        """
        Return a formatted bar label for the pinned sensor entity,
        or None if the entity is unavailable.
        """
        if not eid or eid not in states:
            return None
        state_data = states[eid]
        val = state_data.get("state", "")
        unit = state_data.get("attributes", {}).get(
            "unit_of_measurement", ""
        )
        try:
            val = f"{float(val):.1f}"
        except (ValueError, TypeError):
            pass
        return f"{val}{unit}" if val else None

    # --- Session / fetch -----------------------------------------------

    def _get_session(self):
        if not hasattr(self, "_session") or self._session is None:
            self._session = requests.Session()
        return self._session

    async def _fetch_config_ws(self, base_url, token, dash_id):
        """Fetch Lovelace config via WebSocket (supports YAML mode)."""
        ws_url = (
            base_url
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            + "/api/websocket"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    # 1. Auth
                    msg = await ws.receive_json()
                    if msg.get("type") != "auth_required":
                        return None

                    raw = token.replace("Bearer ", "") \
                        if token.startswith("Bearer ") else token
                    await ws.send_json(
                        {"type": "auth", "access_token": raw}
                    )

                    msg = await ws.receive_json()
                    if msg.get("type") != "auth_ok":
                        c.print_debug(
                            f"HASS Lovelace: WS Auth failed: {msg}",
                            color="red",
                        )
                        return None

                    # 2. Get Config
                    cmd = {"id": 1, "type": "lovelace/config"}
                    if dash_id != "lovelace":
                        cmd["url_path"] = dash_id

                    await ws.send_json(cmd)
                    msg = await ws.receive_json()
                    if msg.get("success"):
                        return msg.get("result")
                    c.print_debug(
                        "HASS Lovelace: WS Config fetch failed: "
                        f"{msg}",
                        color="red",
                    )
                    return None
        except Exception as e:
            c.print_debug(
                f"HASS Lovelace: WS Error: {e}", color="red"
            )
            return None

    def fetch_data(self):
        server = self.config.get("server")
        token = self.config.get("bearer_token")
        dash_id = self.config.get("dashboard_id", "lovelace")

        if not server or not token:
            return None

        base_url = (
            server.rstrip("/")
            if "://" in server
            else f"http://{server}"
        )

        bearer_token = (
            f"Bearer {token}"
            if not token.startswith("Bearer ")
            else token
        )
        headers = {
            "Authorization": bearer_token,
            "content-type": "application/json",
        }

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
                f"HASS Lovelace: Failed to fetch via WS: {e}",
                color="yellow",
            )

        if config is None:
            url_config = (
                f"{base_url}/api/config/lovelace/config"
                if dash_id == "lovelace"
                else (
                    f"{base_url}/api/config/lovelace/config/{dash_id}"
                )
            )
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
                f"HASS Lovelace: Error fetching states: {e}",
                color="red",
            )
            return None

    # --- Popover build -------------------------------------------------

    def build_popover(self, data, widget):
        server = data["server"]
        token = data["token"]
        config = data.get("config", {})
        states = data.get("states", {})

        container = c.box("v", spacing=20)

        title = config.get("title", "Home Assistant")
        container.append(c.label(title, style="heading"))

        main_box = c.box("v", spacing=20)

        views = config.get("views", [])
        if not views:
            cards = config.get("cards", [])
            if cards:
                ibox = c.box("v", style="box")
                for card in cards:
                    self.build_card_rows(
                        card, states, server, token, ibox,
                        widget=widget,
                    )
                if ibox.get_first_child():
                    main_box.append(ibox)
        else:
            for view in views:
                view_box = c.box("v", spacing=20)
                cards = view.get("cards", [])
                sections = view.get("sections", [])

                if not cards and sections:
                    for section in sections:
                        sec_cards = section.get("cards", [])
                        self._render_cards_with_headings(
                            sec_cards, states, server, token,
                            view_box, widget=widget,
                        )
                else:
                    self._render_cards_with_headings(
                        cards, states, server, token,
                        view_box, widget=widget,
                    )

                if view_box.get_first_child():
                    main_box.append(view_box)

        res = c.VScrollGradientBox(
            main_box, max_height=500, bg_color="#1c1f26"
        )
        c.add_style(res, "scroll")
        container.append(res)
        return container

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

        # Optimistically update local switches immediately.
        for sw in switch_widgets:
            if sw.get_active() != state:
                sw._by_group = True
                sw.set_active(state)
                delattr(sw, "_by_group")

        try:
            with self._get_session().post(
                f"{server}/api/services/homeassistant/{service}",
                headers={
                    "Authorization": token,
                    "content-type": "application/json",
                },
                json={"entity_id": eids},
                timeout=3,
            ):
                pass
        except Exception:
            pass
        return False

    def toggle_ha(self, server, token, eid, switch=None):
        # Skip individual request when triggered by a group toggle.
        if switch and getattr(switch, "_by_group", False):
            return False

        try:
            domain = eid.split(".")[0]
            with self._get_session().post(
                f"{server}/api/services/{domain}/toggle",
                headers={
                    "Authorization": token,
                    "content-type": "application/json",
                },
                json={"entity_id": eid},
                timeout=3,
            ):
                pass
        except Exception:
            pass
        return False

    def _update_group_switch(self, group_sw, eids, states):
        """Update group switch state from individual entity states."""
        if not group_sw:
            return
        any_on = any(
            states.get(eid, {}).get("state") == "on"
            for eid in eids
        )
        if group_sw.get_active() != any_on:
            group_sw.set_active(any_on)

    def _render_cards_with_headings(
        self, cards, states, server, token, parent, widget=None
    ):
        """Render a list of cards grouped by heading cards."""
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

            # Collect toggleable entity IDs in this section.
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
                    ] and eid not in toggleable_eids:
                        toggleable_eids.append(eid)

            switch_widgets_dict = {}
            group_sw = None

            if group["heading"]:
                card = group["heading"]
                heading = (
                    card.get("heading")
                    or card.get("text")
                    or card.get("title")
                )
                if heading:
                    header_box = c.box("h", spacing=10)
                    header_box.append(
                        c.label(
                            heading, style="title", ha="start", he=True
                        )
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

            # Render cards.
            ibox = c.box("v", style="box")
            if group["cards"]:
                for card in group["cards"]:
                    self.build_card_rows(
                        card, states, server, token, ibox,
                        switch_widgets_dict, widget=widget,
                    )

            # Connect group switch now that individual switches exist.
            if group_sw:

                def on_group_switch_set(
                    _sw, state,
                    s=server, t=token,
                    e=toggleable_eids,
                    w=switch_widgets_dict.values(),
                ):
                    if getattr(_sw, "_by_sync", False):
                        return False
                    self.group_toggle_ha(s, t, e, state, list(w))
                    return False

                group_sw.connect("state-set", on_group_switch_set)

                def on_individual_switch_change(
                    _sw, _new_state,
                    gsw=group_sw,
                    sw_dict=switch_widgets_dict,
                ):
                    if getattr(_sw, "_by_group", False):
                        return False
                    any_on = any(
                        _new_state if s == _sw else s.get_active()
                        for s in sw_dict.values()
                    )
                    if gsw.get_active() != any_on:
                        gsw._by_sync = True
                        gsw.set_active(any_on)
                        delattr(gsw, "_by_sync")
                    return False

                for sw in switch_widgets_dict.values():
                    sw.connect(
                        "state-set", on_individual_switch_change
                    )

            if ibox.get_first_child():
                current_section.append(ibox)

            if current_section.get_first_child():
                parent.append(current_section)

    def build_card_rows(
        self, card, states, server, token, container,
        switch_dict=None, widget=None,
    ):
        ctype = card.get("type")
        if ctype in ["grid", "horizontal-stack", "vertical-stack"]:
            for c_info in card.get("cards", []):
                self.build_card_rows(
                    c_info, states, server, token, container,
                    switch_dict, widget=widget,
                )
            return

        if ctype in ["entities", "glance"]:
            for ent in card.get("entities", []):
                row = self._create_entity_row(
                    ent, states, server, token, switch_dict,
                    widget=widget,
                )
                if row:
                    if container.get_first_child():
                        container.append(c.sep("h"))
                    container.append(row)
        elif ctype in ["button", "sensor"]:
            row = self._create_entity_row(
                card, states, server, token, switch_dict,
                widget=widget,
            )
            if row:
                if container.get_first_child():
                    container.append(c.sep("h"))
                container.append(row)

    def _create_entity_row(
        self, ent, states, server, token,
        switch_dict=None, widget=None,
    ):
        if isinstance(ent, dict):
            eid = ent.get("entity")
        else:
            eid = ent

        if not eid or eid not in states:
            return None

        state_data = states[eid]
        name = (
            (ent.get("name") if isinstance(ent, dict) else None)
            or state_data.get("attributes", {}).get("friendly_name")
        )
        if not name:
            name = eid.split(".")[-1].replace("_", " ").title()

        row = c.box("h", spacing=10, style="inner-box")
        row.append(c.label(name, ha="start", he=True))

        domain = eid.split(".")[0]
        if domain == "sensor":
            val = state_data.get("state", "unknown")
            try:
                val = f"{float(val):.1f}"
            except (ValueError, TypeError):
                pass
            unit = state_data.get(
                "attributes", {}
            ).get("unit_of_measurement", "")
            row.append(c.label(f"{val}{unit}", ha="end"))

            # Pin button — filled icon when this entity is pinned.
            pinned = (
                widget is not None
                and getattr(widget, "_pinned_eid", None) == eid
            )
            pin_btn = c.button(
                "" if pinned else "",
                style="pin-button",
            )
            if pinned:
                c.add_style(pin_btn, "pinned")
            pin_btn.set_valign(Gtk.Align.CENTER)
            pin_btn.set_tooltip_text(
                "Unpin from bar" if pinned else "Pin value to bar"
            )

            def on_pin_clicked(
                _btn, e=eid, w=widget, s=states,
            ):
                # Toggle: unpin if already pinned, else pin this entity.
                if getattr(w, "_pinned_eid", None) == e:
                    w._pinned_eid = None
                    self._save_pinned(None)
                else:
                    w._pinned_eid = e
                    self._save_pinned(e)
                # Update bar label immediately.
                label_text = self._format_pinned_label(
                    s, w._pinned_eid
                )
                if label_text:
                    w.set_label(label_text)
                else:
                    # Revert to the module icon only.
                    w.set_label("")
                # Rebuild popover to reflect new pin state.
                data = c.state_manager.get(self.name)
                if data:
                    w.set_widget(self.build_popover(data, w))
                    w.get_popover().popup()

            pin_btn.connect("clicked", on_pin_clicked)
            row.append(pin_btn)

        elif domain == "binary_sensor":
            val = state_data.get("state", "unknown")
            row.append(c.label(val, ha="end"))
        elif domain in [
            "switch", "light", "input_boolean",
            "automation", "script",
        ]:
            sw = Gtk.Switch.new()
            sw.set_active(state_data.get("state") == "on")
            sw.set_valign(Gtk.Align.CENTER)
            sw.connect(
                "state-set",
                self._make_toggle_handler(server, token, eid),
            )
            if switch_dict is not None:
                switch_dict[eid] = sw
            row.append(sw)
        else:
            val = state_data.get("state", "unknown")
            row.append(c.label(val, ha="end"))

        return row

    def _make_toggle_handler(self, server, token, eid):
        return lambda sw, _st: self.toggle_ha(server, token, eid, sw)

    # --- Widget lifecycle ----------------------------------------------

    def create_widget(self, bar):
        m = c.Module(True, True)
        m.set_position(bar.position)
        m.set_icon("")
        m.set_visible(False)

        # Restore persisted pin on startup.
        m._pinned_eid = self._load_pinned()

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def _get_displayed_eids(self, config):
        """Return the set of entity IDs rendered in the dashboard."""
        eids = set()
        views = config.get("views", [])
        cards = config.get("cards", []) if not views else []
        for view in views:
            for card in view.get("cards", []):
                eids.update(self._extract_entities(card))
            for section in view.get("sections", []):
                for card in section.get("cards", []):
                    eids.update(self._extract_entities(card))
        for card in cards:
            eids.update(self._extract_entities(card))
        return eids

    def update_ui(self, widget, data):
        if not data or "config" not in data:
            return
        widget.set_visible(True)

        # Update bar label from pinned sensor every cycle.
        states = data.get("states", {})
        pinned = getattr(widget, "_pinned_eid", None)
        label_text = self._format_pinned_label(states, pinned)
        if label_text:
            widget.set_label(label_text)
        else:
            widget.set_label("")

        if not widget.get_active():
            # Fingerprint only toggleable entities (switches, lights,
            # automations). Sensor values change constantly and don't
            # affect popover structure, so excluding them prevents a
            # full rebuild on every polling cycle.
            displayed = self._get_displayed_eids(data["config"])
            toggleable_domains = {
                "switch", "light", "input_boolean",
                "automation", "script",
            }
            fingerprint = tuple(
                (eid, states[eid].get("state"))
                for eid in sorted(displayed)
                if eid in states
                and eid.split(".")[0] in toggleable_domains
            )
            if (
                getattr(widget, "_popover_fingerprint", None)
                == fingerprint
            ):
                return
            widget._popover_fingerprint = fingerprint
            widget.set_widget(self.build_popover(data, widget))


module_map = {"hass_lovelace": HASSLovelace}
