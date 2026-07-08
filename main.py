import os
import telebot
from flask import Flask, request
import threading
import uuid

from core import bot, TOKEN, user_sessions, session_lock, DOWNLOAD_DIR
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import extractors
import uploader
import converter

app = Flask(__name__)

# ==========================================================
# 🌐 إعدادات الاستقبال (Webhook)
# ==========================================================
@app.route('/', methods=['GET'])
def index():
    return "🚀 Bot is Online and Ready!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Webhook Error: {e}")
    return 'OK', 200

# ==========================================================
# 1. استقبال الروابط وفرزها
# ==========================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "أهلاً بك يا صديقي في المساعد الذكي والمونتاج 🚀\n\n"
        "🔗 **للتحميل:** أرسل أي رابط فيديو أو قائمة تشغيل.\n"
        "🔄 **للتحويل:** أرسل أي ملف مباشرة هنا وسأقوم بتحويله!\n\n"
        "💡 أدعم الذكاء الاصطناعي، الهندسة الصوتية، ومحول الصيغ الشامل."
    )
    bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(func=lambda msg: msg.text and 'http' in msg.text)
def handle_url(message):
    url = message.text.strip()
    chat_id = message.chat.id
    msg_id = message.message_id
    
    with session_lock:
        user_sessions[chat_id] = {
            'url': url, 'chat_id': chat_id, 'original_msg_id': msg_id,
            'is_playlist': False, 'entries': [], 'selected_indices': set(),
            'start_sec': 0, 'end_sec': 0, 'premium_features': [], 'speed_val': 1.5 
        }
        
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📥 تحميل عادي (سريع)", callback_data="mode_normal"),
        InlineKeyboardButton("🚀 تحميل بمزايا احترافية", callback_data="mode_premium")
    )
    bot.send_message(message.chat.id, "اللينك وصل يا صديقي 🔒\nتحب نتعامل معاه إزاي؟", reply_markup=markup)

# ==========================================================
# 2. محول الصيغ الشامل
# ==========================================================
@bot.message_handler(content_types=['document', 'video', 'audio', 'photo', 'voice'])
def handle_media_upload(message):
    msg = bot.send_message(message.chat.id, "🔄 استلمت الملف!\nاكتب الصيغة اللي عايز تحوله ليها (مثال: mp4, mp3, jpg):")
    bot.register_next_step_handler(msg, process_conversion, message)

def process_conversion(ext_msg, original_msg):
    target_ext = ext_msg.text.strip().lower().replace('.', '')
    bot.send_message(ext_msg.chat.id, f"⏳ جاري التحويل لـ {target_ext}...")
    threading.Thread(target=execute_conversion, args=(ext_msg.chat.id, original_msg, target_ext)).start()

def execute_conversion(chat_id, message, target_ext):
    try:
        import converter
        file_id = None
        if message.document: file_id = message.document.file_id
        elif message.video: file_id = message.video.file_id
        elif message.audio: file_id = message.audio.file_id
        elif message.voice: file_id = message.voice.file_id
        elif message.photo: file_id = message.photo[-1].file_id
        
        if not file_id: return
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_input = os.path.join(DOWNLOAD_DIR, f"temp_{uuid.uuid4().hex}_{os.path.basename(file_info.file_path)}")
        
        with open(temp_input, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        output_file = converter.universal_convert(temp_input, target_ext)
        
        if output_file and os.path.exists(output_file):
            with open(output_file, 'rb') as f:
                bot.send_document(chat_id, f, caption=f"✅ تم التحويل إلى {target_ext}")
            os.remove(output_file)
        else:
            bot.send_message(chat_id, "❌ فشل التحويل. تأكد أن الصيغة مدعومة.")
            
        if os.path.exists(temp_input): os.remove(temp_input)
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ: {e}")

# ==========================================================
# 3. توجيه الأوامر
# ==========================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_') or call.data.startswith('prem_'))
def handle_modes(call):
    chat_id = call.message.chat.id
    
    with session_lock:
        if chat_id not in user_sessions:
            bot.answer_callback_query(call.id, "الجلسة انتهت. ابعت اللينك تاني.", show_alert=True)
            return
            
    if call.data == "mode_normal":
        bot.edit_message_text("⏳ جاري الفحص...", chat_id, call.message.message_id)
        extractors.start_extraction(chat_id, call.message.message_id)
    # باقي الأوامر الاحترافية تم اختصارها لتنظيف الكود الأساسي (يمكنك إضافتها لاحقاً أو ترك مستخرجاتك تتعامل معها)

if __name__ == '__main__':
    print("🚀 خادم Flask يعمل الآن وجاهز للاستضافة الجديدة...")
    # Render يعين الـ Port تلقائياً عبر متغيرات البيئة
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)