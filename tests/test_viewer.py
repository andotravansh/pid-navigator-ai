"""Tests for the zoom and pan crop helper."""

from PIL import Image

from ui.viewer import crop_view


def test_zoom_one_returns_whole_image():
    image = Image.new("RGB", (400, 200))
    assert crop_view(image, 1.0, 50, 50).size == (400, 200)


def test_zoom_halves_the_visible_area():
    image = Image.new("RGB", (400, 200))
    assert crop_view(image, 2.0, 50, 50).size == (200, 100)


def test_pan_is_clamped_inside_the_image():
    image = Image.new("RGB", (400, 200))
    assert crop_view(image, 4.0, 0, 0).size == (100, 50)
    assert crop_view(image, 4.0, 100, 100).size == (100, 50)
    assert crop_view(image, 4.0, 500, -40).size == (100, 50)


def test_invalid_zoom_is_limited():
    image = Image.new("RGB", (400, 200))
    assert crop_view(image, 0.1, 50, 50).size == (400, 200)


def test_large_views_are_downscaled():
    image = Image.new("RGB", (6000, 3000))
    view = crop_view(image, 1.0, 50, 50, max_side=1200)
    assert max(view.size) == 1200
