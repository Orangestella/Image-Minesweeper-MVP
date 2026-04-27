define config.name = "Image Minesweeper Live2D"
define config.version = "2.0-renpy"
define gui.show_name = True

define config.screen_width = 1280
define config.screen_height = 720

define config.has_sound = True
define config.has_music = True
define config.has_voice = True

define build.name = "ImageMinesweeperLive2D"

# This project uses a minimal custom screen set instead of Ren'Py's default
# template UI. Avoid the default quit confirmation, which depends on that UI.
define config.quit_action = Quit(confirm=False)
define config.gl2 = True
define config.log_live2d_loading = True

init -1 python:
    import os
    _ms_font_candidates = [
        os.path.join(config.basedir, "game", "assets", "MiSans-Regular.ttf"),
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for _ms_font in _ms_font_candidates:
        if os.path.exists(_ms_font):
            _ms_font = _ms_font.replace("\\", "/")
            style.default.font = _ms_font
            style.button_text.font = _ms_font
            style.input.font = _ms_font
            break
