import struct
import zlib
from PIL import Image

class SIIImage:
    def __init__(self, width, height, pixels):
        self.width = width
        self.height = height
        self.pixels = pixels # bytearray RGBA

    def to_pil(self):
        return Image.frombytes("RGBA", (self.width, self.height), bytes(self.pixels))

def decode(data: bytes) -> SIIImage:
    if len(data) < 16:
        raise ValueError("File too small")
    
    magic, version, flags, width, height, chunk_count, reserved = struct.unpack("<4sBBHHHI", data[:16])
    
    if magic != b"SII1":
        raise ValueError("Invalid magic")
    if version != 1:
        raise ValueError("Unsupported version")

    offset = 16
    palette = []
    pixels = bytearray(width * height * 4)

    for _ in range(chunk_count):
        chunk_type, length, crc = struct.unpack("<4sII", data[offset:offset+12])
        offset += 12
        chunk_data = data[offset:offset+length]
        
        if zlib.crc32(chunk_data) & 0xFFFFFFFF != crc:
            raise ValueError("CRC32 mismatch")
        
        if chunk_type == b"PALT":
            for i in range(0, length, 4):
                palette.append(chunk_data[i:i+4])
        elif chunk_type == b"DATA":
            ptr = 0
            pixel_idx = 0
            while ptr < len(chunk_data) and pixel_idx < width * height:
                index = chunk_data[ptr]
                run = struct.unpack("<H", chunk_data[ptr+1:ptr+3])[0]
                ptr += 3
                
                color = palette[index]
                for _ in range(run):
                    if pixel_idx >= width * height: break
                    pixels[pixel_idx*4 : pixel_idx*4+4] = color
                    pixel_idx += 1
        offset += length

    return SIIImage(width, height, pixels)

def load(filepath: str) -> SIIImage:
    with open(filepath, "rb") as f:
        return decode(f.read())

def encode(img: Image.Image, max_colors=256) -> bytes:
    img = img.convert("RGBA")
    width, height = img.size
    pixels = list(img.getdata())

    palette = []
    palette_map = {}
    
    for r, g, b, a in pixels:
        if a < 128:
            continue
        color = (r, g, b, a)
        if color not in palette_map:
            if len(palette) < max_colors - 1:
                palette_map[color] = len(palette)
                palette.append(color)
    
    trans_index = len(palette)
    palette.append((0, 0, 0, 0))

    rle_data = bytearray()
    i = 0
    total_pixels = width * height

    while i < total_pixels:
        r, g, b, a = pixels[i]
        
        if a < 128:
            current_idx = trans_index
        else:
            current_idx = palette_map.get((r, g, b, a), trans_index)

        run = 1
        while i + run < total_pixels and run < 65535:
            nr, ng, nb, na = pixels[i + run]
            if na < 128:
                next_idx = trans_index
            else:
                next_idx = palette_map.get((nr, ng, nb, na), trans_index)
            
            if next_idx != current_idx:
                break
            run += 1

        rle_data.extend(struct.pack("<BH", current_idx, run))
        i += run

    palt_data = b"".join([struct.pack("<BBBB", *c) for c in palette])
    palt_crc = zlib.crc32(palt_data) & 0xFFFFFFFF
    palt_chunk = struct.pack("<4sII", b"PALT", len(palt_data), palt_crc) + palt_data

    data_crc = zlib.crc32(rle_data) & 0xFFFFFFFF
    data_chunk = struct.pack("<4sII", b"DATA", len(rle_data), data_crc) + rle_data

    header = struct.pack("<4sBBHHHI", b"SII1", 1, 1, width, height, 2, 0)
    
    return header + palt_chunk + data_chunk

def save(img: Image.Image, filepath: str, max_colors=256):
    data = encode(img, max_colors)
    with open(filepath, "wb") as f:
        f.write(data)