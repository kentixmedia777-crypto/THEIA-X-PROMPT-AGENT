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

        wealth_modifier = "wearing worn, slightly faded everyday clothing." if socioeconomic_status.lower() in ["poor", "struggling"]
