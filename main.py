import streamlit as st
import google.generativeai as genai
import replicate
import json
import random
import hashlib
import os
import requests
from PIL import Image, ImageEnhance
from io import BytesIO

# --- CONFIGURATION ---
ACCESS_PASSWORD = "LUCALLES-PRODUCTION-2026"
HISTORY_FILE = "theia_genetic_history.json"

# --- STREAMLIT CALLBACK FUNCTION (FIXES THE CRASH) ---
def reset_edits(subject_name):
    st.session_state[f"b_{subject_name}"] = 1.0
    st.session_state[f"c_{subject_name}"] = 1.0
    st.session_state[f"s_{subject_name}"] = 1.0

# --- THEIA PYTHON ENGINE ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

        self.bone_structures = [
            "a prominent supraorbital ridge, slight facial asymmetry",
            "a flat midface with a weak receding chin",
            "an asymmetrical jaw structure with a slightly deviated septum",
            "deep-set, hooded eyes with realistic uneven eyelids",
            "a round facial structure with soft cheeks and a broad alar base",
            "a narrow face with a pronounced dorsal hump on the nose",
            "a strong mandibular structure, slight underbite",
            "a completely ordinary, mundane facial structure, zero model proportions"
        ]

        self.skin_textures = [
            "raw unretouched skin, natural sebum catching the light, faint acne scarring, film grain",
            "sun-damaged skin with asymmetrical freckling, deep crow's feet around the eyes",
            "harsh skin texture, slight rosacea on the cheeks, razor burn, unedited snapshot",
            "realistic peach fuzz, uneven natural skin tone, slight under-eye bags with shadows",
            "matte but normal human skin, natural blemishes, visible capillaries on the nose"
        ]

        self.environments = [
            "an overgrown backyard with random clutter",
            "a windy public park path, slightly messy background",
            "a fluorescent-lit grocery store aisle (Aisle 4), background clutter of cereal boxes",
            "a cramped, messy bedroom with clothes thrown around",
            "a busy, unglamorous city crosswalk",
            "a public restroom with harsh overhead mirror lighting"
        ]

        self.lighting_conditions = [
            "harsh direct camera flash creating strong unflattering drop shadows",
            "flat, overcast mundane daylight, very even but dull",
            "clashing mixed light: cool window light and a warm tungsten desk lamp",
            "cheap overhead fluorescent lighting creating downward shadows",
            "overexposed direct sunlight creating blown-out highlights"
        ]

        self.camera_hardware = [
            "shot on a cheap Kodak disposable camera, heavy chemical film grain, light leaks",
            "taken on 35mm amateur analog film, gritty texture, slight chromatic aberration",
            "a grainy, noisy Polaroid snapshot, poor lens quality, degraded film colors",
            "an unfiltered candid film photograph, mundane aesthetic, high ISO noise",
            "a casual, unedited disposable camera shot, zero depth-of-field effect, raw flash"
        ]
        
        self.timeframes = [
            "Taken exactly one year ago on a normal day",
            "Captured 14 months prior to any incidents",
            "A casual memory from a year before the events"
        ]

        self.framings = [
            "framed as an awkward Selfie, holding the camera with one arm, showing slight wide-angle lens distortion",
            "framed as a mundane Mirror Selfie, imperfect focus",
            "framed as an Environmental Candid mid-conversation, off-center",
            "framed as a Spontaneous Snapshot caught mid-movement, unretouched composition"
        ]

        self.expressions = [
            "laughing mid-sentence, head thrown back, non-symmetric smile",
            "talking expressive face, completely unposed, natural resting face",
            "an awkward but genuine smile, slight squint",
            "mid-gesture, relaxed spontaneous posture, looking away naturally"
        ]

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()

    def _save_history(self):
        with open(HISTORY_FILE, 'w') as f:
            json.dump(list(self.history), f)

    def generate_prompt(self, character_name, socioeconomic_status="middle class"):
        is_unique = False
        while not is_unique:
            bone = random.choice(self.bone_structures)
            skin = random.choice(self.skin_textures)
            genetic_signature = f"{bone} | {skin}"
            sig_hash = hashlib.md5(genetic_signature.encode()).hexdigest()
            
            if sig_hash not in self.history:
                self.history.add(sig_hash)
                self._save_history()
                is_unique = True

        environment = random.choice(self.environments)
        lighting = random.choice(self.lighting_conditions)
        framing = random.choice(self.framings)
        expression = random.choice(self.expressions)
        camera = random.choice(self.camera_hardware)
        timeframe = random.choice(self.timeframes)

        wealth_modifier = "wearing worn, slightly faded everyday clothing." if socioeconomic_status.lower() in ["poor", "struggling"] else "wearing standard everyday casual clothing."

        # OpenAI prefers conversational, descriptive prompts over tags
        prompt = (
            f"A completely mundane, highly amateur candid snapshot of a real person named {character_name}. "
            f"The image looks like it was {camera}. They have {bone}. Their skin features {skin}. "
            f"They are showing a dynamic unposed expression: {expression}. "
            f"The image is {framing}. SETTING: {environment}, {wealth_modifier}. "
            f"LIGHTING: {lighting}. {timeframe}, unrelated to any future tragedy. "
            f"It must look like a raw, unedited, spontaneous snapshot with zero posing, absolutely zero AI airbrushing, and a low aesthetic score."
        )
        return prompt, genetic_signature

# --- UI SETUP ---
st.set_page_config(page_title="THEIA PRO", page_icon="👁️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    .stApp { 
        background-color: #0b0c10; 
        background-image: radial-gradient(circle at 15% 50%, rgba(88, 101, 242, 0.05), transparent 25%), 
                          radial-gradient(circle at 85% 30%, rgba(235, 69, 158, 0.05), transparent 25%);
        font-family: 'Inter', sans-serif; 
        color: #e4e6eb;
    }
    [data-testid="stSidebar"] { 
        background: rgba(30, 31, 34, 0.6) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    .custom-title {
        font-family: 'Inter', sans-serif;
        font-weight: 900;
        font-size: 4rem;
        background: linear-gradient(90deg, #5865F2 0%, #EB459E 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1.5px;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    .custom-subtitle {
        font-family: 'Inter', sans-serif;
        font-weight: 300;
        font-size: 1.1rem;
        color: #949ba4;
        margin-top: -5px;
        margin-bottom: 40px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 20px;
        letter-spacing: 1px;
    }
    h3, h4, p, label, .stMarkdown { color: #dbdee1 !important; }
    .stTextArea textarea, .stTextInput input { 
        background: rgba(43, 45, 49, 0.7) !important; 
        backdrop-filter: blur(10px);
        color: #ffffff !important; 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 12px; 
        font-family: 'Inter', sans-serif;
        padding: 15px;
        transition: all 0.3s ease;
    }
    .stTextArea textarea:focus, .stTextInput input:focus { 
        border-color: #5865F2; 
        box-shadow: 0 0 15px rgba(88, 101, 242, 0.3); 
        background: rgba(43, 45, 49, 0.9) !important;
    }
    .stButton>button, .stDownloadButton>button { 
        background: linear-gradient(135deg, #5865F2 0%, #a23db8 100%) !important; 
        color: white !important; 
        border-radius: 8px !important; 
        font-weight: 700 !important; 
        border: none !important; 
        padding: 12px 28px !important; 
        text-transform: uppercase !important; 
        letter-spacing: 1px !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important;
    }
    .stButton>button:hover, .stDownloadButton>button:hover { 
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(88, 101, 242, 0.5) !important; 
    }
</style>
""", unsafe_allow_html=True)

# --- SECURITY & API CONFIG ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
    API_STATUS = True
except:
    API_STATUS = False

EXTRACTION_PROMPT = """
You are an expert script analyst. Read the following true crime/documentary script and extract all the significant, named characters.
Do NOT extract background roles (e.g., "Paramedic", "Police Officer 1").
For each character, determine their socioeconomic status based on context clues (e.g., "wealthy", "middle class", "struggling").

You MUST return ONLY a raw JSON array of objects. Do not wrap it in markdown block quotes. Just the raw text.
Format example:
[
    {"name": "John Doe", "socioeconomic_status": "middle class"}
]
SCRIPT TO ANALYZE:
"""

st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v5.5.1 Enterprise Studio</div>', unsafe_allow_html=True)

password_input = st.sidebar.text_input("🔒 Security Portal", type="password", placeholder="Enter Passcode...")

if password_input == ACCESS_PASSWORD:
    st.sidebar.success("🟢 SYSTEM ONLINE")
    st.sidebar.markdown("---")
    
    if API_STATUS:
        st.sidebar.info("🧠 Brain: Gemini 2.5 Pro")
        st.sidebar.info("🎨 Engine: OpenAI GPT-Image 1.5")
        st.sidebar.info("🏢 Auth: Lucalles Productions")
        st.sidebar.info("🛠️ Post-Processing: Active")
    
    # --- SESSION STATE MEMORY ---
    if 'generated_subjects' not in st.session_state:
        st.session_state.generated_subjects = []

    st.markdown("#### 🎬 Script Ingestion")
    user_script = st.text_area("Input Stream", height=150, placeholder="Paste your documentary/narrative script here...", label_visibility="collapsed")
    
    if st.button("INITIALIZE THEIA ENGINE"):
        if user_script:
            st.session_state.generated_subjects = [] # Clear old memory
            with st.spinner("Analyzing variables and rendering via OpenAI..."):
                try:
                    model = genai.GenerativeModel("gemini-2.5-pro")
                    response = model.generate_content(EXTRACTION_PROMPT + user_script)
                    # Safe JSON extraction
                    raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
                    character_data = json.loads(raw_json)
                    
                    theia_engine = TheiaPromptGenerator()
                    
                    for char in character_data:
                        name = char.get("name", "Unknown Subject")
                        status = char.get("socioeconomic_status", "middle class")
                        prompt, genetics = theia_engine.generate_prompt(name, status)
                        
                        # Generate Image using OpenAI on Replicate
                        output = replicate.run(
                            "openai/gpt-image-1.5",
                            input={
                                "prompt": prompt,
                                "size": "1024x1024",
                                "quality": "high", # <-- FIXED PARAMETER HERE
                                "style": "natural"
                            }
                        )
                        
                        # Download image into memory
                        image_url = str(output[0])
                        img_response = requests.get(image_url)
                        img_bytes = img_response.content
                        
                        # Save to memory so sliders don't delete it
                        st.session_state.generated_subjects.append({
                            "name": name,
                            "prompt": prompt,
                            "hash": genetics,
                            "image_bytes": img_bytes
                        })
                except Exception as e:
                    st.error("❌ System Processing Error")
                    st.code(f"Error Details: {e}")
        else:
            st.warning("⚠️ Input Buffer Empty. Please paste a script.")

    # --- THE EDITING & DOWNLOAD INTERFACE ---
    if st.session_state.generated_subjects:
        st.markdown("---")
        st.success(f"✅ Extraction & Rendering Complete: Found {len(st.session_state.generated_subjects)} Subjects")
        
        for subject in st.session_state.generated_subjects:
            name = subject["name"]
            st.markdown(f"### 📸 Subject: {name}")
            st.caption(f"**Locked Genetic Hash:** `{subject['hash']}`")
            
            st.code(subject["prompt"], language="markdown")
            
            st.markdown("##### 🎛️ Post-Processing Adjustments")
            
            # Initialize slider defaults
            if f"b_{name}" not in st.session_state: st.session_state[f"b_{name}"] = 1.0
            if f"c_{name}" not in st.session_state: st.session_state[f"c_{name}"] = 1.0
            if f"s_{name}" not in st.session_state: st.session_state[f"s_{name}"] = 1.0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                brightness = st.slider("Brightness", 0.5, 1.5, key=f"b_{name}")
            with col2:
                contrast = st.slider("Contrast", 0.5, 1.5, key=f"c_{name}")
            with col3:
                sharpness = st.slider("Sharpness", 0.0, 2.5, key=f"s_{name}")
            
            # The secure callback button
            st.button("↩️ Reset Edits (Undo)", key=f"reset_{name}", on_click=reset_edits, args=(name,))
            
            # Apply PIL Edits
            base_img = Image.open(BytesIO(subject["image_bytes"]))
            base_img = ImageEnhance.Brightness(base_img).enhance(brightness)
            base_img = ImageEnhance.Contrast(base_img).enhance(contrast)
            final_img = ImageEnhance.Sharpness(base_img).enhance(sharpness)
            
            st.image(final_img, use_container_width=True)
            
            buf = BytesIO()
            final_img.save(buf, format="JPEG", quality=95)
            st.download_button(
                label=f"⬇️ Download {name} (Edited)",
                data=buf.getvalue(),
                file_name=f"{name.replace(' ', '_')}_theia_render.jpg",
                mime="image/jpeg",
                key=f"dl_{name}"
            )
            st.markdown("<br><br>", unsafe_allow_html=True)
