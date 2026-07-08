from core import bot, user_sessions, session_lock, COOKIES_FILE
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import threading
import os

PAGE_SIZE = 10  # عدد الفيديوهات في كل صفحة

# ==========================================================
# 1. دوال مساعدة
# ==========================================================
def time_to_sec(time_str):
    try:
        parts = time_str.strip().split(':')
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except: pass
    return 0

# ==========================================================
# 2. الفحص الأولي السريع
# ==========================================================
def start_extraction(chat_id, msg_id):
    threading.Thread(target=_async_extract, args=(chat_id, msg_id)).start()

def _async_extract(chat_id, msg_id):
    with session_lock:
        url = user_sessions[chat_id]['url']
    
    try:
        ydl_opts = {
            'extract_flat': True, 
            'quiet': True, 
            'no_warnings': True, 
            'ignoreerrors': True  
        }
        if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                bot.edit_message_text("❌ معلش، مقدرناش نقرأ اللينك ده. اتأكد إنه شغال ومش برايفت.", chat_id, msg_id)
                return
            
            with session_lock:
                if 'entries' in info:
                    valid_entries = [e for e in info['entries'] if e is not None]
                    
                    user_sessions[chat_id]['is_playlist'] = True
                    user_sessions[chat_id]['entries'] = valid_entries
                    user_sessions[chat_id]['title'] = info.get('title', 'قائمة تشغيل')
                    user_sessions[chat_id]['pl_page'] = 0
                    is_playlist = True
                else:
                    user_sessions[chat_id]['is_playlist'] = False
                    user_sessions[chat_id]['title'] = info.get('title', 'فيديو مفرد')
                    user_sessions[chat_id]['thumb_url'] = info.get('thumbnail')
                    is_playlist = False
                    
        if is_playlist:
            render_playlist_page(chat_id, msg_id)
        else:
            fetch_real_qualities(chat_id, msg_id, url, False, info.get('title', 'فيديو مفرد'))
                    
    except Exception as e:
        bot.edit_message_text(f"❌ حصلت مشكلة أثناء فحص الرابط!\nالسبب التقني: {str(e)[:50]}", chat_id, msg_id)

# ==========================================================
# 3. واجهة البلاي ليست
# ==========================================================
def render_playlist_page(chat_id, msg_id):
    with session_lock:
        session = user_sessions[chat_id]
        page = session.get('pl_page', 0)
        entries = session.get('entries', [])
        selected = session.get('selected_indices', set())
        title = session.get('title', 'قائمة تشغيل')
        
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(entries))
    
    text = f"📁 البلاي ليست: {str(title)[:50]}...\n"
    text += f"✅ اللي اخترته: {len(selected)} من أصل {len(entries)} فيديو\n\n"
    
    for i in range(start_idx, end_idx):
        mark = "✅" if i in selected else "⬜"
        entry = entries[i]
        vid_title = entry.get('title', f'فيديو {i+1}') if isinstance(entry, dict) else f'فيديو {i+1}'
        text += f"{i+1}. {mark} {str(vid_title)[:35]}...\n"
        
    markup = InlineKeyboardMarkup(row_width=5)
    
    btn_row = []
    for i in range(start_idx, end_idx):
        btn_row.append(InlineKeyboardButton(str(i+1), callback_data=f"ext_tog_{i}"))
    for i in range(0, len(btn_row), 5):
        markup.add(*btn_row[i:i+5])
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data="ext_prev"))
    if end_idx < len(entries): nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data="ext_next"))
    if nav_row: markup.add(*nav_row)
    
    markup.add(InlineKeyboardButton("✅ تحديد الكل", callback_data="ext_all"), 
               InlineKeyboardButton("❌ إلغاء التحديد", callback_data="ext_clear"))
    markup.add(InlineKeyboardButton("🔢 تحديد نطاق (من - إلى)", callback_data="ext_range"))
    markup.add(InlineKeyboardButton("📥 تأكيد وهات الجودات", callback_data="ext_confirm"))
    
    try: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
    except: pass

# ==========================================================
# 4. جلب الجودات 
# ==========================================================
def fetch_real_qualities(chat_id, msg_id, url, is_playlist, header_text):
    bot.edit_message_text("⏳ لحظات بنجيب لك الجودات المتاحة للفيديو...", chat_id, msg_id)
    
    def _fetch():
        try:
            ydl_opts = {'extract_flat': False, 'quiet': True, 'no_warnings': True}
            if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                
                seen_h = set()
                opts = []
                for f in formats:
                    if f.get('vcodec') != 'none':
                        h = f.get('height')
                        if h and h not in seen_h and h >= 144:
                            seen_h.add(h)
                            opts.append(h)
                
            opts.sort(reverse=True)
            markup = InlineKeyboardMarkup(row_width=1)
            
            for opt in opts[:5]: 
                markup.add(InlineKeyboardButton(f"📺 جودة {opt}p", callback_data=f"addq_{opt}p"))
            
            markup.add(InlineKeyboardButton("🎵 صوت (MP3) فقط", callback_data="addq_mp3"))
            
            if not is_playlist:
                markup.add(InlineKeyboardButton("✂️ قص جزء من الفيديو", callback_data="ext_cut"))

            bot.edit_message_text(f"{str(header_text)[:50]}\n\n👇 الجودات المتاحة قدامك اهي، اختار اللي يناسبك:", chat_id, msg_id, reply_markup=markup)
            
        except Exception as e:
            bot.edit_message_text(f"❌ معلش، مقدرناش نوصل لجودات الفيديو ده. ممكن يكون برايفت أو محذوف.\nالسبب: {str(e)[:50]}", chat_id, msg_id)
            
    threading.Thread(target=_fetch).start()

# ==========================================================
# 5. التفاعل مع الأزرار
# ==========================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('ext_'))
def handle_extractors(call):
    chat_id = call.message.chat.id
    action = call.data
    
    with session_lock:
        if chat_id not in user_sessions:
            bot.answer_callback_query(call.id, "الجلسة انتهت. ابعت اللينك من تاني.", show_alert=True)
            return
        session = user_sessions[chat_id]

    if action.startswith('ext_tog_'):
        idx = int(action.split('_')[2])
        with session_lock:
            if idx in session['selected_indices']: session['selected_indices'].remove(idx)
            else: session['selected_indices'].add(idx)
        render_playlist_page(chat_id, call.message.message_id)
        
    elif action == 'ext_next':
        with session_lock: session['pl_page'] += 1
        render_playlist_page(chat_id, call.message.message_id)
        
    elif action == 'ext_prev':
        with session_lock: session['pl_page'] -= 1
        render_playlist_page(chat_id, call.message.message_id)
        
    elif action == 'ext_all':
        with session_lock: session['selected_indices'] = set(range(len(session['entries'])))
        render_playlist_page(chat_id, call.message.message_id)
        
    elif action == 'ext_clear':
        with session_lock: session['selected_indices'] = set()
        render_playlist_page(chat_id, call.message.message_id)
        
    elif action == 'ext_range':
        msg = bot.send_message(chat_id, "🔢 ابعت لي الأرقام اللي عايزها بالشكل ده (من - إلى)\nمثال: `5 - 12`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: _process_range(m, call.message.message_id))
        
    elif action == 'ext_cut':
        msg = bot.send_message(chat_id, "✂️ ابعت لي وقت القص بالشكل ده (دقيقة:ثانية - دقيقة:ثانية)\nمثال: `00:15 - 00:45`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: _process_cut(m, call.message.message_id))

    elif action == 'ext_confirm':
        if not session['selected_indices']:
            bot.answer_callback_query(call.id, "أنت لسه مخترتش أي فيديو يا صديقي!", show_alert=True)
            return
        first_selected_idx = list(session['selected_indices'])[0]
        first_url = session['entries'][first_selected_idx].get('url', session['entries'][first_selected_idx].get('webpage_url'))
        fetch_real_qualities(chat_id, call.message.message_id, first_url, True, f"📁 جهزنا {len(session['selected_indices'])} فيديو")

def _process_range(message, origin_msg_id):
    chat_id = message.chat.id
    try:
        start, end = map(int, message.text.split('-'))
        with session_lock:
            total = len(user_sessions[chat_id]['entries'])
            start = max(1, min(start, total))
            end = max(1, min(end, total))
            user_sessions[chat_id]['selected_indices'].update(range(start-1, end))
        bot.delete_message(chat_id, message.message_id)
        render_playlist_page(chat_id, origin_msg_id)
    except: bot.send_message(chat_id, "❌ الأرقام مش مظبوطة، جرب تاني واكتبها كده: 5 - 12")

def _process_cut(message, origin_msg_id):
    chat_id = message.chat.id
    try:
        s, e = message.text.split('-')
        with session_lock:
            user_sessions[chat_id]['start_sec'] = time_to_sec(s)
            user_sessions[chat_id]['end_sec'] = time_to_sec(e)
            url = user_sessions[chat_id]['url']
        fetch_real_qualities(chat_id, origin_msg_id, url, False, "✂️ وضع قص الفيديو جاهز")
    except: bot.send_message(chat_id, "❌ الوقت مش مكتوب صح، جرب تكتبه كده: 01:30 - 04:22")