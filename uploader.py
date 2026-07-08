from core import bot, user_sessions, session_lock, task_queue, DOWNLOAD_DIR, COOKIES_FILE
import core
import yt_dlp
import threading
import time
import os
import re
import subprocess
import requests
import uuid
import zipfile
import random

# استيراد كافة وحدات المعالجة
import media_editor
import ai_tools
import advanced_ai
import audio_tools

# ==========================================================
# مصفوفة مفاتيح الـ API (نظام توزيع الأحمال - Load Balancing)
# ==========================================================
GEMINI_API_KEYS = [
    "AIzaSyBjfN20M4YbiVYzJ4_0GgA-cG8qARJoUpk",
    "AIzaSyCNtOImAX1wOy4vo9Efhoo3IPy-ZEL7Psw"
]

# ==========================================================
# 1. دوال مساعدة وتخطي أخطاء تيليجرام
# ==========================================================
def safe_send_message(chat_id, text):
    """دالة ذكية لمنع انهيار البوت إذا أرسل الذكاء الاصطناعي رموز Markdown غير مكتملة"""
    try:
        # المحاولة الأولى: إرسال النص منسقاً
        bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception as e:
        if "parse entities" in str(e).lower() or "markdown" in str(e).lower():
            # المحاولة الثانية: إذا اعترض تيليجرام، نرسل النص ككلام عادي بدون تنسيق
            bot.send_message(chat_id, text)
        else:
            bot.send_message(chat_id, f"❌ تعذر إرسال مخرجات الذكاء الاصطناعي بسبب طول النص.")

def clean_ansi(text): return re.sub(r'\x1b\[[0-9;]*m', '', str(text))

def make_progress_bar(percent_str, length=12):
    try: pct = float(percent_str.replace('%', '').strip())
    except: pct = 0.0
    filled = int((pct / 100.0) * length)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {pct:.1f}%"

def get_safe_title(title):
    if not title: return "Media_" + str(uuid.uuid4())[:6]
    safe = re.sub(r'[^\w\s\u0600-\u06FF-]', '', str(title))
    safe = " ".join(safe.split())[:40].strip()
    return safe if safe else "Media_" + str(uuid.uuid4())[:6]

def get_unique_filename(title, ext):
    base_path = os.path.join(DOWNLOAD_DIR, f"{get_safe_title(title)}")
    if not os.path.exists(f"{base_path}.{ext}"): return f"{base_path}.%(ext)s"
    counter = 1
    while os.path.exists(f"{base_path}({counter}).{ext}"): counter += 1
    return f"{base_path}({counter}).%(ext)s"

def download_thumbnail(thumb_url, title):
    if not thumb_url: return None
    try:
        thumb_path = os.path.join(DOWNLOAD_DIR, f"{get_safe_title(title)}_thumb.jpg")
        response = requests.get(thumb_url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(thumb_path, 'wb') as f:
                for chunk in response.iter_content(1024): f.write(chunk)
            return thumb_path
    except: pass
    return None

# ==========================================================
# 2. الطابور
# ==========================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('addq_'))
def add_to_queue(call):
    chat_id = call.message.chat.id
    quality = call.data.split('_')[1] 
    with session_lock:
        if chat_id not in user_sessions:
            bot.answer_callback_query(call.id, "الجلسة انتهت. ابعت اللينك من تاني.", show_alert=True)
            return
        session_data = dict(user_sessions[chat_id])
        session_data['selected_indices'] = set(session_data.get('selected_indices', []))
    bot.edit_message_text("📥 طلبك دخل الطابور. ثواني وهنبدأ المعالجة...", chat_id, call.message.message_id)
    task_queue.put({'chat_id': chat_id, 'session': session_data, 'quality': quality})
    with core.queue_processing_lock:
        if not core.is_queue_running:
            core.is_queue_running = True
            threading.Thread(target=process_queue, daemon=True).start()

def process_queue():
    while not task_queue.empty():
        task = task_queue.get()
        chat_id, session, quality = task['chat_id'], task['session'], task['quality']
        try:
            if session['is_playlist']:
                selected = sorted(list(session['selected_indices']))
                bot.send_message(chat_id, f"🚀 بنبدأ تجهيز فيديوهات القائمة ({len(selected)} مقاطع)...")
                for idx in selected:
                    entry = session['entries'][idx]
                    url = entry.get('url', entry.get('webpage_url'))
                    title = entry.get('title', f'Video_{idx+1}')
                    msg = bot.send_message(chat_id, f"⏳ جاري سحب المقطع [{idx+1}]: {title[:30]}...")
                    execute_download(chat_id, msg.message_id, session, url, title, quality, 0, 0, entry.get('thumbnail'))
            else:
                msg = bot.send_message(chat_id, "⏳ بدأنا نسحب الملف للسيرفر...")
                execute_download(chat_id, msg.message_id, session, session['url'], session['title'], quality, session['start_sec'], session['end_sec'], session.get('thumb_url'))
        except Exception as e: print(f"Queue Error: {e}")
        task_queue.task_done()
    with core.queue_processing_lock: core.is_queue_running = False

# ==========================================================
# 3. محرك التنفيذ الرئيسي للمزايا الاحترافية
# ==========================================================
def execute_download(chat_id, msg_id, session_data, url, title, quality, start_sec, end_sec, thumb_url):
    last_update_time = 0
    premium_feats = session_data.get('premium_features', [])
    speed_val = session_data.get('speed_val', 1.5)
    
    # اختيار مفتاح عشوائي من المفاتيح لتوزيع الضغط على حسابات جوجل
    current_api_key = random.choice(GEMINI_API_KEYS)
    
    def progress_hook(d):
        nonlocal last_update_time
        if d['status'] == 'downloading':
            current_time = time.time()
            if current_time - last_update_time > 3.5: 
                pct = make_progress_bar(clean_ansi(d.get('_percent_str', '0%')))
                spd = clean_ansi(d.get('_speed_str', '0 B/s')).strip()
                eta = clean_ansi(d.get('_eta_str', '00:00')).strip()
                try: bot.edit_message_text(f"⬇️ بنسحب الملف للسيرفر بتاعنا...\n\n{pct}\n⚡ السرعة: {spd} | ⏱️ المتبقي: {eta}", chat_id, msg_id)
                except: pass
                last_update_time = current_time

    ext_target = "mp3" if quality == "mp3" else "mkv"
    out_template = get_unique_filename(title, ext_target)
    ydl_opts = {
        'outtmpl': out_template, 'progress_hooks': [progress_hook], 
        'quiet': True, 'no_warnings': True, 'writesubtitles': True, 'subtitleslangs': ['ar', 'en'], 'embedsubtitles': True,
        'windowsfilenames': True, 'restrictfilenames': True, 'retries': 30, 'fragment_retries': 30, 'nocheckcertificate': True, 'ignoreerrors': True
    }
    if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE
    
    if quality == "mp3": ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]})
    else:
        res = quality.replace('p', '')
        ydl_opts.update({'format': f'bestvideo[height<={res}]+bestaudio/best/best', 'merge_output_format': 'mkv'})
        
    if start_sec > 0 or end_sec > 0:
        ydl_opts['download_ranges'] = lambda info_dict, ydl: [{'start_time': start_sec, 'end_time': end_sec if end_sec > 0 else info_dict.get('duration')}]
        ydl_opts['postprocessor_args'] = {'video': ['-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac']}

    dl_file, local_thumb = None, None
    try:
        local_thumb = download_thumbnail(thumb_url, title)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: raise Exception("تعذر جلب الملف من المصدر")
            dl_file = ydl.prepare_filename(info)
            if quality == "mp3": dl_file = dl_file.rsplit('.', 1)[0] + '.mp3'

        bot.edit_message_text("⚙️ الملف نزل، بنبدأ المعالجة الاحترافية (AI ومونتاج)...", chat_id, msg_id)
        
        # --------------------------------------------------------
        # 1. مهام الذكاء الاصطناعي 
        # --------------------------------------------------------
        if premium_feats:
            if 'ai_sum' in premium_feats:
                bot.edit_message_text("🤖 الذكاء الاصطناعي بيلخص المحاضرة...", chat_id, msg_id)
                res = ai_tools.analyze_audio_with_ai(dl_file, current_api_key)
                # تقسيم النص لتفادي الحد الأقصى لرسائل تيليجرام واستخدام Safe Send
                chunks = [res[i:i+4000] for i in range(0, len(res), 4000)]
                bot.send_message(chat_id, "📝 **الملخص العام:**", parse_mode="Markdown")
                for chunk in chunks: safe_send_message(chat_id, chunk)

            if 'ai_chap' in premium_feats:
                bot.edit_message_text("📑 الذكاء الاصطناعي بيفهرس المحاضرة زمنياً...", chat_id, msg_id)
                res = advanced_ai.generate_auto_chapters(dl_file, current_api_key)
                bot.send_message(chat_id, "📑 **الفهرس التلقائي:**", parse_mode="Markdown")
                safe_send_message(chat_id, res)

            if 'ai_ref' in premium_feats:
                bot.edit_message_text("🔗 جاري استخراج الروابط والمصادر المذكورة...", chat_id, msg_id)
                res = advanced_ai.extract_links_and_references(dl_file, current_api_key)
                bot.send_message(chat_id, "🔗 **المصادر والروابط:**", parse_mode="Markdown")
                safe_send_message(chat_id, res)

        # --------------------------------------------------------
        # 2. السلايدز و قارئ الشاشة (OCR)
        # --------------------------------------------------------
        if premium_feats and ('slides' in premium_feats or 'ai_ocr' in premium_feats):
            bot.edit_message_text("🖼️ بنستخرج السلايدز بذكاء (عزل الماوس وتكرار المشاهد)...", chat_id, msg_id)
            slides_folder = os.path.join(DOWNLOAD_DIR, f"slides_{uuid.uuid4().hex[:6]}")
            slides = media_editor.extract_slides(dl_file, slides_folder)
            
            if slides:
                if 'ai_ocr' in premium_feats:
                    bot.edit_message_text("👁️ الـ AI بيقرأ النصوص والأكواد من السلايدز...", chat_id, msg_id)
                    ocr_res = advanced_ai.extract_text_from_slides_ocr(slides, current_api_key)
                    bot.send_message(chat_id, "👁️ **نصوص وأكواد السلايدز:**", parse_mode="Markdown")
                    safe_send_message(chat_id, ocr_res)
                
                if 'slides' in premium_feats:
                    zip_path = os.path.join(DOWNLOAD_DIR, f"Slides_{get_safe_title(title)}.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for s in slides: zf.write(s, os.path.basename(s))
                    with open(zip_path, 'rb') as zdoc:
                        bot.send_document(chat_id, zdoc, caption="🖼️ جميع السلايدز مجمعة بدقة عالية.")
                    try: os.remove(zip_path)
                    except: pass
            
            try:
                for s in slides: os.remove(s)
                os.rmdir(slides_folder)
            except: pass

        # --------------------------------------------------------
        # 3. الهندسة الصوتية 
        # --------------------------------------------------------
        if premium_feats:
            if 'aud_sil' in premium_feats:
                bot.edit_message_text("✂️ بنحذف فترات الصمت لتوفير وقتك...", chat_id, msg_id)
                dl_file = audio_tools.remove_silence(dl_file)
            if 'aud_noi' in premium_feats:
                bot.edit_message_text("🎧 بنعزل الضوضاء وبنقي الصوت...", chat_id, msg_id)
                dl_file = audio_tools.reduce_noise(dl_file)
            if 'aud_voc' in premium_feats:
                bot.edit_message_text("🎤 بنعزل صوت الموسيقى ونخلي صوت الشرح بس...", chat_id, msg_id)
                dl_file = audio_tools.isolate_vocals(dl_file)

        # --------------------------------------------------------
        # 4. المونتاج المرئي
        # --------------------------------------------------------
        if premium_feats:
            if 'speed' in premium_feats:
                bot.edit_message_text(f"⏩ بنسرع الفيديو بمقدار {speed_val}x ...", chat_id, msg_id)
                fast_file = os.path.join(DOWNLOAD_DIR, f"fast_{os.path.basename(dl_file)}")
                dl_file = media_editor.change_video_speed(dl_file, fast_file, speed=speed_val)

            if 'compress' in premium_feats:
                bot.edit_message_text("🗜️ بنضغط الفيديو لأصغر حجم ممكن...", chat_id, msg_id)
                comp_file = os.path.join(DOWNLOAD_DIR, f"comp_{os.path.basename(dl_file)}")
                dl_file = media_editor.compress_video(dl_file, comp_file)

            if 'gif' in premium_feats:
                bot.edit_message_text("🎞️ بنحول الملف لـ GIF...", chat_id, msg_id)
                gif_file = os.path.join(DOWNLOAD_DIR, f"gif_{os.path.basename(dl_file)}.gif")
                dl_file = media_editor.create_gif(dl_file, gif_file)
                quality = 'gif'
        
        # --------------------------------------------------------
        # التقسيم والرفع النهائي
        # --------------------------------------------------------
        file_size_mb = os.path.getsize(dl_file) / (1024 * 1024)
        files_to_send = [dl_file]
        
        if file_size_mb > 49.5:
            bot.edit_message_text(f"✂️ حجم الملف ({file_size_mb:.1f} MB) كبير.. بنقسمه...", chat_id, msg_id)
            base_name, ext = dl_file.rsplit('.', 1)
            subprocess.run(['ffmpeg', '-i', dl_file, '-c', 'copy', '-map', '0', '-segment_time', '00:04:00', '-f', 'segment', '-reset_timestamps', '1', f'{base_name}_part%03d.{ext}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            files_to_send = sorted([os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.startswith(os.path.basename(base_name) + "_part")])
            os.remove(dl_file) 

        for idx, f_path in enumerate(files_to_send):
            part_suffix = f" (جزء {idx+1}/{len(files_to_send)})" if len(files_to_send) > 1 else ""
            upload_msg = f"📤 الملف جهز وبنبعتهولك!{part_suffix}\n💡 تقدر تقفل وتخرج، أول ما يوصل هيجيلك إشعار."
            bot.edit_message_text(upload_msg, chat_id, msg_id)
            
            with open(f_path, 'rb') as f:
                caption_text = f"🎬 *{get_safe_title(title)}*{part_suffix}"
                if local_thumb and os.path.exists(local_thumb):
                    with open(local_thumb, 'rb') as thumb_data:
                        if quality == "mp3": bot.send_audio(chat_id, f, caption=caption_text, parse_mode="Markdown", thumb=thumb_data, timeout=60000)
                        elif quality == "gif": bot.send_document(chat_id, f, caption=caption_text, parse_mode="Markdown", thumb=thumb_data, timeout=60000)
                        else: bot.send_video(chat_id, f, caption=caption_text, parse_mode="Markdown", supports_streaming=True, thumb=thumb_data, timeout=60000)
                else:
                    if quality == "mp3": bot.send_audio(chat_id, f, caption=caption_text, parse_mode="Markdown", timeout=60000)
                    elif quality == "gif": bot.send_document(chat_id, f, caption=caption_text, parse_mode="Markdown", timeout=60000)
                    else: bot.send_video(chat_id, f, caption=caption_text, parse_mode="Markdown", supports_streaming=True, timeout=60000)
            os.remove(f_path)
            
        bot.edit_message_text("✅ الملف وصل بالسلامة!", chat_id, msg_id)
            
    except Exception as e:
        try: bot.edit_message_text(f"❌ حصلت مشكلة.\nالسبب: {str(e)[:100]}", chat_id, msg_id)
        except: pass
        if dl_file and os.path.exists(dl_file): os.remove(dl_file)
    finally:
        time.sleep(1.5)
        try:
            if local_thumb and os.path.exists(local_thumb): os.remove(local_thumb)
        except: pass