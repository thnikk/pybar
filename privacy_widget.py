#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import common as c


def privacy_widget(info):
    """ UPS widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('Privacy', style='heading')
    main_box.add(label)

    for category, progs in info.items():
        category_box = c.box('v', spacing=10)
        category_box.add(c.label(category, style='title', ha='start'))
        prog_box = c.box('v', style='box')
        for prog in progs:
            prog_box.add(c.label(prog, style='inner-box'))
            if prog != progs[-1]:
                prog_box.add(c.sep('h'))
        category_box.add(prog_box)
        main_box.add(category_box)

    return main_box
