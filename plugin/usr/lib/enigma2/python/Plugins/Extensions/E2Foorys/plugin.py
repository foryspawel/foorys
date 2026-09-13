# -*- coding: utf-8 -*-

"""Punkt wejścia pluginu E2-Foorys dla Enigma2."""

from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor

from .config import ensure_config


def main(session, **kwargs):
    from .ui import E2FoorysMain

    session.open(E2FoorysMain)


def Plugins(**kwargs):
    ensure_config()
    descriptors = [
        PluginDescriptor(
            name="E2-Foorys",
            description="Listy kanałów, pluginy i oscam.dvbapi",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="foorys.png",
            fnc=main,
        )
    ]
    if hasattr(PluginDescriptor, "WHERE_EXTENSIONSMENU"):
        descriptors.append(
            PluginDescriptor(
                name="E2-Foorys",
                description="Listy kanałów, pluginy i oscam.dvbapi",
                where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                icon="foorys.png",
                fnc=main,
            )
        )
    return descriptors
