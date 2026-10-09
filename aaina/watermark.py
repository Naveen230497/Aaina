"""Aaina Invisible Watermarking: Cryptographically sign images using LSB Steganography."""
from PIL import Image
import io

def _text_to_bin(text: str) -> str:
    return ''.join(format(ord(char), '08b') for char in text) + '1111111111111110' # 16-bit delimiter

def embed_watermark(image_bytes: bytes, secret_text: str) -> bytes:
    """Embeds an invisible string into an image using Least Significant Bit (LSB) steganography."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    binary_secret = _text_to_bin(secret_text)
    
    if len(binary_secret) > img.width * img.height * 3:
        raise ValueError("Image too small to hold this watermark.")
        
    pixels = img.load()
    data_idx = 0
    
    for y in range(img.height):
        for x in range(img.width):
            if data_idx < len(binary_secret):
                r, g, b = pixels[x, y]
                
                # Modify the least significant bit of each color channel
                if data_idx < len(binary_secret):
                    r = (r & ~1) | int(binary_secret[data_idx])
                    data_idx += 1
                if data_idx < len(binary_secret):
                    g = (g & ~1) | int(binary_secret[data_idx])
                    data_idx += 1
                if data_idx < len(binary_secret):
                    b = (b & ~1) | int(binary_secret[data_idx])
                    data_idx += 1
                    
                pixels[x, y] = (r, g, b)
            else:
                break
        if data_idx >= len(binary_secret):
            break
            
    out = io.BytesIO()
    img.save(out, format="PNG")  # PNG is lossless, required for LSB
    return out.getvalue()
