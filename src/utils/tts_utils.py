import os
import logging
import aiohttp
from config import DATA_DIR, ELEVENLABS_API_KEY, USE_PROXY, PRIORITY_PROXY

logger = logging.getLogger(__name__)

TTS_DIR = os.path.join(DATA_DIR, 'tts')
os.makedirs(TTS_DIR, exist_ok=True)

# Топовые голоса для русского языка в ElevenLabs
VOICES = {
    'adam': 'pNInz6obpgDQGcFmaJgB',      # Мужской, глубокий, отлично говорит по-русски (РЕКОМЕНДУЕТСЯ)
    'bella': 'EXAVITQu4vr4xnSDxMaL',    # Женский, мягкий и естественный
    'callum': 'cgSgspJ2msm6clMCkdW9',   # Мужской, энергичный
}

DEFAULT_VOICE = 'adam'

async def generate_tts(text: str, voice_key: str = DEFAULT_VOICE, filename: str = 'tts_output.mp3') -> str:
    """
    Генерирует голосовое сообщение через ElevenLabs API.
    """
    voice_id = VOICES.get(voice_key, VOICES[DEFAULT_VOICE])
    output_path = os.path.join(TTS_DIR, filename)
    tmp_path = output_path + '.tmp'
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # Лучшая модель для русского
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    # Используем прокси если включен
    proxy = None
    if USE_PROXY and PRIORITY_PROXY:
        proxy = PRIORITY_PROXY  # Например: "http://127.0.0.1:10808"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, proxy=proxy) as response:
                if response.status == 200:
                    with open(tmp_path, 'wb') as f:
                        f.write(await response.read())
                    
                    # Атомарная замена
                    if os.path.exists(output_path):
                        os.replace(output_path, output_path + '.bak')
                    os.replace(tmp_path, output_path)
                    
                    logger.info(f"✅ ElevenLabs TTS сгенерирован: {output_path} (голос: {voice_key})")
                    return output_path
                else:
                    error_text = await response.text()
                    logger.error(f"❌ ElevenLabs API error {response.status}: {error_text}")
                    raise Exception(f"API Error: {response.status} - {error_text[:100]}")
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass
        logger.error(f"❌ Ошибка генерации TTS: {e}")
        raise

def get_available_voices() -> dict:
    """Возвращает словарь доступных голосов."""
    return VOICES

def cleanup_old_tts(max_age_hours: int = 24):
    """Удаляет старые TTS файлы."""
    import time
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for filename in os.listdir(TTS_DIR):
        if filename.endswith('.mp3'):
            filepath = os.path.join(TTS_DIR, filename)
            if now - os.path.getmtime(filepath) > max_age_seconds:
                try:
                    os.remove(filepath)
                    logger.info(f"🧹 Удален старый TTS файл: {filename}")
                except:
                    pass