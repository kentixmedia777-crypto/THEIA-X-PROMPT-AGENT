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

# --- UPDATED THEIA ENGINE (TRUE DIVERSITY & SEED PATCH) ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

        # AUDIT FIX 1: DIVERSIFIED GEOMETRY
        # Replaced generic 'bone structure' with specific geometries & ancestry, inspired by the reference images.
        self.facial_geometries_variant_a = [
            "completely average, everyday facial structure",
            "a flat midface with a soft, unassuming jawline",
            "round facial structure with soft cheeks and a broad alar base",
            "striking Northern European features, fair complexion, light eyes",
            "distinctive East Asian ancestry, flat facial profile, monolid eyes",
            "Mediterranean complexion, distinctive long facial structure, prominent nose",
            "delicate, beautiful, and balanced natural features",
            "square jawline with high cheekbones and defined bone structure"
        ]
        
        # AUDIT FIX 2: VARYING SKIN TEXTURE (No Clones)
        # Replaced confusing 'raw unretouched skin' keywords. GPT Image 1.5 defaults to a generic face when hit with "Raw Snapshot."
        # These new descriptions force diversity across average/handsome/beautiful tiers.
        self.skin_textures_variant_a = [
            "natural human skin with realistic pores, texture, and complex variations.",
            "soft and smooth skin texture with a clean, well-maintained look, but still highly realistic.",
            "a textured and authentic complexion, showing some common skin variations like moles, subtle freckles, and visible pores.",
            "matte but normal human skin, very faint natural freckles, visible capillaries.",
            "a naturally healthy glow, completely unedited, faint laugh lines.",
            "realistic, normal human skin with a varied tone and visible texture."
        ]

        # Keeping distinctive geometries for unique casting, updated for GPT Image 1.5 obedience
        self.facial_geometries_variant_b = [
            "pronounced supraorbital ridge, heavy facial asymmetry",
            "narrow face with a prominent dorsal hump on the nose, weak chin",
            "asymmetrical jaw structure with a slightly deviated septum, uneven eyes",
            "strong West African ancestry, defined bone structure, broad nasal base",
            "Indigenous South American features, high cheekbones, strong profile",
            "coarsened and robust facial features, deeply set, asymmetrical eyes and a coarse beard"
        ]
        
        # AUDIT FIX 3: VARYING FLAWED SKIN (No Clones)
        # Ensuring flawed skins are also varied and not just "all harsh."
        self.skin_textures_variant_b = [
            "highly detailed and coarse skin texture, showing complex imperfections like deep acne scarring and visible pores.",
            "sun-damaged and weathered complexion with deep crow's feet and an authentic, rugged texture.",
            "authentic and varied facial complexion with notable features like moles, uneven pigmentation, and subtle texture.",
            "visible rough texture, deep pigmentation, and notable imperfections.",
            "sun-baked, rough skin texture with noticeable lines and pores."
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

        # AUDIT FIX 4: REALISTIC LIGHTING
        # Maintaining the natural style from the reference images, fully laundered.
        self.lighting_conditions = [
            "flat, overcast daylight, creating soft and even natural lighting",
            "golden hour sunlight casting warm, long shadows",
            "bright, natural window light illuminating one side of the face",
            "harsh direct camera flash creating strong drop shadows",
            "dappled sunlight filtering through tree leaves",
            "mixed indoor lighting with cool window light and warm overhead bulbs"
        ]

        self.camera_hardware_poor = [
            "shot on an older budget smartphone from 2015, slight digital noise",
            "taken with a basic budget Android phone, raw image quality",
            "a grainy point-and-shoot digital photo, amateur framing"
        ]
        
        self.camera_hardware_middle = [
            "a candid smartphone photo from an average modern phone, unretouched",
            "shot as an unfiltered iPhone photo with natural focus, casual snapshot",
            "taken on a mid-range phone camera, everyday documentary style"
        ]
        
        self.camera_hardware_wealthy = [
            "captured on a modern flagship smartphone with crisp, natural depth",
            "taken by friend on a high-end phone, strictly no filters",
            "a casual, high-quality unedited phone snapshot"
        ]
        
        self.timeframes = [
            "taken exactly one year ago",
            "captured 14 months prior to any incident",
            "a casual memory from the past",
            "an everyday snapshot from last year"
        ]

        # AUDIT FIX 5: NATURAL POSES & FRAMINGS
        # Integrating the requested shot types (Medium Shot, Close Up, Cowboy Shot) and inspired angles for dynamic composition.
        self.framings = [
            "Medium Shot (waist-up), naturally framed by the environment.",
            "Medium Close Up, focusing on the head and shoulders with natural depth.",
            "Cowboy Shot (thigh-up), with a strong focus on posture and presence.",
            "Close Up, with a tight focus on the face and expression.",
            "Candid Environmental Shot from a three-quarter angle.",
            "Low Angle perspective, adding dynamism to the composition.",
            "High Angle perspective, looking down on the subject naturally."
        ]

        # Natural human expressions, good for documentary style
        self.expressions = [
            "laughing mid-sentence, looking joyful and unposed",
            "showing a soft, relaxed, contented smile",
            "talking expressively, completely unposed natural face",
            "an awkward but polite smile for the camera",
            "mid-gesture, relaxed spontaneous posture, highly candid",
            "a serene, calm expression, caught in thought",
            "mid-conversation, gesturing naturally with hands",
            "looking slightly to the side, natural and spontaneous"
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

    # AUDIT FIX 6: DYNAMIC PROMPT LOGIC (SEEDED FACES + VARIATION)
    def generate_prompt(self, character_name, socioeconomic_status="middle class", appearance_tier="average"):
        
        # 1. THE DYNAMIC SEED. Instead of random hashing, we generate an integer based on the character's unique parameters (name+genetics).
        # This provides GPT Image 1.5 with a context lock for this specific individual, forcing diversity.
        name_seed = int(hashlib.md5((character_name + appearance_tier).encode()).hexdigest(), 16) % 10000

        # 2. DIVERSIFIED CASTING (Fixing generic tiers)
        # We simplify the 'ugly' vs 'average' concept which confuses GPT Image 1.5 into defaulting its face.
        # We replace this with highly specific 'facial geometry' and 'global ancestry' for diverse 'casting.'
        
        if appearance_tier in ["average", "handsome/beautiful"]:
            # Uses cleaner geometry, dynamic ancestry, and standard beauty
            facial_structure = random.choice(self.facial_geometries_variant_a)
            skin_complexion = random.choice(self.skin_textures_variant_a)
        elif appearance_tier == "flawed/ugly":
            # Uses asymmetric geometry, coarsened structure, or alternative ancestry
            facial_structure = random.choice(self.facial_geometries_variant_b)
            skin_complexion = random.choice(self.skin_textures_variant_b)
        else:
            # Absolute default in case of error
            facial_structure = "completely ordinary, everyday facial structure"
            skin_complexion = "natural human skin texture, unretouched"

        # Unique signature to track the face
        genetic_signature = f"{facial_structure} | {skin_complexion} [Seed:{name_seed}]"
        sig_hash = hashlib.md5(genetic_signature.encode()).hexdigest()
        
        # History tracking (keeping your logic)
        if sig_hash not in self.history:
            self.history.add(sig_hash)
            self._save_history()

        # Context selection (DIVERSIFIED FRAMINGS)
        environment = random.choice(self.environments)
        lighting = random.choice(self.lighting_conditions)
        expression = random.choice(self.expressions)
        timeframe = random.choice(self.timeframes)
        framing = random.choice(self.framings)

        # Economic hardware selection (keeping your logic)
        if socioeconomic_status.lower() in ["poor", "struggling", "working class"]:
            camera = random.choice(self.camera_hardware_poor)
            wealth_modifier = "wearing worn, slightly faded everyday clothing."
        elif socioeconomic_status.lower() in ["wealthy", "rich", "high class"]:
            camera = random.choice(self.camera_hardware_wealthy)
            wealth_modifier = "wearing high-quality, well-fitted everyday clothing."
        else:
            camera = random.choice(self.camera_hardware_middle)
            wealth_modifier = "wearing standard, everyday casual clothing."

        # 3. VOCABULARY LAUNDERING & DYNAMIC POSE (Filter Safe + diversified composition)
        # Cleaned prompt language (no 'amateur,' 'raw unretouched,' 'NSFW words')
        # Integrated dynamic framings and natural posture definitions.
        
        prompt = (
            f"A highly realistic, documentary-style photograph of a unique individual named {character_name}. "
            f"This is a specific, unique identity, seed signature: [Seed:{name_seed}]. "
            f"They have {facial_structure}. Their face features {skin_complexion}. "
            f"The image is framed as a {framing}, captured by {camera}. "
            f"They are showing a natural human expression: {expression}. SETTING: {environment}. "
            f"LIGHTING: {lighting}. {timeframe}, {wealth_modifier}. "
            f"They are captured in a spontaneous pose, unique to this individual. This is a high-resolution, unmodified snapshot direct from a camera. No AI airbrushing, no plastic 3D skin, no beauty filters, and no studio lighting."
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

# ==========================================
# MODIFICATION 1: EXTRACTION PROMPT
# ==========================================
EXTRACTION_PROMPT = """
You are an expert script analyst. Read the following true crime/documentary script and extract all the significant, named characters.
Do NOT extract background roles (e.g., "Paramedic", "Police Officer 1").
For each character, determine:
1. socioeconomic_status ("wealthy", "middle class", "struggling")
2. appearance_tier ("average", "flawed/ugly", "handsome/beautiful")
3. age (estimate if not explicitly stated)
4. details (a short 1-sentence summary of who they are in the story)

You MUST return ONLY a raw JSON array of objects. Do not wrap it in markdown block quotes. Just the raw text.
Format example:
[
    {"name": "John Doe", "age": "45", "details": "The lead detective on the case.", "socioeconomic_status": "middle class", "appearance_tier": "average"}
]
SCRIPT TO ANALYZE:
"""

st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v7.0 Modular Studio</div>', unsafe_allow_html=True)

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
        st.sidebar.info("🧠 Brain: Gemini Pro (Latest)")
        st.sidebar.info("🎨 Engine: Modular RPX")
        st.sidebar.info("🏢 Auth: Lucalles Productions")

    # ==========================================
    # MODIFICATION 2: UI TABS REPLACEMENT
    # ==========================================
    tab1, tab2 = st.tabs(["📝 Prompt Studio", "🎨 Image Studio"])

    # --- TAB 1: PROMPT STUDIO ---
    with tab1:
        st.markdown("#### 🎬 Script Ingestion")
        user_script = st.text_area("Input Stream", height=150, placeholder="Paste your documentary/narrative script here...", label_visibility="collapsed")
        
        if st.button("EXTRACT & BUILD PROMPTS"):
            if user_script:
                with st.spinner("Analyzing roles and building genetic profiles via Gemini..."):
                    try:
                        model = genai.GenerativeModel("gemini-2.5-pro")
                        response = model.generate_content(EXTRACTION_PROMPT + user_script)
                        raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
                        character_data = json.loads(raw_json)
                        
                        theia_engine = TheiaPromptGenerator()
                        
                        st.success(f"✅ Extraction Complete: Found {len(character_data)} Subjects")
                        st.markdown("---")
                        
                        for char in character_data:
                            name = char.get("name", "Unknown Subject")
                            status = char.get("socioeconomic_status", "middle class")
                            appearance = char.get("appearance_tier", "average")
                            age = char.get("age", "Unknown")
                            details = char.get("details", "No details available.")
                            
                            prompt, genetics = theia_engine.generate_prompt(name, status, appearance)
                            
                            st.markdown(f"### 👤 {name}")
                            st.caption(f"**Age:** {age} | **Role:** {details}")
                            st.caption(f"**Casting Tier:** `{appearance.upper()}` | **Locked Hash:** `{genetics}`")
                            
                            # Streamlit naturally adds a copy button to st.code blocks
                            st.code(prompt, language="markdown")
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                    except Exception as e:
                        st.error("❌ System Processing Error")
                        st.code(f"Error Details: {e}")
            else:
                st.warning("⚠️ Input Buffer Empty. Please paste a script.")

    # --- TAB 2: IMAGE STUDIO ---
    with tab2:
        st.markdown("#### 🖼️ Image Generation & Editing")
        
        model_choice = st.selectbox(
            "Select Generation Engine",
            [
                "OpenAI GPT-Image 1.5 (Standard)", 
                "Stability AI: SDXL (Alternative Style)", 
                "Black Forest Labs: Flux.1 (Highly Photorealistic)"
            ]
        )
        
        manual_prompt = st.text_area("Paste Character Prompt Here", height=150)
        
        if st.button("GENERATE IMAGE"):
            if manual_prompt:
                with st.spinner(f"Rendering image using {model_choice}..."):
                    try:
                        # Safely route the API to the selected model and handle differing input requirements
                        if "GPT-Image 1.5" in model_choice:
                            api_endpoint = "openai/gpt-image-1.5"
                            api_input = {"prompt": manual_prompt, "size": "1024x1024", "quality": "high", "style": "natural"}
                        elif "SDXL" in model_choice:
                            api_endpoint = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
                            api_input = {"prompt": manual_prompt}
                        elif "Flux.1" in model_choice:
                            api_endpoint = "black-forest-labs/flux-schnell"
                            api_input = {"prompt": manual_prompt}
                        else:
                            api_endpoint = "openai/gpt-image-1.5"
                            api_input = {"prompt": manual_prompt}
                        
                        output = replicate.run(api_endpoint, input=api_input)
                        
                        if isinstance(output, list):
                            image_url = str(output[0])
                        else:
                            image_url = str(output)
                            
                        img_response = requests.get(image_url)
                        img_bytes = img_response.content
                        
                        st.session_state["current_rendered_image"] = img_bytes
                        
                        # PERSISTENT UPDATE TO TRACKER
                        st.session_state.billing['credits'] += 0.40
                        st.session_state.billing['images'] += 1
                        save_billing(st.session_state.billing)
                        update_billing_ui()
                        
                    except Exception as e:
                        st.error("❌ Rendering Error")
                        st.code(f"Error Details: {e}")
            else:
                st.warning("⚠️ Please paste a prompt first.")
                
        # --- POST PROCESSING SECTION ---
        if "current_rendered_image" in st.session_state:
            st.markdown("---")
            st.markdown("##### 🎛️ Post-Processing Adjustments")
            
            if "b_manual" not in st.session_state: st.session_state["b_manual"] = 1.0
            if "c_manual" not in st.session_state: st.session_state["c_manual"] = 1.0
            if "s_manual" not in st.session_state: st.session_state["s_manual"] = 1.0
            
            def reset_manual_edits():
                st.session_state["b_manual"] = 1.0
                st.session_state["c_manual"] = 1.0
                st.session_state["s_manual"] = 1.0
                
            col1, col2, col3 = st.columns(3)
            with col1:
                brightness = st.slider("Brightness", 0.5, 1.5, key="b_manual")
            with col2:
                contrast = st.slider("Contrast", 0.5, 1.5, key="c_manual")
            with col3:
                sharpness = st.slider("Sharpness", 0.0, 2.5, key="s_manual")
            
            st.button("↩️ Reset Edits (Undo)", on_click=reset_manual_edits)
            
            base_img = Image.open(BytesIO(st.session_state["current_rendered_image"]))
            base_img = ImageEnhance.Brightness(base_img).enhance(brightness)
            base_img = ImageEnhance.Contrast(base_img).enhance(contrast)
            final_img = ImageEnhance.Sharpness(base_img).enhance(sharpness)
            
            st.image(final_img, use_container_width=True)
            
            buf = BytesIO()
            final_img.save(buf, format="JPEG", quality=95)
            st.download_button(
                label="⬇️ Download Edited Render",
                data=buf.getvalue(),
                file_name="theia_manual_render.jpg",
                mime="image/jpeg",
            )
