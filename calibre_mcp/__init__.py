from calibre.customize import InterfaceActionBase


class CalibreMCPPlugin(InterfaceActionBase):
    name = 'Calibre MCP'
    description = (
        'Serves the current library to Claude and other MCP clients over '
        'streamable HTTP on 127.0.0.1. Read-only.'
    )
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Chris Sivori'
    version = (0, 1, 0)
    minimum_calibre_version = (6, 0, 0)

    actual_plugin = 'calibre_plugins.calibre_mcp.ui:MCPAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.calibre_mcp.config import ConfigWidget
        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
        ac = self.actual_plugin_
        if ac is not None:
            ac.restart_server()
