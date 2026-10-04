from qt.core import QCheckBox, QFormLayout, QLabel, QSpinBox, QWidget

from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/calibre_mcp')
prefs.defaults['port'] = 8395
prefs.defaults['autostart'] = True


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        layout = QFormLayout(self)

        self.port = QSpinBox(self)
        self.port.setRange(1024, 65535)
        self.port.setValue(prefs['port'])
        layout.addRow('Port:', self.port)

        self.autostart = QCheckBox('Start the server when calibre starts', self)
        self.autostart.setChecked(prefs['autostart'])
        layout.addRow(self.autostart)

        note = QLabel(
            'The server listens on 127.0.0.1 only and never writes to the library.'
        )
        note.setWordWrap(True)
        layout.addRow(note)

    def save_settings(self):
        prefs['port'] = self.port.value()
        prefs['autostart'] = self.autostart.isChecked()
