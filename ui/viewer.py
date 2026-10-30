"""Pure image helper for the zoom and pan viewer (no Streamlit)."""

from __future__ import annotations

from PIL import Image

MIN_ZOOM = 1.0
MAX_ZOOM = 16.0


def crop_view(
    image: Image.Image,
    zoom: float,
    pan_x_pct: float,
    pan_y_pct: float,
    max_side: int = 2400,
) -> Image.Image:
    """Return the visible region for a zoom factor and a centre point.

    ``pan_*_pct`` is the centre of the view as a percentage of the image.
    The result is always inside the image and is limited to ``max_side``
    pixels so the browser payload stays reasonable.
    """
    zoom = min(max(float(zoom), MIN_ZOOM), MAX_ZOOM)
    width, height = image.size
    crop_w = max(1.0, width / zoom)
    crop_h = max(1.0, height / zoom)
    centre_x = min(max(pan_x_pct, 0.0), 100.0) / 100.0 * width
    centre_y = min(max(pan_y_pct, 0.0), 100.0) / 100.0 * height
    left = min(max(centre_x - crop_w / 2, 0.0), width - crop_w)
    top = min(max(centre_y - crop_h / 2, 0.0), height - crop_h)
    view = image.crop((round(left), round(top), round(left + crop_w), round(top + crop_h)))
    view.thumbnail((max_side, max_side))
    return view
