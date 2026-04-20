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
        
        current_month = datetime.datetime.now().strftime("%B %Y")
        saved_month = sheet.cell(2, 1).value 
        
        if saved_month == current_month:
            credits_val = sheet.cell(2, 2).value 
            images_val = sheet.cell(2, 3).value  
            return {
                "month": current_month,
                "credits": float(credits_val) if credits_val else 0.0,
                "images": int(images_val) if images_val else 0
            }
        else:
            sheet.update_cell(2, 1, current_month) 
            sheet.update_cell(2, 2, 0.0)           
            sheet.update_cell(2, 3, 0)             
            return {"month": current_month, "credits": 0.0, "images": 0}
            
    except Exception as e:
        return {"month": "System Error", "credits": 0.0, "images": 0}

def save_billing(data):
    try:
        client = get_gspread_client()
        sheet = client.open("Theia Billing").sheet1
        sheet.update_cell(2, 2, data["credits"]) 
        sheet.update_cell(2, 3, data["images"])  
    except:
        pass

# --- STREAMLIT CALLBACK FUNCTION ---
def reset_edits(subject_name):
    st.session_state[f"b_{subject_name}"] = 1.0
    st.session_state[f"c_{subject_name}"] = 1.0
    st.session_state[f"s_{subject_name}"] = 1.0

# --- UPDATED THEIA ENGINE (MASTER COMMAND: REAL AI PERSON) ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

        # TIER 1 & 2: ABOVE STANDARD / ABOVE AVERAGE (Handsome/Beautiful, Glowing Skin)
        self.geo_above_average = [
            "striking, balanced facial proportions with a strong, defined jawline",
            "elegant Northern European features, high cheekbones, radiant complexion",
            "beautiful, delicate natural features with symmetrical facial framing",
            "handsome Mediterranean structure, strong profile, expressive eyes",
            "striking East Asian features, smooth jawline, beautifully defined eyes"
        ]
        self.skin_above_average = [
            "flawless but realistic natural skin, a healthy sun-kissed glow, zero acne, very faint natural pores",
            "soft, highly maintained skin texture, completely clear complexion with a radiant, happy glow",
            "beautiful, smooth human skin catching the natural light beautifully, zero heavy blemishes"
        ]

        # TIER 3 & 4: STANDARD / AVERAGE (Everyday Normal People, Varied Skin)
        self.geo_average = [
            "completely average, everyday facial structure, friendly and approachable",
            "a flat midface with a soft, unassuming jawline and kind eyes",
            "round facial structure with soft cheeks and a broader nose",
            "typical, everyday proportions, slightly asymmetrical but highly natural",
            "a standard, relatable face shape with a comfortable, familiar structure"
        ]
        self.skin_average = [
            "natural human skin with realistic pores, a few faint freckles, completely unedited texture",
            "matte but normal human skin, faint laugh lines around the eyes, natural variations in tone",
            "a textured and authentic complexion, maybe one or two tiny natural blemishes, very realistic",
            "normal, everyday skin with a healthy but unpolished look, catching the sunlight naturally"
        ]

        # TIER 5: BELOW AVERAGE (Flawed, Coarse, Highly Asymmetrical)
        self.geo_below_average = [
            "pronounced supraorbital ridge, heavy facial asymmetry, rugged structure",
            "narrow face with a prominent dorsal hump on the nose, weak chin",
            "coarsened and robust facial features, deeply set, asymmetrical eyes"
        ]
        self.skin_below_average = [
            "sun-damaged and weathered complexion with deep crow's feet and a rugged texture",
            "highly detailed and coarse skin texture, showing visible pores and an uneven, raw complexion"
        ]

        # NEW: MASTER BODY TYPES (Somatotypes & Shapes)
        self.body_types = [
            "an Ectomorph build: lean, thin, and wiry with long limbs",
            "a Mesomorph build: naturally athletic, broad-shouldered, and well-proportioned",
            "an Endomorph build: a stockier, softer, and more solid physical frame",
            "an Hourglass body shape: balanced proportions with a clearly defined waist",
            "a Pear body shape: slightly wider at the hips with a narrower upper body",
            "a Rectangle body shape: a uniform, straight build from shoulders to hips",
            "an Inverted Triangle build: broad shoulders tapering down to a narrow waist",
            "a robust, full-figured, and curvy physique",
            "a very petite, compact, and completely average frame"
        ]

        # NEW: THE "BEST DAY EVER" VIBES & EXPRESSIONS
        self.vibes = [
            "radiating absolute joy and having the best day of their life",
            "giving off a warm, magnetic, and incredibly friendly energy",
            "looking blissfully relaxed, carefree, and at total peace",
            "bursting with vibrant, spontaneous, and positive energy",
            "appearing wildly happy, confident, and full of life"
        ]
        self.expressions = [
            "flashing a massive, genuine, teeth-showing smile directly at the camera",
            "laughing out loud mid-sentence, eyes crinkled with pure joy",
            "showing a bright, beaming, confident smile while looking right at the lens",
            "a relaxed, contented, and deeply happy expression, looking totally at ease",
            "a fun, spontaneous, slightly goofy smile, clearly enjoying the moment"
        ]

        # NEW: DIVERSIFIED LOCATIONS (Leisure, Outdoors, Vacations)
        self.environments = [
            "outdoors on a beautiful sunny day, standing near a sparkling lake",
            "sitting outside at a bustling, sunlit cafe patio with a drink on the table",
            "on a scenic hiking trail surrounded by lush green trees and blue skies",
            "relaxing in a cozy, warmly lit local bar or pub having a great time",
            "on a bright, breezy beach with the ocean visible in the background",
            "in a vibrant, colorful public park during a perfect summer afternoon",
            "inside a bright, modern living room with sunlight pouring through large windows",
            "standing casually on a bustling city street on a beautiful clear day"
        ]

        self.lighting_conditions = [
            "gorgeous golden hour sunlight casting a warm, beautiful glow on their face",
            "bright, clear, natural daylight illuminating them perfectly",
            "soft, flattering overcast light creating incredibly realistic, even skin tones",
            "warm ambient indoor lighting creating a cozy and inviting atmosphere"
        ]

        # NEW: DYNAMIC FRAMINGS & SELFIES (Eye Contact prioritized)
        self.framings = [
            "framed as a casual close-up Selfie, holding the phone with one arm extended, making direct eye contact with the camera",
            "framed as a fun Medium Shot Selfie, looking directly into the lens with a great angle",
            "a Candid Medium Shot taken by a friend sitting across from them, subject is looking happily at the camera",
            "a Cowboy Shot (thigh-up), standing confidently and looking directly at the camera",
            "a Close-Up portrait taken by a friend, focusing deeply on their happy expression and eye contact",
            "a Full Body Shot taken outdoors, showing their entire outfit and posture, looking towards the camera"
        ]

        self.camera_hardware_middle = [
            "a crisp, beautiful smartphone photo from a modern phone, completely unretouched",
            "shot as an unfiltered iPhone snapshot with natural focus and vibrant colors",
            "taken on a high-quality digital camera, capturing everyday documentary realism"
        ]

        self.timeframes = [
            "captured exactly during a perfect, memorable day",
            "a casual, spontaneous memory from a fantastic weekend",
            "an everyday snapshot capturing a beautiful moment in time"
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

    def generate_prompt(self, character_name, socioeconomic_status="standard", appearance_tier="standard"):
        
        # The ultimate Unique Seed: Guarantees a clean slate and unique face per name
        name_seed = int(hashlib.md5((character_name + appearance_tier).encode()).hexdigest(), 16) % 100000

        # Map to the new 5-Tier System
        tier_lower = appearance_tier.lower()
        if tier_lower in ["above standard", "above average"]:
            facial_structure = random.choice(self.geo_above_average)
            skin_complexion = random.choice(self.skin_above_average)
        elif tier_lower in ["standard", "average"]:
            facial_structure = random.choice(self.geo_average)
            skin_complexion = random.choice(self.skin_average)
        elif tier_lower == "below average":
            facial_structure = random.choice(self.geo_below_average)
            skin_complexion = random.choice(self.skin_below_average)
        else:
            facial_structure = random.choice(self.geo_average)
            skin_complexion = random.choice(self.skin_average)

        body_type = random.choice(self.body_types)
        vibe = random.choice(self.vibes)

        genetic_signature = f"{facial_structure} | {body_type} | [Seed:{name_seed}]"
        sig_hash = hashlib.md5(genetic_signature.encode()).hexdigest()
        
        if sig_hash not in self.history:
            self.history.add(sig_hash)
            self._save_history()

        environment = random.choice(self.environments)
        lighting = random.choice(self.lighting_conditions)
        expression = random.choice(self.expressions)
        timeframe = random.choice(self.timeframes)
        framing = random.choice(self.framings)

        # Standardized realistic clothing based on the photos
        camera = random.choice(self.camera_hardware_middle)
        clothing_options = [
            "a comfortable, stylish everyday t-shirt", 
            "a casual, unbranded button-up shirt", 
            "a light outdoor jacket perfect for the weather", 
            "a cozy, well-fitting sweater",
            "casual, neat, everyday weekend wear"
        ]
        wealth_modifier = f"wearing {random.choice(clothing_options)}."
        
        prompt = (
            f"A highly realistic, documentary-style photograph of a totally unique, real human individual named {character_name}. "
            f"This is a specific identity, seed signature: [Seed:{name_seed}]. "
            f"They have {body_type}. They have {facial_structure}. Their face features {skin_complexion}. "
            f"They are {vibe}. "
            f"The image is {framing}, captured by {camera}. "
            f"They are showing a deeply human emotion: {expression}. SETTING: {environment}. "
            f"LIGHTING: {lighting}. {timeframe}, {wealth_modifier}. "
            f"This must look like a flawless, unmodified, completely authentic snapshot of a real person living their best life. Absolutely zero AI artifacts, no plastic 3D skin, no beauty filters, and no studio staging."
        )
        return prompt, genetic_signature

# --- UI SETUP ---
st.set_page_config(page_title="THEIA PRO", page_icon="👁️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stHeaderActionElements"],
    [data-testid="stToolbar"],
    [data-testid="stAppToolbar"] { display: none !important; }

    header { background-color: transparent !important; }
    footer { visibility: hidden !important; }
    
    .stApp { 
        background-color: #0b0c10; 
        background-image: radial-gradient(circle at 15% 50%, rgba(88, 101, 242, 0.05), transparent 25%), 
                          radial-gradient(circle at 85% 30%, rgba(235, 69, 158, 0.05), transparent 25%);
        font-family: 'Inter', sans-serif; color: #e4e6eb;
    }
    [data-testid="stSidebar"] { 
        background: rgba(30, 31, 34, 0.6) !important; backdrop-filter: blur(16px) !important; border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    .custom-title { font-weight: 900; font-size: 4rem; background: linear-gradient(90deg, #5865F2 0%, #EB459E 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1.5px; margin-bottom: 0px; padding-bottom: 0px; }
    .custom-subtitle { font-weight: 300; font-size: 1.1rem; color: #949ba4; margin-top: -5px; margin-bottom: 40px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 20px; letter-spacing: 1px; }
    h3, h4, p, label, .stMarkdown { color: #dbdee1 !important; }
    .stTextArea textarea, .stTextInput input { background: rgba(43, 45, 49, 0.7) !important; backdrop-filter: blur(10px); color: #ffffff !important; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; font-family: 'Inter', sans-serif; padding: 15px; }
    .stTextArea textarea:focus, .stTextInput input:focus { border-color: #5865F2; box-shadow: 0 0 15px rgba(88, 101, 242, 0.3); background: rgba(43, 45, 49, 0.9) !important; }
    .stButton>button, .stDownloadButton>button { background: linear-gradient(135deg, #5865F2 0%, #a23db8 100%) !important; color: white !important; border-radius: 8px !important; font-weight: 700 !important; border: none !important; padding: 12px 28px !important; text-transform: uppercase !important; font-family: 'Inter', sans-serif !important; box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important; }
    .stButton>button:hover, .stDownloadButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 20px rgba(88, 101, 242, 0.5) !important; }
</style>
""", unsafe_allow_html=True)

# --- SECURITY & API CONFIG ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
    API_STATUS = True
except:
    API_STATUS = False

# UPDATED: EXTRACTION PROMPT NOW USES THE 5-TIER SYSTEM
EXTRACTION_PROMPT = """
You are an expert script analyst. Read the following true crime/documentary script and extract all the significant, named characters.
Do NOT extract background roles.
For each character, determine:
1. socioeconomic_status ("wealthy", "standard", "struggling")
2. appearance_tier (Choose EXACTLY ONE from this list: "below average", "average", "standard", "above average", "above standard")
3. age (estimate if not explicitly stated)
4. details (a short 1-sentence summary of who they are in the story)

You MUST return ONLY a raw JSON array of objects. Do not wrap it in markdown block quotes. Just the raw text.
Format example:
[
    {"name": "John Doe", "age": "45", "details": "The lead detective.", "socioeconomic_status": "standard", "appearance_tier": "above average"}
]
SCRIPT TO ANALYZE:
"""

st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v7.0 Modular Studio</div>', unsafe_allow_html=True)

password_input = st.sidebar.text_input("🔒 Security Portal", type="password", placeholder="Enter Passcode...")

if password_input == ACCESS_PASSWORD:
    st.sidebar.success("🟢 SYSTEM ONLINE")
    st.sidebar.markdown("---")
    
    if 'billing' not in st.session_state:
        st.session_state.billing = load_billing()
        
    billing_display = st.sidebar.empty()
    
    def update_billing_ui():
        month_name = datetime.datetime.now().strftime("%B %Y")
        billing_display.markdown(f"""
            <div style='background: rgba(43,45,49,0.5); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px;'>
                <p style='color: #949ba4; margin: 0; font-size: 0.8rem;'>{month_name} USAGE</p>
                <h2 style='color: #43b581; margin: 5px 0 5px 0;'>💳 Credit ${st.session_state.billing['credits']:.2f}</h2>
                <p style='color: #dbdee1; margin: 0; font-size: 0.9rem;'>🖼️ {st.session_state.billing['images']} Images Generated</p>
            </div>
        """, unsafe_allow_html=True)
        
    update_billing_ui()
    st.sidebar.markdown("---")
    
    if API_STATUS:
        st.sidebar.info("🧠 Brain: Gemini Pro (Latest)")
        st.sidebar.info("🎨 Engine: Modular RPX")
        st.sidebar.info("🏢 Auth: Lucalles Productions")

    tab1, tab2, tab3 = st.tabs(["📝 Prompt Studio", "🎨 Image Studio", "📁 Style Bank"])

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
                            status = char.get("socioeconomic_status", "standard")
                            appearance = char.get("appearance_tier", "standard")
                            age = char.get("age", "Unknown")
                            details = char.get("details", "No details available.")
                            
                            prompt, genetics = theia_engine.generate_prompt(name, status, appearance)
                            
                            st.markdown(f"### 👤 {name}")
                            st.caption(f"**Age:** {age} | **Role:** {details}")
                            st.caption(f"**Casting Tier:** `{appearance.upper()}` | **Locked Hash:** `{genetics}`")
                            
                            st.code(prompt, language="markdown")
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                    except Exception as e:
                        st.error("❌ System Processing Error")
                        st.code(f"Error Details: {e}")
            else:
                st.warning("⚠️ Input Buffer Empty. Please paste a script.")

    with tab2:
        st.markdown("#### 🖼️ Image Generation & Editing")
        
        model_choice = st.selectbox(
            "Select Generation Engine",
            [
                "Google: Nano Banana 2 (Latest)",
                "OpenAI GPT-Image 1.5 (Standard)", 
                "Black Forest Labs: Flux.1 (Highly Photorealistic)",
                "Stability AI: SDXL (Alternative Style)"
            ]
        )
        
        manual_prompt = st.text_area("Paste Character Prompt Here", height=150)
        
        if st.button("GENERATE IMAGE"):
            if manual_prompt:
                with st.spinner(f"Rendering image using {model_choice}..."):
                    try:
                        if "Nano Banana" in model_choice:
                            api_endpoint = "google/nano-banana-2" 
                            api_input = {"prompt": manual_prompt} 
                        elif "GPT-Image 1.5" in model_choice:
                            api_endpoint = "openai/gpt-image-1.5"
                            api_input = {"prompt": manual_prompt, "size": "1024x1024", "quality": "high", "style": "natural"}
                        elif "Flux.1" in model_choice:
                            api_endpoint = "black-forest-labs/flux-schnell"
                            api_input = {"prompt": manual_prompt}
                        elif "SDXL" in model_choice:
                            api_endpoint = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
                            api_input = {"prompt": manual_prompt}
                        
                        output = replicate.run(api_endpoint, input=api_input)
                        
                        if isinstance(output, list):
                            image_url = str(output[0])
                        else:
                            image_url = str(output)
                            
                        img_response = requests.get(image_url)
                        img_bytes = img_response.content
                        
                        st.session_state["current_rendered_image"] = img_bytes
                        
                        st.session_state.billing['credits'] += 0.40
                        st.session_state.billing['images'] += 1
                        save_billing(st.session_state.billing)
                        update_billing_ui()
                        
                    except Exception as e:
                        st.error("❌ Rendering Error")
                        st.code(f"Error Details: {e}")
            else:
                st.warning("⚠️ Please paste a prompt first.")
                
        if "current_rendered_image" in st.session_state:
            st.markdown("---")
            st.markdown("##### 🎛️ Post-Processing & Cropping")
            
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
            
            st.button("↩️ Reset Sliders", on_click=reset_manual_edits)
            
            base_img = Image.open(BytesIO(st.session_state["current_rendered_image"]))
            enhanced_img = ImageEnhance.Brightness(base_img).enhance(brightness)
            enhanced_img = ImageEnhance.Contrast(enhanced_img).enhance(contrast)
            enhanced_img = ImageEnhance.Sharpness(enhanced_img).enhance(sharpness)
            
            st.markdown("---")
            
            try:
                from streamlit_cropper import st_cropper
                enable_crop = st.checkbox("✂️ Enable Cropping Tool")
                if enable_crop:
                    st.caption("Drag the corners of the blue box to crop. The final image will be updated below.")
                    final_img = st_cropper(enhanced_img, realtime_update=True, box_color='#5865F2', aspect_ratio=None)
                else:
                    final_img = enhanced_img
                    st.image(final_img, use_container_width=True)
            except ImportError:
                final_img = enhanced_img
                st.image(final_img, use_container_width=True)
                st.warning("Cropper module not found. Add 'streamlit-cropper' to requirements.txt to enable cropping.")

            buf = BytesIO()
            final_img.save(buf, format="JPEG", quality=95)
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="⬇️ Download Final Render",
                data=buf.getvalue(),
                file_name="theia_studio_render.jpg",
                mime="image/jpeg",
)

    # --- TAB 3: STYLE BANK ---
    with tab3:
        st.markdown("#### 📁 Cloud Style Bank (Google Drive)")
        drive_folder_id = st.secrets.get("gcp_service_account", {}).get("drive_folder_id")
        
        if not drive_folder_id:
            st.error("⚠️ Setup Required: Please add `drive_folder_id = \"YOUR_FOLDER_ID\"` to your Streamlit secrets to enable the Cloud Style Bank.")
        else:
            st.info("Upload reference photos here. The AI will 'look' at these images to extract the exact lighting and aesthetic for your prompts.")
            uploaded_file = st.file_uploader("Upload Reference Image", type=["jpg", "jpeg", "png"])
            
            if st.button("UPLOAD TO DRIVE"):
                if uploaded_file:
                    with st.spinner("Securely uploading to your Google Drive..."):
                        try:
                            upload_to_drive(uploaded_file.getvalue(), uploaded_file.name, drive_folder_id)
                            st.success("✅ Image securely added to the Style Bank!")
                        except Exception as e:
                            st.error(f"❌ Upload failed: {e}")
                else:
                    st.warning("Please select a file first.")
                    
            st.markdown("##### Current Cloud Gallery")
            if st.button("Load Existing Styles"):
                with st.spinner("Fetching gallery from Google Drive..."):
                    images = get_drive_images(drive_folder_id)
                    if images:
                        cols = st.columns(3)
                        for i, img in enumerate(images):
                            with cols[i % 3]:
                                if 'thumbnailLink' in img:
                                    st.image(img['thumbnailLink'], caption=img['name'], use_container_width=True)
                    else:
                        st.info("Your Style Bank is currently empty.")
