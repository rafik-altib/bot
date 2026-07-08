import os
import subprocess
import google.generativeai as genai
import time

# إجبار النظام على استخدام بروتوكولات اتصال تتخطى مشاكل الشبكات المحلية
os.environ['GRPC_DNS_RESOLVER'] = 'native'

def analyze_audio_with_ai(video_file_path, api_key):
    try:
        # استخدام بروتوكول REST كبديل آمن لتخطي خطأ 400 Discovery
        genai.configure(api_key=api_key, transport='rest')
        
        # تم التحديث لنموذج Gemini 2.5 Flash بناءً على طلبك
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        audio_path = video_file_path + "_temp_audio.mp3"
        print("Extracting audio for AI...")
        subprocess.run(['ffmpeg', '-y', '-i', video_file_path, '-q:a', '0', '-map', 'a', audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        target_file = audio_path if os.path.exists(audio_path) else video_file_path
        
        print("Uploading audio to Gemini AI...")
        audio_file = genai.upload_file(path=target_file)
        
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)
            
        if audio_file.state.name == "FAILED":
            raise Exception("فشلت معالجة الملف في سيرفرات جوجل.")

        prompt = (
            "أنت مساعد أكاديمي محترف. استمع إلى هذه المحاضرة أو المقطع الصوتي بعناية، وقم بالآتي باللغة العربية:\n"
            "1. استخراج أهم النقاط والمفاهيم التي تم ذكرها (تلخيص دقيق).\n"
            "2. كتابة تفريغ نصي كامل ومنسق للكلام المذكور في المقطع قدر الإمكان.\n"
            "رجاءً اجعل الإجابة منظمة باستخدام العناوين العريضة والنقاط."
        )
        
        print("Generating AI Analysis...")
        response = model.generate_content([prompt, audio_file])
        
        genai.delete_file(audio_file.name)
        if target_file == audio_path and os.path.exists(audio_path): os.remove(audio_path)
        
        return response.text
        
    except Exception as e:
        print(f"AI Error: {e}")
        return f"❌ معلش، حصلت مشكلة في تحليل الذكاء الاصطناعي للملف ده.\n(ملاحظة: هذا الخطأ شائع في شبكات الإنترنت المحلية وسيزول عند رفع البوت للسحابة)\nالسبب: {str(e)[:100]}"