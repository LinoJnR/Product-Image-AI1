"""Product-focused foreground extraction with optional human and shadow cleanup.

The product RGB pixels are always taken from the source image. Segmentation only
controls the alpha mask; it does not recolour or regenerate visible product pixels.
"""
import io
from functools import lru_cache

from PIL import Image, ImageFilter


@lru_cache(maxsize=2)
def _get_rembg_session(model_name='u2net'):
    """Cache the general foreground and human-segmentation models."""
    try:
        from rembg import new_session
        return new_session(model_name)
    except Exception as exc:
        raise RuntimeError(
            f"Could not initialize the '{model_name}' AI model. The first run may need "
            "internet access to download it. Check memory, model-cache write access, "
            f"and restart the app. Details: {exc}"
        ) from exc


def _get_mask(image, model_name):
    from rembg import remove
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    mask_bytes = remove(buf.getvalue(), only_mask=True, session=_get_rembg_session(model_name))
    with Image.open(io.BytesIO(mask_bytes)) as mask_image:
        mask = mask_image.convert('L')
        if mask.size != image.size:
            mask = mask.resize(image.size, Image.Resampling.LANCZOS)
        return mask.copy()


def make_white_background(
    image,
    remove_bg=True,
    transparent=False,
    remove_humans=True,
    zero_shadows=True,
    mask_threshold=145,
):
    """Extract foreground, subtract detected people/hands, and clean soft shadows.

    This is a best-effort segmentation pipeline, not generative inpainting. If a
    hand covers the product, the hidden product detail cannot be recovered from
    the source image. The user should inspect the preview before publishing.
    """
    original = image.convert('RGBA')
    if not remove_bg:
        foreground = original
    else:
        try:
            alpha = _get_mask(original, 'u2net')
            if remove_humans:
                # Human segmentation helps remove hands/arms that the general
                # foreground model may otherwise retain as part of the subject.
                human = _get_mask(original, 'u2net_human_seg')
                # Subtract only confidently detected human pixels. This can also
                # remove product pixels hidden behind fingers, which cannot be
                # reconstructed without a separate generative inpainting model.
                human = human.point(lambda p: 255 if p >= 96 else 0)
                # Pixel-wise subtraction using Pillow's ImageChops.
                from PIL import ImageChops
                alpha = ImageChops.subtract(alpha, human)

            if zero_shadows:
                # Discard low-confidence, soft mask pixels commonly associated
                # with cast/contact shadows. A stronger threshold is selectable.
                threshold = max(1, min(254, int(mask_threshold)))
                alpha = alpha.point(lambda p: 255 if p >= threshold else 0)
            else:
                # Retain antialiased edges while removing almost-transparent haze.
                alpha = alpha.point(lambda p: 0 if p < 18 else p)

            foreground = original.copy()
            foreground.putalpha(alpha)
        except ImportError as exc:
            raise RuntimeError(
                "Background removal is not installed. Run 'pip install -r requirements.txt'."
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f'Product extraction failed for this image: {exc}') from exc

    if transparent:
        return foreground
    white = Image.new('RGBA', original.size, (255, 255, 255, 255))
    white.alpha_composite(foreground)
    return white.convert('RGB')
