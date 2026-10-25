import ctypes, os, sys
from PIL import Image

dll_path = os.path.abspath("SmallImageInterface.dll")
sii = ctypes.CDLL(dll_path)

class SiiImage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("width", ctypes.c_uint16), ("height", ctypes.c_uint16), ("flags", ctypes.c_uint8), ("pixels", ctypes.POINTER(ctypes.c_uint8))]

sii.sii_encode_file.argtypes = [ctypes.POINTER(SiiImage), ctypes.c_void_p, ctypes.c_char_p]
sii.sii_encode_file.restype = ctypes.c_int
sii.sii_last_error.restype = ctypes.c_char_p

def convert(png_path, sii_path):
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    if w > 4096 or h > 4096: print("Слишком большая!"); return
    pixels = img.tobytes()
    flat_pixels = (ctypes.c_uint8 * len(pixels)).from_buffer_copy(pixels)
    sii_img = SiiImage(width=w, height=h, flags=0, pixels=flat_pixels)
    if sii.sii_encode_file(ctypes.byref(sii_img), None, sii_path.encode('utf-8')) == 0:
        print(f"✅ УСПЕХ: {png_path} -> {sii_path} ({os.path.getsize(sii_path)} байт)")
    else:
        print(f"❌ ОШИБКА: {sii.sii_last_error().decode()}")

if __name__ == "__main__":
    convert(sys.argv[1], os.path.splitext(sys.argv[1])[0] + ".sii")
