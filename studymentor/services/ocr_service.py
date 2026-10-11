import shutil


class OCRUnavailable(Exception):
    pass


def available():
    try:
        import pytesseract  # noqa
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def ocr_image(img):
    """OCR a PIL image after light preprocessing. Raises OCRUnavailable if Tesseract is missing."""
    if not available():
        raise OCRUnavailable("Tesseract OCR is not installed on the server.")
    import pytesseract
    from PIL import ImageOps
    g = ImageOps.autocontrast(ImageOps.grayscale(img))
    if max(g.size) < 1600:
        f = 1600 / max(g.size)
        g = g.resize((int(g.width * f), int(g.height * f)))
    return pytesseract.image_to_string(g, config="--psm 3")
