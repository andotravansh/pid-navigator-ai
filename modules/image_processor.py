"""Optional OpenCV preprocessing for diagram images.

The original image is never modified; every function returns new data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

MIN_DIMENSION = 64
MAX_DIMENSION = 16000


@dataclass(frozen=True)
class PreprocessOptions:
    """Which preprocessing steps to apply (all off by default)."""

    grayscale: bool = False
    enhance_contrast: bool = False
    clip_limit: float = 2.0
    max_dimension: Optional[int] = None
    threshold: bool = False
    threshold_block_size: int = 31
    threshold_c: int = 10

    @property
    def is_noop(self) -> bool:
        """True when no step is enabled."""
        return not (
            self.grayscale
            or self.enhance_contrast
            or self.threshold
            or self.max_dimension
        )


def pil_to_array(image: Image.Image) -> np.ndarray:
    """Convert a PIL image to an RGB uint8 array."""
    return np.array(image.convert("RGB"), dtype=np.uint8)


def array_to_pil(array: np.ndarray) -> Image.Image:
    """Convert a grayscale (H, W) or RGB (H, W, 3) array to a PIL image."""
    return Image.fromarray(array)


def to_grayscale(array: np.ndarray) -> np.ndarray:
    """Convert an RGB array to grayscale (no-op if already single-channel)."""
    if array.ndim == 2:
        return array
    return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)


def enhance_contrast(
    array: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8
) -> np.ndarray:
    """Apply CLAHE contrast enhancement (on the lightness channel for colour)."""
    if clip_limit <= 0:
        raise ValueError("clip_limit must be positive.")
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    if array.ndim == 2:
        return clahe.apply(array)
    lab = cv2.cvtColor(array, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def apply_adaptive_threshold(
    gray: np.ndarray, block_size: int = 31, c: int = 10
) -> np.ndarray:
    """Binarise a grayscale image with a local (adaptive) threshold."""
    if gray.ndim != 2:
        raise ValueError("Thresholding requires a grayscale image.")
    if block_size < 3 or block_size % 2 == 0:
        raise ValueError("block_size must be an odd number >= 3.")
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )


def resize_to_max_dimension(array: np.ndarray, max_dimension: int) -> np.ndarray:
    """Scale the image so its longest side equals ``max_dimension``."""
    if not MIN_DIMENSION <= max_dimension <= MAX_DIMENSION:
        raise ValueError(
            f"max_dimension must be between {MIN_DIMENSION} and {MAX_DIMENSION}."
        )
    height, width = array.shape[:2]
    scale = max_dimension / max(height, width)
    if abs(scale - 1.0) < 1e-6:
        return array.copy()
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(array, new_size, interpolation=interpolation)


def preprocess(image: Image.Image, options: PreprocessOptions) -> Image.Image:
    """Run the enabled steps in order: resize, grayscale, contrast, threshold.

    The input image is left untouched; a new image is always returned.
    """
    if options.is_noop:
        return image.copy()

    array = pil_to_array(image)
    if options.max_dimension:
        array = resize_to_max_dimension(array, options.max_dimension)
    if options.grayscale or options.threshold:
        array = to_grayscale(array)
    if options.enhance_contrast:
        array = enhance_contrast(array, options.clip_limit)
    if options.threshold:
        array = apply_adaptive_threshold(
            array, options.threshold_block_size, options.threshold_c
        )
    return array_to_pil(array)