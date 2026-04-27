init -2 python:
    import json
    import math
    import os
    import random
    import re
    import shutil
    import tarfile
    import tempfile
    import time
    import uuid
    from collections import deque

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        tk = None
        filedialog = None

    MS_ROWS = 16
    MS_COLS = 16
    MS_DEFAULT_MINES = 40
    MS_MAX_MINES = MS_ROWS * MS_COLS - 9
    MS_AUDIO_EXTENSIONS = { ".wav", ".ogg", ".mp3" }
    MS_IMAGE_EXTENSIONS = { ".png", ".jpg", ".jpeg", ".bmp", ".webp" }
    MS_DEFAULT_DIALOGUES = [
        {"text": "Careful. The next cell may tell the truth.", "audio_path": None},
        {"text": "Nice move. Keep going.", "audio_path": None},
        {"text": "When you win, the full inner image appears.", "audio_path": None},
    ]

    MS_RESOURCE_ATTRS = [
        "cover_image_path",
        "reveal_image_path",
        "win_audio_path",
        "safe_audio_path",
        "mine_audio_path",
        "bgm_audio_path",
        "play_model_path",
        "win_model_path",
    ]

    def ms_user_root():
        root = getattr(config, "savedir", None) or config.basedir
        path = os.path.join(root, "image_minesweeper_live2d")
        os.makedirs(path, exist_ok=True)
        return path

    def ms_settings_path():
        project_settings = os.path.join(config.basedir, "game", "resource_settings.json")
        if os.path.exists(project_settings):
            return project_settings
        return os.path.join(ms_user_root(), "settings.json")

    def ms_writable_settings_path():
        project_settings = os.path.join(config.basedir, "game", "resource_settings.json")
        if os.path.exists(project_settings):
            return project_settings
        return os.path.join(ms_user_root(), "settings.json")

    def ms_cache_dir():
        path = os.path.join(ms_user_root(), "cache")
        os.makedirs(path, exist_ok=True)
        return path

    def ms_packs_dir():
        path = os.path.join(ms_cache_dir(), "packs")
        os.makedirs(path, exist_ok=True)
        return path

    def ms_file_dialog(kind, title, save=False, default_name="pack.tar"):
        if filedialog is not None:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if kind == "dir":
                value = filedialog.askdirectory(title=title)
            elif save:
                value = filedialog.asksaveasfilename(title=title, initialfile=default_name, defaultextension=".tar", filetypes=[("Tar files", "*.tar"), ("All files", "*.*")])
            else:
                value = filedialog.askopenfilename(title=title, filetypes=[("All files", "*.*")])
            root.destroy()
            return value or None

        if os.name == "nt":
            value = ms_windows_dialog(kind, title, save=save, default_name=default_name)
            if value:
                return value

        prompt = title + " (paste full path)"
        value = renpy.invoke_in_new_context(renpy.input, prompt, length=500)
        value = (value or "").strip()
        return value or None

    def ms_windows_dialog(kind, title, save=False, default_name="pack.tar"):
        if kind == "dir":
            return ms_windows_folder_dialog(title)
        return ms_windows_file_dialog(title, save=save, default_name=default_name)

    def ms_windows_file_dialog(title, save=False, default_name="pack.tar"):
        class OPENFILENAMEW(ctypes.Structure):
            _fields_ = [
                ("lStructSize", wintypes.DWORD),
                ("hwndOwner", wintypes.HWND),
                ("hInstance", wintypes.HINSTANCE),
                ("lpstrFilter", wintypes.LPCWSTR),
                ("lpstrCustomFilter", wintypes.LPWSTR),
                ("nMaxCustFilter", wintypes.DWORD),
                ("nFilterIndex", wintypes.DWORD),
                ("lpstrFile", wintypes.LPWSTR),
                ("nMaxFile", wintypes.DWORD),
                ("lpstrFileTitle", wintypes.LPWSTR),
                ("nMaxFileTitle", wintypes.DWORD),
                ("lpstrInitialDir", wintypes.LPCWSTR),
                ("lpstrTitle", wintypes.LPCWSTR),
                ("Flags", wintypes.DWORD),
                ("nFileOffset", wintypes.WORD),
                ("nFileExtension", wintypes.WORD),
                ("lpstrDefExt", wintypes.LPCWSTR),
                ("lCustData", wintypes.LPARAM),
                ("lpfnHook", wintypes.LPVOID),
                ("lpTemplateName", wintypes.LPCWSTR),
                ("pvReserved", wintypes.LPVOID),
                ("dwReserved", wintypes.DWORD),
                ("FlagsEx", wintypes.DWORD),
            ]

        OFN_EXPLORER = 0x00080000
        OFN_FILEMUSTEXIST = 0x00001000
        OFN_PATHMUSTEXIST = 0x00000800
        OFN_OVERWRITEPROMPT = 0x00000002
        buffer = ctypes.create_unicode_buffer(4096)
        if save:
            buffer.value = default_name
        filters = "All files\0*.*\0Tar files\0*.tar\0Images\0*.png;*.jpg;*.jpeg;*.bmp;*.webp\0Audio\0*.wav;*.ogg;*.mp3\0\0"
        ofn = OPENFILENAMEW()
        ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
        ofn.lpstrFilter = filters
        ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
        ofn.nMaxFile = len(buffer)
        ofn.lpstrTitle = title
        ofn.lpstrDefExt = "tar" if save else None
        ofn.Flags = OFN_EXPLORER | OFN_PATHMUSTEXIST
        if save:
            ofn.Flags |= OFN_OVERWRITEPROMPT
        else:
            ofn.Flags |= OFN_FILEMUSTEXIST
        dialog = ctypes.windll.comdlg32.GetSaveFileNameW if save else ctypes.windll.comdlg32.GetOpenFileNameW
        if dialog(ctypes.byref(ofn)):
            return buffer.value
        return None

    def ms_windows_folder_dialog(title):
        class BROWSEINFOW(ctypes.Structure):
            _fields_ = [
                ("hwndOwner", wintypes.HWND),
                ("pidlRoot", wintypes.LPVOID),
                ("pszDisplayName", wintypes.LPWSTR),
                ("lpszTitle", wintypes.LPCWSTR),
                ("ulFlags", wintypes.UINT),
                ("lpfn", wintypes.LPVOID),
                ("lParam", wintypes.LPARAM),
                ("iImage", ctypes.c_int),
            ]

        BIF_RETURNONLYFSDIRS = 0x00000001
        BIF_NEWDIALOGSTYLE = 0x00000040
        display_name = ctypes.create_unicode_buffer(260)
        browse = BROWSEINFOW()
        browse.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
        browse.lpszTitle = title
        browse.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE
        pidl = ctypes.windll.shell32.SHBrowseForFolderW(ctypes.byref(browse))
        if not pidl:
            return None
        path = ctypes.create_unicode_buffer(4096)
        ok = ctypes.windll.shell32.SHGetPathFromIDListW(pidl, path)
        try:
            ctypes.windll.ole32.CoTaskMemFree(pidl)
        except Exception:
            pass
        return path.value if ok else None

    def ms_commonpath_inside(path, root):
        try:
            return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
        except Exception:
            return False

    def ms_blend_parameter(live2d, name, blend, value, weight=1.0):
        try:
            live2d.blend_parameter(name, blend, value, weight)
        except Exception:
            pass

    def ms_sanitize_motion_attribute(name):
        name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(name).lower()).strip("_")
        if not name:
            name = "motion"
        if name[0].isdigit():
            name = "m_" + name
        return name

    def ms_live2d_motion_name(model_name, file_name):
        name = os.path.basename(file_name).lower().partition(".")[0]
        prefix, _sep, suffix = name.partition("_")
        if prefix == model_name:
            name = suffix
        return name

    def ms_live2d_has_motion(live2d):
        try:
            return bool(getattr(live2d, "motions", None))
        except Exception:
            return False

    class MSLocalTimeDisplayable(renpy.display.displayable.Displayable):
        def __init__(self, child, started_at=None, finished_child=None, duration=0.0):
            super(MSLocalTimeDisplayable, self).__init__()
            self.child = child
            self.started_at = started_at
            self.finished_child = finished_child
            self.duration = duration

        def render(self, width, height, st, at):
            if self.started_at is None:
                child_st = st
            else:
                child_st = max(0.0, time.time() - self.started_at)
            child = self.child
            if self.finished_child is not None and self.duration > 0.0 and child_st >= self.duration:
                child = self.finished_child
            rv = renpy.render(child, width, height, child_st, at)
            renpy.redraw(self, 1.0 / 30.0)
            return rv

        def visit(self):
            if self.finished_child is not None:
                return [self.child, self.finished_child]
            return [self.child]

    def ms_live2d_update(live2d, st):
        app = getattr(store, "ms_active_app", None)
        if app is None:
            return 1.0 / 30.0

        if ms_live2d_has_motion(live2d):
            return 1.0 / 30.0

        breath = math.sin(st * 2.0) * 0.45 + 0.45
        slow = math.sin(st * 0.85)
        eye = math.sin(st * 1.15)

        ms_blend_parameter(live2d, "ParamBreath", "Overwrite", breath, 0.8)
        ms_blend_parameter(live2d, "ParamAngleX", "Overwrite", slow * 8.0 + app.model_look_x, 0.65)
        ms_blend_parameter(live2d, "ParamAngleY", "Overwrite", math.sin(st * 0.65) * 5.0 + app.model_look_y, 0.65)
        ms_blend_parameter(live2d, "ParamAngleZ", "Overwrite", math.sin(st * 0.55) * 4.0, 0.45)
        ms_blend_parameter(live2d, "ParamBodyAngleX", "Overwrite", slow * 4.0, 0.5)
        ms_blend_parameter(live2d, "ParamEyeBallX", "Overwrite", eye * 0.45, 0.6)
        ms_blend_parameter(live2d, "ParamEyeBallY", "Overwrite", math.sin(st * 0.9) * 0.18, 0.5)

        if app.model_reaction_remaining > 0.0:
            app.model_reaction_remaining = max(0.0, app.model_reaction_remaining - (1.0 / 30.0))
            amount = min(1.0, app.model_reaction_remaining * 2.0)
            ms_blend_parameter(live2d, "ParamMouthOpenY", "Overwrite", 0.75 * amount, 0.8)
            ms_blend_parameter(live2d, "ParamAngleX", "Add", app.model_reaction_x * amount, 0.75)
            ms_blend_parameter(live2d, "ParamAngleY", "Add", app.model_reaction_y * amount, 0.75)

        return 1.0 / 30.0

    class MinesweeperRenpyApp(object):
        rows = MS_ROWS
        cols = MS_COLS

        def __init__(self):
            self.board_area = (32, 92, 560, 560)
            self.message = "Settings loaded"
            self.mine_count = MS_DEFAULT_MINES
            self.active_mine_count = MS_DEFAULT_MINES
            self.cover_opacity = 255
            self.reveal_opacity = 255
            self.mine_style = "O"
            self.cover_image_path = None
            self.reveal_image_path = None
            self.win_audio_path = None
            self.safe_audio_path = None
            self.mine_audio_path = None
            self.bgm_audio_path = None
            self.play_model_path = None
            self.win_model_path = None
            self.play_model_status = None
            self.win_model_status = None
            self._image_displayable_cache = {}
            self._image_size_cache = {}
            self.dialogues = [dict(item) for item in MS_DEFAULT_DIALOGUES]
            self.current_line = "Click the model or dialogue box for a random line."
            self.bgm_playing = False
            self.bgm_paused = False
            self.model_look_x = 0.0
            self.model_look_y = 0.0
            self.model_reaction_x = 0.0
            self.model_reaction_y = 0.0
            self.model_reaction_remaining = 0.0
            self.play_model_image_name = "ms_live2d_play"
            self.win_model_image_name = "ms_live2d_win"
            self.play_model_motion = None
            self.win_model_motion = None
            self.play_model_motion_bag = []
            self.win_model_motion_bag = []
            self.play_model_motion_until = 0.0
            self.play_model_motion_started = 0.0
            self.model_x = 940
            self.model_y = 80
            self.model_scale = 1.0
            store.ms_active_app = self
            self.load_settings()
            self.reset_board()
            self.update_board_layout()

        def settings_data(self):
            return {
                "mine_count": self.mine_count,
                "cover_opacity": self.cover_opacity,
                "reveal_opacity": self.reveal_opacity,
                "mine_style": self.mine_style,
                "cover_image_path": self.cover_image_path,
                "reveal_image_path": self.reveal_image_path,
                "win_audio_path": self.win_audio_path,
                "safe_audio_path": self.safe_audio_path,
                "mine_audio_path": self.mine_audio_path,
                "bgm_audio_path": self.bgm_audio_path,
                "play_model_path": self.play_model_path,
                "win_model_path": self.win_model_path,
                "play_model_status": self.play_model_status,
                "win_model_status": self.win_model_status,
                "dialogues": self.dialogues,
                "model_x": self.model_x,
                "model_y": self.model_y,
                "model_scale": self.model_scale,
            }

        def save_settings(self):
            with open(ms_writable_settings_path(), "w", encoding="utf-8") as f:
                json.dump(self.settings_data(), f, ensure_ascii=False, indent=2)

        def load_settings(self):
            path = ms_settings_path()
            if not os.path.exists(path):
                self.save_settings()
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                self.message = "Settings could not be read"
                return
            self.mine_count = self.clamp(data.get("mine_count", MS_DEFAULT_MINES), 1, MS_MAX_MINES)
            self.cover_opacity = self.clamp(data.get("cover_opacity", 255), 0, 255)
            self.reveal_opacity = self.clamp(data.get("reveal_opacity", 255), 0, 255)
            self.mine_style = data.get("mine_style", "O") if data.get("mine_style", "O") in ("O", "X", "#") else "O"
            for attr in MS_RESOURCE_ATTRS:
                setattr(self, attr, data.get(attr))
            self.play_model_status = data.get("play_model_status")
            self.win_model_status = data.get("win_model_status")
            self.play_model_motion = None
            self.play_model_motion_until = 0.0
            self.play_model_motion_started = 0.0
            self.win_model_motion = self.pick_default_motion_from_status(self.win_model_status)
            self.dialogues = self.clean_dialogues(data.get("dialogues") or self.dialogues)
            self.model_x = self.clamp(data.get("model_x", self.model_x), -460, 1200)
            self.model_y = self.clamp(data.get("model_y", self.model_y), -520, 660)
            self.model_scale = self.clamp_float(data.get("model_scale", self.model_scale), 0.45, 1.8)
            cleared = self.clear_missing_paths()
            if cleared:
                self.save_settings()
                self.message = "Missing resources cleared: " + ", ".join(cleared)

        def pick_default_motion_from_status(self, status):
            motions = [name for name in ((status or {}).get("motions") or []) if name]
            if not motions:
                return None
            for needle in ("idle", "loop", "wait", "mtn_idle", "motion"):
                for index, name in enumerate(motions):
                    if needle in name:
                        return "motion_%d" % index
            return "motion_0"

        def clean_dialogues(self, dialogues):
            cleaned = []
            for item in dialogues:
                text = item.get("text", "")
                if not isinstance(text, str) or any(ord(ch) > 127 for ch in text):
                    continue
                cleaned.append({"text": text, "audio_path": item.get("audio_path")})
            return cleaned or [dict(item) for item in MS_DEFAULT_DIALOGUES]

        def clamp(self, value, low, high):
            try:
                value = int(value)
            except Exception:
                value = low
            return max(low, min(high, value))

        def clamp_float(self, value, low, high):
            try:
                value = float(value)
            except Exception:
                value = low
            return max(low, min(high, value))

        def reset_board(self):
            self.mines = set()
            self.revealed = set()
            self.flagged = set()
            self.numbers = [[0 for c in range(self.cols)] for r in range(self.rows)]
            self.first_click = True
            self.game_over = False
            self.won = False

        def start_game(self):
            self.active_mine_count = self.mine_count
            self.reset_board()
            self.play_model_motion = None
            self.play_model_motion_until = 0.0
            self.play_model_motion_started = 0.0
            self.update_board_layout()
            self.message = "Left click reveal, right click flag"
            renpy.restart_interaction()

        def place_mines(self, safe_cell):
            safe = set([safe_cell])
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr = safe_cell[0] + dr
                    nc = safe_cell[1] + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        safe.add((nr, nc))
            candidates = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in safe]
            self.mines = set(random.sample(candidates, self.active_mine_count))
            for r in range(self.rows):
                for c in range(self.cols):
                    self.numbers[r][c] = self.count_adjacent_mines(r, c)

        def count_adjacent_mines(self, row, col):
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    if (row + dr, col + dc) in self.mines:
                        count += 1
            return count

        def reveal_cell(self, row, col):
            if self.game_over or self.won or (row, col) in self.flagged or (row, col) in self.revealed:
                return
            if self.first_click:
                self.place_mines((row, col))
                self.first_click = False
            if (row, col) in self.mines:
                self.revealed.add((row, col))
                self.game_over = True
                self.message = "Mine hit. Press Start to retry"
                self.trigger_model_reaction()
                self.play_event_audio("mine_audio_path")
                renpy.restart_interaction()
                return
            before = len(self.revealed)
            self.flood_reveal(row, col)
            if len(self.revealed) > before:
                self.trigger_model_reaction()
                self.play_event_audio("safe_audio_path")
            self.check_win()
            renpy.restart_interaction()

        def flood_reveal(self, row, col):
            queue = deque([(row, col)])
            while queue:
                r, c = queue.popleft()
                if (r, c) in self.revealed or (r, c) in self.flagged:
                    continue
                self.revealed.add((r, c))
                if self.numbers[r][c] != 0:
                    continue
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr = r + dr
                        nc = c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols and (nr, nc) not in self.mines:
                            queue.append((nr, nc))

        def toggle_flag(self, row, col):
            if self.game_over or self.won or (row, col) in self.revealed:
                return
            if (row, col) in self.flagged:
                self.flagged.remove((row, col))
            else:
                self.flagged.add((row, col))
            self.trigger_model_reaction()
            renpy.restart_interaction()

        def check_win(self):
            if len(self.revealed) == self.rows * self.cols - self.active_mine_count:
                self.won = True
                self.message = "Cleared. Full reveal image is shown."
                self.trigger_model_reaction()
                self.play_event_audio("win_audio_path")

        def image_dimensions(self, path):
            displayable = self.image_displayable(path)
            if displayable is None:
                return None
            cache_key = self.image_cache_key(path)
            if cache_key in self._image_size_cache:
                return self._image_size_cache[cache_key]
            try:
                size = renpy.image_size(displayable)
                self._image_size_cache[cache_key] = size
                return size
            except Exception:
                return None

        def update_board_layout(self):
            source = self.cover_image_path or self.reveal_image_path
            dims = self.image_dimensions(source)
            aspect = 1.0
            if dims:
                aspect = float(dims[0]) / max(1, dims[1])
            ax, ay, aw, ah = self.board_area
            if aspect >= 1:
                self.board_w = aw
                self.board_h = max(1, int(round(aw / aspect)))
            else:
                self.board_h = ah
                self.board_w = max(1, int(round(ah * aspect)))
            self.board_x = ax + (aw - self.board_w) // 2
            self.board_y = ay + (ah - self.board_h) // 2

        def cell_geometry(self, row, col):
            left = int(round(col * self.board_w / float(self.cols)))
            right = int(round((col + 1) * self.board_w / float(self.cols)))
            top = int(round(row * self.board_h / float(self.rows)))
            bottom = int(round((row + 1) * self.board_h / float(self.rows)))
            return left, top, max(1, right - left), max(1, bottom - top)

        def crop_geometry(self, path, row, col):
            dims = self.image_dimensions(path)
            if not dims:
                return (0, 0, 1, 1)
            iw, ih = dims
            left = int(round(col * iw / float(self.cols)))
            right = int(round((col + 1) * iw / float(self.cols)))
            top = int(round(row * ih / float(self.rows)))
            bottom = int(round((row + 1) * ih / float(self.rows)))
            return (left, top, max(1, right - left), max(1, bottom - top))

        def image_displayable(self, path):
            if path and self.resource_exists(path):
                cache_key = self.image_cache_key(path)
                cached = self._image_displayable_cache.get(cache_key)
                if cached is not None:
                    return cached
                try:
                    displayable = Image(self.resource_renpy_path(path))
                    self._image_displayable_cache[cache_key] = displayable
                    return displayable
                except Exception as exc:
                    self.message = "Image load failed: %s" % exc
                    return None
            return None

        def image_cache_key(self, path):
            try:
                abs_path = self.resource_abs_path(path)
                return (os.path.abspath(abs_path), os.path.getmtime(abs_path), os.path.getsize(abs_path))
            except Exception:
                return (path or "", 0, 0)

        def resource_abs_path(self, path):
            if not path:
                return None
            if os.path.isabs(path):
                return path
            return os.path.join(config.basedir, "game", path.replace("/", os.sep))

        def resource_renpy_path(self, path):
            if not path:
                return None
            if os.path.isabs(path):
                return path.replace("\\", "/")
            return path.replace("\\", "/")

        def resource_exists(self, path):
            abs_path = self.resource_abs_path(path)
            return bool(abs_path and os.path.exists(abs_path))

        def cell_view(self, row, col):
            x, y, w, h = self.cell_geometry(row, col)
            cell = (row, col)
            show_mine = self.game_over and cell in self.mines
            revealed = cell in self.revealed or show_mine
            path = self.reveal_image_path if revealed else self.cover_image_path
            return {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "image_displayable": self.image_displayable(path) if path and self.resource_exists(path) else None,
                "crop": self.crop_geometry(path, row, col) if path else (0, 0, 1, 1),
                "alpha": (self.reveal_opacity if revealed else self.cover_opacity) / 255.0,
                "fallback": "#373d48" if revealed else "#485d78",
                "flag": (not revealed) and cell in self.flagged,
                "mine": show_mine,
                "number": 0 if show_mine or not revealed else self.numbers[row][col],
                "number_color": self.number_color(self.numbers[row][col]),
            }

        def number_color(self, n):
            return {
                1: "#4096ff", 2: "#46be6e", 3: "#f05c5c", 4: "#846ce8",
                5: "#ec913e", 6: "#40c8c8", 7: "#dddddd", 8: "#9199a6",
            }.get(n, "#eef1f5")

        def short_path(self, path):
            return os.path.basename(path) if path else "not set"

        def resource_status(self, path):
            if not path:
                return "not set"
            if self.resource_exists(path):
                return "found"
            return "missing"

        def audio_files_in_directory(self, path):
            path = self.resource_abs_path(path)
            if not path or not os.path.isdir(path):
                return []
            files = []
            for current, _dirs, names in os.walk(path):
                for name in names:
                    full = os.path.join(current, name)
                    if os.path.isfile(full) and os.path.splitext(name)[1].lower() in MS_AUDIO_EXTENSIONS:
                        files.append(self.audio_renpy_path(full))
            return files

        def audio_renpy_path(self, abs_path):
            game_root = os.path.join(config.basedir, "game")
            try:
                if os.path.commonpath([os.path.abspath(abs_path), os.path.abspath(game_root)]) == os.path.abspath(game_root):
                    return os.path.relpath(abs_path, game_root).replace("\\", "/")
            except Exception:
                pass
            return abs_path.replace("\\", "/")

        def random_audio_path(self, path):
            if not path:
                return None
            abs_path = self.resource_abs_path(path)
            if os.path.isdir(abs_path):
                files = self.audio_files_in_directory(path)
                return random.choice(files) if files else None
            return self.audio_renpy_path(abs_path) if abs_path and os.path.exists(abs_path) else None

        def play_event_audio(self, attr):
            path = self.random_audio_path(getattr(self, attr))
            if not path:
                return
            renpy.music.stop(channel="sound")
            try:
                renpy.sound.play(path, channel="sound")
            except Exception as exc:
                self.message = "Audio play failed: %s" % exc

        def toggle_bgm(self):
            if self.bgm_playing:
                renpy.music.set_pause(True, channel="music")
                self.bgm_playing = False
                self.bgm_paused = True
                self.message = "BGM paused"
            else:
                path = self.random_audio_path(self.bgm_audio_path)
                if not path:
                    self.message = "BGM is not set"
                elif self.bgm_paused:
                    renpy.music.set_pause(False, channel="music")
                    self.bgm_playing = True
                    self.bgm_paused = False
                    self.message = "BGM playing"
                else:
                    try:
                        renpy.music.play(path, channel="music", loop=True)
                        self.bgm_playing = True
                        self.message = "BGM playing"
                    except Exception as exc:
                        self.message = "BGM play failed: %s" % exc
            renpy.restart_interaction()

        def model_kind(self, path):
            abs_path = self.resource_abs_path(path)
            if not abs_path or not os.path.exists(abs_path):
                return None
            if os.path.isfile(abs_path):
                lower = abs_path.lower()
                if lower.endswith(".model3.json"):
                    return "moc3"
                if lower.endswith(".moc") or lower.endswith(".moc2"):
                    return "moc2"
            if os.path.isdir(abs_path):
                model3 = self.find_model_file(abs_path, lambda name: name.lower().endswith(".model3.json"))
                if model3:
                    return "moc3"
                moc2 = self.find_model_file(abs_path, lambda name: name.lower().endswith((".moc", ".moc2")))
                if moc2:
                    return "moc2"
            return None

        def find_model_file(self, root, predicate):
            if os.path.isfile(root):
                return root if predicate(os.path.basename(root)) else None
            for current, _dirs, files in os.walk(root):
                for name in files:
                    if predicate(name):
                        return os.path.join(current, name)
            return None

        def model_entry_path(self, path):
            abs_path = self.resource_abs_path(path)
            if not abs_path or not os.path.exists(abs_path):
                return None
            if os.path.isfile(abs_path):
                return self.resource_renpy_path(path)
            if os.path.isdir(abs_path):
                found = self.find_model_file(abs_path, lambda name: name.lower().endswith(".model3.json"))
                if found:
                    if os.path.isabs(path):
                        return found.replace("\\", "/")
                    relative = os.path.relpath(found, os.path.join(config.basedir, "game"))
                    return relative.replace("\\", "/")
            return None

        def model_entry_abs_path(self, path):
            entry = self.model_entry_path(path)
            if not entry:
                return None
            if os.path.isabs(entry):
                return entry
            return os.path.join(config.basedir, "game", entry.replace("/", os.sep))

        def motion_attribute_name(self, raw_name, model_entry):
            name = os.path.basename(raw_name).lower().partition(".")[0]
            model_name = os.path.basename(model_entry).lower().partition(".")[0]
            prefix, _sep, suffix = name.partition("_")
            if prefix == model_name:
                name = suffix
            return ms_sanitize_motion_attribute(name)

        def model_motion_names(self, path):
            entry_abs = self.model_entry_abs_path(path)
            if not entry_abs or not os.path.exists(entry_abs):
                return []
            try:
                with open(entry_abs, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except Exception:
                return []
            motions = data.get("FileReferences", {}).get("Motions", {})
            names = []
            for _group, items in motions.items():
                for item in items:
                    file_name = item.get("File") or item.get("file")
                    if file_name:
                        names.append("motion_%d" % len(names))
            return names

        def model_motion_raw_names(self, path):
            entry_abs = self.model_entry_abs_path(path)
            if not entry_abs or not os.path.exists(entry_abs):
                return []
            try:
                with open(entry_abs, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except Exception:
                return []
            model_name = os.path.basename(entry_abs).lower().partition(".")[0]
            names = []
            motions = data.get("FileReferences", {}).get("Motions", {})
            for _group, items in motions.items():
                for item in items:
                    file_name = item.get("File") or item.get("file")
                    if file_name:
                        names.append(ms_live2d_motion_name(model_name, file_name))
            return names

        def model_motion_raw_name(self, path, motion):
            names = self.model_motion_names(path)
            raw_names = self.model_motion_raw_names(path)
            if motion in names:
                index = names.index(motion)
                if index < len(raw_names):
                    return raw_names[index]
            return None

        def pick_default_motion(self, path):
            names = self.model_motion_names(path)
            if not names:
                return None
            for needle in ("idle", "loop", "wait", "mtn_idle", "motion"):
                for name in names:
                    if needle in name:
                        return name
            return names[0]

        def model_displayable(self):
            path = self.win_model_path if self.won and self.win_model_path else self.play_model_path
            status = self.win_model_status if self.won and self.win_model_path else self.play_model_status
            kind = self.model_kind(path)
            if kind == "moc3" and getattr(renpy, "has_live2d", lambda: False)():
                should_loop = bool(self.won and self.win_model_path)
                motion = self.win_model_motion if self.won and self.win_model_path else self.play_model_motion
                if not self.won and motion and time.time() >= self.play_model_motion_until:
                    self.play_model_motion = None
                    self.play_model_motion_until = 0.0
                    self.play_model_motion_started = 0.0
                    motion = None
                entry = self.model_entry_path(path)
                if entry:
                    raw_motion = self.model_motion_raw_name(path, motion) if motion else None
                    motions = [raw_motion] if raw_motion else None
                    child = Live2D(entry, zoom=0.22, loop=should_loop, motions=motions, update_function=ms_live2d_update)
                    if raw_motion and not should_loop:
                        idle_child = Live2D(entry, zoom=0.22, loop=False, update_function=ms_live2d_update)
                        duration = max(0.0, self.play_model_motion_until - self.play_model_motion_started)
                        return MSLocalTimeDisplayable(child, self.play_model_motion_started, idle_child, duration)
                    return child
                return Text("Live2D image was not generated.\nRun resource_loader.py again.", color="#eef1f5", size=18, text_align=0.5)
            if kind == "moc2":
                return Text("moc2 model imported\nRen'Py native Live2D renders moc3/model3.json only", color="#eef1f5", size=18, text_align=0.5)
            if status:
                return Text("Live2D model status:\n%s" % status.get("status", "unknown"), color="#eef1f5", size=18, text_align=0.5)
            return Text("Click here after setting a Live2D model", color="#eef1f5", size=18, text_align=0.5)

        def model_box_size(self):
            return (int(round(310 * self.model_scale)), int(round(440 * self.model_scale)))

        def adjust_model_scale(self, delta):
            self.model_scale = self.clamp_float(self.model_scale + delta, 0.45, 1.8)
            self.save_settings()
            renpy.restart_interaction()

        def model_dragged(self, drags, drop):
            if not drags:
                return None
            drag = drags[0]
            self.model_x = self.clamp(getattr(drag, "x", self.model_x), -460, 1200)
            self.model_y = self.clamp(getattr(drag, "y", self.model_y), -520, 660)
            self.save_settings()
            return None

        def model_clicked(self, drag):
            self.random_dialogue()
            return None

        def model_debug_text(self):
            path = self.win_model_path if self.won and self.win_model_path else self.play_model_path
            if not path:
                return "model: not set"
            kind = self.model_kind(path) or "unknown"
            entry = self.model_entry_path(path) or "no model3.json"
            live2d = "live2d yes" if getattr(renpy, "has_live2d", lambda: False)() else "live2d no"
            motion = self.win_model_motion if self.won and self.win_model_path else self.play_model_motion
            raw_motion = self.model_motion_raw_name(path, motion) if motion else None
            return "%s | %s | %s | motion %s -> %s" % (kind, live2d, os.path.basename(entry), motion or "none", raw_motion or "none")

        def random_dialogue(self):
            if not self.dialogues:
                self.current_line = "No dialogue lines configured."
                renpy.restart_interaction()
                return
            item = random.choice(self.dialogues)
            self.current_line = item.get("text") or ""
            self.trigger_model_reaction()
            path = self.random_audio_path(item.get("audio_path"))
            if path:
                renpy.music.stop(channel="voice")
                try:
                    renpy.sound.play(path, channel="voice")
                except Exception as exc:
                    self.message = "Voice play failed: %s" % exc
            renpy.restart_interaction()

        def trigger_model_reaction(self):
            self.cycle_model_motion()
            self.model_look_x = random.uniform(-7.0, 7.0)
            self.model_look_y = random.uniform(-4.0, 4.0)
            self.model_reaction_x = random.uniform(-10.0, 10.0)
            self.model_reaction_y = random.uniform(3.0, 8.0)
            self.model_reaction_remaining = 1.1

        def cycle_model_motion(self):
            if self.won and self.win_model_path:
                self.win_model_motion = self.next_random_model_motion(
                    self.win_model_path,
                    self.win_model_motion,
                    "win_model_motion_bag",
                )
                raw_motion = self.model_motion_raw_name(self.win_model_path, self.win_model_motion)
                self.message = "Live2D motion: %s" % (raw_motion or self.win_model_motion or "none")
            else:
                motion = self.next_random_model_motion(
                    self.play_model_path,
                    self.play_model_motion,
                    "play_model_motion_bag",
                )
                self.play_model_motion = motion
                duration = self.model_motion_duration(self.play_model_path, motion)
                self.play_model_motion_started = time.time()
                self.play_model_motion_until = self.play_model_motion_started + duration
                raw_motion = self.model_motion_raw_name(self.play_model_path, motion)
                self.message = "Live2D motion: %s (%.1fs)" % (raw_motion or motion or "none", duration)

        def next_random_model_motion(self, path, current, bag_attr):
            names = self.model_motion_names(path)
            if not names:
                return current
            bag = [name for name in getattr(self, bag_attr, []) if name in names]
            if not bag:
                bag = list(names)
                random.shuffle(bag)
                if current in bag and len(bag) > 1 and bag[-1] == current:
                    bag[0], bag[-1] = bag[-1], bag[0]
            motion = bag.pop()
            setattr(self, bag_attr, bag)
            return motion

        def model_motion_duration(self, path, motion):
            names = self.model_motion_names(path)
            if motion not in names:
                return 2.0
            entry_abs = self.model_entry_abs_path(path)
            if not entry_abs or not os.path.exists(entry_abs):
                return 2.0
            try:
                with open(entry_abs, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except Exception:
                return 2.0
            index = names.index(motion)
            files = []
            for _group, items in data.get("FileReferences", {}).get("Motions", {}).items():
                for item in items:
                    file_name = item.get("File") or item.get("file")
                    if file_name:
                        files.append(file_name)
            if index >= len(files):
                return 2.0
            motion_path = os.path.join(os.path.dirname(entry_abs), files[index].replace("/", os.sep))
            try:
                with open(motion_path, "r", encoding="utf-8-sig") as f:
                    motion_data = json.load(f)
                return self.clamp_float(motion_data.get("Meta", {}).get("Duration", 2.0), 0.5, 30.0)
            except Exception:
                return 2.0

        def pick_resource_file(self, attr, kind, should_copy):
            path = ms_file_dialog("file", "Select " + attr)
            if not path:
                return
            if kind == "image" and os.path.splitext(path)[1].lower() not in MS_IMAGE_EXTENSIONS:
                self.message = "Unsupported image file"
                return
            if kind == "audio" and os.path.splitext(path)[1].lower() not in MS_AUDIO_EXTENSIONS:
                self.message = "Unsupported audio file"
                return
            stored = self.copy_to_cache(path, attr) if should_copy else path
            setattr(self, attr, stored)
            self.update_board_layout()
            self.save_settings()
            self.message = attr + " saved"
            renpy.restart_interaction()

        def pick_audio_directory(self, attr, should_copy):
            path = ms_file_dialog("dir", "Select audio directory")
            if not path:
                return
            if not self.audio_files_in_directory(path):
                self.message = "No supported audio files found"
                return
            stored = self.copy_to_cache(path, attr) if should_copy else path
            setattr(self, attr, stored)
            self.save_settings()
            self.message = attr + " directory saved"
            renpy.restart_interaction()

        def pick_model(self, target):
            path = ms_file_dialog("dir", "Select Live2D model directory or cancel and paste path")
            if not path:
                path = ms_file_dialog("file", "Select Live2D model file")
            if not path:
                return
            kind = self.model_kind(path)
            if kind is None:
                self.message = "No supported model marker found"
                return
            attr = "play_model_path" if target == "play" else "win_model_path"
            setattr(self, attr, self.copy_to_cache(path, attr))
            self.save_settings()
            self.message = "%s model saved (%s)" % (target, kind)
            renpy.restart_interaction()

        def add_dialogue_line(self):
            text = renpy.invoke_in_new_context(renpy.input, "Dialogue text", length=300)
            text = (text or "").strip()
            if not text:
                return
            audio = ms_file_dialog("file", "Optional dialogue audio")
            if audio and os.path.splitext(audio)[1].lower() in MS_AUDIO_EXTENSIONS:
                audio = self.copy_to_cache(audio, "dialogue_audio")
            else:
                audio = None
            self.dialogues.append({"text": text, "audio_path": audio})
            self.save_settings()
            self.message = "Dialogue line added"
            renpy.restart_interaction()

        def clear_resource(self, attr):
            setattr(self, attr, None)
            self.update_board_layout()
            self.save_settings()
            self.message = attr + " cleared"
            renpy.restart_interaction()

        def adjust_mines(self, delta):
            self.mine_count = self.clamp(self.mine_count + delta, 1, MS_MAX_MINES)
            self.save_settings()
            renpy.restart_interaction()

        def adjust_opacity(self, target, delta):
            if target == "cover":
                self.cover_opacity = self.clamp(self.cover_opacity + delta, 0, 255)
            else:
                self.reveal_opacity = self.clamp(self.reveal_opacity + delta, 0, 255)
            self.save_settings()
            renpy.restart_interaction()

        def set_mine_style(self, style):
            self.mine_style = style
            self.save_settings()
            renpy.restart_interaction()

        def reset_defaults(self):
            renpy.music.stop(channel="sound")
            renpy.music.stop(channel="music")
            renpy.music.stop(channel="voice")
            self.__init__()
            for attr in MS_RESOURCE_ATTRS:
                setattr(self, attr, None)
            self.dialogues = []
            self.mine_count = MS_DEFAULT_MINES
            self.cover_opacity = 255
            self.reveal_opacity = 255
            self.mine_style = "O"
            self.model_x = 940
            self.model_y = 80
            self.model_scale = 1.0
            self.save_settings()
            self.message = "Settings reset to defaults"
            renpy.restart_interaction()

        def clear_cache(self):
            renpy.music.stop(channel="sound")
            renpy.music.stop(channel="music")
            renpy.music.stop(channel="voice")
            cache = ms_cache_dir()
            cleared = []
            for attr in MS_RESOURCE_ATTRS:
                path = getattr(self, attr)
                if path and ms_commonpath_inside(path, cache):
                    setattr(self, attr, None)
                    cleared.append(attr)
            for item in self.dialogues:
                path = item.get("audio_path")
                if path and ms_commonpath_inside(path, cache):
                    item["audio_path"] = None
            for name in os.listdir(cache):
                full = os.path.join(cache, name)
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
            os.makedirs(ms_packs_dir(), exist_ok=True)
            self.update_board_layout()
            self.save_settings()
            self.message = "Cache cleared"
            if cleared:
                self.message += "; cached settings reset"
            renpy.restart_interaction()

        def clear_missing_paths(self):
            cleared = []
            for attr in MS_RESOURCE_ATTRS:
                path = getattr(self, attr)
                if path and not self.resource_exists(path):
                    setattr(self, attr, None)
                    cleared.append(attr)
            for item in self.dialogues:
                path = item.get("audio_path")
                if path and not self.resource_exists(path):
                    item["audio_path"] = None
                    cleared.append("dialogue_audio")
            return cleared

        def copy_to_cache(self, path, label):
            root = os.path.join(ms_cache_dir(), label + "_" + uuid.uuid4().hex)
            if os.path.isdir(path):
                shutil.copytree(path, root)
                return root
            os.makedirs(root, exist_ok=True)
            target = os.path.join(root, os.path.basename(path))
            shutil.copy2(path, target)
            return target

        def export_pack(self):
            target = ms_file_dialog("file", "Export pack", save=True, default_name="minesweeper_live2d_pack.tar")
            if not target:
                return
            try:
                with tempfile.TemporaryDirectory(dir=ms_cache_dir()) as work:
                    metadata = self.build_pack(work)
                    with open(os.path.join(work, "metadata.json"), "w", encoding="utf-8") as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=2)
                    with tarfile.open(target, "w") as tar:
                        tar.add(os.path.join(work, "metadata.json"), arcname="metadata.json")
                        assets = os.path.join(work, "assets")
                        if os.path.exists(assets):
                            tar.add(assets, arcname="assets")
                self.message = "Pack exported"
            except Exception as exc:
                self.message = "Pack export failed: %s" % exc
            renpy.restart_interaction()

        def build_pack(self, work):
            settings = self.settings_data()
            resources = {}
            for attr in MS_RESOURCE_ATTRS:
                resources[attr] = self.copy_resource_to_pack(getattr(self, attr), work, attr)
                settings[attr] = None
            for i, item in enumerate(settings.get("dialogues", [])):
                key = "dialogue_%03d_audio" % i
                resources[key] = self.copy_resource_to_pack(item.get("audio_path"), work, key)
                item["audio_path"] = None
                item["audio_resource"] = key if resources[key] else None
            return {
                "format": "image-minesweeper-live2d-pack",
                "version": 1,
                "settings": settings,
                "resources": resources,
            }

        def copy_resource_to_pack(self, source, work, key):
            if not source or not os.path.exists(source):
                return None
            target_dir = os.path.join(work, "assets", key)
            if os.path.isdir(source):
                shutil.copytree(source, target_dir)
                return {"type": "directory", "path": os.path.relpath(target_dir, work).replace("\\", "/")}
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, os.path.basename(source))
            shutil.copy2(source, target)
            return {"type": "file", "path": os.path.relpath(target, work).replace("\\", "/")}

        def import_pack(self):
            source = ms_file_dialog("file", "Import pack")
            if not source:
                return
            target_dir = os.path.join(ms_packs_dir(), uuid.uuid4().hex)
            try:
                os.makedirs(target_dir, exist_ok=True)
                with tarfile.open(source, "r") as tar:
                    self.safe_extract_tar(tar, target_dir)
                with open(os.path.join(target_dir, "metadata.json"), "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                self.apply_pack(metadata, target_dir)
                self.message = "Pack imported"
            except Exception as exc:
                self.message = "Pack import failed: %s" % exc
            renpy.restart_interaction()

        def safe_extract_tar(self, tar, destination):
            destination = os.path.abspath(destination)
            for member in tar.getmembers():
                if member.issym() or member.islnk():
                    raise ValueError("links are not allowed")
                target = os.path.abspath(os.path.join(destination, member.name))
                if not target.startswith(destination + os.sep) and target != destination:
                    raise ValueError("unsafe path in tar")
            tar.extractall(destination)

        def apply_pack(self, metadata, import_dir):
            if metadata.get("format") != "image-minesweeper-live2d-pack":
                raise ValueError("unsupported pack format")
            settings = metadata.get("settings", {})
            resources = metadata.get("resources", {})
            self.mine_count = self.clamp(settings.get("mine_count", MS_DEFAULT_MINES), 1, MS_MAX_MINES)
            self.cover_opacity = self.clamp(settings.get("cover_opacity", 255), 0, 255)
            self.reveal_opacity = self.clamp(settings.get("reveal_opacity", 255), 0, 255)
            self.mine_style = settings.get("mine_style", "O")
            for attr in MS_RESOURCE_ATTRS:
                self.set_path_from_resource(attr, resources.get(attr), import_dir)
            self.dialogues = settings.get("dialogues") or []
            for item in self.dialogues:
                key = item.pop("audio_resource", None)
                if key:
                    item["audio_path"] = self.pack_resource_abs_path(resources.get(key), import_dir)
            self.update_board_layout()
            self.save_settings()

        def set_path_from_resource(self, attr, resource, import_dir):
            setattr(self, attr, self.pack_resource_abs_path(resource, import_dir))

        def pack_resource_abs_path(self, resource, import_dir):
            if not resource:
                return None
            path = os.path.abspath(os.path.join(import_dir, resource.get("path", "")))
            if ms_commonpath_inside(path, import_dir) and os.path.exists(path):
                return path
            return None
