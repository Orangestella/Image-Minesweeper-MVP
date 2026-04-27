screen minesweeper_main(app):
    tag minesweeper
    modal True

    add Solid("#181b22")

    text "Image Minesweeper Live2D" xpos 32 ypos 22 size 32 color "#eef1f5"
    text app.message xpos 34 ypos 62 size 18 color "#9aa4b2"

    use minesweeper_board(app)
    use minesweeper_side_panel(app)
    use minesweeper_model_overlay(app)

screen minesweeper_board(app):
    fixed:
        xpos app.board_x
        ypos app.board_y
        xysize (app.board_w, app.board_h)

        if app.won and app.reveal_image_path:
            $ win_image = app.image_displayable(app.reveal_image_path)
            if win_image:
                add win_image xysize (app.board_w, app.board_h)
            else:
                add Solid("#373d48") xysize (app.board_w, app.board_h)
        else:
            for row in range(app.rows):
                for col in range(app.cols):
                    $ cell = app.cell_view(row, col)
                    if cell["image_displayable"]:
                        add Crop(cell["crop"], cell["image_displayable"]) xpos cell["x"] ypos cell["y"] xysize (cell["w"], cell["h"]) alpha cell["alpha"]
                    else:
                        add Solid(cell["fallback"]) xpos cell["x"] ypos cell["y"] xysize (cell["w"], cell["h"])
                    button:
                        xpos cell["x"]
                        ypos cell["y"]
                        xysize (cell["w"], cell["h"])
                        padding (0, 0)
                        background Null()
                        hover_background Solid("#3e495b80")
                        action Function(app.reveal_cell, row, col)
                        alternate Function(app.toggle_flag, row, col)

                        fixed:
                            xysize (cell["w"], cell["h"])
                            if cell["flag"]:
                                text "F" xalign 0.5 yalign 0.5 size 22 color "#eef1f5"
                            if cell["mine"]:
                                text app.mine_style xalign 0.5 yalign 0.5 size 24 color "#ec5858"
                            elif cell["number"]:
                                text str(cell["number"]) xalign 0.5 yalign 0.5 size 22 color cell["number_color"]

        add Solid("#0a0d12") xpos 0 ypos 0 xysize (app.board_w, 1)
        add Solid("#0a0d12") xpos 0 ypos app.board_h - 1 xysize (app.board_w, 1)
        add Solid("#0a0d12") xpos 0 ypos 0 xysize (1, app.board_h)
        add Solid("#0a0d12") xpos app.board_w - 1 ypos 0 xysize (1, app.board_h)

screen minesweeper_side_panel(app):
    frame:
        xpos 620
        ypos 84
        xysize (310, 586)
        background Solid("#222731")

        vbox:
            xpos 18
            ypos 18
            spacing 10

            textbutton "Start / Restart" action Function(app.start_game) xsize 270
            textbutton "Settings" action Show("minesweeper_settings", app=app) xsize 270
            textbutton "BGM Play / Pause" action Function(app.toggle_bgm) xsize 270

            null height 10
            text "Left click: reveal" size 16 color "#9aa4b2"
            text "Right click: flag" size 16 color "#9aa4b2"

screen minesweeper_model_overlay(app):
    $ model_w, model_h = app.model_box_size()

    drag:
        drag_name "ms_live2d_model"
        xpos app.model_x
        ypos app.model_y
        xysize (model_w, model_h)
        draggable True
        droppable False
        drag_raise True
        drag_handle (0.0, 0.0, 1.0, 0.82)
        drag_offscreen (80, 80)
        clicked app.model_clicked
        dragged app.model_dragged

        fixed:
            xysize (model_w, model_h)

            add app.model_displayable() xalign 0.5 yalign 0.45 zoom app.model_scale

            text app.current_line:
                xalign 0.5
                yalign 0.9
                xsize model_w
                text_align 0.5
                size 18
                color "#eef1f5"
                outlines [(2, "#181b22", 0, 0)]

            hbox:
                xalign 1.0
                yalign 1.0
                spacing 4

                textbutton "-" action Function(app.adjust_model_scale, -0.1) xysize (34, 34)
                textbutton "+" action Function(app.adjust_model_scale, 0.1) xysize (34, 34)

screen minesweeper_settings(app):
    modal True
    zorder 20

    add Solid("#181b22")
    text "Settings" xpos 64 ypos 34 size 34 color "#eef1f5"
    text app.message xpos 210 ypos 48 size 18 color "#9aa4b2"

    frame:
        xpos 32
        ypos 92
        xysize (1216, 586)
        background Solid("#222731")

        fixed:
            textbutton "Back" xpos 24 ypos 18 xsize 120 action Hide("minesweeper_settings")
            textbutton "Reset defaults" xpos 1060 ypos 18 xsize 130 action Function(app.reset_defaults)

            text "Mine count" xpos 32 ypos 88 size 22 color "#eef1f5"
            text "[app.mine_count]" xpos 300 ypos 88 size 22 color "#4aa3ff"
            textbutton "-5" xpos 620 ypos 82 xsize 54 action Function(app.adjust_mines, -5)
            textbutton "-1" xpos 682 ypos 82 xsize 54 action Function(app.adjust_mines, -1)
            textbutton "+1" xpos 744 ypos 82 xsize 54 action Function(app.adjust_mines, 1)
            textbutton "+5" xpos 806 ypos 82 xsize 54 action Function(app.adjust_mines, 5)

            text "Image opacity" xpos 32 ypos 140 size 22 color "#eef1f5"
            text "covered [app.cover_opacity] / revealed [app.reveal_opacity]" xpos 300 ypos 144 size 16 color "#9aa4b2"
            textbutton "C-" xpos 620 ypos 134 xsize 54 action Function(app.adjust_opacity, "cover", -25)
            textbutton "C+" xpos 682 ypos 134 xsize 54 action Function(app.adjust_opacity, "cover", 25)
            textbutton "R-" xpos 744 ypos 134 xsize 54 action Function(app.adjust_opacity, "reveal", -25)
            textbutton "R+" xpos 806 ypos 134 xsize 54 action Function(app.adjust_opacity, "reveal", 25)

            text "Mine style" xpos 32 ypos 192 size 22 color "#eef1f5"
            text "[app.mine_style]" xpos 300 ypos 192 size 22 color "#4aa3ff"
            textbutton "O" xpos 620 ypos 186 xsize 54 action Function(app.set_mine_style, "O")
            textbutton "X" xpos 682 ypos 186 xsize 54 action Function(app.set_mine_style, "X")
            textbutton "#" xpos 744 ypos 186 xsize 54 action Function(app.set_mine_style, "#")
