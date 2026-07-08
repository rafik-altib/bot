import os
import subprocess
import zipfile

# ==========================================================
# 1. تسريع الفيديو 
# ==========================================================
def change_video_speed(input_file, output_file, speed=1.5):
    try:
        video_pts = 1.0 / speed
        audio_tempo = speed
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-filter_complex', f'[0:v]setpts={video_pts}*PTS[v];[0:a]atempo={audio_tempo}[a]',
            '-map', '[v]', '-map', '[a]',
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except Exception as e:
        print(f"Error speeding up: {e}")
    return input_file 

# ==========================================================
# 2. ضغط الفيديو (بالمعادلة الذكية الجديدة)
# ==========================================================
def compress_video(input_file, output_file):
    try:
        # استخدام min(480,ih) يضمن أن الفيديو سيصغر فقط ولن يكبر أبداً إذا كانت جودته الأصلية ضعيفة
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-vf', "scale=-2:'min(480,ih)'", 
            '-vcodec', 'libx265', '-crf', '32', '-preset', 'faster',
            '-c:a', 'copy', 
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except Exception as e:
        print(f"Error compressing: {e}")
    return input_file

# ==========================================================
# 3. تحويل إلى GIF
# ==========================================================
def create_gif(input_file, output_file, duration=10):
    try:
        cmd = [
            'ffmpeg', '-y', '-t', str(duration), '-i', input_file,
            '-vf', 'fps=10,scale=480:-1:flags=lanczos',
            '-c:v', 'gif',
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except Exception as e:
        print(f"Error making GIF: {e}")
    return input_file

# ==========================================================
# 4. استخراج شرائح العرض (الخوارزمية الدقيقة والطوارئ)
# ==========================================================
def extract_slides(video_file, output_folder):
    """خوارزمية ذكية لاستخراج السلايدز مع خطة طوارئ لمنع الملفات الفارغة"""
    try:
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        output_pattern = os.path.join(output_folder, "Slide_%03d.jpg")
        
        # الاعتماد على فلتر mpdecimate لحذف الفريمات المكررة بذكاء، ثم أخذ لقطة
        cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-vf', "mpdecimate,setpts=N/FRAME_RATE/TB,fps=1/5", # لقطة لكل 5 ثواني من الفيديو الصافي
            '-q:v', '2', 
            output_pattern
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        slides = sorted([os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith('.jpg')])
        
        # خطة الطوارئ: لو الفلتر فشل والملف طلع فاضي، هناخد لقطة إجبارية كل 30 ثانية
        if not slides:
            print("Fallback: Using basic interval extraction...")
            cmd_fallback = [
                'ffmpeg', '-y', '-i', video_file,
                '-vf', "fps=1/30", 
                '-q:v', '2', 
                output_pattern
            ]
            subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            slides = sorted([os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith('.jpg')])
            
        return slides
    except Exception as e:
        print(f"Error extracting slides: {e}")
        return []

# ==========================================================
# 5. تجميع الملفات في ZIP
# ==========================================================
def create_zip_archive(file_paths_list, zip_output_path):
    try:
        with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths_list:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
        if os.path.exists(zip_output_path): return zip_output_path
    except Exception as e:
        print(f"Error creating ZIP: {e}")
    return None

print("✅ تم تحميل محرك المونتاج (media_editor.py) بنجاح...")