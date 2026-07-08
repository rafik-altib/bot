import os
import subprocess
import time
import google.generativeai as genai

# إجبار النظام على استخدام بروتوكولات اتصال تتخطى مشاكل الشبكات المحلية
os.environ['GRPC_DNS_RESOLVER'] = 'native'

# ==========================================================
# دالة مساعدة لاستخراج الصوت ورفعه لجوجل (لتوفير الوقت والموارد)
# ==========================================================
def _upload_audio_to_gemini(video_file_path, api_key):
    genai.configure(api_key=api_key, transport='rest')
    audio_path = video_file_path + "_temp_audio.mp3"
    
    # استخراج الصوت بسرعة فائقة
    subprocess.run(['ffmpeg', '-y', '-i', video_file_path, '-q:a', '0', '-map', 'a', audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    target_file = audio_path if os.path.exists(audio_path) else video_file_path
    uploaded_file = genai.upload_file(path=target_file)
    
    # انتظار معالجة الملف في سيرفرات جوجل
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = genai.get_file(uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise Exception("فشلت معالجة الملف الصوتي في سيرفرات جوجل.")
        
    return uploaded_file, audio_path

# ==========================================================
# 1. الفهرسة التلقائية (Auto-Chapters)
# ==========================================================
def generate_auto_chapters(video_file_path, api_key):
    """تقسيم الفيديو لفصول مع طوابع زمنية (Timestamps)"""
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        uploaded_file, audio_path = _upload_audio_to_gemini(video_file_path, api_key)
        
        prompt = (
            "استمع إلى هذا المقطع الصوتي بعناية. "
            "قم بإنشاء فهرس زمني (Chapters) يوضح المواضيع الرئيسية التي تم التحدث عنها. "
            "الرجاء التنسيق بهذا الشكل:\n"
            "⏱️ [الدقيقة:الثانية] - عنوان الموضوع\n"
            "اجعل العناوين واضحة ومفيدة للمراجعة الأكاديمية."
        )
        
        response = model.generate_content([prompt, uploaded_file])
        
        # تنظيف الملفات
        genai.delete_file(uploaded_file.name)
        if os.path.exists(audio_path): os.remove(audio_path)
        
        return response.text
    except Exception as e:
        return f"❌ خطأ في إنشاء الفهرس: {e}"

# ==========================================================
# 2. استخراج المصادر والروابط (References Extractor)
# ==========================================================
def extract_links_and_references(video_file_path, api_key):
    """استخراج أي روابط، أسماء كتب، أدوات، أو مراجع ذكرها المتحدث"""
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        uploaded_file, audio_path = _upload_audio_to_gemini(video_file_path, api_key)
        
        prompt = (
            "استمع إلى هذا المقطع الصوتي. "
            "استخرج أي مصادر ذكرها المتحدث، مثل: روابط مواقع (URLs)، أسماء كتب، أوراق بحثية، "
            "أسماء برامج أو أدوات، أو أي مراجع أخرى.\n"
            "رتبها في قائمة نقطية واضحة. إذا لم يذكر أي مصادر، قل 'لم يتم ذكر مصادر خارجية في هذا المقطع'."
        )
        
        response = model.generate_content([prompt, uploaded_file])
        
        genai.delete_file(uploaded_file.name)
        if os.path.exists(audio_path): os.remove(audio_path)
        
        return response.text
    except Exception as e:
        return f"❌ خطأ في استخراج المصادر: {e}"

# ==========================================================
# 3. البحث الدلالي داخل الفيديو (Semantic Search)
# ==========================================================
def semantic_video_search(video_file_path, search_query, api_key):
    """البحث عن موضوع معين داخل الفيديو وإرجاع وقته وملخصه"""
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        uploaded_file, audio_path = _upload_audio_to_gemini(video_file_path, api_key)
        
        prompt = (
            f"ابحث عن الموضوع التالي: '{search_query}' في هذا المقطع الصوتي.\n"
            "إذا تحدث عنه المتحدث، أجب بالآتي:\n"
            "1. متى تحدث عنه بالتحديد؟ (الزمن التقريبي)\n"
            "2. ما هو ملخص ما قاله المتحدث في هذه النقطة؟\n"
            "إذا لم يتحدث عنه، أخبرني بذلك بوضوح."
        )
        
        response = model.generate_content([prompt, uploaded_file])
        
        genai.delete_file(uploaded_file.name)
        if os.path.exists(audio_path): os.remove(audio_path)
        
        return response.text
    except Exception as e:
        return f"❌ خطأ في البحث الدلالي: {e}"

# ==========================================================
# 4. قارئ الشاشة والأكواد من السلايدز (Video OCR)
# ==========================================================
def extract_text_from_slides_ocr(slide_image_paths, api_key):
    """أخذ الصور (السلايدز) واستخراج النصوص، الأكواد، والمعادلات منها باستخدام AI"""
    try:
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # لا نرسل أكثر من 15 صورة في المرة الواحدة لتفادي التحميل الزائد على الـ API
        limited_slides = slide_image_paths[:15]
        
        uploaded_images = []
        for img_path in limited_slides:
            img = genai.upload_file(path=img_path)
            uploaded_images.append(img)
            
        prompt = (
            "أنت خبير في التعرف الضوئي على الحروف (OCR) وفهم الأكواد.\n"
            "قم بقراءة هذه الشرائح (Slides) بدقة، واستخرج الآتي بالترتيب:\n"
            "1. أي أكواد برمجية (ضعها داخل علامات الأكواد المخصصة ``` ).\n"
            "2. أي نصوص هامة، تعريفات، أو معادلات رياضية.\n"
            "تجاهل الديكورات وأرقام الصفحات، وركز على المحتوى العلمي."
        )
        
        content_request = [prompt] + uploaded_images
        response = model.generate_content(content_request)
        
        # تنظيف الصور من سيرفرات جوجل
        for img in uploaded_images:
            genai.delete_file(img.name)
            
        return response.text
    except Exception as e:
        return f"❌ خطأ في قراءة النصوص من الشرائح: {e}"

print("🧠 تم تحميل أدوات الذكاء الاصطناعي المتقدمة (advanced_ai.py)...")