#!/usr/bin/python3 -u
"""
Description: Waybar tooltip library
Author: thnikk
"""


def span(text, color=None, size=None, bg=None) -> str:
    """ Colorize text """
    colors = {
        "red": "#bf616a",
        "blue": "#8fa1be",
        "green": "#a3be8c",
        "orange": "#d08770",
        "purple": "#b48ead",
        "yellow": "#ebcb8b",
    }
    try:
        color = colors[color]
    except KeyError:
        pass
    if isinstance(size, int):
        size = f"{size}pt"
    try:
        bg = colors[bg]
    except KeyError:
        pass
    attributes = " ".join(['span'] + [
        f'{key}="{value}"' for key, value in
        {"color": color, "font_size": size, "background": bg}.items()
        if value
    ])
    return f'<{attributes}>{text}</span>'


def heading(text) -> str:
    """ Create tooltip heading """
    return span(text, 'blue', 16)
