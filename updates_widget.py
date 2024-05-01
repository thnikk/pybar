#!/usr/bin/python3 -u
"""
Description: Updates widget
Author: thnikk
"""
import common as c


def updates_widget(info):
    """ Update widget """
    main_box = c.box('v', style='widget', spacing=20)
    label = c.label('Updates', style='heading')
    main_box.add(label)

    urls = {
        "Pacman": "https://archlinux.org/packages/",
        "AUR": "https://aur.archlinux.org/packages/",
        "Flatpak": "https://flathub.org/apps/search?q=",
    }

    for manager, packages in info.items():
        if not packages:
            continue
        manager_box = c.box('v', spacing=10)
        heading = c.label(manager, style='title', ha='start')
        manager_box.add(heading)
        packages_box = c.box('v')
        scroll_box = c.scroll(0, 348)
        for package in packages:
            package_box = c.box('h', style='event-box', spacing=20)
            package_label = c.button(package[0], style='none')
            try:
                package_label.connect(
                    'clicked', c.click_link,
                    f'{urls[manager]}{package[0]}')
            except KeyError:
                pass
            package_box.pack_start(package_label, False, False, 0)
            package_box.pack_end(
                c.label(package[1], style='green-fg'), False, False, 0)
            packages_box.add(package_box)
            if package != packages[-1]:
                packages_box.pack_start(c.sep('h'), 1, 1, 0)

        if len(packages) > 10:
            scroll_box.get_style_context().add_class('events-box')
            scroll_box.add(packages_box)
            manager_box.add(scroll_box)
        else:
            packages_box.get_style_context().add_class('events-box')
            manager_box.add(packages_box)

        manager_box.add(packages_box)
        main_box.add(manager_box)

    return main_box
