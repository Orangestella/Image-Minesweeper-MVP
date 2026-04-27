# Image Minesweeper MVP

Pygame minesweeper with configurable mine count, two board images, three event sounds, adjustable image opacity, selectable mine styles, and persistent settings.
The board aspect ratio follows the covered image when available, otherwise the revealed image, while still using a 16x16 grid.

## Ren'Py Formal Version

The formal Ren'Py rewrite lives in `renpy_minesweeper/`.

Run `python renpy_minesweeper/resource_loader.py` first to copy resources into the Ren'Py project, then open that folder from the Ren'Py launcher. The Live2D version keeps the minesweeper rules and resource pack workflow, and adds gameplay/win Live2D model slots plus clickable random dialogue lines with paired audio.

## Run

```powershell
pip install -r requirements.txt
python main.py
```

## Controls

- Left click: reveal a cell
- Right click: flag or unflag a cell
- `Settings`: edit mine count, opacity, mine style, images, audio, and BGM
- `BGM Play / Pause`: loop the configured BGM or pause/resume it
- `Use path`: save the selected file path in `config/settings.json`
- `Copy`: copy the selected file into `cache/` and save the cached path
- Audio rows also support `Use dir` and `Copy dir`; when an audio setting points to a directory, each trigger randomly plays one `.wav`, `.ogg`, or `.mp3` file from that directory
- `Export pack`: copy the current settings and all referenced resources into a temporary package, write `metadata.json`, and save a `.tar`
- `Import pack`: extract a previously exported `.tar` into `cache/packs/` and switch the settings to the imported resources
- `Clear cache`: delete cached resources/imported packs and clear any settings that pointed into `cache/`

Settings are saved automatically after every change. If an image or audio file is missing later, the game falls back to colored cells or silence.


## Acknowledgements

The UI of this project uses the MiSans font. The MiSans font is copyrighted by Xiaomi Inc. and is permitted for free commercial use by the general public under the MiSans Font Intellectual Property License Agreement.
