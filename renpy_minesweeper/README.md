# Image Minesweeper Live2D Ren'Py Version

This is the formal Ren'Py rewrite of the pygame MVP.

## Features

- 16x16 minesweeper with first-click safety.
- Configurable mine count, mine style, image opacity, BGM, event audio, and two board images.
- Board aspect ratio follows the covered image when available, otherwise the revealed image.
- Winning shows the full revealed image without opacity.
- Audio can be a file or a directory; directories are sampled randomly on each trigger.
- Data packs export/import settings, images, audio, Live2D model folders/files, dialogue lines, and dialogue audio as `.tar`.
- Live2D model slots: one model during gameplay and one after victory.
- Clicking the model randomly shows a dialogue line and plays its paired audio when available.

## Live2D Notes

Ren'Py's native Live2D displayable loads Cubism 3/4/5 `model3.json` models. This project imports moc2 markers for data-pack compatibility, but displays a fallback notice for moc2 because native Ren'Py rendering does not load Cubism 2/moc2 models.

## How To Run

1. Run the external resource loader:

```powershell
python resource_loader.py
```

Use it to copy images, audio, Live2D models, dialogue lines, and packs into `game/imported_resources/`. It writes `game/resource_settings.json`.

2. Open the `renpy_minesweeper` folder as a Ren'Py project from the Ren'Py launcher, then launch the project.

The game no longer opens file pickers or reads arbitrary external resource paths. It only reads resources that the loader copied into the Ren'Py `game/` directory.

If Live2D is not installed in your Ren'Py SDK, the model panel will show a fallback message while the minesweeper game continues to work.
