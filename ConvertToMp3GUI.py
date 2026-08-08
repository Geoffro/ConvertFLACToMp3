import os
import sys
import subprocess
import zipfile
import shutil
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLineEdit, QLabel, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QFormLayout, QToolButton, QMenu, QAction
)
from ConvertToMp3 import (
    AUDIO_EXTENSIONS, list_audio_files, parse_track_info, clean_album_name,
    check_ffmpeg, encoding_args, detect_artist_from_filenames, all_tracks_numbered
)
import re


def add_files_to_music(mp3_paths):
    """Import files into Apple Music via AppleScript.

    Returns (ok, message, locations), where locations are the paths the tracks
    actually ended up at. Those differ from mp3_paths when Music is set to copy
    files into its media folder, and match when it references them in place.
    """
    if sys.platform != 'darwin':
        return False, "Apple Music import is only supported on macOS.", []
    items = ", ".join(
        'POSIX file "%s"' % p.replace('\\', '\\\\').replace('"', '\\"')
        for p in mp3_paths
    )
    script = (
        'tell application "Music"\n'
        '    set added to (add {%s}) as list\n'
        '    set out to ""\n'
        '    repeat with t in added\n'
        '        set out to out & (POSIX path of (get location of t)) & linefeed\n'
        '    end repeat\n'
        '    return out\n'
        'end tell'
    ) % items
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for Apple Music.", []
    except Exception as e:
        return False, str(e), []
    if result.returncode != 0:
        return False, result.stderr.decode().strip(), []
    locations = [l for l in result.stdout.decode().splitlines() if l.strip()]
    return True, "", locations


class ConversionWorker(QtCore.QObject):
    log_message = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, ffmpeg_path, artist, album, bitrate, mp3_root, multiple_disks, tracks):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.artist = artist
        self.album = album
        self.bitrate = bitrate
        self.mp3_root = mp3_root
        self.multiple_disks = multiple_disks
        self.tracks = tracks

    def run(self):
        for track in self.tracks:
            disk = track['disk']
            track_number = track['track_number']
            track_name = track['track_name']
            src_path = track['src_path']
            safe_name = re.sub(r'[\\/:"*?<>|]+', '', track_name)
            safe_name = re.sub(r'\s+', ' ', safe_name).strip()
            if self.multiple_disks and disk:
                disk_folder = os.path.join(self.mp3_root, f"Disc {disk}")
                os.makedirs(disk_folder, exist_ok=True)
                mp3_path = os.path.join(disk_folder, f"{safe_name}.mp3")
            else:
                os.makedirs(self.mp3_root, exist_ok=True)
                mp3_path = os.path.join(self.mp3_root, f"{safe_name}.mp3")
            if os.path.exists(mp3_path):
                self.log_message.emit(f"Skipping existing: {mp3_path}")
                continue
            cmd = [
                self.ffmpeg_path,
                '-i', src_path,
            ] + encoding_args(src_path, self.bitrate) + [
                '-y',
                '-metadata', f'artist={self.artist}',
                '-metadata', f'album={self.album}'
            ]
            if track_number:
                cmd += ['-metadata', f'track={track_number}']
            if self.multiple_disks and disk:
                cmd += ['-metadata', f'disc={disk}']
            cmd += [mp3_path]
            # MP3 sources are stream-copied, so call it copying rather than converting
            verb, past = ('Copying', 'Copied') if src_path.lower().endswith('.mp3') else ('Converting', 'Converted')
            try:
                self.log_message.emit(f"{verb}: {os.path.basename(src_path)} -> {mp3_path}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    self.log_message.emit(f"{past}: {safe_name}.mp3")
                else:
                    self.log_message.emit(f"Failed to process {os.path.basename(src_path)}: {result.stderr.decode().strip()}")
            except Exception as e:
                self.log_message.emit(f"Failed to process {os.path.basename(src_path)}: {e}")
        self.finished.emit()

class ConvertToMp3GUI(QMainWindow):

    def populate_metadata(self):
        # Try to detect artist and album from folder or files
        if not self.unzip_dir:
            return
        # Recursively find the first FLAC file and use its name for artist detection
        # If the user imported a folder (not a zip), use the top-level folder for album
        imported_folder = os.path.basename(os.path.normpath(self.unzip_dir))
        album = clean_album_name(imported_folder)
        self.album_edit.setText(album)
        # Try to detect artist from the first FLAC-containing folder
        for dirpath, _, filenames in os.walk(self.unzip_dir):
            flacs = [f for f in filenames if f.lower().endswith('.flac')]
            if flacs:
                artist = detect_artist_from_filenames(dirpath)
                if artist:
                    self.artist_edit.setText(artist)
                break

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", "")
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self.log(f"Selected output directory: {dir_path}")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ConvertToMp3 - Import and Convert")
        self.setGeometry(100, 100, 1100, 700)
        self.zip_path = None
        self.unzip_dir = None
        self.all_mp3 = False
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Import and output dir
        import_layout = QHBoxLayout()
        self.import_btn = QToolButton()
        self.import_btn.setText("Import Album  ")
        self.import_btn.setPopupMode(QToolButton.InstantPopup)
        import_menu = QMenu()
        import_menu.addAction("Import .zip File", self._import_zip_dialog)
        import_menu.addAction("Import Folder", self._import_folder_dialog)
        self.import_btn.setMenu(import_menu)
        import_layout.addWidget(self.import_btn)
        import_layout.addWidget(QLabel("Unzip to:"))
        self.output_dir_edit = QLineEdit()
        import_layout.addWidget(self.output_dir_edit)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_output_dir)
        import_layout.addWidget(self.browse_btn)
        main_layout.addLayout(import_layout)

        # Metadata group
        meta_group = QGroupBox("Metadata")
        meta_layout = QFormLayout()
        self.artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.bitrate_edit = QLineEdit("192k")
        meta_layout.addRow(QLabel("Artist:"), self.artist_edit)
        meta_layout.addRow(QLabel("Album:"), self.album_edit)
        meta_layout.addRow(QLabel("Bitrate:"), self.bitrate_edit)
        meta_group.setLayout(meta_layout)
        main_layout.addWidget(meta_group)

        # Tracks table
        self.tracks_table = QtWidgets.QTableWidget()
        self.tracks_table.setColumnCount(4)
        self.tracks_table.setHorizontalHeaderLabels(["Disk", "Track #", "Track Name", "Filename"])
        self.tracks_table.horizontalHeader().setStretchLastSection(True)
        self.tracks_table.verticalHeader().setVisible(False)
        main_layout.addWidget(QLabel("Tracks (editable):"))
        main_layout.addWidget(self.tracks_table)

        # Save Changes button (disabled by default)
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_changes)
        main_layout.addWidget(self.save_btn)

        # Buttons
        btn_layout = QHBoxLayout()
        self.conflict_btn = QPushButton("Check for Conflicts")
        self.conflict_btn.clicked.connect(self.check_conflicts)
        btn_layout.addWidget(self.conflict_btn)
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.clicked.connect(self.do_conversion)
        btn_layout.addWidget(self.convert_btn)
        self.music_btn = QPushButton("Add to Apple Music")
        self.music_btn.clicked.connect(self.add_to_apple_music)
        btn_layout.addWidget(self.music_btn)
        main_layout.addLayout(btn_layout)

        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def clear_state(self):
        self.zip_path = None
        self.unzip_dir = None
        self.all_mp3 = False
        self.convert_btn.setEnabled(True)
        self.convert_btn.setToolTip("")
        self.artist_edit.clear()
        self.album_edit.clear()
        self.output_dir_edit.clear()
        try:
            self.tracks_table.itemChanged.disconnect()
        except Exception:
            pass
        self.tracks_table.setRowCount(0)
        self.save_btn.setEnabled(False)
        self.log_text.clear()

    def _import_zip_dialog(self):
        downloads = os.path.expanduser("~/Downloads")
        zip_path, _ = QFileDialog.getOpenFileName(self, "Select Zip File", downloads, "ZIP Files (*.zip)")
        if zip_path:
            self._import_zip(zip_path)

    def _import_folder_dialog(self):
        downloads = os.path.expanduser("~/Downloads")
        folder_path = QFileDialog.getExistingDirectory(self, "Select Album Folder", downloads)
        if folder_path:
            self._import_folder(folder_path)

    def _import_folder(self, folder_path):
        self.clear_state()
        self.unzip_dir = folder_path
        self.output_dir_edit.setText(folder_path)
        self.log(f"Imported folder: {folder_path}")
        self.populate_metadata()
        self.populate_tracks_table()

    def _import_zip(self, zip_path):
        self.clear_state()
        self.zip_path = zip_path
        zip_dir = os.path.dirname(zip_path)
        base = os.path.splitext(os.path.basename(zip_path))[0]
        output_dir = os.path.join(zip_dir, base)
        self.output_dir_edit.setText(output_dir)
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.log(f"Failed to create output directory: {output_dir}\n{e}")
            return
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        self.unzip_dir = output_dir
        self.log(f"Unzipped {zip_path} to {output_dir}")
        self.populate_metadata()
        self.populate_tracks_table()

    def find_audio_files_recursive(self, root):
        audio_files = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Don't pick up our own output as a source when re-importing a folder
            if dirpath == root and 'mp3' in dirnames:
                dirnames.remove('mp3')
            # Disk detection: look for folder names like 'CD1', 'Disc 2', '01', '02', etc.
            disk = None
            disk_patterns = [r'(?:disc|disk|cd)[ _-]?(\d+)', r'^(\d{1,2})$']
            for part in dirpath.split(os.sep):
                for pat in disk_patterns:
                    m = re.match(pat, part, re.IGNORECASE)
                    if m:
                        disk = m.group(1)
                        break
                if disk:
                    break
            for f in filenames:
                if f.lower().endswith(AUDIO_EXTENSIONS):
                    audio_files.append((dirpath, f, disk))
        return audio_files


    def populate_tracks_table(self):
        self.tracks_table.setRowCount(0)
        if not self.unzip_dir:
            self.log("No folder loaded. Use Import .zip or Import Folder.")
            return
        audio_files = self.find_audio_files_recursive(self.unzip_dir)
        if not audio_files:
            self.log("No FLAC or MP3 files found in the selected folder.")
            return
        mp3_sources = sum(1 for _, f, _ in audio_files if f.lower().endswith('.mp3'))
        self.all_mp3 = mp3_sources == len(audio_files)
        if self.all_mp3:
            self.log("Album is already MP3 - nothing to convert. Use Add to Apple Music "
                     "to import these files directly.")
            self.convert_btn.setEnabled(False)
            self.convert_btn.setToolTip("Album is already MP3 - nothing to convert.")
        elif mp3_sources:
            self.log(f"{mp3_sources} of {len(audio_files)} file(s) are already MP3 and will be "
                     f"copied and retagged rather than re-encoded (bitrate does not apply to them).")
        # Disconnect signal to avoid triggering on item insert
        try:
            self.tracks_table.itemChanged.disconnect()
        except Exception:
            pass
        for i, (dirpath, filename, disk) in enumerate(audio_files):
            base = os.path.splitext(filename)[0]
            track_number, track_name = parse_track_info(base)
            self.tracks_table.insertRow(i)
            # Disk
            disk_item = QtWidgets.QTableWidgetItem(str(disk) if disk else "1")
            self.tracks_table.setItem(i, 0, disk_item)
            # Track #
            track_item = QtWidgets.QTableWidgetItem(str(track_number) if track_number else "")
            self.tracks_table.setItem(i, 1, track_item)
            # Track Name (always editable)
            name_item = QtWidgets.QTableWidgetItem(track_name)
            self.tracks_table.setItem(i, 2, name_item)
            # Filename (not editable)
            file_item = QtWidgets.QTableWidgetItem(os.path.join(dirpath, filename))
            file_item.setFlags(file_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.tracks_table.setItem(i, 3, file_item)
        self.tracks_table.itemChanged.connect(self.on_table_item_changed)
        self.save_btn.setEnabled(False)

    def on_table_item_changed(self, item):
        # Enable save button if any item is changed
        self.save_btn.setEnabled(True)

    def save_changes(self):
        # For now, just disable the button again (could add more logic)
        self.save_btn.setEnabled(False)

    def check_conflicts(self):
        output_dir = self.output_dir_edit.text()
        if not output_dir:
            self.log("No output directory specified.")
            return
        if not os.path.exists(output_dir):
            self.log("Output directory does not exist. No conflicts.")
            return
        conflicts = []
        for filename in list_audio_files(self.unzip_dir):
            base = os.path.splitext(filename)[0]
            _, track_name = parse_track_info(base)
            safe_name = re.sub(r'[\\/:"*?<>|]+', '', track_name)
            safe_name = re.sub(r'\s+', ' ', safe_name).strip()
            mp3_path = os.path.join(output_dir, f"{safe_name}.mp3")
            if os.path.exists(mp3_path):
                conflicts.append(mp3_path)
        if conflicts:
            self.log(f"Conflicts found: {len(conflicts)} files will be overwritten.")
            for c in conflicts:
                self.log(f"Conflict: {c}")
        else:
            self.log("No conflicts detected.")

    def do_conversion(self):
        if self.all_mp3:
            self.log("Album is already MP3 - nothing to convert.")
            return
        self.log("Starting conversion...")
        output_dir = self.output_dir_edit.text()
        artist = self.artist_edit.text()
        album = self.album_edit.text()
        bitrate = self.bitrate_edit.text()
        if not self.unzip_dir or not output_dir:
            self.log("Input or output directory not set.")
            return
        if not artist:
            self.log("Artist not set.")
            return
        ffmpeg_path = check_ffmpeg()
        if not ffmpeg_path:
            self.log("ffmpeg not found.")
            return
        # Check if there are multiple disks
        disk_values = set()
        for row in range(self.tracks_table.rowCount()):
            disk = self.tracks_table.item(row, 0).text()
            if disk:
                disk_values.add(disk)
        multiple_disks = len(disk_values) > 1
        mp3_root = os.path.join(output_dir, "mp3")
        tracks = []
        for row in range(self.tracks_table.rowCount()):
            tracks.append({
                'disk': self.tracks_table.item(row, 0).text(),
                'track_number': self.tracks_table.item(row, 1).text(),
                'track_name': self.tracks_table.item(row, 2).text(),
                'src_path': self.tracks_table.item(row, 3).text(),
            })

        self.convert_btn.setEnabled(False)
        self.conversion_thread = QtCore.QThread()
        self.conversion_worker = ConversionWorker(ffmpeg_path, artist, album, bitrate, mp3_root, multiple_disks, tracks)
        self.conversion_worker.moveToThread(self.conversion_thread)
        self.conversion_worker.log_message.connect(self.log)
        self.conversion_worker.finished.connect(self._on_conversion_finished)
        self.conversion_thread.started.connect(self.conversion_worker.run)
        self.conversion_thread.start()

    def _mp3_files_for_import(self):
        """(source_dir, mp3 paths) to hand to Apple Music.

        Prefers converted output, and falls back to the imported album itself
        when it was already MP3 and so never went through conversion.
        """
        output_dir = self.output_dir_edit.text()
        if output_dir:
            mp3_root = os.path.join(output_dir, "mp3")
            if os.path.isdir(mp3_root):
                paths = []
                for dirpath, _, filenames in os.walk(mp3_root):
                    for f in sorted(filenames):
                        if f.lower().endswith('.mp3'):
                            paths.append(os.path.join(dirpath, f))
                if paths:
                    return mp3_root, paths
        if self.unzip_dir:
            paths = sorted(
                os.path.join(d, f)
                for d, f, _ in self.find_audio_files_recursive(self.unzip_dir)
                if f.lower().endswith('.mp3')
            )
            if paths:
                return self.unzip_dir, paths
        return None, []

    def add_to_apple_music(self):
        source_dir, mp3_paths = self._mp3_files_for_import()
        if not mp3_paths:
            self.log("No MP3 files found. Import an album first, and convert it if it is FLAC.")
            return
        self.log(f"Adding {len(mp3_paths)} file(s) to Apple Music from {source_dir}...")
        self.music_btn.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            ok, message, locations = add_files_to_music(mp3_paths)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.music_btn.setEnabled(True)
        if not ok:
            self.log(f"Failed to add files to Apple Music: {message}")
            return
        self.log(f"Added {len(mp3_paths)} file(s) to Apple Music.")
        # Where the tracks landed tells us whether Music copied them into its
        # media folder or is referencing the source files in place.
        sources = {os.path.realpath(p) for p in mp3_paths}
        copied = [l for l in locations if os.path.realpath(l) not in sources]
        if not locations:
            self.log("Could not determine whether Music copied the files.")
        elif copied:
            self.log(f"Music copied the files into its media folder ({os.path.dirname(copied[0])}). "
                     f"{source_dir} is safe to move or delete.")
        else:
            self.log(f"Music is referencing the files in place at {source_dir}. "
                     f"Moving or deleting that folder will break the library entries.")

    def _on_conversion_finished(self):
        self.log("Conversion complete.")
        self.conversion_thread.quit()
        self.conversion_thread.wait()
        self.convert_btn.setEnabled(True)
    def log(self, msg):
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()
        QtWidgets.QApplication.processEvents()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConvertToMp3GUI()
    window.show()
    sys.exit(app.exec_())
