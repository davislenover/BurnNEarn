"""Every module in the app.

create_app() adds each module in PLUGINS to the app. Importing this file also
imports every module's tables, which is how Alembic finds them. Add a module
here once it has a plugin.py.
"""

from app.core.plugins import Plugin
from app.market import plugin as market

PLUGINS: tuple[Plugin, ...] = (market.PLUGIN,)
