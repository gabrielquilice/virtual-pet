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
