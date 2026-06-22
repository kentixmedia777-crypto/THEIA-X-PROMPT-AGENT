import streamlit as st
import google.generativeai as genai
import json
import random
import hashlib
import os
import requests
import datetime
import gspread
import base64
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
ACCESS_PASSWORD = "LUCALLES-PRODUCTION-2026"
HISTORY_FILE = "theia_genetic_history.json"

# --- GCP & GOOGLE SHEETS AUTHENTICATION ---
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

# --- STYLE BANK LOGIC (ImgBB + Google Sheets) ---
def upload_to_imgbb(file_bytes, api_key):
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": base64.b64encode(file_bytes).decode("utf-8")
    }
    res = requests.post(url, data=payload)
    res_data = res.json()
    if res_data.get("success"):
        return res_data["data"]["url"]
    else:
        raise Exception(res_data.get("error", {}).get("message", "Unknown ImgBB Error"))

def save_style_url_to_sheet(image_url):
    client = get_gspread_client()
    sheet = client.open("Theia Billing").worksheet("Style Bank")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([image_url, timestamp])

def get_style_urls_from_sheet():
    try:
        client = get_gspread_client()
        sheet = client.open("Theia Billing").worksheet("Style Bank")
        urls = sheet.col_values(1) # Gets everything in Column A
        return [url for url in urls if url.startswith("http")]
    except:
        return []

# --- THEIA ENGINE ---
class TheiaPromptGenerator:
    def __init__(self):
        self.history = self._load_history()

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

        self.geo_average = [
            "completely average, everyday facial structure, friendly and approachable",
            "a flat midface with a soft, unassuming jawline and kind eyes",
            "round facial structure with soft cheeks and a broader nose",
            "typical, everyday proportions, slightly asymmetrical but highly natural",
            "a standard, relatable face shape with a comfortable, familiar structure"
        ]
        self.skin_average = [
            "completely normal skin, casual phone lighting, no hyper-details",
            "average everyday complexion, standard resolution, unedited",
            "normal skin, flat lighting, looks like a basic digital photo",
            "standard human skin, no beauty filters, plain lighting"
        ]

        self.geo_below_average = [
            "pronounced supraorbital ridge, heavy facial asymmetry, rugged structure",
            "narrow face with a prominent dorsal hump on the nose, weak chin",
            "coarsened and robust facial features, deeply set, asymmetrical eyes"
        ]
        self.skin_below_average = [
            "unedited normal skin, maybe a slight blemish, low-res phone quality",
            "average unpolished complexion, basic lighting, completely normal",
            "everyday skin, no studio lighting, authentic amateur photo look"
        ]

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

        self.environments = [
            "outdoors on a beautiful sunny day, standing near a public park fountain",
            "sitting casually inside a brightly lit local grocery store aisle",
            "riding as a passenger inside a public city bus during the day",
            "standing on a normal, bustling downtown city street on a clear afternoon",
            "outdoors in a dense, beautiful Pacific Northwest forest in the USA",
            "outdoors on a vast, sunlit grassy savanna in Africa",
            "on a bright, sunny public beach right by the ocean shoreline",
            "sitting casually at the corner edge of a clear blue swimming pool",
            "relaxing indoors, sitting comfortably on an unmade bed in a messy bedroom",
            "sitting outside at a bustling, casual cafe patio with a drink on the table",
            "inside a standard, everyday living room with natural daylight from a window"
        ]

        self.lighting_conditions = [
            "clear, even natural ambient light, neutral-cool white balance, completely un-staged",
            "flat overcast daylight, cool digital white balance, absolute zero warm golden tones",
            "standard everyday indoor ceiling light, neutral color cast, balanced normal exposure",
            "clean midday daylight, realistic unedited light distribution, zero artificial tint"
        ]

        self.framings = [
            "a casual group photo taken with friends, subject is smiling alongside them",
            "a candid snapshot taken by a family member from a slightly low angle",
            "a quick, slightly off-center snapshot taken across the room",
            "a wide-angle shot showing the subject interacting with their environment, looking away from the camera",
            "framed as an everyday group selfie with a friend's arm holding the camera",
            "a Candid Medium Shot taken by a companion across a table, casual posture",
            "a normal, everyday photo taken from a high angle, looking down slightly",
            "a random camera-roll snapshot where the subject isn't perfectly centered"
        ]

        # PURGED IPHONES: Locked to 2018 Budget Android & Sub-1 Megapixel sensors
        self.camera_hardware_middle = [
            "captured on a budget 2018 Android smartphone, sub-1 megapixel front camera quality, slightly soft digital capture, zero artificial sharpening",
            "authentic 2018 mid-specs mobile snapshot, cheap digital sensor capture, completely un-calibrated flat colors, blown-out highlights, deep infinite focus",
            "middle-low quality Android phone camera, 0.5MP digital capture look, visible mobile sensor grain, unretouched, zero cinematic background blur",
            "throwaway budget smartphone picture, standard fixed mobile lens, slightly muddy midtones, completely flat digital capture without modern computational processing"
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

    def generate_prompt(self, character_name, socioeconomic_status="standard", appearance_tier="standard", style_dna=None, gender="person", race="diverse", hair="average hair", eyes="average eyes", clothing="casual clothes"):
        
        name_seed = int(hashlib.md5((character_name + appearance_tier + gender + race).encode()).hexdigest(), 16) % 100000

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

        expression = random.choice(self.expressions)
        framing = random.choice(self.framings)
        camera = random.choice(self.camera_hardware_middle)
        
        if style_dna:
            visual_aesthetic = f"STYLE & LIGHTING MATCH: {style_dna}"
            background_details = "The background features highly authentic everyday office or domestic items matching this specific setting."
            if any(word in style_dna.lower() for word in ["office", "indoor", "room", "desk", "inside", "house", "apartment"]):
                clothing = "casual, normal everyday indoor attire"
            color_override = "adhering to the natural lighting color of the setting"
        else:
            available_envs = [env for env in self.environments if not hasattr(self, 'last_env') or env != self.last_env]
            environment = random.choice(available_envs)
            self.last_env = environment
            
            lighting = random.choice(self.lighting_conditions)
            timeframe = random.choice(self.timeframes)
            visual_aesthetic = f"SETTING: {environment}. LIGHTING: {lighting}. {timeframe}."
            background_details = "The background features highly authentic, everyday lived-in details."
            color_override = "with a realistic, flat sRGB mobile color palette"

            env_lower = environment.lower()
            if "beach" in env_lower:
                clothing = "a stylish two-piece bikini swimwear" if gender in ["woman", "girl"] else "boardshorts and a casual short-sleeve rash guard"
            elif "pool" in env_lower:
                clothing = "casual poolside swimwear"
            elif "bed" in env_lower or "bedroom" in env_lower:
                clothing = "comfortable, ultra-casual sleepwear or comfortable loungewear"
            elif "forest" in env_lower or "hiking" in env_lower:
                clothing = "practical outdoor hiking clothes and a light jacket"
            elif "bus" in env_lower or "grocery" in env_lower or "street" in env_lower:
                clothing = "completely normal, everyday casual streetwear"

        # ULTIMATE PROMPT (v10.5): Banned iPhones, cinematic filters, green tints, and high resolution
        prompt = (
            f"A throwaway, low-quality smartphone photograph of an everyday {race} {gender} named {character_name}. "
            f"This is a specific identity, seed signature: [Seed:{name_seed}]. "
            f"PHYSICAL TRAITS: They have {hair} and {eyes}. This {gender} has {body_type}. "
            f"FACIAL GEOMETRY: {facial_structure}. SKIN TEXTURE: {skin_complexion}. "
            f"They are {vibe}. "
            f"The composition is {framing}, {camera}. "
            f"{visual_aesthetic} {background_details} "
            f"They are showing a candid emotion: {expression}. ATTIRE: strictly wearing {clothing}. "
            f"This must look exactly like an authentic, mid-low quality 2018 Android photo gallery snapshot {color_override}. "
            f"Absolutely zero AI artifacts, NO iPhone camera quality, NO cinematic filters, NO green color tint, NO movie color grading, NO bokeh, NO blurred background, NO hyper-sharp skin pores, NO individual hair strands visible, NO hyper-vibrant saturation, NO modern computational rendering, and NO beauty filters."
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
    API_STATUS = True
except:
    API_STATUS = False

EXTRACTION_PROMPT = """
You are an expert script analyst and casting director.
Read the following true crime/documentary script and extract all significant characters.

For each character, determine:
1. socioeconomic_status ("wealthy", "standard", "struggling")
2. appearance_tier ("below average", "average", "standard", "above average")
3. age (estimate if not explicitly stated)
4. gender ("man", "woman", "boy", "girl", or "non-binary")
5. race_ethnicity (e.g., "Caucasian", "African American", "East Asian", "Hispanic", etc.)
6. hair (e.g., "short blonde buzzcut", "long curly black hair", "bald")
7. eyes (e.g., "piercing blue eyes", "warm brown eyes")
8. clothing (e.g., "faded mechanic uniform", "expensive tailored suit", "casual oversized hoodie")
9. details (a short 1-sentence summary of who they are in the story)

You MUST return ONLY a raw JSON object. Do not wrap it in markdown block quotes. Just the raw text.
Format example:
{
    "characters": [
        {
            "name": "John Doe", 
            "age": "45", 
            "gender": "man", 
            "race_ethnicity": "African American",
            "hair": "short graying hair",
            "eyes": "dark brown eyes",
            "clothing": "worn-out denim jacket",
            "details": "The lead detective on the case.", 
            "socioeconomic_status": "standard", 
            "appearance_tier": "above average"
        }
    ]
}
SCRIPT TO ANALYZE:
"""

VISION_DNA_PROMPT = """
Analyze the attached reference image. You will perform a 'Semantic Camera & Pose Theft'. Do NOT describe the specific identity or features of the subject in the photo. Instead, reverse-engineer the physical photography data and the exact bodily posture.

Return a single, highly technical paragraph made of exactly 5 strict sentences matching these criteria:
Sentence 1: Camera height, angle, and framing distance.
Sentence 2: The exact type, color temperature, and harshness of the primary light source.
Sentence 3: The post-processing light curve, exposure offset, and color saturation/tint.
Sentence 4: The depth of field, background focus sharpness, and sensor megapixel quality.
Sentence 5: The physical body pose, shoulder posture, arm placement, and head tilt of the primary subject.
"""

st.markdown('<div class="custom-title">THEIA</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-subtitle">Advanced Photographic Intelligence | v8.5 Cloud Studio</div>', unsafe_allow_html=True)

password_input = st.sidebar.text_input("🔒 Security Portal", type="password", placeholder="Enter Passcode...")

if password_input == ACCESS_PASSWORD:
    st.sidebar.success("🟢 SYSTEM ONLINE")
    st.sidebar.markdown("---")
    
    if API_STATUS:
        st.sidebar.info("🧠 Brain: Gemini Flash 3.5")
        st.sidebar.info("🎨 Engine: Python")
        st.sidebar.info("☁️ Memory: ImgBB Cloud Sync")
        st.sidebar.info("🏢 Auth: Lucalles Productions")

    tab1, tab2 = st.tabs(["📝 Prompt Studio", "📁 Style Bank"])

    with tab1:
        st.markdown("#### 🎬 Script Ingestion")
        user_script = st.text_area("Input Stream", height=150, placeholder="Paste your documentary/narrative script here...", label_visibility="collapsed")
        
        # FULLY DECOUPLED LOOP ENGINE
        if st.button("EXTRACT & BUILD PROMPTS"):
            if user_script:
                with st.spinner("Analyzing script text and mapping characters..."):
                    try:
                        style_urls = get_style_urls_from_sheet()
                        model = genai.GenerativeModel("gemini-3.5-flash")
                        
                        response = model.generate_content([EXTRACTION_PROMPT + user_script])
                        raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
                        parsed_data = json.loads(raw_json)
                        character_data = parsed_data.get("characters", [])
                        
                        theia_engine = TheiaPromptGenerator()
                        st.success(f"✅ Extraction Complete: Found {len(character_data)} Subjects")
                        st.markdown("---")
                        
                        for char in character_data:
                            name = char.get("name", "Unknown Subject")
                            status = char.get("socioeconomic_status", "standard")
                            appearance = char.get("appearance_tier", "standard")
                            age = char.get("age", "Unknown")
                            gender = char.get("gender", "person") 
                            race = char.get("race_ethnicity", "mixed race")
                            hair = char.get("hair", "average hair")
                            eyes = char.get("eyes", "average eyes")
                            clothing = char.get("clothing", "casual everyday clothes")
                            details = char.get("details", "No details available.")
                            
                            char_style_dna = ""
                            if style_urls:
                                try:
                                    random_img_url = random.choice(style_urls)
                                    char_image_bytes = requests.get(random_img_url).content
                                    
                                    vision_payload = [
                                        VISION_DNA_PROMPT,
                                        {"mime_type": "image/jpeg", "data": char_image_bytes}
                                    ]
                                    vision_response = model.generate_content(vision_payload)
                                    char_style_dna = vision_response.text.strip()
                                except:
                                    char_style_dna = ""

                            prompt, genetics = theia_engine.generate_prompt(
                                name, status, appearance, char_style_dna, gender, race, hair, eyes, clothing
                            )
                            
                            st.markdown(f"### 👤 {name}")
                            st.caption(f"**Age:** {age} | **Gender:** {gender.title()} | **Race:** {race.title()}")
                            st.caption(f"**Hair:** {hair.title()} | **Eyes:** {eyes.title()}")
                            st.caption(f"**Attire:** {clothing.title()} | **Role:** {details}")
                            if char_style_dna:
                                st.info(f"📷 **Isolated Vision DNA Clone for {name}:** *{char_style_dna}*")
                            st.caption(f"**Casting Tier:** `{appearance.upper()}` | **Locked Hash:** `{genetics}`")
                            
                            st.code(prompt, language="markdown")
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                    except Exception as e:
                        st.error("❌ System Processing Error")
                        st.code(f"Error Details: {e}")
            else:
                st.warning("⚠️ Input Buffer Empty. Please paste a script.")

    with tab2:
        st.markdown("#### 📁 Cloud Style Bank (ImgBB Sync)")
        imgbb_api_key = st.secrets.get("imgbb_api_key")
        
        if not imgbb_api_key:
            st.error("⚠️ Setup Required: Please add `imgbb_api_key = \"YOUR_API_KEY\"` to your Streamlit secrets to enable the Cloud Style Bank.")
        else:
            st.info("Upload reference photos here. The AI will 'look' at these images to extract the exact lighting and aesthetic for your prompts.")
            uploaded_file = st.file_uploader("Upload Reference Image", type=["jpg", "jpeg", "png"])
            
            if st.button("UPLOAD TO STYLE BANK"):
                if uploaded_file:
                    with st.spinner("Securely uploading to Cloud Database..."):
                        try:
                            # 1. Upload to ImgBB
                            img_url = upload_to_imgbb(uploaded_file.getvalue(), imgbb_api_key)
                            # 2. Save URL to Google Sheets
                            save_style_url_to_sheet(img_url)
                            st.success("✅ Image securely added to the Style Bank!")
                        except Exception as e:
                            st.error(f"❌ Upload failed: {e}")
                else:
                    st.warning("Please select a file first.")
                    
            st.markdown("##### Current Cloud Gallery")
            if st.button("Load Existing Styles"):
                with st.spinner("Fetching gallery from Database..."):
                    urls = get_style_urls_from_sheet()
                    if urls:
                        cols = st.columns(3)
                        for i, url in enumerate(urls):
                            with cols[i % 3]:
                                st.image(url, use_container_width=True)
                    else:
                        st.info("Your Style Bank is currently empty.")
