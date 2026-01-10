import streamlit as st
from openai import OpenAI
import os
import io
import requests
import numpy as np
from PIL import Image
from pydub import AudioSegment
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

# ==========================================
# 🎭 CONFIGURACIÓN: ANIMADOR JOPARA AI
# ==========================================
APP_NAME = "Animador Jopara AI 🦜"

st.set_page_config(page_title=APP_NAME, page_icon="🎭", layout="centered")

# Estilos CSS Dark Mode Profesional
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
    st.error("⚠️ ERROR CRÍTICO: No se encontró OPENAI_API_KEY en los Secrets.")
    st.info("Configura tu clave en Streamlit Cloud > App Settings > Secrets")
    st.stop()
client = OpenAI(api_key=api_key)

# ==========================================
# 🧠 LÓGICA DE INTELIGENCIA ARTIFICIAL
# ==========================================

def transcribir_audio(audio_path):
    """Fase 1: Oído (Whisper)"""
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es" # Forzamos español para mejorar precisión
        )
    return transcript.text

def imaginar_personaje(texto, pista_usuario=""):
    """Fase 2: Cerebro (GPT-4o)"""
    prompt_sistema = """
    Eres un Director de Arte de animación satírica.
    Basado en el texto del audio, crea un prompt visual para DALL-E 3.
    
    ESTILO: Caricatura vectorial plana (Flat Vector Art), fondo sólido simple, estilo "Adult Cartoon" (tipo Rick & Morty o South Park pero HD).
    
    REGLAS:
    1. Describe al personaje físicamente (ropa, expresión, accesorios).
    2. NO incluyas texto en la imagen.
    3. Responde SOLO con el prompt en INGLÉS.
    """
    
    prompt_usuario = f"Contexto del audio: '{texto}'.\nPista extra del usuario: '{pista_usuario}'."
    
    res = client.chat.completions.create(
        model="gpt-4o", 
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ]
    )
    return res.choices[0].message.content

def generar_sprites(descripcion):
    """Fase 3: Mano Artística (DALL-E 3)"""
    
    base_style = "Flat 2D vector character, clean lines, vibrant colors, solid neutral background. High quality, masterpiece."
    
    # Prompt A: Boca CERRADA
    prompt_closed = f"{base_style} Character description: {descripcion}. Pose: Neutral, listening. Mouth: CLOSED tightly."
    
    # Prompt B: Boca ABIERTA
    prompt_open = f"{base_style} Character description: {descripcion}. Pose: Same character speaking loudly. Mouth: WIDE OPEN shouting or talking."
    
    def fetch_dalle(prompt):
        res = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1)
        return Image.open(io.BytesIO(requests.get(res.data[0].url).content))

    return fetch_dalle(prompt_closed), fetch_dalle(prompt_open)

# ==========================================
# 🎞️ MOTOR DE ANIMACIÓN
# ==========================================

def procesar_video(audio_path, img_closed, img_open, fps=8):
    """Fase 4: Animación (Boca de Marioneta)"""
    
    # Guardar imgs temporales
    img_closed.save("frame_closed.png")
    img_open.save("frame_open.png")
    
    # Cargar audio
    audio = AudioSegment.from_file(audio_path)
    
    # Configurar umbral de silencio dinámico
    avg_db = audio.dBFS
    silence_threshold = avg_db - 5 # Ajustable: cuanto más bajo, más sensible
    
    clips = []
    chunk_len_ms = 1000 // fps # Duración de cada cuadro
    
    # Iterar sobre el audio
    for i in range(0, len(audio), chunk_len_ms):
        chunk = audio[i:i+chunk_len_ms]
        duration = len(chunk) / 1000.0
        
        # Lógica de marioneta: Si el volumen supera el umbral, boca abierta
        if chunk.dBFS > silence_threshold:
            clip = ImageClip("frame_open.png").set_duration(duration)
        else:
            clip = ImageClip("frame_closed.png").set_duration(duration)
        
        clips.append(clip)
        
    # Unir todo
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(AudioFileClip(audio_path))
    
    output_filename = "animacion_final.mp4"
    video.write_videofile(
        output_filename, fps=fps, codec="libx264", audio_codec="aac",
        preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p'],
        logger=None # Silenciar logs en consola
    )
    
    return output_filename

# ==========================================
# 📱 INTERFAZ
# ==========================================
st.title(APP_NAME)
st.markdown("### 🗣️ Tu Audio -> Gente Rota con IA")
st.write("Sube un audio filtrado, una queja o un chiste y la IA creará la animación.")

# Input
col1, col2 = st.columns([2, 1])
with col1:
    audio_file = st.file_uploader("📂 Subir Audio (MP3/WAV/OGG)", type=["mp3", "wav", "ogg", "m4a"])
with col2:
    contexto = st.text_area("Pista (Opcional)", placeholder="Ej: Es una señora 'chuchi' retando a su jardinero.", height=100)

if audio_file:
    st.audio(audio_file)
    
    if st.button("🎬 ¡ACCIÓN! (Generar Video)"):
        with st.status("🏗️ Produciendo animación...", expanded=True) as status:
            try:
                # 1. Guardar Audio
                status.write("💾 Procesando archivo de audio...")
                temp_audio = "temp_input.mp3"
                with open(temp_audio, "wb") as f:
                    f.write(audio_file.getbuffer())
                
                # 2. Transcripción
                status.write("👂 Escuchando conversación...")
                texto = transcribir_audio(temp_audio)
                st.info(f"📝 **Se escuchó:** \"{texto}\"")
                
                # 3. Personaje
                status.write("🧠 Diseñando personaje...")
                desc = imaginar_personaje(texto, contexto)
                
                # 4. Arte
                status.write("🎨 DALL-E 3 dibujando (esto toma unos segundos)...")
                img_c, img_a = generar_sprites(desc)
                
                # Preview
                c1, c2 = st.columns(2)
                with c1: st.image(img_c, caption="Callado")
                with c2: st.image(img_a, caption="Hablando")
                
                # 5. Render
                status.write("🎞️ Animando marioneta...")
                video_path = procesar_video(temp_audio, img_c, img_a)
                
                status.update(label="✅ ¡LISTO!", state="complete", expanded=False)
                
                # Resultado
                st.divider()
                st.subheader("📺 Tu Video Viral:")
                st.video(video_path)
                
                with open(video_path, "rb") as v:
                    st.download_button("⬇️ Descargar Video", v, "gente_rota_ia.mp4", mime="video/mp4", type="primary")
                    
            except Exception as e:
                status.update(label="❌ Error", state="error")
                st.error(f"Ocurrió un error: {e}")
