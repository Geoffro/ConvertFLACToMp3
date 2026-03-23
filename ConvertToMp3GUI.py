import os
import zipfile
import shutil
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLineEdit, QLabel, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QFormLayout
)
from ConvertToMp3 import (
    list_flac_files, parse_track_info, clean_album_name, check_ffmpeg,
    convert_flac_to_mp3, detect_artist_from_filenames, all_tracks_numbered
)
import re

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
        self.setGeometry(100, 100, 750, 600)
        self.zip_path = None
        self.unzip_dir = None
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Import zip and output dir
        import_layout = QHBoxLayout()
        self.import_zip_btn = QPushButton("Import .zip")
        self.import_zip_btn.clicked.connect(self.import_zip)
        import_layout.addWidget(self.import_zip_btn)
        self.import_folder_btn = QPushButton("Import Folder")
        self.import_folder_btn.clicked.connect(self.import_folder)
        import_layout.addWidget(self.import_folder_btn)
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
        main_layout.addLayout(btn_layout)

        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def import_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", "")
        if not folder_path:
            return
        self.zip_path = None
        self.unzip_dir = folder_path
        self.output_dir_edit.setText(folder_path)
        self.log(f"Imported folder: {folder_path}")
        self.populate_metadata()
        self.populate_tracks_table()

    def import_zip(self):
        zip_path, _ = QFileDialog.getOpenFileName(self, "Select Zip File", "", "Zip Files (*.zip)")
        if not zip_path:
            return
        self.zip_path = zip_path
        # Determine output dir
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            # Use zip filename (without extension) in the same directory as the zip file
            zip_dir = os.path.dirname(zip_path)
            base = os.path.splitext(os.path.basename(zip_path))[0]
            output_dir = os.path.join(zip_dir, base)
            self.output_dir_edit.setText(output_dir)
        # Create output dir if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.log(f"Failed to create output directory: {output_dir}\n{e}")
            return
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        self.unzip_dir = output_dir
        self.log(f"Unzipped {zip_path} to {output_dir}")
        folder_name = os.path.basename(os.path.normpath(output_dir))
        album = clean_album_name(folder_name)
        self.album_edit.setText(album)
        self.populate_metadata()
        self.populate_tracks_table()

    def find_flac_files_recursive(self, root):
        flac_files = []
        for dirpath, dirnames, filenames in os.walk(root):
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
                if f.lower().endswith('.flac'):
                    flac_files.append((dirpath, f, disk))
        return flac_files


    def populate_tracks_table(self):
        self.tracks_table.setRowCount(0)
        if not self.unzip_dir:
            self.log("No folder loaded. Use Import .zip or Import Folder.")
            return
        flac_files = self.find_flac_files_recursive(self.unzip_dir)
        if not flac_files:
            self.log("No FLAC files found in the selected folder.")
            return
        # Disconnect signal to avoid triggering on item insert
        try:
            self.tracks_table.itemChanged.disconnect()
        except Exception:
            pass
        for i, (dirpath, filename, disk) in enumerate(flac_files):
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
        for filename in list_flac_files(self.unzip_dir):
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
        for row in range(self.tracks_table.rowCount()):
            disk = self.tracks_table.item(row, 0).text()
            track_number = self.tracks_table.item(row, 1).text()
            track_name = self.tracks_table.item(row, 2).text()
            flac_path = self.tracks_table.item(row, 3).text()
            safe_name = re.sub(r'[\\/:"*?<>|]+', '', track_name)
            safe_name = re.sub(r'\s+', ' ', safe_name).strip()
            # Write to mp3/disk-specific subfolder if multiple disks
            if multiple_disks and disk:
                disk_folder = os.path.join(mp3_root, f"Disc {disk}")
                os.makedirs(disk_folder, exist_ok=True)
                mp3_path = os.path.join(disk_folder, f"{safe_name}.mp3")
            else:
                os.makedirs(mp3_root, exist_ok=True)
                mp3_path = os.path.join(mp3_root, f"{safe_name}.mp3")
            if os.path.exists(mp3_path):
                self.log(f"Skipping existing: {mp3_path}")
                continue
            cmd = [
                ffmpeg_path,
                '-i', flac_path,
                '-b:a', bitrate,
                '-y',
                '-metadata', f'artist={artist}',
                '-metadata', f'album={album}'
            ]
            if track_number:
                cmd += ['-metadata', f'track={track_number}']
            # Always write disk number if there are multiple disks and disk is present
            if multiple_disks and disk:
                cmd += ['-metadata', f'disc={disk}']
            cmd += [mp3_path]
            try:
                import subprocess
                self.log(f"Converting: {os.path.basename(flac_path)} -> {mp3_path}")
                QtWidgets.QApplication.processEvents()
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    self.log(f"Converted: {safe_name}.mp3")
                else:
                    self.log(f"Failed to convert {os.path.basename(flac_path)}: {result.stderr.decode().strip()}")
            except Exception as e:
                self.log(f"Failed to convert {os.path.basename(flac_path)}: {e}")
            QtWidgets.QApplication.processEvents()
        self.log("Conversion complete.")
    def log(self, msg):
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()
        QtWidgets.QApplication.processEvents()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = ConvertToMp3GUI()
    window.show()
    sys.exit(app.exec_())
