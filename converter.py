import os
import subprocess
import uuid

# المسار الافتراضي للحفظ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'BotFiles')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def universal_convert(input_file, target_extension):
    """
    دالة عبقرية تستخدم FFmpeg لتحويل أي صيغة ميديا (فيديو، صوت، صورة) إلى أي صيغة أخرى.
    target_extension: mp4, mp3, jpg, png, mkv, avi, webp, wav, etc.
    """
    try:
        # إزالة النقطة لو المستخدم كتبها (مثال: .jpg نخليها jpg)
        target_extension = target_extension.replace('.', '').lower()
        
        base_name = os.path.basename(input_file).rsplit('.', 1)[0]
        output_file = os.path.join(DOWNLOAD_DIR, f"{base_name}_converted_{uuid.uuid4().hex[:4]}.{target_extension}")
        
        # إعدادات خاصة لتحويلات الصور لضمان الجودة
        if target_extension in ['jpg', 'jpeg', 'png', 'webp', 'bmp']:
            cmd = ['ffmpeg', '-y', '-i', input_file, '-q:v', '2', output_file]
        
        # إعدادات خاصة لتحويلات الصوت
        elif target_extension in ['mp3', 'wav', 'ogg', 'm4a']:
            cmd = ['ffmpeg', '-y', '-i', input_file, '-vn', '-c:a', 'libmp3lame' if target_extension=='mp3' else 'copy', output_file]
            
        # إعدادات عامة للفيديو والصيغ الأخرى
        else:
            cmd = ['ffmpeg', '-y', '-i', input_file, '-c:v', 'copy', '-c:a', 'copy', output_file]
            
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(output_file):
            return output_file
            
    except Exception as e:
        print(f"Conversion Error: {e}")
        
    return None # يرجع None في حالة الفشل

print("🔄 تم تحميل محول الصيغ الشامل (converter.py)...")