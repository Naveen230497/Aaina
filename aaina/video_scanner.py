"""Video Scanner Module: Extract keyframes from MP4/MOV for deepfake detection."""
import cv2
import tempfile
import os

def extract_keyframes(video_bytes: bytes, num_frames: int = 3) -> list:
    """Extracts evenly spaced frames from a video file in memory."""
    frames = []
    
    # Write bytes to a temporary file since OpenCV requires a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(video_bytes)
        temp_path = temp_video.name
        
    try:
        cap = cv2.VideoCapture(temp_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames <= 0:
            return frames
            
        # Calculate frame indices to extract
        step = max(1, total_frames // (num_frames + 1))
        indices = [step * i for i in range(1, num_frames + 1)]
        
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # Convert frame to JPEG bytes
                is_success, buffer = cv2.imencode(".jpg", frame)
                if is_success:
                    frames.append(buffer.tobytes())
                    
        cap.release()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass # Ignore file lock errors on Windows
        
    return frames
