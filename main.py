import streamlit as st
import google.generativeai as genai
import replicate
import json
import random
import hashlib
import os
import requests
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageEnhance
from io import BytesIO

# --- CONFIGURATION ---
ACCESS_PASSWORD = "LUCALLES-PRODUCTION-2026"
HISTORY_FILE = "theia_genetic_history.json"
# Notice: BILLING_FILE = "theia_billing.json" has been removed because we use the database now.

# --- PERSISTENT BILLING LOGIC (GOOGLE SHEETS DATABASE) ---
def get_gspread_client():
    creds_dict = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"],
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
        "universe_domain": "googleapis.com"
    }
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def load_billing():
    try:
        client = get_gspread_client()
        sheet = client.open("Theia Billing").sheet1
        
        # 1. Check what the real-world month is right now
        current_month = datetime.datetime.now().strftime("%B %Y")
        
        # 2. Look at Cell A2 in the database to see what month is saved there
        saved_month = sheet.cell(2, 1).value 
        
        # 3. IF THE MONTHS MATCH: Load the current credits
        if saved_month == current_month:
            credits_val = sheet.cell(2, 2).value # Reads Cell B2
            images_val = sheet.cell(2, 3).value  # Reads Cell C2
            return {
                "month": current_month,
                "credits": float(credits_val) if credits_val else 0.0,
                "images": int(images_val) if images_val else 0
            }
            
        # 4. IF IT IS A NEW MONTH: Reset everything in the database to 0!
        else:
            sheet.update_cell(2, 1, current_month) # Update A2 to the new month
            sheet.update_cell(2, 2, 0.0)           # Reset B2 (Credits) to 0
            sheet.update_cell(2, 3, 0)             # Reset C2 (Images) to 0
            return {"month": current_month, "credits": 0.0, "images": 0}
            
    except Exception as e:
        return {"month": "System Error", "credits": 0.0, "images": 0}

def save_billing(data):
    try:
        client = get_gspread_client()
        sheet = client.open("Theia Billing").sheet1
        sheet.update_cell(2, 2, data["credits"]) # Writes to Cell B2
        sheet.update_cell(2, 3, data["images"])  # Writes to Cell C2
    except:
        pass

# --- STREAMLIT CALLBACK FUNCTION ---
def reset_edits(subject_name):
    st.session_state[f"b_{subject_name}"] = 1.0
    st.session_state[f"c_{subject_name}"] = 1.0
    st.session_state[f"s_{subject_name}"] = 1.0

# --- THEIA PYTHON ENGINE (TRUE CASTING UPGRADE) ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

        self.bone_average = [
            "a completely ordinary, everyday facial structure",
            "a flat midface with a soft, unassuming jawline",
            "a round facial structure with soft cheeks and a broad alar base"
        ]
        self.skin_average = [
            "raw unretouched skin, natural sebum catching the light, faint everyday blemishes",
            "matte but normal human skin, very faint natural freckles, visible capillaries"
        ]

        self.bone_flawed = [
            "a prominent supraorbital ridge with heavy facial asymmetry",
            "a narrow face with a pronounced dorsal hump on the nose and a weak chin",
            "an asymmetrical jaw structure with a slightly deviated septum and uneven eyes"
        ]
        self.skin_flawed = [
            "harsh skin texture, deep acne scarring, visible pores, and uneven pigmentation",
            "sun-damaged, weathered skin with deep crow's feet and unedited harsh blemishes"
        ]

        self.bone_attractive = [
            "a strong, defined jawline with striking, conventionally attractive features",
            "handsome, symmetrical proportions with a relaxed natural brow",
            "delicate, beautiful, and balanced natural features"
        ]
        self.skin_attractive = [
            "clear and well-maintained skin, slight natural shine on the nose, realistic human texture (not plastic)",
            "a naturally healthy glow, completely unedited, faint laugh lines"
        ]

        self.environments = [
            "a bright, overgrown backyard on a weekend",
            "a windy public park path with natural foliage in the background",
            "a fluorescent-lit grocery store aisle with blurred shelves",
            "a mildly messy bedroom with natural window light",
            "a busy city crosswalk with concrete textures",
            "sitting in the driver seat of a parked car",
            "a warm, softly lit local coffee shop",
            "a modern, clean apartment living room"
        ]

        self.lighting_conditions = [
            "flat, overcast daylight, creating soft and even natural lighting",
            "golden hour sunlight casting warm, long shadows",
            "bright, natural window light illuminating one side of the face",
            "harsh direct camera flash creating strong drop shadows",
            "dappled sunlight filtering through tree leaves",
            "mixed indoor lighting with cool window light and warm overhead bulbs"
        ]

        self.camera_hardware_poor = [
            "shot on an older budget smartphone from 2015, slight digital noise, unedited",
            "taken with a basic budget Android phone, raw image quality, slight motion blur",
            "a grainy point-and-shoot digital photo, mundane amateur framing"
        ]
        
        self.camera_hardware_middle = [
            "a candid smartphone photo from an average modern phone, unretouched",
            "shot as an unfiltered iPhone photo with natural focus, casual snapshot",
            "taken on a mid-range phone camera, everyday documentary style"
        ]
        
        self.camera_hardware_wealthy = [
            "captured on a modern flagship smartphone with crisp, natural depth",
            "taken by a friend on a high-end phone with beautiful ambient light, strictly no filters",
            "a casual, high-quality unedited phone snapshot, natural sharpness"
        ]
        
        self.timeframes = [
            "Taken exactly one year ago on a normal day",
            "Captured 14 months prior to any incidents",
            "A casual, happy memory from a year before the events",
            "An everyday snapshot taken a year in the past"
        ]

        self.framings = [
            "framed as a casual Selfie, holding the camera with one arm",
            "framed as an Environmental Candid shot from waist-up, interacting with the space",
            "framed as an unposed Companion Shot taken by a friend across a table",
            "framed as an Action Snapshot caught mid-movement, slightly imperfect framing",
            "framed as a candid profile shot, looking completely away from the camera"
        ]

        self.expressions = [
            "laughing mid-sentence, looking genuine, joyful, and unposed",
            "showing a soft, relaxed, contented smile",
            "talking expressively, completely unposed natural face",
            "an awkward but polite smile for the camera",
            "mid-gesture, relaxed spontaneous posture, highly candid",
            "a serene, calm expression, caught in thought"
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

    def generate_prompt(self, character_name, socioeconomic_status="middle class", appearance_tier="average"):
        is_unique = False
        while not is_unique:
            if appearance_tier == "handsome/beautiful":
                bone = random.choice(self.bone_attractive)
                skin = random.choice(self.skin_attractive)
            elif appearance_tier == "flawed/ugly":
                bone = random.choice(self.bone_flawed)
                skin = random.choice(self.skin_flawed)
            else:
                bone = random.choice(self.bone_average)
                skin = random.choice(self.skin_average)

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
        timeframe = random.choice(self.timeframes)

        if socioeconomic_status.lower() in ["poor", "struggling", "working class"]:
            camera = random.choice(self.camera_hardware_poor)
            wealth_modifier = "wearing worn, slightly faded everyday clothing."
        elif socioeconomic_status.lower() in ["wealthy", "rich", "high class"]:
            camera = random.choice(self.camera_hardware_wealthy)
            wealth_modifier = "wearing high-quality, well-fitted everyday clothing."
        else:
            camera = random.choice(self.camera_hardware_middle)
            wealth_modifier = "wearing standard, everyday casual clothing."

        prompt = (
            f"A highly realistic, casual documentary-style photograph of a person named {character_name}. "
            f"The image looks like it was {camera}. They have {bone}. Their skin features {skin}. "
            f"They are showing a natural, everyday expression: {expression}. "
            f"The image is {framing}. SETTING: {environment}, {wealth_modifier}. "
            f"LIGHTING: {lighting}. {timeframe}, captured on a normal, uneventful day. "
            f"It must look like a standard, unmodified snapshot directly from a camera. No AI airbrushing, no plastic 3D skin, no beauty filters, and no studio lighting."
        )
        return prompt, genetic_signature

# --- UI SETUP ---
st.set_page_config(page_title="THEIA PRO", page_icon="👁️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    
  /* --- PRIVACY & UI PATCH --- */
   /* 1. Kill BOTH the collapse and expand arrows so the sidebar is strictly permanent */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] { 
        display: none !important; 
    }

   /* 2. NUKE THE TOP RIGHT MENU (Share, Github, Edit, Dots) */
    [data-testid="stHeaderActionElements"],
    [data-testid="stToolbar"],
    [data-testid="stAppToolbar"] {
        display: none !important;
    }

   /* 3. Make header transparent to hide the ugly white bar */
    header { background-color: transparent !important; }
    
    /* Hide the footer watermark */
    footer { visibility: hidden !important; }
    
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
Also determine their 'appearance_tier' based on their role or vibe in the story (choose exactly ONE: "average", "flawed/ugly", "handsome/beautiful"). If their appearance isn't obvious from the script, default strictly to "average".

You MUST return ONLY a raw JSON array of objects. Do not wrap it in markdown block quotes. Just the raw text.
Format example:
[
    {"name": "John Doe", "socioeconomic_status": "middle class", "appearance_tier": "average"}
]
SCRIPT TO ANALYZE:
"""

st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v6.0 Enterprise Studio</div>', unsafe_allow_html=True)

password_input = st.sidebar.text_input("🔒 Security Portal", type="password", placeholder="Enter Passcode...")

if password_input == ACCESS_PASSWORD:
    st.sidebar.success("🟢 SYSTEM ONLINE")
    st.sidebar.markdown("---")
    
    # --- MONTHLY BILLING TRACKER UI ---
    if 'billing' not in st.session_state:
        st.session_state.billing = load_billing()
        
    billing_display = st.sidebar.empty()
    
    def update_billing_ui():
        month_name = datetime.datetime.now().strftime("%B %Y")
        billing_display.markdown(f"""
            <div style='background: rgba(43,45,49,0.5); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px;'>
                <p style='color: #949ba4; margin: 0; font-family: Inter; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;'>{month_name} USAGE</p>
                <h2 style='color: #43b581; margin: 5px 0 5px 0; font-weight: 900; font-family: Inter;'>💳 Credit ${st.session_state.billing['credits']:.2f}</h2>
                <p style='color: #dbdee1; margin: 0; font-family: Inter; font-size: 0.9rem;'>🖼️ {st.session_state.billing['images']} Images Generated</p>
            </div>
        """, unsafe_allow_html=True)
        
    update_billing_ui()
    st.sidebar.markdown("---")
    
    if API_STATUS:
        st.sidebar.info("🧠 Brain: Gemini 2.5 Pro")
        st.sidebar.info("🎨 Engine: OpenAI GPT-Image 1.5")
        st.sidebar.info("🏢 Auth: Lucalles Productions")
        st.sidebar.info("🛠️ Post-Processing: Active")
    
    if 'generated_subjects' not in st.session_state:
        st.session_state.generated_subjects = []

    st.markdown("#### 🎬 Script Ingestion")
    user_script = st.text_area("Input Stream", height=150, placeholder="Paste your documentary/narrative script here...", label_visibility="collapsed")
    
    if st.button("INITIALIZE THEIA ENGINE"):
        if user_script:
            st.session_state.generated_subjects = [] 
            with st.spinner("Analyzing roles and casting authentic appearances via OpenAI..."):
                try:
                    model = genai.GenerativeModel("gemini-2.5-pro")
                    response = model.generate_content(EXTRACTION_PROMPT + user_script)
                    raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
                    character_data = json.loads(raw_json)
                    
                    theia_engine = TheiaPromptGenerator()
                    
                    for char in character_data:
                        name = char.get("name", "Unknown Subject")
                        status = char.get("socioeconomic_status", "middle class")
                        appearance = char.get("appearance_tier", "average")
                        
                        prompt, genetics = theia_engine.generate_prompt(name, status, appearance)
                        
                        output = replicate.run(
                            "openai/gpt-image-1.5",
                            input={
                                "prompt": prompt,
                                "size": "1024x1024",
                                "quality": "high", 
                                "style": "natural"
                            }
                        )
                        
                        image_url = str(output[0])
                        img_response = requests.get(image_url)
                        img_bytes = img_response.content
                        
                        st.session_state.generated_subjects.append({
                            "name": name,
                            "prompt": prompt,
                            "hash": genetics,
                            "appearance_tier": appearance,
                            "image_bytes": img_bytes
                        })
                        
                        # PERSISTENT UPDATE TO TRACKER
                        st.session_state.billing['credits'] += 0.40
                        st.session_state.billing['images'] += 1
                        save_billing(st.session_state.billing)
                        update_billing_ui()
                        
                except Exception as e:
                    st.error("❌ System Processing Error")
                    st.code(f"Error Details: {e}")
        else:
            st.warning("⚠️ Input Buffer Empty. Please paste a script.")

    if st.session_state.generated_subjects:
        st.markdown("---")
        st.success(f"✅ Extraction & Casting Complete: Found {len(st.session_state.generated_subjects)} Subjects")
        
        for subject in st.session_state.generated_subjects:
            name = subject["name"]
            st.markdown(f"### 📸 Subject: {name}")
            st.caption(f"**Casting Tier:** `{subject['appearance_tier'].upper()}` | **Locked Hash:** `{subject['hash']}`")
            
            st.code(subject["prompt"], language="markdown")
            
            st.markdown("##### 🎛️ Post-Processing Adjustments")
            
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
            
            st.button("↩️ Reset Edits (Undo)", key=f"reset_{name}", on_click=reset_edits, args=(name,))
            
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
