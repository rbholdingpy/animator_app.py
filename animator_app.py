import streamlit as st
from openai import OpenAI
import os
import io
import requests
import numpy as np
from PIL import Image

# Importación directa para MoviePy v2.0+
from moviepy import ImageClip, concatenate_videoclips, AudioFileClip

# ==========================================
# 🎭 CONFIGURACIÓN
# ==========================================
APP_NAME = "Animador Jopara AI 🦜"
st.set_page_config(page_title=APP_NAME, page_icon="🎭", layout="centered")
st.markdown("""<style>.stApp { background-color: #121212; color: #E0E0E0; } h1 { color: #00FF94; } .stButton>button { background: linear-gradient(45deg, #00FF94, #00CC76); color: black; border: none; padding: 15px; font-weight: bold; transition: 0.2s; } .stButton>button:hover { transform: scale(1.02); }</style>""", unsafe_allow_html=True)

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key: st.error("⚠️ ERROR: Configura OPENAI_API_KEY."); st.stop()
client = OpenAI(api_key=api_key)

# ==========================================
# 🧠 LÓGICA DE IA
# ==========================================
def transcribir_audio(audio_path):
    with open(audio_path, "rb") as f: transcript = client.audio.transcriptions.create(model="whisper-1", file=f, language="es")
    return transcript.text

def imaginar_personaje(texto, pista=""):
    prompt = f"Director de Arte animación satírica. Prompt visual DALL-E 3 basado en audio. ESTILO: Flat Vector Art, Adult Cartoon (Rick & Morty HD), fondo sólido. SOLO prompt en INGLÉS. Contexto: '{texto}'. Pista: '{pista}'."
    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
    return res.choices[0].message.content

def generar_sprites(desc):
    style = "Flat 2D vector character, clean lines, solid neutral background."
    p_closed = f"{style} Description: {desc}. Pose: Neutral listening. Mouth: CLOSED tightly."
    p_open = f"{style} Description: {desc}. Pose: Speaking loudly. Mouth: WIDE OPEN shouting."
    def fetch(p):
        res = client.images.generate(model="dall-e-3", prompt=p, size="1024x1024", n=1)
        # Reducimos a 512x512 para ahorrar memoria RAM
        return Image.open(io.BytesIO(requests.get(res.data[0].url).content)).resize((512, 512))
    return fetch(p_closed), fetch(p_open)

# ==========================================
# 🎞️ MOTOR DE ANIMACIÓN (CORREGIDO)
# ==========================================
def procesar_video(audio_path, img_closed, img_open, fps=10):
    """Anima analizando el perfil de volumen completo primero"""
    
    # 1. Preparar imágenes
    img_closed.save("frame_closed.png")
    img_open.save("frame_open.png")
    clip_closed = ImageClip("frame_closed.png")
    clip_open = ImageClip("frame_open.png")
    
    # 2. Cargar y analizar audio completo
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    # Extraemos los datos crudos del audio (array de numpy)
    # Usamos una frecuencia de muestreo baja (audiolab_fps) para el análisis, es suficiente
    audiolab_fps = 4000 
    audio_data = audio_clip.to_soundarray(fps=audiolab_fps)
    
    # Si es estéreo, convertimos a mono promediando canales
    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)
        
    # Obtenemos el perfil de volumen (valor absoluto)
    volume_profile = np.abs(audio_data)
    
    # Calculamos un umbral dinámico: el promedio de volumen multiplicado por un factor
    avg_volume = np.mean(volume_profile)
    # Factor 1.3 significa que debe sonar un 30% más fuerte que el promedio para abrir la boca
    # Ponemos un mínimo de 0.02 para evitar ruido de fondo
    threshold = max(avg_volume * 1.3, 0.02)
    
    clips = []
    step = 1.0 / fps 
    times = np.arange(0, duration, step)
    
    # 3. Bucle de animación
    for t in times:
        # Encontramos qué índice del array de audio corresponde a este tiempo 't'
        sample_idx = int(t * audiolab_fps)
        
        # Seguridad para no salirnos del array al final
        if sample_idx >= len(volume_profile):
            sample_idx = len(volume_profile) - 1
            
        current_volume = volume_profile[sample_idx]
        
        # Decisión: ¿Volumen actual supera el umbral?
        if current_volume > threshold:
            # Usamos .copy() para evitar problemas al reutilizar el mismo clip
            clip = clip_open.copy().with_duration(step)
        else:
            clip = clip_closed.copy().with_duration(step)
            
        clips.append(clip)
        
    # 4. Renderizado final
    # method="compose" es más robusto visualmente que "chain"
    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio_clip)
    
    output_filename = "animacion_final.mp4"
    
    # Usamos threads=1 para máxima estabilidad en servidor gratuito
    video.write_videofile(
        output_filename, fps=fps, codec="libx264", audio_codec="aac",
        preset="veryfast", ffmpeg_params=['-pix_fmt', 'yuv420p'],
        threads=1, logger=None
    )
    
    # Limpieza
    os.remove("frame_closed.png")
    os.remove("frame_open.png")
    
    return output_filename

# ==========================================
# 📱 INTERFAZ
# ==========================================
st.title(APP_NAME)
st.write("🗣️ Sube un audio -> Animación estilo 'Gente Rota'")

col1, col2 = st.columns([2, 1])
with col1: audio_file = st.file_uploader("📂 Audio (MP3/WAV/OGG)", type=["mp3", "wav", "ogg", "m4a"])
with col2: contexto = st.text_area("Pista (Ej: Señora enojada)", height=100)

if audio_file and st.button("🎬 ¡ANIMAR!"):
    with st.status("🏗️ Procesando... (Ten paciencia)", expanded=True) as s:
        temp_audio = "temp.mp3"
        with open(temp_audio, "wb") as f: f.write(audio_file.getbuffer())
        
        s.write("👂 Transcribiendo..."); texto = transcribir_audio(temp_audio); st.caption(f"📝 \"{texto}\"")
        s.write("🧠 Imaginando..."); desc = imaginar_personaje(texto, contexto)
        s.write("🎨 Dibujando (DALL-E 3)..."); img_c, img_a = generar_sprites(desc)
        c1, c2 = st.columns(2); c1.image(img_c, "Callado"); c2.image(img_a, "Hablando")
        
        s.write("🎞️ Animando boca (Esto toma unos minutos)...")
        try:
            video_path = procesar_video(temp_audio, img_c, img_a)
            s.update(label="✅ ¡Listo!", state="complete", expanded=False)
            st.video(video_path)
            with open(video_path, "rb") as v: st.download_button("⬇️ Descargar Video", v, "animacion.mp4", "video/mp4")
        except Exception as e:
            s.update(label="❌ Error de memoria o proceso", state="error")
            st.error(f"Ups, el servidor se quedó sin memoria. Intenta con un audio más corto.\nError: {e}")
