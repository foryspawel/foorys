# -*- coding: utf-8 -*-

"""Punkt wejścia pluginu E2-Foorys dla Enigma2."""

from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor

from .config import ensure_config


def main(session, **kwargs):
    from .relay import get_agent, start_agent
    from .dashboard import E2FoorysMain

    get_agent().attach_session(session)
    start_agent()
    session.open(E2FoorysMain)


def autostart(reason, **kwargs):
    """Uruchamia klienta Relay razem z Enigma2, także gdy panel jest zamknięty."""

    from .relay import start_agent, stop_agent

    if reason == 0:
        start_agent()
    elif reason == 1:
        stop_agent()


def sessionstart(reason, session=None, **kwargs):
    """Udostępnia agentowi bezpieczny kontekst do zaplanowanego restartu GUI."""

    from .relay import get_agent

    agent = get_agent()
    if reason == 0 and session is not None:
        agent.attach_session(session)
    elif reason == 1:
        agent.detach_session()


def menu(menuid, **kwargs):
    """Dodaje skrót do głównego menu Enigma2 obok Ustawień."""

    if menuid == "mainmenu" and bool(ensure_config().show_in_main_menu.value):
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
    if hasattr(PluginDescriptor, "WHERE_AUTOSTART"):
        descriptors.append(
            PluginDescriptor(
                name="E2-Foorys Relay",
                description="Bezpieczne połączenie z Foorys Relay",
                where=PluginDescriptor.WHERE_AUTOSTART,
                fnc=autostart,
            )
        )
    if hasattr(PluginDescriptor, "WHERE_SESSIONSTART"):
        descriptors.append(
            PluginDescriptor(
                name="E2-Foorys Relay session",
                description="Obsługa sesji Foorys Relay",
                where=PluginDescriptor.WHERE_SESSIONSTART,
                fnc=sessionstart,
            )
        )
    return descriptors
