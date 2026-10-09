# -*- coding: utf-8 -*-
from handoff import CANONICAL_URL, MAX_URL_LENGTH


def open_default_browser(url):
    if not url.startswith(CANONICAL_URL + '#revit=') or len(url) > MAX_URL_LENGTH:
        raise ValueError('Invalid Web handoff URL.')
    from System.Diagnostics import Process, ProcessStartInfo
    info = ProcessStartInfo()
    info.FileName = url
    info.UseShellExecute = True
    info.Verb = 'open'
    # No cmd.exe, command-line interpolation, local server, or embedded browser.
    Process.Start(info)
