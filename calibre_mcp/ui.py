from qt.core import QApplication, QMenu

from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.calibre_mcp.config import prefs
from calibre_plugins.calibre_mcp.server import MCPServer


class MCPAction(InterfaceAction):
    name = 'Calibre MCP'
    action_spec = ('MCP', None, 'Serve this library to MCP clients such as Claude', None)
    action_type = 'current'
    dont_add_to = frozenset(['context-menu', 'context-menu-device'])

    def genesis(self):
        self.server = None
        # The server thread reads this; only the GUI thread replaces it.
        # The library isn't open yet during genesis().
        self.db = None
        # get_icons is injected into plugin modules by calibre; passing the
        # plugin name lets icon themes override it.
        self.qaction.setIcon(get_icons('images/icon.svg', 'Calibre MCP'))  # noqa: F821
        self.menu = QMenu(self.gui)
        self.menu.aboutToShow.connect(self.rebuild_menu)
        self.qaction.setMenu(self.menu)
        self.qaction.triggered.connect(self.show_status)

    def initialization_complete(self):
        self.db = self.gui.current_db.new_api
        if prefs['autostart']:
            self.start_server(quiet=True)

    def library_changed(self, db):
        self.db = db.new_api

    def shutting_down(self):
        self.stop_server()
        return True

    # server lifecycle

    def start_server(self, quiet=False):
        if self.server is not None and self.server.running:
            return
        server = MCPServer(lambda: self.db, prefs['port'])
        try:
            server.start()
        except OSError as e:
            if not quiet:
                error_dialog(self.gui, 'Calibre MCP',
                             f'Could not listen on port {prefs["port"]}: {e}', show=True)
            print(f'calibre-mcp: could not start on port {prefs["port"]}: {e}')
            return
        self.server = server

    def stop_server(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def restart_server(self):
        self.stop_server()
        self.start_server()

    # menu

    def rebuild_menu(self):
        m = self.menu
        m.clear()
        running = self.server is not None and self.server.running
        status = m.addAction(f'Running at {self.server.url}' if running else 'Stopped')
        status.setEnabled(False)
        m.addSeparator()
        if running:
            m.addAction('Copy "claude mcp add" command', self.copy_command)
            m.addAction('Stop server', self.stop_server)
        else:
            m.addAction('Start server', self.start_server)
        m.addSeparator()
        m.addAction('Settings…', self.show_settings)

    def command(self):
        return f'claude mcp add --transport http calibre {self.server.url}'

    def copy_command(self):
        QApplication.clipboard().setText(self.command())

    def show_status(self):
        if self.server is not None and self.server.running:
            info_dialog(self.gui, 'Calibre MCP',
                        f'Serving this library at {self.server.url}\n\n'
                        f'Add it to Claude Code with:\n{self.command()}',
                        show=True, show_copy_button=True)
        else:
            info_dialog(self.gui, 'Calibre MCP',
                        'The server is stopped. Start it from this button\'s menu.',
                        show=True)

    def show_settings(self):
        self.interface_action_base_plugin.do_user_config(self.gui)
