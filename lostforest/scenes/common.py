"""Helpers shared by menu scenes."""
from ..ui.backdrop import MenuBackdrop
from ..world.level import discover_levels


def backdrop(app):
    """The animated menu background is shared so it keeps scrolling between menus."""
    if getattr(app, "backdrop", None) is None:
        app.backdrop = MenuBackdrop(app.assets)
    return app.backdrop


def levels(app):
    if getattr(app, "levels", None) is None:
        app.levels = discover_levels()
    return app.levels


def start_level(app, index):
    from .gameplay import GameplayScene
    app.scenes.switch(GameplayScene(app, index))
