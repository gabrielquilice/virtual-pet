from PySide6.QtCore import QPoint

from virtual_pet import sprites


def test_art_block_becomes_a_frame():
    frame = sprites.art("""
        .K.
        KBK
    """)

    assert frame == (".K.", "KBK")


def test_mirrored_frame_faces_the_other_way():
    assert sprites.mirrored(("KB..", ".WN.")) == ("..BK", ".NW.")


def test_silhouette_covers_only_visible_pixels():
    region = sprites.silhouette(("K..", ".KK"), 3)

    assert region.contains(QPoint(1, 1))  # "K" at (0, 0)
    assert not region.contains(QPoint(4, 1))  # "." at (1, 0)
    assert region.contains(QPoint(8, 5))  # "K" at (2, 1)
    assert not region.contains(QPoint(1, 4))  # "." at (0, 1)


def test_animation_loops_through_its_frames_at_its_rate():
    animation = sprites.Animation((("a",), ("b",)), fps=2)

    shown = [animation.frame_at(seconds) for seconds in (0, 0.4, 0.6, 1.2)]

    assert shown == [("a",), ("a",), ("b",), ("a",)]


def test_each_column_can_be_drawn_in_its_own_palette():
    palettes = ({"B": "#00ff00"}, {"B": "#0000ff"})

    image = sprites.draw_columns(("BB.", ".BB"), palettes, (0, 1, 1))

    assert image.pixelColor(0, 0).name() == "#00ff00"
    assert image.pixelColor(1, 0).name() == "#0000ff"
    assert image.pixelColor(2, 0).alpha() == 0
    assert image.pixelColor(2, 1).name() == "#0000ff"


def test_one_palette_draws_every_column_alike():
    assert sprites.draw(("BB",), {"B": "#00ff00"}) == sprites.draw_columns(
        ("BB",), ({"B": "#00ff00"},), (0, 0)
    )
