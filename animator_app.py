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
st.set_page_config(page_title=APP_NAME, page_icon="✨", layout="centered")

# Estilos CSS más amigables
st.markdown("""
    <style>
    .stApp { background-color: #222233; color: #E0E0FF; }
    h1 { color: #FF94E4; text-align: center; font-family: 'Comic Sans MS', 'Arial Rounded MT Bold', sans-serif; }
    .stButton>button { 
        background: linear-gradient(45deg, #FF94E4, #5599FF);
        color: white; border-radius: 15px; border: none; padding: 15px; 
        font-weight: bold; font-size: 1.1em; transition: transform 0.2s;
    }
    .stButton>button:hover { transform: scale(1.03); }
    div[data-testid="stStatusWidget"] { background-color: #333355; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key: st.error("⚠️ ERROR: Configura OPENAI_API_KEY."); st.stop()
client = OpenAI(api_key=api_key)

# ==========================================
# 🧠 LÓGICA DE IA (NUEVO ESTILO INFANTIL)
# ==========================================
def transcribir_audio(audio_path):
    with open(audio_path, "rb") as f: transcript = client.audio.transcriptions.create(model="whisper-1", file=f, language="es")
    return transcript.text

def imaginar_personaje(texto, pista=""):
    # --- CAMBIO DE ESTILO AQUÍ ---
    prompt = """
    You are a Lead Character Designer for a charming children's animation studio (like Pixar or Studio Ghibli).
    Create a visual prompt for DALL-E 3 based on the audio context.
    STYLE: Cute children's book illustration, friendly, soft shapes, warm colors, charming, simple clean design, solid pastel background. Not grotesque or edgy.
    Context: '{texto}'. Extra clue: '{pista}'.
    Respond ONLY with the prompt in ENGLISH.
    """
    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
    return res.choices[0].message.content

def generar_sprites(desc):
    # --- ESTILO BASE MÁS TIERNO ---
    style = "Charming cartoon style, cute friendly character, soft colors, clean lines, solid pastel background."
    p_closed = f"{style} Description: {desc}. Pose: Cute neutral listening face. Mouth: CLOSED and smiling gently."
    # Enfatizamos "boca grande abierta" para que se note la diferencia
    p_open = f"{style} Description: {desc}. Pose: Same character talking excitedly. Mouth: WIDE OPEN forming an 'O' shape or big smile."
    
    def fetch(p):
        res = client.images.generate(model="dall-e-3", prompt=p, size="1024x1024", n=1)
        # Mantenemos resize a 512 para que no explote la memoria
        return Image.open(io.BytesIO(requests.get(res.data[0].url).content)).resize((512, 512))
    return fetch(p_closed), fetch(p_open)

# ==========================================
# 🎞️ MOTOR DE ANIMACIÓN (MÁS SENSIBLE)
# ==========================================
def procesar_video(audio_path, img_closed, img_open, fps=10):
    """Anima usando un umbral muy sensible para garantizar movimiento"""
    
    # 1. Preparar imágenes y clips base
    img_closed.save("frame_closed.png")
    img_open.save("frame_open.png")
    # Creamos los clips una sola vez para reusarlos
    base_clip_closed = ImageClip("frame_closed.png")
    base_clip_open = ImageClip("frame_open.png")
    
    # 2. Cargar Audio
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    clips = []
    step = 1.0 / fps 
    times = np.arange(0, duration, step)
    
    # Umbral de volumen muy bajo (3%). Cualquier cosa sobre esto abre la boca.
    # Esto hace la animación mucho más "habladora".
    THRESHOLD = 0.03
    
    # 3. Bucle de análisis cuadro por cuadro
    for t in times:
        try:
            # Extraemos el pequeño fragmento de audio correspondiente a este cuadro
            # Usamos fps=22050 para tener suficientes datos para analizar
            chunk = audio_clip.subclip(t, t + step).to_soundarray(fps=22050)
            
            # Calculamos el volumen máximo en este pequeño fragmento
            if chunk is not None and len(chunk) > 0:
                # np.abs convierte todo a positivo, np.max busca el pico más alto
                volume = np.max(np.abs(chunk))
            else:
                volume = 0
        except Exception:
            volume = 0
            
        # Decisión: ¿El volumen supera el umbral mínimo?
        if volume > THRESHOLD:
            # Usamos .copy() es CRÍTICO en MoviePy v2 al reusar clips en un bucle
            clip = base_clip_open.copy().with_duration(step)
        else:
            clip = base_clip_closed.copy().with_duration(step)
            
        clips.append(clip)
        
    # 4. Renderizado final
    # Usamos 'compose' que es más seguro para evitar pantallazos negros
    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio_clip)
    
    output_filename = "animacion_final.mp4"
    
    # Configuración para máxima estabilidad en servidor gratuito (lento pero seguro)
    video.write_videofile(
        output_filename, fps=fps, codec="libx264", audio_codec="aac",
        preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p'],
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
st.write("✨ Sube un audio -> Animación estilo 'Cartoon Tierno'")

col1, col2 = st.columns([2, 1])
with col1: audio_file = st.file_uploader("📂 Audio (MP3/WAV/OGG)", type=["mp3", "wav", "ogg", "m4a"])
with col2: contexto = st.text_area("Pista (Ej: Un osito contando un chiste)", height=100)

if audio_file and st.button("🎬 ¡ANIMAR!"):
    with st.status("🏗️ Procesando magia... (Paciencia, el render tarda)", expanded=True) as s:
        temp_audio = "temp.mp3"
        with open(temp_audio, "wb") as f: f.write(audio_file.getbuffer())
        
        s.write("👂 Escuchando..."); texto = transcribir_audio(temp_audio); st.caption(f"📝 \"{texto}\"")
        s.write("🧠 Imaginando personaje tierno..."); desc = imaginar_personaje(texto, contexto)
        s.write("🎨 Dibujando (DALL-E 3)..."); img_c, img_a = generar_sprites(desc)
        c1, c2 = st.columns(2); c1.image(img_c, "Boca Cerrada"); c2.image(img_a, "Boca Abierta (Hablando)")
        
        s.write("🎞️ Animando la boca (Esto es lo que más tarda)...")
        try:
            video_path = procesar_video(temp_audio, img_c, img_a)
            s.update(label="✅ ¡Video Listo!", state="complete", expanded=False)
            st.success("¡Aquí está tu animación!")
            st.video(video_path)
            with open(video_path, "rb") as v: st.download_button("⬇️ Descargar Video ✨", v, "animacion_tierna.mp4", "video/mp4")
        except Exception as e:
            s.update(label="❌ Error durante el renderizado", state="error")
            st.error(f"El servidor se quedó sin memoria o hubo un error técnico. Prueba con un audio más corto.\nDetalle: {e}")
