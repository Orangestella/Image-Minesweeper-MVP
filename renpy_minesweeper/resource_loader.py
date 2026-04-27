import json
import os
import re
import shutil
import tarfile
import tempfile
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk


ROOT = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.join(ROOT, "game")
RESOURCE_DIR = os.path.join(GAME_DIR, "imported_resources")
SETTINGS_PATH = os.path.join(GAME_DIR, "resource_settings.json")
GENERATED_LIVE2D_PATH = os.path.join(GAME_DIR, "generated_live2d.rpy")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3"}

RESOURCE_FIELDS = {
    "cover_image_path": "Covered image",
    "reveal_image_path": "Revealed image",
    "win_audio_path": "Win audio",
    "safe_audio_path": "Safe audio",
    "mine_audio_path": "Mine audio",
    "bgm_audio_path": "BGM audio",
    "play_model_path": "Play Live2D model",
    "win_model_path": "Win Live2D model",
}

DEFAULT_SETTINGS = {
    "mine_count": 40,
    "cover_opacity": 255,
    "reveal_opacity": 255,
    "mine_style": "O",
    "cover_image_path": None,
    "reveal_image_path": None,
    "win_audio_path": None,
    "safe_audio_path": None,
    "mine_audio_path": None,
    "bgm_audio_path": None,
    "play_model_path": None,
    "win_model_path": None,
    "play_model_status": None,
    "win_model_status": None,
    "dialogues": [
        {"text": "Careful. The next cell may tell the truth.", "audio_path": None},
        {"text": "Nice move. Keep going.", "audio_path": None},
        {"text": "When you win, the full inner image appears.", "audio_path": None},
    ],
}


def find_files(root, predicate):
    if os.path.isfile(root):
        return [root] if predicate(os.path.basename(root)) else []
    matches = []
    for current, _dirs, files in os.walk(root):
        for name in files:
            if predicate(name):
                matches.append(os.path.join(current, name))
    return matches


def inspect_live2d_model(path):
    model3_files = find_files(path, lambda name: name.lower().endswith(".model3.json"))
    if model3_files:
        entry = model3_files[0]
        folder = os.path.dirname(entry)
        moc3_files = find_files(folder, lambda name: name.lower().endswith(".moc3"))
        motions = motion_names_from_model3(entry)
        status = "moc3 resource valid; requires Ren'Py Live2D SDK and GL2"
        detail = f"Found {os.path.relpath(entry, path if os.path.isdir(path) else os.path.dirname(path))}; motions: {', '.join(motions) if motions else 'none'}"
        if not moc3_files:
            status = "moc3 entry found, but .moc3 file was not found nearby"
            detail = "Ren'Py may fail to render this model."
        return {"kind": "moc3", "status": status, "detail": detail, "motions": motions}

    moc2_files = find_files(path, lambda name: name.lower().endswith((".moc", ".moc2")))
    if moc2_files:
        return {
            "kind": "moc2",
            "status": "moc2 imported, not renderable by native Ren'Py Live2D",
            "detail": "Use a Cubism 3/4/5 model with model3.json for rendering.",
            "motions": [],
        }

    return {
        "kind": None,
        "status": "No Live2D entry found",
        "detail": "Expected *.model3.json for moc3 or *.moc/*.moc2 for moc2.",
        "motions": [],
    }


def motion_names_from_model3(entry):
    try:
        with open(entry, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except Exception:
        return []
    motions = data.get("FileReferences", {}).get("Motions", {})
    names = []
    for _group, items in motions.items():
        for item in items:
            file_name = item.get("File") or item.get("file")
            if not file_name:
                continue
            attr = sanitize_motion_attribute(live2d_motion_name(file_name, entry))
            if attr not in names:
                names.append(attr)
    return names


def sanitize_motion_attribute(name):
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(name).lower()).strip("_")
    if not name:
        name = "motion"
    if name[0].isdigit():
        name = "m_" + name
    return name


def live2d_motion_name(file_name, entry):
    name = os.path.basename(file_name).lower().partition(".")[0]
    model_name = os.path.basename(entry).lower().partition(".")[0]
    prefix, _sep, suffix = name.partition("_")
    if prefix == model_name:
        name = suffix
    return name


def raw_motion_names_from_model3(entry):
    try:
        with open(entry, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except Exception:
        return []
    motions = data.get("FileReferences", {}).get("Motions", {})
    names = []
    for _group, items in motions.items():
        for item in items:
            file_name = item.get("File") or item.get("file")
            if not file_name:
                continue
            raw = live2d_motion_name(file_name, entry)
            if raw not in names:
                names.append(raw)
    return names


def ensure_dirs():
    os.makedirs(RESOURCE_DIR, exist_ok=True)


def load_settings():
    ensure_dirs()
    if not os.path.exists(SETTINGS_PATH):
        save_settings(dict(DEFAULT_SETTINGS))
    with open(SETTINGS_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(settings):
    ensure_dirs()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=True, indent=2)
    write_generated_live2d(settings)


def game_relative(path):
    return os.path.relpath(path, GAME_DIR).replace("\\", "/")


def copy_file(source, bucket):
    extension = os.path.splitext(source)[1]
    folder = os.path.join(RESOURCE_DIR, bucket)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, f"{uuid.uuid4().hex}{extension}")
    shutil.copy2(source, target)
    return game_relative(target)


def copy_directory(source, bucket, allowed_extensions=None):
    folder = os.path.join(RESOURCE_DIR, bucket, uuid.uuid4().hex)
    os.makedirs(folder, exist_ok=True)
    copied = 0
    for name in os.listdir(source):
        src = os.path.join(source, name)
        if not os.path.isfile(src):
            continue
        extension = os.path.splitext(name)[1].lower()
        if allowed_extensions is not None and extension not in allowed_extensions:
            continue
        shutil.copy2(src, os.path.join(folder, name))
        copied += 1
    if copied == 0:
        shutil.rmtree(folder)
        raise ValueError("No supported files found in selected directory.")
    return game_relative(folder)


def copy_model(source, bucket):
    folder = os.path.join(RESOURCE_DIR, bucket, uuid.uuid4().hex)
    if os.path.isdir(source):
        shutil.copytree(source, folder)
    else:
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(source, os.path.join(folder, os.path.basename(source)))
    return game_relative(folder)


def game_abs(path):
    if not path:
        return None
    if os.path.isabs(path):
        return path
    return os.path.join(GAME_DIR, path.replace("/", os.sep))


def model_entry_relative(model_path):
    root = game_abs(model_path)
    if not root or not os.path.exists(root):
        return None
    files = find_files(root, lambda name: name.lower().endswith(".model3.json"))
    if not files:
        return None
    return game_relative(files[0])


def pick_default_motion_for_settings(settings, attr):
    status = settings.get(attr.replace("_path", "_status")) or {}
    motions = [sanitize_motion_attribute(name) for name in (status.get("motions") or [])]
    for needle in ("idle", "loop", "wait", "mtn_idle", "motion"):
        for name in motions:
            if needle in name:
                return name
    return motions[0] if motions else None


def write_generated_live2d(settings):
    lines = [
        "# Auto-generated by resource_loader.py.",
        "# Do not edit by hand; run the loader again instead.",
        "",
    ]
    for attr, image_name, should_loop in (("play_model_path", "ms_live2d_play", False), ("win_model_path", "ms_live2d_win", True)):
        entry = model_entry_relative(settings.get(attr))
        if entry:
            entry_abs = os.path.join(GAME_DIR, entry.replace("/", os.sep))
            raw_motions = raw_motion_names_from_model3(entry_abs)
            alias = {f"motion_{index}": raw for index, raw in enumerate(raw_motions)}
            alias_repr = repr(alias)
            lines.append(f'image {image_name} = Live2D("{entry}", zoom=0.22, loop={should_loop}, update_function=ms_live2d_update, aliases={alias_repr})')
    lines.append("")
    with open(GENERATED_LIVE2D_PATH, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def safe_extract_tar(tar, destination):
    destination = os.path.abspath(destination)
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise ValueError("Links are not allowed in packs.")
        target = os.path.abspath(os.path.join(destination, member.name))
        if not target.startswith(destination + os.sep) and target != destination:
            raise ValueError("Unsafe path in tar.")
    tar.extractall(destination)


class ResourceLoader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Minesweeper Resource Loader")
        self.geometry("900x640")
        self.settings = load_settings()
        self.status = tk.StringVar(value="Ready")
        self.vars = {}
        self.build_ui()
        self.refresh()

    def build_ui(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Button(top, text="Export Pack", command=self.export_pack).pack(side="left")
        ttk.Button(top, text="Import Pack", command=self.import_pack).pack(side="left", padx=8)
        ttk.Button(top, text="Clear Imported Resources", command=self.clear_resources).pack(side="left", padx=8)
        ttk.Label(top, textvariable=self.status).pack(side="left", padx=16)

        form = ttk.Frame(self, padding=12)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        self.add_number_row(form, 0, "Mine count", "mine_count", 1, 247)
        self.add_number_row(form, 1, "Covered opacity", "cover_opacity", 0, 255)
        self.add_number_row(form, 2, "Revealed opacity", "reveal_opacity", 0, 255)

        ttk.Label(form, text="Mine style").grid(row=3, column=0, sticky="w", pady=5)
        self.mine_style = tk.StringVar(value=self.settings.get("mine_style", "O"))
        ttk.Combobox(form, textvariable=self.mine_style, values=["O", "X", "#"], state="readonly", width=8).grid(row=3, column=1, sticky="w")
        ttk.Button(form, text="Save", command=self.save_basic).grid(row=3, column=2, sticky="w")

        row = 4
        for attr, label in RESOURCE_FIELDS.items():
            self.add_resource_row(form, row, label, attr)
            row += 1

        ttk.Separator(form).grid(row=row, column=0, columnspan=5, sticky="ew", pady=12)
        row += 1
        ttk.Label(form, text="Dialogue text").grid(row=row, column=0, sticky="w")
        self.dialogue_text = tk.StringVar()
        ttk.Entry(form, textvariable=self.dialogue_text).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(form, text="Add Line", command=self.add_dialogue).grid(row=row, column=2, sticky="w")
        row += 1
        self.dialogue_list = tk.Listbox(form, height=6)
        self.dialogue_list.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=6)
        ttk.Button(form, text="Remove Selected Line", command=self.remove_dialogue).grid(row=row, column=3, sticky="nw", padx=8)

    def add_number_row(self, parent, row, label, key, minimum, maximum):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        var = tk.IntVar(value=int(self.settings.get(key, DEFAULT_SETTINGS[key])))
        self.vars[key] = var
        ttk.Spinbox(parent, from_=minimum, to=maximum, textvariable=var, width=8).grid(row=row, column=1, sticky="w")
        ttk.Button(parent, text="Save", command=self.save_basic).grid(row=row, column=2, sticky="w")

    def add_resource_row(self, parent, row, label, attr):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        var = tk.StringVar(value=self.settings.get(attr) or "not set")
        self.vars[attr] = var
        ttk.Entry(parent, textvariable=var, state="readonly").grid(row=row, column=1, sticky="ew", padx=8)
        if "image" in attr:
            ttk.Button(parent, text="Load File", command=lambda a=attr: self.load_file(a, IMAGE_EXTENSIONS)).grid(row=row, column=2)
        elif "model" in attr:
            ttk.Button(parent, text="Load Model", command=lambda a=attr: self.load_model(a)).grid(row=row, column=2)
        else:
            ttk.Button(parent, text="Load File", command=lambda a=attr: self.load_file(a, AUDIO_EXTENSIONS)).grid(row=row, column=2)
            ttk.Button(parent, text="Load Dir", command=lambda a=attr: self.load_audio_dir(a)).grid(row=row, column=3, padx=4)
        ttk.Button(parent, text="Clear", command=lambda a=attr: self.clear_attr(a)).grid(row=row, column=4, padx=4)

    def refresh(self):
        for key, var in self.vars.items():
            if key in self.settings:
                value = self.settings.get(key)
                if isinstance(var, tk.StringVar):
                    var.set(value or "not set")
                else:
                    var.set(value)
        if hasattr(self, "mine_style"):
            self.mine_style.set(self.settings.get("mine_style", "O"))
        if hasattr(self, "dialogue_list"):
            self.dialogue_list.delete(0, "end")
            for item in self.settings.get("dialogues", []):
                self.dialogue_list.insert("end", item.get("text", ""))

    def save_basic(self):
        self.settings["mine_count"] = int(self.vars["mine_count"].get())
        self.settings["cover_opacity"] = int(self.vars["cover_opacity"].get())
        self.settings["reveal_opacity"] = int(self.vars["reveal_opacity"].get())
        self.settings["mine_style"] = self.mine_style.get()
        save_settings(self.settings)
        self.status.set("Settings saved.")

    def load_file(self, attr, extensions):
        filetypes = [("Supported files", " ".join(f"*{e}" for e in sorted(extensions))), ("All files", "*.*")]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if not path:
            return
        if os.path.splitext(path)[1].lower() not in extensions:
            messagebox.showerror("Unsupported file", "The selected file type is not supported.")
            return
        self.settings[attr] = copy_file(path, attr)
        save_settings(self.settings)
        self.status.set(f"{RESOURCE_FIELDS[attr]} loaded.")
        self.refresh()

    def load_audio_dir(self, attr):
        path = filedialog.askdirectory()
        if not path:
            return
        try:
            self.settings[attr] = copy_directory(path, attr, AUDIO_EXTENSIONS)
        except ValueError as exc:
            messagebox.showerror("No files", str(exc))
            return
        save_settings(self.settings)
        self.status.set(f"{RESOURCE_FIELDS[attr]} directory loaded.")
        self.refresh()

    def load_model(self, attr):
        path = filedialog.askdirectory(title="Select Live2D model directory")
        if not path:
            path = filedialog.askopenfilename(title="Select Live2D model file", filetypes=[("Live2D files", "*.model3.json *.moc *.moc2"), ("All files", "*.*")])
        if not path:
            return
        inspection = inspect_live2d_model(path)
        if inspection["kind"] is None:
            messagebox.showerror("Invalid Live2D model", inspection["detail"])
            return
        self.settings[attr] = copy_model(path, attr)
        status_key = attr.replace("_path", "_status")
        self.settings[status_key] = inspection
        save_settings(self.settings)
        if inspection["kind"] == "moc3" and inspection["status"].startswith("moc3 resource valid"):
            messagebox.showinfo("Live2D model loaded", f"{RESOURCE_FIELDS[attr]} loaded.\n{inspection['status']}\n{inspection['detail']}")
        else:
            messagebox.showwarning("Live2D model loaded with warning", f"{RESOURCE_FIELDS[attr]} loaded.\n{inspection['status']}\n{inspection['detail']}")
        self.status.set(f"{RESOURCE_FIELDS[attr]} loaded: {inspection['status']}")
        self.refresh()

    def clear_attr(self, attr):
        self.settings[attr] = None
        if attr.endswith("_path"):
            self.settings[attr.replace("_path", "_status")] = None
        save_settings(self.settings)
        self.status.set(f"{RESOURCE_FIELDS[attr]} cleared.")
        self.refresh()

    def add_dialogue(self):
        text = self.dialogue_text.get().strip()
        if not text:
            return
        audio = filedialog.askopenfilename(title="Optional dialogue audio", filetypes=[("Audio files", "*.wav *.ogg *.mp3"), ("All files", "*.*")])
        audio_path = None
        if audio:
            if os.path.splitext(audio)[1].lower() not in AUDIO_EXTENSIONS:
                messagebox.showerror("Unsupported file", "The selected audio type is not supported.")
                return
            audio_path = copy_file(audio, "dialogue_audio")
        self.settings.setdefault("dialogues", []).append({"text": text, "audio_path": audio_path})
        self.dialogue_text.set("")
        save_settings(self.settings)
        self.refresh()

    def remove_dialogue(self):
        selection = list(self.dialogue_list.curselection())
        if not selection:
            return
        index = selection[0]
        dialogues = self.settings.setdefault("dialogues", [])
        if 0 <= index < len(dialogues):
            dialogues.pop(index)
            save_settings(self.settings)
            self.refresh()

    def clear_resources(self):
        if not messagebox.askyesno("Clear resources", "Delete all imported resources and clear resource settings?"):
            return
        if os.path.exists(RESOURCE_DIR):
            shutil.rmtree(RESOURCE_DIR)
        ensure_dirs()
        for attr in RESOURCE_FIELDS:
            self.settings[attr] = None
        for item in self.settings.get("dialogues", []):
            item["audio_path"] = None
        save_settings(self.settings)
        self.status.set("Imported resources cleared.")
        self.refresh()

    def export_pack(self):
        target = filedialog.asksaveasfilename(defaultextension=".tar", filetypes=[("Tar files", "*.tar"), ("All files", "*.*")])
        if not target:
            return
        with tempfile.TemporaryDirectory() as work:
            metadata = dict(self.settings)
            assets = os.path.join(work, "assets")
            os.makedirs(assets, exist_ok=True)
            if os.path.exists(RESOURCE_DIR):
                shutil.copytree(RESOURCE_DIR, os.path.join(assets, "imported_resources"))
            with open(os.path.join(work, "metadata.json"), "w", encoding="utf-8") as file:
                json.dump({"format": "image-minesweeper-live2d-pack", "version": 2, "settings": metadata}, file, ensure_ascii=True, indent=2)
            with tarfile.open(target, "w") as tar:
                tar.add(os.path.join(work, "metadata.json"), arcname="metadata.json")
                tar.add(assets, arcname="assets")
        self.status.set("Pack exported.")

    def import_pack(self):
        source = filedialog.askopenfilename(filetypes=[("Tar files", "*.tar"), ("All files", "*.*")])
        if not source:
            return
        with tempfile.TemporaryDirectory() as work:
            with tarfile.open(source, "r") as tar:
                safe_extract_tar(tar, work)
            metadata_path = os.path.join(work, "metadata.json")
            if not os.path.exists(metadata_path):
                messagebox.showerror("Invalid pack", "metadata.json was not found.")
                return
            with open(metadata_path, "r", encoding="utf-8") as file:
                metadata = json.load(file)
            settings = metadata.get("settings")
            if not isinstance(settings, dict):
                messagebox.showerror("Invalid pack", "Pack settings are invalid.")
                return
            imported = os.path.join(work, "assets", "imported_resources")
            if os.path.exists(imported):
                if os.path.exists(RESOURCE_DIR):
                    shutil.rmtree(RESOURCE_DIR)
                shutil.copytree(imported, RESOURCE_DIR)
            self.settings = dict(DEFAULT_SETTINGS)
            self.settings.update(settings)
            save_settings(self.settings)
        self.status.set("Pack imported.")
        self.refresh()


if __name__ == "__main__":
    ResourceLoader().mainloop()
