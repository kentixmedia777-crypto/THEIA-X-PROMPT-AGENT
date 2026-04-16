import streamlit as st
import google.generativeai as genai
import replicate
import json
import random
import hashlib
import os

# --- CONFIGURATION ---
ACCESS_PASSWORD = "LUCALLES-PRODUCTION-2026"
HISTORY_FILE = "theia_genetic_history.json"

# --- THEIA PYTHON ENGINE ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

        self.bone_structures = [
            "prominent supraorbital ridge with wide zygomatic bones",
            "flat midface with a weak receding chin and soft jawline",
            "asymmetrical jaw structure with a slightly deviated septum",
            "high, sharp cheekbones with deep-set, hooded eyes",
            "round facial structure with soft cheeks and a broad alar base",
            "narrow, angular face with a pronounced dorsal hump on the nose",
            "strong, square mandibular structure with wide-set eyes",
            "soft, oval face with epicanthic folds and a delicate chin",
            "symmetrical facial structure, strong defined jawline, high cheekbones",
            "delicate and balanced features, straight nasal bridge, almond-shaped eyes",
            "handsome, conventionally attractive proportions, strong chin, relaxed brow",
            "beautiful natural bone structure, soft jawline, large expressive eyes"
        ]

        self.skin_textures = [
            "visible pores, natural sebum catching the light, faint acne scarring",
            "sun-damaged skin with asymmetrical freckling and fine lines around the eyes",
            "unretouched skin texture, slight rosacea on the cheeks, razor burn",
            "realistic peach fuzz, uneven pigmentation, natural skin tone",
            "weathered skin, deep laugh lines, slight under-eye bags",
            "matte but natural skin, slight imperfection on the forehead, visible capillaries",
            "clear complexion, very faint natural freckles, soft natural lighting reflection",
            "well-maintained skin, slight natural shine on the nose, realistic pores but no major blemishes",
            "naturally healthy glow, faint laugh lines, clean unedited look",
            "smooth skin with a subtle, everyday smartphone beauty filter applied, slight digital smoothing"
        ]

        self.environments = [
            "Outdoor: overgrown backyard",
            "Outdoor: windy public park path",
            "Outdoor: busy city crosswalk with concrete textures",
            "Outdoor: edge of a lake, muddy banks, bright natural light",
            "Indoor: fluorescent-lit grocery store aisle",
            "Indoor: cramped, messy bedroom",
            "Indoor: warm, softly lit local pub",
            "Indoor: harsh mirror lighting in a public restroom or gym locker room",
            "Indoor: inside a parked car, driver seat"
        ]

        self.lighting_conditions = [
            "harsh direct camera flash creating hard drop shadows",
            "flat, overcast daylight, very even and shadowless",
            "mixed lighting: cool window light clashing with warm overhead tungsten bulbs",
            "dappled sunlight filtering through tree leaves",
            "golden hour sunlight casting long, natural shadows and causing slight squinting",
            "cheap overhead fluorescent lighting creating unflattering downward shadows"
        ]

        self.camera_hardware_poor = [
            "shot on a scratched, old budget smartphone from 2013, high noise, soft details",
            "grainy, noisy point-and-shoot digital photo, poor low-light performance",
            "taken with a very basic, older budget Android, artifacting and blur"
        ]
        
        self.camera_hardware_middle = [
            "candid smartphone photo from an average 2018 model, natural grain",
            "unfiltered older iPhone photo, soft focus, raw and unedited",
            "shot on a mid-range phone camera, slight motion blur, casual feel"
        ]
        
        self.camera_hardware_wealthy = [
            "candid moment captured on a newer smartphone, raw feel, natural depth but unedited",
            "photo taken by a companion on their high-end phone, unposed, natural ambient light",
            "casual snapshot on a modern flagship phone, strictly no filters applied, slight grain"
        ]
        
        self.timeframes = [
            "Taken exactly one year ago on a normal day",
            "Captured 14 months prior to any incidents",
            "A casual memory from a year before the events",
            "An everyday snapshot taken a year in the past"
        ]

        self.framings = [
            "Selfie: subject holding camera with one arm, slight wide-angle distortion",
            "Mirror Selfie: subject holding phone up to a mirror, casual posture",
            "Companion Shot: taken by a friend across a table, eye-level, relaxed distance",
            "Companion Shot: taken by a partner, close proximity, candid",
            "Environmental Candid: mid-body shot from a distance, interacting with the setting",
            "Action Snapshot: caught mid-movement, slightly off-center, imperfect framing"
        ]

        self.expressions = [
            "laughing mid-sentence, genuine and unposed",
            "soft, relaxed, contented smile",
            "confident, slightly goofy grin",
            "peace sign thrown up with a wide, spontaneous smile",
            "serene, calm expression, looking slightly off-camera",
            "awkward but polite smile, looking directly at the lens"
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

        if socioeconomic_status.lower() in ["poor", "struggling", "working class"]:
            camera = random.choice(self.camera_hardware_poor)
        elif socioeconomic_status.lower() in ["wealthy", "rich", "high class"]:
            camera = random.choice(self.camera_hardware_wealthy)
        else:
            camera = random.choice(self.camera_hardware_middle)
            
        timeframe = random.choice(self.timeframes)

        wealth_modifier = ""
        if socioeconomic_status.lower() in ["wealthy", "rich", "high class"]:
            wealth_modifier = "wearing high-quality, well-fitted clothing, environment looks maintained"
        elif socioeconomic_status.lower() in ["poor", "struggling", "working class"]:
            wealth_modifier = "wearing worn, slightly faded clothing, environment looks lived-in and cluttered"
        else:
            wealth_modifier = "wearing standard, everyday casual clothing"

        prompt = (
            f"A highly realistic amateur photograph of {character_name}. "
            f"TIMEFRAME & CONTEXT: {timeframe}, completely unrelated to any future tragedy. "
            f"FACIAL GEOMETRY: {bone}. SKIN TEXTURE: {skin}. "
            f"EXPRESSION: {expression}. EYE CONTACT: looking at the camera. "
            f"ATTIRE/VIBE: {wealth_modifier}. "
            f"SETTING: {environment}. "
            f"LIGHTING: {lighting}. "
            f"CAMERA/FRAMING: {framing}. {camera}. "
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
    .stButton>button { 
        background: linear-gradient(135deg, #5865F2 0%, #a23db8 100%); 
        color: white; 
        border-radius: 8px; 
        font-weight: 700; 
        border: none; 
        padding: 12px 28px; 
        text-transform: uppercase; 
        letter-spacing: 1px;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .stButton>button:hover { 
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(88, 101, 242, 0.5); 
    }
    .stAlert { 
        background: rgba(43, 45, 49, 0.5); 
        backdrop-filter: blur(10px);
        color: #dbdee1; 
        border: 1px solid rgba(255,255,255,0.1); 
        border-radius: 12px;
    }
    code { color: #EB459E; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;}
    pre { background: rgba(30, 31, 34, 0.8) !important; border: 1px solid rgba(255,255,255,0.05); border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- SECURITY & API CONFIG ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    replicate_key = st.secrets["REPLICATE_API_TOKEN"]
    API_STATUS = True
except:
    API_STATUS = False

# --- SYSTEM EXTRACTION PROMPT ---
EXTRACTION_PROMPT = """
You are an expert script analyst. Read the following true crime/documentary script and extract all the significant, named characters.
Do NOT extract background roles (e.g., "Paramedic", "Police Officer 1").
For each character, determine their socioeconomic status based on context clues (e.g., "wealthy", "middle class", "struggling").

You MUST return ONLY a raw JSON array of objects. Do not wrap it in markdown block quotes (no ```json). Just the raw text.
Format example:
[
    {"name": "John Doe", "socioeconomic_status": "middle class"}
]

SCRIPT TO ANALYZE:
"""

# --- MAIN APP ---
st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v5.0 Enterprise SDXL</div>', unsafe_allow_html=True)

password_input = st.sidebar.text_input("🔒 Security Portal", type="password", placeholder="Enter Passcode...")

if password_input == ACCESS_PASSWORD:
    st.sidebar.success("🟢 SYSTEM ONLINE")
    st.sidebar.markdown("---")
    
    if API_STATUS:
        st.sidebar.info("🧠 Brain: Gemini 2.5 Pro")
        st.sidebar.info("🎨 Engine: Stable Diffusion XL")
        st.sidebar.info("🏢 Auth: Lucalles Productions")
    else:
        st.sidebar.error("❌ API Keys Missing in Streamlit Secrets")
    
    st.markdown("#### 🎬 Script Ingestion")
    user_script = st.text_area("Input Stream", height=250, placeholder="Paste your documentary/narrative script here...", label_visibility="collapsed")
    
    st.write("") 
    
    if st.button("INITIALIZE THEIA ENGINE"):
        if user_script:
            with st.spinner("Theia is analyzing narrative variables using Gemini 2.5 Pro..."):
                try:
                    model = genai.GenerativeModel("gemini-2.5-pro")
                    response = model.generate_content(EXTRACTION_PROMPT + user_script)
                    
                    raw_json = response.text.strip()
                    if raw_json.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1
http://googleusercontent.com/immersive_entry_chip/2
