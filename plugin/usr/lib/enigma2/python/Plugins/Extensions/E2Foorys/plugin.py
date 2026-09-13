# -*- coding: utf-8 -*-

"""Punkt wejścia pluginu E2-Foorys dla Enigma2."""

from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor

from .config import ensure_config


def main(session, **kwargs):
    from .dashboard import E2FoorysMain

    session.open(E2FoorysMain)


def menu(menuid, **kwargs):
    """Dodaje skrót do głównego menu Enigma2 obok Ustawień."""

    if menuid == "mainmenu":
        return [("E2-Foorys", main, "e2foorys", 70)]
    return []


def Plugins(**kwargs):
    ensure_config()
    descriptors = [
        PluginDescriptor(
            name="E2-Foorys",
            description="E2-Foorys: listy, aktualizacje, softcam i diagnostyka",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="foorys.png",
            fnc=main,
        )
    ]
    if hasattr(PluginDescriptor, "WHERE_MENU"):
        descriptors.append(
            PluginDescriptor(
                name="E2-Foorys",
                description="E2-Foorys: listy, aktualizacje, softcam i diagnostyka",
                where=PluginDescriptor.WHERE_MENU,
                fnc=menu,
            )
        )
    if hasattr(PluginDescriptor, "WHERE_EXTENSIONSMENU"):
        descriptors.append(
            PluginDescriptor(
                name="E2-Foorys",
                description="E2-Foorys: listy, aktualizacje, softcam i diagnostyka",
                where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                icon="foorys.png",
                fnc=main,
            )
        )
    return descriptors
