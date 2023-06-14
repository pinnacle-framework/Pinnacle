import PIL.Image
import PIL.JpegImagePlugin
import PIL.PngImagePlugin
import io

from pinnacledb.core.type import Type


def encode_pil_image(x):
    buffer = io.BytesIO()
    x.save(buffer, format='png')
    return buffer.getvalue()


def decode_pil_image(bytes):
    return PIL.Image.open(io.BytesIO(bytes))


pil_image = Type(
    'pil_image',
    encoder=encode_pil_image,
    decoder=decode_pil_image,
)
