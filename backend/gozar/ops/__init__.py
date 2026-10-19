"""Server operations over SSH — the engine of the Telegram console's 🖥 nodes and 🗄 servers.

Infra, like ``remnawave/``: no Telegram, no database, no settings. A job (``services/ops``) hands
these modules a connected ``ssh.Server``, the panel (``remnawave/ops.OpsPanel``) and a
``report.Reporter``, and they do the work — every remote step a ``bash -s`` script fed on stdin, so
no secret ever appears in a command line or in ``ps``. Ported from tunnelbot 2026.10.17.6, where each
step was verified on real servers and a real Remnawave 3.4.4 panel.
"""
