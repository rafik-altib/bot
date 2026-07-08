import os
import subprocess
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'BotFiles')

def remove_silence(input_file):
    """
    يقوم بحذف فترات الصمت (أكثر من ثانية) من الفيديو أو المقطع الصوتي.
    يوفر وقت المحاضرة بشكل كبير جداً!
    """
    output_file = os.path.join(DOWNLOAD_DIR, f"no_silence_{os.path.basename(input_file)}")
    try:
        # فلتر يزيل الصمت الأقل من -30 ديسبل
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-af', 'silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-30dB',
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except: pass
    return input_file

def reduce_noise(input_file):
    """
    تنقية الصوت وإزالة الضوضاء الخلفية (وشوشة المروحة، صدى المدرج).
    """
    output_file = os.path.join(DOWNLOAD_DIR, f"clear_audio_{os.path.basename(input_file)}")
    try:
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-af', 'afftdn', # فلتر تقليل الضوضاء
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except: pass
    return input_file

def isolate_vocals(input_file):
    """
    محاولة عزل صوت المتحدث وتقليل الموسيقى الخلفية قدر الإمكان.
    (تعمل بتقنية إلغاء الطور Phase Cancellation)
    """
    output_file = os.path.join(DOWNLOAD_DIR, f"vocal_only_{os.path.basename(input_file)}")
    try:
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-af', 'pan=stereo|c0=c0|c1=-c1', # عزل الترددات الوسطى
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file): return output_file
    except: pass
    return input_file

print("🎛️ تم تحميل أدوات الهندسة الصوتية (audio_tools.py)...")