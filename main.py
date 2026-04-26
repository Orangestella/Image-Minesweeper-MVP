import json
import os
import random
import shutil
import sys
import tarfile
import tempfile
import uuid
from collections import deque

import pygame


try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None
    filedialog = None


WINDOW_WIDTH = 980
WINDOW_HEIGHT = 720
BOARD_SIZE = 560
ROWS = 16
COLS = 16
DEFAULT_MINES = 40
MIN_MINES = 1
MAX_MINES = ROWS * COLS - 9
OPACITY_STEP = 25
MINE_STYLES = ["O", "X", "#"]
AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3"}

RESOURCE_FIELDS = [
    ("cover_image_path", "Covered image"),
    ("reveal_image_path", "Revealed image"),
    ("win_audio_path", "Win audio"),
    ("safe_audio_path", "Safe audio"),
    ("mine_audio_path", "Mine audio"),
    ("bgm_audio_path", "BGM audio"),
]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(APP_DIR, "config")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")
CACHE_DIR = os.path.join(APP_DIR, "cache")
PACKS_DIR = os.path.join(CACHE_DIR, "packs")

BG = (24, 27, 34)
PANEL = (34, 39, 49)
PANEL_LIGHT = (48, 55, 68)
TEXT = (238, 241, 245)
MUTED = (154, 164, 178)
ACCENT = (74, 163, 255)
DANGER = (236, 88, 88)
GRID = (13, 17, 23)

NUMBER_COLORS = {
    1: (64, 150, 255),
    2: (70, 190, 110),
    3: (240, 92, 92),
    4: (132, 108, 232),
    5: (236, 145, 62),
    6: (64, 200, 200),
    7: (220, 220, 220),
    8: (145, 153, 166),
}


def load_font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


class Button:
    def __init__(self, rect, text, action, kind="normal"):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.kind = kind

    def draw(self, screen, font):
        mouse = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse)
        if self.kind == "danger":
            color = (156, 56, 61) if hovered else (126, 45, 51)
        elif self.kind == "ok":
            color = (50, 130, 83) if hovered else (41, 105, 70)
        else:
            color = (62, 73, 91) if hovered else PANEL_LIGHT
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, (73, 84, 104), self.rect, 1, border_radius=6)
        label = font.render(self.text, True, TEXT)
        screen.blit(label, label.get_rect(center=self.rect.center))

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.action()
                return True
        return False


class MinesweeperGame:
    def __init__(self):
        pygame.init()
        self.audio_enabled = True
        try:
            pygame.mixer.init()
            self.sfx_channel = pygame.mixer.Channel(0)
        except pygame.error:
            self.audio_enabled = False
            self.sfx_channel = None

        pygame.display.set_caption("Image Minesweeper MVP")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = load_font(20)
        self.small_font = load_font(16)
        self.big_font = load_font(34, bold=True)
        self.number_font = load_font(24, bold=True)

        self.board_area_rect = pygame.Rect(32, 92, BOARD_SIZE, BOARD_SIZE)
        self.board_rect = self.board_area_rect.copy()

        self.mine_count = DEFAULT_MINES
        self.active_mine_count = DEFAULT_MINES
        self.cover_opacity = 255
        self.reveal_opacity = 255
        self.mine_style_index = 0
        self.cover_image_path = None
        self.reveal_image_path = None
        self.win_audio_path = None
        self.safe_audio_path = None
        self.mine_audio_path = None
        self.bgm_audio_path = None
        self.cover_image = None
        self.reveal_image = None
        self.cover_image_source = None
        self.reveal_image_source = None
        self.update_board_layout()
        self.win_sound = None
        self.safe_sound = None
        self.mine_sound = None
        self.bgm_playing = False
        self.bgm_paused = False

        self.view = "game"
        self.state = "menu"
        self.message = "Settings are loaded from disk"
        self.game_buttons = []
        self.settings_buttons = []

        self.ensure_storage()
        self.load_settings()
        self.reset_board()
        self.build_buttons()

    def ensure_storage(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        os.makedirs(PACKS_DIR, exist_ok=True)

    def settings_data(self):
        return {
            "mine_count": self.mine_count,
            "cover_opacity": self.cover_opacity,
            "reveal_opacity": self.reveal_opacity,
            "mine_style_index": self.mine_style_index,
            "cover_image_path": self.cover_image_path,
            "reveal_image_path": self.reveal_image_path,
            "win_audio_path": self.win_audio_path,
            "safe_audio_path": self.safe_audio_path,
            "mine_audio_path": self.mine_audio_path,
            "bgm_audio_path": self.bgm_audio_path,
        }

    def save_settings(self):
        self.ensure_storage()
        with open(SETTINGS_PATH, "w", encoding="utf-8") as file:
            json.dump(self.settings_data(), file, ensure_ascii=False, indent=2)

    def load_settings(self):
        if not os.path.exists(SETTINGS_PATH):
            self.save_settings()
            return
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.message = "Settings file could not be read"
            return

        self.mine_count = self.clamp(data.get("mine_count", DEFAULT_MINES), MIN_MINES, MAX_MINES)
        self.cover_opacity = self.clamp(data.get("cover_opacity", 255), 0, 255)
        self.reveal_opacity = self.clamp(data.get("reveal_opacity", 255), 0, 255)
        self.mine_style_index = self.clamp(data.get("mine_style_index", 0), 0, len(MINE_STYLES) - 1)
        self.cover_image_path = data.get("cover_image_path")
        self.reveal_image_path = data.get("reveal_image_path")
        self.win_audio_path = data.get("win_audio_path")
        self.safe_audio_path = data.get("safe_audio_path")
        self.mine_audio_path = data.get("mine_audio_path")
        self.bgm_audio_path = data.get("bgm_audio_path")

        cleared = self.clear_missing_resource_paths()
        self.cover_image_source = self.load_image_source(self.cover_image_path)
        self.reveal_image_source = self.load_image_source(self.reveal_image_path)
        self.update_board_layout()
        self.win_sound = self.load_sound(self.win_audio_path)
        self.safe_sound = self.load_sound(self.safe_audio_path)
        self.mine_sound = self.load_sound(self.mine_audio_path)
        if cleared:
            self.save_settings()
            self.message = f"Missing resources cleared: {', '.join(cleared)}"

    def clear_missing_resource_paths(self):
        cleared = []
        for attr, label in RESOURCE_FIELDS:
            path = getattr(self, attr)
            if path and not os.path.exists(path):
                setattr(self, attr, None)
                cleared.append(label)
        return cleared

    def clamp(self, value, low, high):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = low
        return max(low, min(high, value))

    def reset_board(self):
        self.mines = set()
        self.revealed = set()
        self.flagged = set()
        self.numbers = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        self.first_click = True
        self.game_over = False
        self.won = False

    def build_buttons(self):
        x = 638
        self.game_buttons = [
            Button((x, 110, 282, 48), "Start / Restart", self.start_game, "ok"),
            Button((x, 174, 282, 44), "Settings", self.open_settings),
            Button((x, 234, 282, 44), "BGM Play / Pause", self.toggle_bgm),
        ]

        sx = 64
        bx = 668
        y = 122
        h = 38
        self.settings_buttons = [
            Button((64, 40, 120, 38), "Back", self.open_game),
            Button((520, 40, 120, 38), "Export pack", self.export_pack),
            Button((660, 40, 120, 38), "Import pack", self.import_pack),
            Button((800, 40, 120, 38), "Reset defaults", self.reset_settings_to_defaults, "danger"),
            Button((bx, y, 56, h), "-5", lambda: self.adjust_mines(-5)),
            Button((bx + 64, y, 56, h), "-1", lambda: self.adjust_mines(-1)),
            Button((bx + 128, y, 56, h), "+1", lambda: self.adjust_mines(1)),
            Button((bx + 192, y, 56, h), "+5", lambda: self.adjust_mines(5)),
            Button((bx, y + 56, 56, h), "C-", lambda: self.adjust_opacity("cover", -OPACITY_STEP)),
            Button((bx + 64, y + 56, 56, h), "C+", lambda: self.adjust_opacity("cover", OPACITY_STEP)),
            Button((bx + 128, y + 56, 56, h), "R-", lambda: self.adjust_opacity("reveal", -OPACITY_STEP)),
            Button((bx + 192, y + 56, 56, h), "R+", lambda: self.adjust_opacity("reveal", OPACITY_STEP)),
            Button((bx, y + 112, 76, h), "Mine O", lambda: self.set_mine_style(0)),
            Button((bx + 86, y + 112, 76, h), "Mine X", lambda: self.set_mine_style(1)),
            Button((bx + 172, y + 112, 76, h), "Mine #", lambda: self.set_mine_style(2)),
        ]

        resource_rows = [
            ("cover", "image", 312),
            ("reveal", "image", 366),
            ("win", "audio", 420),
            ("safe", "audio", 474),
            ("mine", "audio", 528),
            ("bgm", "audio", 582),
        ]
        for target, kind, row_y in resource_rows:
            if kind == "audio":
                self.settings_buttons.append(Button((sx + 448, row_y, 76, h), "Use file", lambda t=target, k=kind: self.pick_resource(t, k, False)))
                self.settings_buttons.append(Button((sx + 530, row_y, 76, h), "Copy file", lambda t=target, k=kind: self.pick_resource(t, k, True)))
                self.settings_buttons.append(Button((sx + 612, row_y, 76, h), "Use dir", lambda t=target: self.pick_audio_directory(t, False)))
                self.settings_buttons.append(Button((sx + 694, row_y, 76, h), "Copy dir", lambda t=target: self.pick_audio_directory(t, True)))
            else:
                self.settings_buttons.append(Button((sx + 520, row_y, 88, h), "Use path", lambda t=target, k=kind: self.pick_resource(t, k, False)))
                self.settings_buttons.append(Button((sx + 618, row_y, 88, h), "Copy", lambda t=target, k=kind: self.pick_resource(t, k, True)))

    def open_settings(self):
        self.view = "settings"
        self.message = "Settings save automatically"

    def open_game(self):
        self.view = "game"
        self.message = "Left click reveal, right click flag"

    def reset_settings_to_defaults(self):
        self.stop_audio()
        self.mine_count = DEFAULT_MINES
        self.cover_opacity = 255
        self.reveal_opacity = 255
        self.mine_style_index = 0
        self.cover_image_path = None
        self.reveal_image_path = None
        self.win_audio_path = None
        self.safe_audio_path = None
        self.mine_audio_path = None
        self.bgm_audio_path = None
        self.cover_image = None
        self.reveal_image = None
        self.cover_image_source = None
        self.reveal_image_source = None
        self.win_sound = None
        self.safe_sound = None
        self.mine_sound = None
        self.bgm_playing = False
        self.bgm_paused = False
        self.save_settings()
        self.message = "Settings reset to defaults"

    def adjust_mines(self, delta):
        self.mine_count = max(MIN_MINES, min(MAX_MINES, self.mine_count + delta))
        self.save_settings()
        self.message = f"Mine count saved: {self.mine_count}"

    def adjust_opacity(self, target, delta):
        if target == "cover":
            self.cover_opacity = max(0, min(255, self.cover_opacity + delta))
            self.message = f"Covered image opacity saved: {self.cover_opacity}"
        else:
            self.reveal_opacity = max(0, min(255, self.reveal_opacity + delta))
            self.message = f"Revealed image opacity saved: {self.reveal_opacity}"
        self.save_settings()

    def set_mine_style(self, index):
        self.mine_style_index = index
        self.save_settings()
        self.message = f"Mine style saved: {MINE_STYLES[index]}"

    def pick_file(self, title, filetypes):
        if filedialog is None:
            self.message = "File picker is unavailable"
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        return path or None

    def pick_directory(self, title):
        if filedialog is None:
            self.message = "File picker is unavailable"
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title=title)
        root.destroy()
        return path or None

    def pick_save_file(self, title, default_name, filetypes):
        if filedialog is None:
            self.message = "File picker is unavailable"
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(title=title, initialfile=default_name, filetypes=filetypes, defaultextension=".tar")
        root.destroy()
        return path or None

    def copy_to_cache(self, path, kind, target):
        if os.path.isdir(path):
            cached_dir = os.path.join(CACHE_DIR, kind, f"{target}_{uuid.uuid4().hex}")
            os.makedirs(cached_dir, exist_ok=True)
            copied = 0
            for audio_path in self.audio_files_in_directory(path):
                shutil.copy2(audio_path, os.path.join(cached_dir, os.path.basename(audio_path)))
                copied += 1
            if copied == 0:
                raise ValueError("No supported audio files found")
            return cached_dir
        extension = os.path.splitext(path)[1]
        filename = f"{target}_{uuid.uuid4().hex}{extension}"
        cached_path = os.path.join(CACHE_DIR, kind, filename)
        os.makedirs(os.path.dirname(cached_path), exist_ok=True)
        shutil.copy2(path, cached_path)
        return cached_path

    def pick_audio_directory(self, target, should_copy):
        if not self.audio_enabled:
            self.message = "Audio device is unavailable"
            return
        path = self.pick_directory(f"Select {target} audio directory")
        if not path:
            return
        try:
            if not self.audio_files_in_directory(path):
                self.message = "No supported audio files found"
                return
            stored_path = self.copy_to_cache(path, "audio", target) if should_copy else path
            self.assign_audio_path(target, stored_path)
        except Exception as exc:
            self.message = f"Audio directory failed: {exc}"
            return
        self.save_settings()
        mode = "directory copied to cache" if should_copy else "directory saved as path"
        self.message = f"{target} audio {mode}"

    def pick_resource(self, target, kind, should_copy):
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All files", "*.*")]
        if kind == "audio":
            filetypes = [("Audio files", "*.wav *.ogg *.mp3"), ("All files", "*.*")]
            if not self.audio_enabled:
                self.message = "Audio device is unavailable"
                return

        path = self.pick_file(f"Select {target} {kind}", filetypes)
        if not path:
            return

        try:
            stored_path = self.copy_to_cache(path, kind, target) if should_copy else path
            if kind == "image":
                resource = self.load_image_source(stored_path, raise_errors=True)
                if target == "cover":
                    self.cover_image_path = stored_path
                    self.cover_image_source = resource
                else:
                    self.reveal_image_path = stored_path
                    self.reveal_image_source = resource
                self.update_board_layout()
            else:
                self.validate_audio_path(stored_path)
                self.assign_audio_path(target, stored_path)
        except Exception as exc:
            self.message = f"Resource load failed: {exc}"
            return

        self.save_settings()
        mode = "copied to cache" if should_copy else "saved as path"
        self.message = f"{target} {kind} {mode}"

    def export_pack(self):
        cleared = self.clear_missing_resource_paths()
        if cleared:
            self.save_settings()
        tar_path = self.pick_save_file("Export data pack", "minesweeper_pack.tar", [("Tar files", "*.tar"), ("All files", "*.*")])
        if not tar_path:
            return
        try:
            with tempfile.TemporaryDirectory(dir=CACHE_DIR) as work_dir:
                metadata = self.build_pack_directory(work_dir)
                metadata_path = os.path.join(work_dir, "metadata.json")
                with open(metadata_path, "w", encoding="utf-8") as file:
                    json.dump(metadata, file, ensure_ascii=False, indent=2)
                with tarfile.open(tar_path, "w") as tar:
                    tar.add(metadata_path, arcname="metadata.json")
                    assets_dir = os.path.join(work_dir, "assets")
                    if os.path.exists(assets_dir):
                        tar.add(assets_dir, arcname="assets")
        except Exception as exc:
            self.message = f"Export pack failed: {exc}"
            return
        self.message = f"Pack exported: {os.path.basename(tar_path)}"

    def build_pack_directory(self, work_dir):
        settings = self.settings_data()
        resources = {}
        for attr, label in RESOURCE_FIELDS:
            source_path = getattr(self, attr)
            settings[attr] = None
            if not source_path or not os.path.exists(source_path):
                resources[attr] = None
                continue

            target_dir = os.path.join(work_dir, "assets", attr)
            os.makedirs(target_dir, exist_ok=True)
            if os.path.isdir(source_path):
                copied = 0
                for audio_path in self.audio_files_in_directory(source_path):
                    shutil.copy2(audio_path, os.path.join(target_dir, os.path.basename(audio_path)))
                    copied += 1
                resources[attr] = {"type": "directory", "path": os.path.relpath(target_dir, work_dir).replace("\\", "/")} if copied else None
            else:
                target_path = os.path.join(target_dir, os.path.basename(source_path))
                shutil.copy2(source_path, target_path)
                resources[attr] = {"type": "file", "path": os.path.relpath(target_path, work_dir).replace("\\", "/")}

        return {
            "format": "image-minesweeper-pack",
            "version": 1,
            "settings": settings,
            "resources": resources,
        }

    def import_pack(self):
        tar_path = self.pick_file("Import data pack", [("Tar files", "*.tar"), ("All files", "*.*")])
        if not tar_path:
            return
        import_dir = os.path.join(PACKS_DIR, uuid.uuid4().hex)
        try:
            os.makedirs(import_dir, exist_ok=True)
            with tarfile.open(tar_path, "r") as tar:
                self.safe_extract_tar(tar, import_dir)
            metadata_path = os.path.join(import_dir, "metadata.json")
            with open(metadata_path, "r", encoding="utf-8") as file:
                metadata = json.load(file)
            if metadata.get("format") != "image-minesweeper-pack":
                raise ValueError("Unsupported pack format")
            self.apply_pack_metadata(metadata, import_dir)
        except Exception as exc:
            self.message = f"Import pack failed: {exc}"
            return
        self.message = f"Pack imported: {os.path.basename(tar_path)}"

    def safe_extract_tar(self, tar, destination):
        destination = os.path.abspath(destination)
        for member in tar.getmembers():
            if member.issym() or member.islnk():
                raise ValueError("Links are not allowed in pack")
            target_path = os.path.abspath(os.path.join(destination, member.name))
            if not target_path.startswith(destination + os.sep) and target_path != destination:
                raise ValueError("Unsafe path in tar")
        tar.extractall(destination)

    def apply_pack_metadata(self, metadata, import_dir):
        settings = metadata.get("settings", {})
        self.stop_audio()
        self.mine_count = self.clamp(settings.get("mine_count", DEFAULT_MINES), MIN_MINES, MAX_MINES)
        self.cover_opacity = self.clamp(settings.get("cover_opacity", 255), 0, 255)
        self.reveal_opacity = self.clamp(settings.get("reveal_opacity", 255), 0, 255)
        self.mine_style_index = self.clamp(settings.get("mine_style_index", 0), 0, len(MINE_STYLES) - 1)

        resources = metadata.get("resources", {})
        for attr, label in RESOURCE_FIELDS:
            resource = resources.get(attr)
            if not resource:
                setattr(self, attr, None)
                continue
            path = os.path.abspath(os.path.join(import_dir, resource.get("path", "")))
            if path.startswith(os.path.abspath(import_dir) + os.sep) and os.path.exists(path):
                setattr(self, attr, path)
            else:
                setattr(self, attr, None)

        self.cover_image_source = self.load_image_source(self.cover_image_path)
        self.reveal_image_source = self.load_image_source(self.reveal_image_path)
        self.update_board_layout()
        self.win_sound = self.load_sound(self.win_audio_path)
        self.safe_sound = self.load_sound(self.safe_audio_path)
        self.mine_sound = self.load_sound(self.mine_audio_path)
        self.bgm_playing = False
        self.bgm_paused = False
        self.save_settings()

    def assign_audio_path(self, target, path):
        if target == "win":
            self.win_audio_path = path
            self.win_sound = self.load_sound(path)
        elif target == "safe":
            self.safe_audio_path = path
            self.safe_sound = self.load_sound(path)
        elif target == "bgm":
            was_playing = self.bgm_playing
            if self.audio_enabled:
                pygame.mixer.music.stop()
            self.bgm_audio_path = path
            self.bgm_playing = False
            self.bgm_paused = False
            if was_playing:
                self.start_bgm()
        else:
            self.mine_audio_path = path
            self.mine_sound = self.load_sound(path)

    def load_image_source(self, path, raise_errors=False):
        if not path:
            return None
        try:
            return pygame.image.load(path).convert()
        except Exception:
            if raise_errors:
                raise
            return None

    def update_board_layout(self):
        source = self.cover_image_source or self.reveal_image_source
        if source:
            aspect = source.get_width() / max(1, source.get_height())
        else:
            aspect = 1

        if aspect >= 1:
            width = BOARD_SIZE
            height = max(1, round(BOARD_SIZE / aspect))
        else:
            width = max(1, round(BOARD_SIZE * aspect))
            height = BOARD_SIZE

        x = self.board_area_rect.x + (self.board_area_rect.width - width) // 2
        y = self.board_area_rect.y + (self.board_area_rect.height - height) // 2
        self.board_rect = pygame.Rect(x, y, width, height)
        self.rescale_board_images()

    def rescale_board_images(self):
        size = (self.board_rect.width, self.board_rect.height)
        self.cover_image = pygame.transform.smoothscale(self.cover_image_source, size) if self.cover_image_source else None
        self.reveal_image = pygame.transform.smoothscale(self.reveal_image_source, size) if self.reveal_image_source else None

    def load_sound(self, path, raise_errors=False):
        if not path or not self.audio_enabled:
            return None
        if os.path.isdir(path):
            return None
        try:
            return pygame.mixer.Sound(path)
        except Exception:
            if raise_errors:
                raise
            return None

    def audio_files_in_directory(self, path):
        if not path or not os.path.isdir(path):
            return []
        audio_files = []
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            extension = os.path.splitext(name)[1].lower()
            if os.path.isfile(full_path) and extension in AUDIO_EXTENSIONS:
                audio_files.append(full_path)
        return audio_files

    def random_audio_path(self, path):
        if os.path.isdir(path):
            files = self.audio_files_in_directory(path)
            return random.choice(files) if files else None
        return path

    def validate_audio_path(self, path):
        if os.path.isdir(path):
            if not self.audio_files_in_directory(path):
                raise ValueError("No supported audio files found")
            return
        pygame.mixer.Sound(path)

    def start_game(self):
        self.active_mine_count = self.mine_count
        self.reset_board()
        self.view = "game"
        self.state = "playing"
        self.message = "Left click reveal, right click flag"

    def place_mines(self, safe_cell):
        safe_cells = {safe_cell}
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr = safe_cell[0] + dr
                nc = safe_cell[1] + dc
                if 0 <= nr < ROWS and 0 <= nc < COLS:
                    safe_cells.add((nr, nc))

        candidates = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in safe_cells]
        self.mines = set(random.sample(candidates, self.active_mine_count))
        for r in range(ROWS):
            for c in range(COLS):
                self.numbers[r][c] = self.count_adjacent_mines(r, c)

    def count_adjacent_mines(self, row, col):
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr = row + dr
                nc = col + dc
                if (nr, nc) in self.mines:
                    count += 1
        return count

    def cell_at(self, pos):
        if not self.board_rect.collidepoint(pos):
            return None
        col = int((pos[0] - self.board_rect.x) * COLS / self.board_rect.width)
        row = int((pos[1] - self.board_rect.y) * ROWS / self.board_rect.height)
        if 0 <= row < ROWS and 0 <= col < COLS:
            return row, col
        return None

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
            self.play_sound("mine")
            return

        before = len(self.revealed)
        self.flood_reveal(row, col)
        if len(self.revealed) > before:
            self.play_sound("safe")
        self.check_win()

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
                    if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in self.mines:
                        queue.append((nr, nc))

    def toggle_flag(self, row, col):
        if self.game_over or self.won or (row, col) in self.revealed:
            return
        if (row, col) in self.flagged:
            self.flagged.remove((row, col))
        else:
            self.flagged.add((row, col))

    def check_win(self):
        target = ROWS * COLS - self.active_mine_count
        if len(self.revealed) == target:
            self.won = True
            self.message = "Cleared. Press Start for a new game"
            self.play_sound("win")

    def play_sound(self, target):
        if self.sfx_channel is None:
            return
        path_attr = f"{target}_audio_path"
        sound_attr = f"{target}_sound"
        path = getattr(self, path_attr)
        if not path:
            return
        if not os.path.exists(path):
            setattr(self, path_attr, None)
            setattr(self, sound_attr, None)
            self.save_settings()
            self.message = f"Missing {target} audio cleared"
            return
        self.sfx_channel.stop()
        try:
            if os.path.isdir(path):
                selected_path = self.random_audio_path(path)
                if not selected_path:
                    self.message = f"No supported {target} audio files found"
                    return
                sound = pygame.mixer.Sound(selected_path)
            else:
                sound = getattr(self, sound_attr)
                if sound is None:
                    sound = pygame.mixer.Sound(path)
                    setattr(self, sound_attr, sound)
        except Exception as exc:
            self.message = f"{target} audio failed: {exc}"
            return
        self.sfx_channel.play(sound)

    def start_bgm(self):
        if not self.audio_enabled or not self.bgm_audio_path:
            self.message = "BGM is not set"
            return
        if not os.path.exists(self.bgm_audio_path):
            self.bgm_audio_path = None
            self.bgm_playing = False
            self.bgm_paused = False
            self.save_settings()
            self.message = "Missing BGM cleared"
            return
        selected_path = self.random_audio_path(self.bgm_audio_path)
        if not selected_path:
            self.message = "No supported BGM files found"
            return
        if self.bgm_paused:
            pygame.mixer.music.unpause()
            self.bgm_playing = True
            self.bgm_paused = False
            self.message = "BGM playing"
            return
        try:
            pygame.mixer.music.load(selected_path)
            pygame.mixer.music.play(-1)
        except Exception as exc:
            self.bgm_playing = False
            self.message = f"BGM load failed: {exc}"
            return
        self.bgm_playing = True
        self.message = "BGM playing"

    def pause_bgm(self):
        if self.audio_enabled:
            pygame.mixer.music.pause()
        self.bgm_playing = False
        self.bgm_paused = True
        self.message = "BGM paused"

    def toggle_bgm(self):
        if self.bgm_playing:
            self.pause_bgm()
        else:
            self.start_bgm()

    def stop_audio(self):
        if not self.audio_enabled:
            return
        if self.sfx_channel is not None:
            self.sfx_channel.stop()
        pygame.mixer.music.stop()
        self.bgm_playing = False
        self.bgm_paused = False

    def draw_text(self, text, pos, font=None, color=TEXT):
        font = font or self.font
        surface = font.render(str(text), True, color)
        self.screen.blit(surface, pos)

    def short_path(self, path):
        return os.path.basename(path) if path else "not set"

    def draw(self):
        self.screen.fill(BG)
        if self.view == "settings":
            self.draw_settings()
        else:
            self.draw_game()
        pygame.display.flip()

    def draw_header(self):
        self.draw_text("Image Minesweeper MVP", (32, 26), self.big_font)
        self.draw_text(self.message, (34, 64), self.small_font, MUTED)

    def draw_game(self):
        self.draw_header()
        self.draw_board()
        self.draw_game_panel()

    def draw_game_panel(self):
        panel_rect = pygame.Rect(620, 80, 328, 570)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (55, 65, 82), panel_rect, 1, border_radius=8)

        for button in self.game_buttons:
            button.draw(self.screen, self.small_font)

        lines = [
            f"Configured mines: {self.mine_count}",
            f"Current game mines: {self.active_mine_count if self.state == 'playing' else '-'}",
            f"Covered opacity: {self.cover_opacity}",
            f"Revealed opacity: {self.reveal_opacity}",
            f"Mine style: {MINE_STYLES[self.mine_style_index]}",
            f"Covered: {self.short_path(self.cover_image_path)}",
            f"Revealed: {self.short_path(self.reveal_image_path)}",
            f"Win audio: {self.short_path(self.win_audio_path)}",
            f"Safe audio: {self.short_path(self.safe_audio_path)}",
            f"Mine audio: {self.short_path(self.mine_audio_path)}",
            f"BGM: {self.short_path(self.bgm_audio_path)}",
            f"BGM state: {'playing' if self.bgm_playing else 'paused'}",
        ]
        y = 260
        for line in lines:
            self.draw_text(line, (638, y), self.small_font, MUTED)
            y += 25

        self.draw_text(f"Settings file: {os.path.relpath(SETTINGS_PATH, APP_DIR)}", (638, 590), self.small_font, MUTED)
        self.draw_text(f"Cache folder: {os.path.relpath(CACHE_DIR, APP_DIR)}", (638, 616), self.small_font, MUTED)

    def draw_settings(self):
        self.draw_text("Settings", (210, 38), self.big_font)
        self.draw_text(self.message, (210, 70), self.small_font, MUTED)
        panel_rect = pygame.Rect(32, 92, 916, 560)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (55, 65, 82), panel_rect, 1, border_radius=8)

        self.draw_text("Mine count", (64, 130), self.font)
        self.draw_text(str(self.mine_count), (360, 130), self.font, ACCENT)

        self.draw_text("Image opacity", (64, 186), self.font)
        self.draw_text(f"covered {self.cover_opacity} / revealed {self.reveal_opacity}", (360, 186), self.small_font, MUTED)

        self.draw_text("Mine style", (64, 242), self.font)
        self.draw_text(MINE_STYLES[self.mine_style_index], (360, 242), self.font, ACCENT)

        rows = [
            ("Covered image", self.cover_image_path, 320),
            ("Revealed image", self.reveal_image_path, 374),
            ("Win audio", self.win_audio_path, 428),
            ("Safe audio", self.safe_audio_path, 482),
            ("Mine audio", self.mine_audio_path, 536),
            ("BGM audio", self.bgm_audio_path, 590),
        ]
        for label, path, y in rows:
            pygame.draw.rect(self.screen, (29, 34, 43), pygame.Rect(54, y - 10, 868, 46), border_radius=6)
            self.draw_text(label, (64, y), self.small_font, TEXT)
            self.draw_text(self.short_path(path), (250, y), self.small_font, MUTED)

        for button in self.settings_buttons:
            button.draw(self.screen, self.small_font)

    def draw_board(self):
        pygame.draw.rect(self.screen, (11, 14, 20), self.board_rect.inflate(8, 8), border_radius=8)
        pygame.draw.rect(self.screen, GRID, self.board_rect)
        for row in range(ROWS):
            for col in range(COLS):
                self.draw_cell(row, col)

    def draw_cell(self, row, col):
        rect = self.cell_rect(row, col)
        cell = (row, col)
        should_show_mines = self.game_over and cell in self.mines

        if cell in self.revealed or should_show_mines:
            self.draw_image_slice(self.reveal_image, rect, row, col, (55, 61, 72), (42, 47, 57), self.reveal_opacity)
            if cell in self.mines:
                self.draw_mine(rect)
            else:
                value = self.numbers[row][col]
                if value:
                    text = self.number_font.render(str(value), True, NUMBER_COLORS[value])
                    self.screen.blit(text, text.get_rect(center=rect.center))
        else:
            self.draw_image_slice(self.cover_image, rect, row, col, (72, 93, 120), (48, 63, 84), self.cover_opacity)
            if cell in self.flagged:
                self.draw_flag(rect)

        pygame.draw.rect(self.screen, (10, 13, 18), rect, 1)

    def cell_rect(self, row, col):
        left = self.board_rect.x + round(col * self.board_rect.width / COLS)
        right = self.board_rect.x + round((col + 1) * self.board_rect.width / COLS)
        top = self.board_rect.y + round(row * self.board_rect.height / ROWS)
        bottom = self.board_rect.y + round((row + 1) * self.board_rect.height / ROWS)
        return pygame.Rect(left, top, right - left, bottom - top)

    def draw_image_slice(self, image, rect, row, col, fallback_a, fallback_b, opacity):
        color = fallback_a if (row + col) % 2 == 0 else fallback_b
        pygame.draw.rect(self.screen, color, rect)
        if image:
            src = pygame.Rect(rect.x - self.board_rect.x, rect.y - self.board_rect.y, rect.width, rect.height)
            tile = image.subsurface(src).copy()
            tile.set_alpha(opacity)
            self.screen.blit(tile, rect)

    def draw_flag(self, rect):
        pole_x = rect.x + rect.width * 0.38
        pygame.draw.line(self.screen, TEXT, (pole_x, rect.y + 8), (pole_x, rect.bottom - 8), 3)
        points = [
            (pole_x + 2, rect.y + 8),
            (rect.right - 9, rect.y + 14),
            (pole_x + 2, rect.y + 20),
        ]
        pygame.draw.polygon(self.screen, DANGER, points)
        pygame.draw.line(self.screen, TEXT, (rect.x + 10, rect.bottom - 8), (rect.right - 9, rect.bottom - 8), 3)

    def draw_mine(self, rect):
        style = MINE_STYLES[self.mine_style_index]
        if style == "\u26aa":
            pygame.draw.circle(self.screen, TEXT, rect.center, max(3, min(rect.width, rect.height) // 4), 3)
            return
        text = self.number_font.render(style, True, DANGER)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def current_buttons(self):
        return self.settings_buttons if self.view == "settings" else self.game_buttons

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        for button in self.current_buttons():
            if button.handle(event):
                return
        if self.view != "game" or self.state != "playing":
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            cell = self.cell_at(event.pos)
            if cell is None:
                return
            if event.button == 1:
                self.reveal_cell(*cell)
            elif event.button == 3:
                self.toggle_flag(*cell)

    def run(self):
        while True:
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            self.clock.tick(60)


if __name__ == "__main__":
    MinesweeperGame().run()
