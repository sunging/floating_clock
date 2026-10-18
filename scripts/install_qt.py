"""Install the pinned Qt SDK using aqt with Qt 6.12's Windows repository layout.

The application is entirely C++; Python is only used by build/deployment tools.
aqt 3.3.0's archive downloader retains checksum verification and relocates qmake.
"""

import os
import sys

from aqt import main
from aqt.archives import QtArchives


def main_with_layout_fix():
    original = QtArchives._arch_ext

    def extension(self):
        if str(self.version) == "6.12.0" and self.os_name == "windows":
            return "_" + self.arch.removeprefix("win64_")
        return original(self)

    QtArchives._arch_ext = extension
    original_xml = QtArchives._download_update_xml

    def update_xml(self, path, silent=False):
        if silent and "/extensions/" in path:
            extension = path.split("/extensions/", 1)[1].split("/", 1)[0]
            if extension not in self.mod_list:
                return None
        return original_xml(self, path, silent)

    QtArchives._download_update_xml = update_xml
    if os.environ.get("FC_AQT_SERIAL") == "1":
        # Some Windows sandboxes cannot create multiprocessing named pipes.
        # Use the same verified downloader/extractor without subprocess workers.
        import aqt.installer as installer
        from aqt.helper import Settings, setup_logging

        original_run = installer.run_installer

        class LogSink:
            def put_nowait(self, record):
                if record.levelno >= 20:
                    print(record.getMessage(), flush=True)

        def serial(archives, base_dir, sevenzip, keep, archive_dest, dry_run=False):
            if dry_run:
                return original_run(archives, base_dir, sevenzip, keep, archive_dest, True)
            for archive in archives:
                installer.installer(
                    archive, base_dir, sevenzip, LogSink(), archive_dest, Settings.configfile, keep
                )
            setup_logging()

        installer.run_installer = serial
    return main()


if __name__ == "__main__":
    sys.exit(main_with_layout_fix())
