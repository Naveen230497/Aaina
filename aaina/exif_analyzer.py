"""EXIF Privacy Analyzer: Detects hidden metadata in uploaded images."""
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io

def analyze_exif(image_bytes: bytes) -> dict:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img.getexif()
        
        if not exif_data:
            return {"status": "clean", "data": {}}

        results = {}
        has_gps = False
        
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name == "GPSInfo":
                has_gps = True
                gps_data = {}
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_data[sub_tag] = value[t]
                results["GPS"] = "Found (Coordinates Hidden)"
            elif isinstance(value, (str, int, float)):
                if tag_name in ("Make", "Model", "DateTime", "Software"):
                    results[tag_name] = str(value)
                    
        if has_gps:
            return {"status": "danger", "data": results}
        elif results:
            return {"status": "warning", "data": results}
        else:
            return {"status": "clean", "data": {}}
            
    except Exception:
        return {"status": "clean", "data": {}}
