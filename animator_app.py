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
# 🎭 CONFIGURACIÓN: ANIMADOR JOPARA AI
# ==========================================
APP_NAME = "Animador Jopara AI 🦜"

st.set_page_config(page_title=APP_NAME, page_icon="🎭", layout="centered")

# Estilos CSS
st.markdown("""
    <style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1 { color: #00FF94; text-align: center; font-family: 'Helvetica', sans-serif; letter-spacing: -1px;}
    .stButton>button { 
        background: linear-gradient(45deg, #00FF94, #00CC76);
        color: black; border-radius: 12px; border: none;
        width: 100%; font-weight: bold; padding: 15px; font-size: 1.1em;
        transition: transform 0.2s;
    }
    .stButton>button:hover { transform: scale(1.02); }
    div[data-testid="stStatusWidget"] { background-color: #1E1E1E; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- API KEY CHECK ---
api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("⚠️ ERROR: Configura tu OPENAI_API_KEY en los Secrets.")
    st.stop()
client = OpenAI(api_key=api_key)

# ==========================================
# 🧠 LÓGICA DE IA (Whisper + DALL-E)
# ==========================================

def transcribir_audio(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es"
        )
    return transcript.text

def imaginar_personaje(texto, pista_usuario=""):
    prompt_sistema = """
    Eres un Director de Arte de animación satírica.
    Crea un prompt visual para DALL-E 3 basado en el audio.
    ESTILO: Flat Vector Art, Adult Cartoon style (Rick & Morty/South Park HD), solid background.
    Responde SOLO con el prompt en INGLÉS.
    """
    prompt_usuario = f"Contexto: '{texto}'.\nPista: '{pista_usuario}'."
    res = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": prompt_usuario}
    ])
    return res.choices[0].message.content

def generar_sprites(descripcion):
    base_style = "Flat 2D vector character, clean lines, vibrant colors, solid neutral background. High quality."
    
    # Prompt A: Boca CERRADA
    prompt_closed = f"{base_style} Description: {descripcion}. Pose: Neutral listening. Mouth: CLOSED tightly."
    # Prompt B: Boca ABIERTA
    prompt_open = f"{base_style} Description: {descripcion}. Pose: Speaking loudly. Mouth: WIDE OPEN shouting."
    
    def fetch_dalle(prompt):
        res = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1)
        return Image.open(io.BytesIO(requests.get(res.data[0].url).content))

    return fetch_dalle(prompt_closed), fetch_dalle(prompt_open)

# ==========================================
# 🎞️ MOTOR DE ANIMACIÓN (MOVIEPY v2.0)
# ==========================================

def procesar_video(audio_path, img_closed, img_open, fps=8):
    """Anima analizando el volumen directamente con MoviePy"""
    
    # 1. Guardar imágenes temporales
    img_closed.save("frame_closed.png")
    img_open.save("frame_open.png")
    
    # 2. Cargar Audio
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    clips = []
    step = 1.0 / fps 
    
    # 3. Iterar por el audio
    times = np.arange(0, duration, step)
    
    for t in times:
        try:
            # Extraer fragmento y analizar volumen
            # En v2.0 usamos fps como argumento clave si es necesario
            chunk = audio_clip.subclip(t, t + step).to_soundarray(fps=22050)
            
            if chunk is not None and len(chunk) > 0:
                volume = np.max(np.abs(chunk))
            else:
                volume = 0
        except Exception:
            volume = 0
            
        threshold = 0.01 
        
        # --- CORRECCIÓN CLAVE v2.0 ---
        # Usamos .with_duration() en lugar de .set_duration()
        if volume > threshold:
            clip = ImageClip("frame_open.png").with_duration(step)
        else:
            clip = ImageClip("frame_closed.png").with_duration(step)
            
        clips.append(clip)
        
    # 5. Unir todo
    video = concatenate_videoclips(clips, method="compose")
    
    # --- CORRECCIÓN CLAVE v2.0 ---
    # Usamos .with_audio() en lugar de .set_audio()
    video = video.with_audio(audio_clip)
    
    output_filename = "animacion_final.mp4"
    
    # Renderizado
    video.write_videofile(
        output_filename, fps=fps, codec="libx264", audio_codec="aac",
        preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p'],
        logger=None
    )
    
    return output_filename

# ==========================================
# 📱 INTERFAZ PRINCIPAL
# ==========================================
st.title(APP_NAME)
st.markdown("### 🗣️ Tu Audio -> Gente Rota con IA")
st.write("Sube un audio filtrado y mira la magia.")

col1, col2 = st.columns([2, 1])
with col1:
    audio_file = st.file_uploader("📂 Subir Audio (MP3/WAV)", type=["mp3", "wav", "ogg", "m4a"])
with col2:
    contexto = st.text_area("Pista (Ej: Político enojado)", height=100)

if audio_file:
    st.audio(audio_file)
    
    if st.button("🎬 GENERAR VIDEO"):
        with st.status("🏗️ Creando animación...", expanded=True) as status:
            try:
                # 1. Guardar Audio
                status.write("💾 Guardando audio...")
                temp_audio = "temp_input.mp3"
                with open(temp_audio, "wb") as f:
                    f.write(audio_file.getbuffer())
                
                # 2. Transcribir
                status.write("👂 Escuchando...")
                texto = transcribir_audio(temp_audio)
                st.info(f"🗣️: \"{texto}\"")
                
                # 3. Imaginar
                status.write("🧠 Diseñando personaje...")
                desc = imaginar_personaje(texto, contexto)
                
                # 4. Dibujar
                status.write("🎨 Pintando (DALL-E 3)...")
                img_c, img_a = generar_sprites(desc)
                
                c1, c2 = st.columns(2)
                with c1: st.image(img_c, caption="Callado")
                with c2: st.image(img_a, caption="Hablando")
                
                # 5. Animar
                status.write("🎞️ Renderizando video...")
                video_path = procesar_video(temp_audio, img_c, img_a)
                
                status.update(label="✅ ¡Éxito!", state="complete", expanded=False)
                
                st.divider()
                st.video(video_path)
                
                with open(video_path, "rb") as v:
                    st.download_button("⬇️ Descargar Video", v, "video_jopara.mp4", mime="video/mp4", type="primary")
                    
            except Exception as e:
                status.update(label="❌ Error", state="error")
                st.error(f"Error técnico: {e}")
