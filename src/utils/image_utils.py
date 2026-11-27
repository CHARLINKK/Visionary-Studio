from PIL import Image, ImageDraw, ImageFont
import copy
import cv2
import numpy as np

def deskew_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
    
    if lines is not None:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line.flatten()[:4]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if -15 < angle < 15 and abs(angle) > 0.5:
                angles.append(angle)
            elif 75 < angle < 105:
                angles.append(angle - 90)
            elif -105 < angle < -75:
                angles.append(angle + 90)
                
        if angles:
            median_angle = np.median(angles)
            if abs(median_angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                return rotated
    return image

def preprocess_image(image_pil: Image.Image) -> Image.Image:
    """
    Pré-processa a imagem:
    1. Deskew
    2. Grayscale
    3. CLAHE
    4. Denoising
    Retorna RGB PIL Image.
    """
    image_np = np.array(image_pil.convert('RGB'))
    image_np = image_np[:, :, ::-1].copy() # RGB to BGR
    
    deskewed = deskew_image(image_np)
    gray = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10, templateWindowSize=7, searchWindowSize=21)
    
    rgb_result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb_result)

def _get_consecutive_trues(bool_array, min_length=5):
    gaps = []
    start = None
    for i, val in enumerate(bool_array):
        if val and start is None:
            start = i
        elif not val and start is not None:
            if i - start >= min_length:
                gaps.append((start, i))
            start = None
    if start is not None and len(bool_array) - start >= min_length:
        gaps.append((start, len(bool_array)))
    return gaps

def recursive_xy_cut(binary_image, x1, y1, x2, y2, min_w, min_h):
    if x2 - x1 < min_w or y2 - y1 < min_h:
        return [{"x1": x1, "y1": y1, "x2": x2, "y2": y2}]
        
    region = binary_image[y1:y2, x1:x2]
    
    row_means = region.mean(axis=1)
    h_gaps = _get_consecutive_trues(row_means > 242, min_length=8)
    
    if h_gaps:
        panels = []
        current_y = y1
        for gap_start, gap_end in h_gaps:
            mid_y = y1 + (gap_start + gap_end) // 2
            if mid_y - current_y >= min_h:
                panels.extend(recursive_xy_cut(binary_image, x1, current_y, x2, mid_y, min_w, min_h))
            current_y = y1 + gap_end
            
        if y2 - current_y >= min_h:
            panels.extend(recursive_xy_cut(binary_image, x1, current_y, x2, y2, min_w, min_h))
        return panels
        
    col_means = region.mean(axis=0)
    v_gaps = _get_consecutive_trues(col_means > 242, min_length=8)
    
    if v_gaps:
        panels = []
        current_x = x1
        for gap_start, gap_end in v_gaps:
            mid_x = x1 + (gap_start + gap_end) // 2
            if mid_x - current_x >= min_w:
                panels.append(recursive_xy_cut(binary_image, current_x, y1, mid_x, y2, min_w, min_h))
            current_x = x1 + gap_end
            
        if x2 - current_x >= min_w:
            panels.append(recursive_xy_cut(binary_image, current_x, y1, x2, y2, min_w, min_h))
            
        flat_panels = []
        panels.reverse()  # Right to Left (Manga)
        for p_list in panels:
            flat_panels.extend(p_list)
        return flat_panels
        
    return [{"x1": x1, "y1": y1, "x2": x2, "y2": y2}]

def detect_panels_recursive(image_pil: Image.Image) -> list[dict]:
    img_np = np.array(image_pil.convert("L"))
    _, binary = cv2.threshold(img_np, 235, 255, cv2.THRESH_BINARY)
    h, w = binary.shape
    min_w = w * 0.10
    min_h = h * 0.05
    return recursive_xy_cut(binary, 0, 0, w, h, min_w, min_h)

def slice_image_in_three(image: Image.Image, overlap_ratio: float = 0.05):
    width, height = image.size
    base_slice_height = height // 3
    overlap_pixels = int(height * overlap_ratio)
    
    slices = []
    top_y1 = 0
    top_y2 = base_slice_height + overlap_pixels
    slices.append({
        "image": image.crop((0, top_y1, width, min(top_y2, height))),
        "offset_x": 0,
        "offset_y": top_y1
    })
    
    mid_y1 = base_slice_height - overlap_pixels
    mid_y2 = (base_slice_height * 2) + overlap_pixels
    slices.append({
        "image": image.crop((0, max(0, mid_y1), width, min(mid_y2, height))),
        "offset_x": 0,
        "offset_y": max(0, mid_y1)
    })
    
    bot_y1 = (base_slice_height * 2) - overlap_pixels
    slices.append({
        "image": image.crop((0, max(0, bot_y1), width, height)),
        "offset_x": 0,
        "offset_y": max(0, bot_y1)
    })
    return slices

def upscale_image(image: Image.Image, scale_factor: float = 2.0):
    width, height = image.size
    new_size = (int(width * scale_factor), int(height * scale_factor))
    return image.resize(new_size, Image.Resampling.LANCZOS)

def draw_ocr_results(image: Image.Image, ocr_data: list, output_path: str):
    img_draw = copy.deepcopy(image)
    draw = ImageDraw.Draw(img_draw)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    for item in ocr_data:
        box = item["box"]
        text = item["text"]
        draw.rectangle(box, outline="red", width=3)
        text_bbox = draw.textbbox((box[0], max(0, box[1] - 25)), text, font=font)
        draw.rectangle(text_bbox, fill="red")
        draw.text((box[0], max(0, box[1] - 25)), text, font=font, fill="white")
        
    img_draw.save(output_path)
    print(f"Visualized OCR results saved to: {output_path}")
