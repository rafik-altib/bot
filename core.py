import telebot
import os
import threading
from queue import Queue

# جلب التوكن، ووضع توكن وهمي مؤقت أثناء البناء (Building) لمنع انهيار السيرفر
TOKEN = os.environ.get("BOT_TOKEN", "dummy_token_for_build_phase")

# تهيئة البوت
bot = telebot.TeleBot(TOKEN, threaded=False)

# إعداد المسارات والملفات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'BotFiles')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# إدارة الجلسات
user_sessions = {}
session_lock = threading.Lock()

# إدارة الطابور (Queue) اللازم لملف الرفع (uploader.py)
task_queue = Queue()
is_queue_running = False
queue_processing_lock = threading.Lock()

print("✅ تم تحميل ملف الإعدادات الأساسية (core.py) بنجاح...")