# -*- coding: utf-8 -*-

"""Skalowanie ekranów E2-Foorys dla SD, HD i Full HD."""

from __future__ import absolute_import

import re


REFERENCE_WIDTH = 1280
REFERENCE_HEIGHT = 720


def desktop_size():
    try:
        from enigma import getDesktop

        size = getDesktop(0).size()
        return int(size.width()), int(size.height())
    except Exception:
        return REFERENCE_WIDTH, REFERENCE_HEIGHT


def layout_scale(width=None, height=None):
    """Zwraca stabilną skalę: 1.5 dla FHD, 1.0 dla HD i fallback dla SD."""

    if width is None or height is None:
        width, height = desktop_size()
    if width >= 1700 and height >= 950:
        return 1.5
    if width < 1200 or height < 680:
        return max(min(float(width) / REFERENCE_WIDTH, float(height) / REFERENCE_HEIGHT), 0.55)
    return 1.0


def _scaled_number(value, scale):
    return str(max(int(round(int(value) * scale)), 1))


def scale_skin_for_ratio(skin_xml, scale):
    """Skaluje wyłącznie współrzędne, rozmiary i czcionki w XML skina."""

    if abs(float(scale) - 1.0) < 0.001:
        return skin_xml

    pair_pattern = re.compile(r'(?P<name>\b(?:position|size))="(?P<x>\d+),(?P<y>\d+)"')
    single_pattern = re.compile(r'(?P<name>\b(?:itemHeight|borderWidth))="(?P<value>\d+)"')
    font_pattern = re.compile(r'font="(?P<face>[^";]+);(?P<size>\d+)"')

    def pair(match):
        return '%s="%s,%s"' % (
            match.group("name"),
            _scaled_number(match.group("x"), scale),
            _scaled_number(match.group("y"), scale),
        )

    def single(match):
        return '%s="%s"' % (
            match.group("name"),
            _scaled_number(match.group("value"), scale),
        )

    def font(match):
        return 'font="%s;%s"' % (
            match.group("face"),
            _scaled_number(match.group("size"), scale),
        )

    skin_xml = pair_pattern.sub(pair, skin_xml)
    skin_xml = single_pattern.sub(single, skin_xml)
    return font_pattern.sub(font, skin_xml)


def scaled_skin(skin_xml):
    return scale_skin_for_ratio(skin_xml, layout_scale())
