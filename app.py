import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components
import requests
from PIL import Image
import base64
import io
from rapidfuzz import process, fuzz
from openai import OpenAI

CURATED_ALTERNATIVES = {
    "Shampoo": [
        "Ethique Shampoo Bar",
        "Earth Rhythm Shampoo Bar",
        "Bare Anatomy Concentrated Shampoo"
    ],
    "Cream": [
        "Minimalist Marula Oil Moisturizer",
        "Earth Rhythm Phyto Clear Moisturizer",
        "Plum Green Tea Moisturizer"
    ],
    "Sunscreen": [
        "Raw Beauty Wellness Sunscreen Stick",
        "Minimalist SPF 50 (50g)",
        "Dot & Key Sunscreen Stick"
    ],
    "Body Wash": [
        "Ethique Solid Body Wash Bar",
        "Earth Rhythm Body Wash Bar",
        "Plum BodyLovin Body Wash Bar"
    ],
    "Food": [
        "Dark chocolate (higher cocoa %, less packaging)",
        "Baked snacks instead of fried",
        "Local brand snacks with paper packaging"
    ],
    "Drink": [
        "Returnable glass bottle drinks",
        "Powder concentrates",
        "Water in aluminum cans"
    ]
}


# -----------------------------
# OPENAI SETUP (GLOBAL)
# -----------------------------
OpenAIKey = st.secrets["OpenAIKey"]
client = OpenAI(api_key=OpenAIKey)

def get_greener_alternatives(current_product_name, summary_df, max_alternatives=5):

    current = summary_df[summary_df["name"] == current_product_name]

    if current.empty:
        return []

    row = current.iloc[0]
    category = row["category"]
    brand = row["brand"]
    current_score = row["eco_score"]

    # ---------- DATA-DRIVEN ----------
    better = summary_df[
        (summary_df["category"] == category) &
        (summary_df["eco_score"] > current_score) &
        (summary_df["name"] != current_product_name)
    ].sort_values("eco_score", ascending=False)

    results = []

    for _, alt in better.head(max_alternatives).iterrows():
        diff = alt["eco_score"] - current_score
        results.append({
            "name": alt["name"],
            "eco_score": alt["eco_score"],
            "improvement": f"{diff:.0f} points better eco score",
            "score_diff": diff
        })

    return results





def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def ocr_image(image):
    img_b64 = image_to_base64(image)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Extract ALL visible text from this product packaging."
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{img_b64}"
                }
            ]
        }]
    )

    return response.output_text

def extract_product_name(all_text):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"""
        From the following packaging text, extract the MOST LIKELY product name.
        Respond ONLY with the product name.

        TEXT:
        {all_text}
        """
    )

    return response.output_text.strip()

def fuzzy_match_product(name, summary_df):
    match, score, _ = process.extractOne(
        name,
        summary_df['name'].tolist(),
        scorer=fuzz.token_sort_ratio
    )
    return match, score
st.set_page_config(page_title="EcoLens", page_icon="🌱", layout="wide")
st.markdown("""
<style>
.block-container { padding-top: 1rem !important; }

/* Sticky header box */
.sticky-header {
  position: sticky;
  top: 0;
  z-index: 999;
  background: linear-gradient(180deg, #1a1f1a 0%, #0e1117 100%);
  padding: 0.5rem 0 0.75rem 0;
  border-bottom: 2px solid #2d5016;
  box-shadow: 0 4px 12px rgba(45, 80, 22, 0.15);
}

/* Button styling */
.stButton > button {
  background: linear-gradient(135deg, #2d5016 0%, #3d6b1f 100%) !important;
  color: #f5f1e8 !important;
  border: none !important;
  border-radius: 12px !important;
  font-weight: 500 !important;
  transition: all 0.3s ease !important;
}

.stButton > button:hover {
  background: linear-gradient(135deg, #3d6b1f 0%, #4d7b2f 100%) !important;
  box-shadow: 0 4px 12px rgba(45, 80, 22, 0.3) !important;
  transform: translateY(-2px) !important;
}

/* Success messages */
.success {
  background: linear-gradient(135deg, #e8f5e9 0%, #f5f1e8 100%) !important;
  border-left: 4px solid #2d5016 !important;
  color: #1a3d0f !important;
}

/* Info messages */
.info {
  background: linear-gradient(135deg, #f5f1e8 0%, #faf8f3 100%) !important;
  border-left: 4px solid #7c9070 !important;
  color: #3d4a35 !important;
}

/* Warning messages */
.warning {
  background: linear-gradient(135deg, #fff4e6 0%, #f5f1e8 100%) !important;
  border-left: 4px solid #d4a373 !important;
  color: #6b4423 !important;
}
</style>
""", unsafe_allow_html=True)




# -----------------------------
# Step 0: Define file paths
# -----------------------------
PRODUCT_CSV = "product.csv"
MATERIAL_CSV = "material.csv"

# -----------------------------
# Step 0: Define file paths
# -----------------------------
PRODUCT_CSV = "product.csv"
MATERIAL_CSV = "material.csv"

# -----------------------------
# Step 1: Read CSV files
# -----------------------------
products_df = pd.read_csv(PRODUCT_CSV)
materials_df = pd.read_csv(MATERIAL_CSV)

# -----------------------------
# FLAGS (BEAUTY + FOOD)
# -----------------------------
ALL_FLAGS = [
    "microplastics",
    "petroleum",
    "silicones",
    "recyclable_packaging",
    "eco_certified",
    "ultra_processed",
    "high_sugar",
    "palm_oil",
    "animal_based"
]

for c in ALL_FLAGS:
    if c not in products_df.columns:
        products_df[c] = 0

products_df[ALL_FLAGS] = products_df[ALL_FLAGS].fillna(0).astype(int)

# =============================
# MATERIAL IMPACT DICTIONARY
# =============================
material_impact_dict = {}
for _, row in materials_df.iterrows():
    material_impact_dict[row['material']] = {
        'carbon': row['carbon_kg_per_kg'],
        'water': row['water_L_per_kg'],
        'energy': row['energy_MJ_per_kg'],
        'waste': row['waste_score']
    }

# =============================
# INITIALIZE RESULTS
# =============================
products_df["total_carbon_kg"] = 0.0
products_df["total_water_L"] = 0.0
products_df["total_energy_MJ"] = 0.0
products_df["total_waste_score"] = 0.0

# =============================
# PACKAGING IMPACT
# =============================
for i, p in products_df.iterrows():
    carbon = water = energy = 0
    waste_vals = []

    for j in range(1, 4):
        mat = p.get(f"material_{j}")
        wt = p.get(f"weight_{j}_g")

        if pd.isna(mat) or pd.isna(wt):
            continue

        imp = material_impact_dict.get(mat)
        if not imp:
            continue

        kg = wt / 1000
        carbon += kg * imp["carbon"]
        water += kg * imp["water"]
        energy += kg * imp["energy"]
        waste_vals.append(imp["waste"])

    products_df.at[i,"total_carbon_kg"] = carbon
    products_df.at[i,"total_water_L"] = water
    products_df.at[i,"total_energy_MJ"] = energy
    products_df.at[i,"total_waste_score"] = np.mean(waste_vals) if waste_vals else 0

# =============================
# NORMALIZATION CAPS
# =============================
products_df["carbon_norm"] = (products_df["total_carbon_kg"] / 0.5).clip(0,1)
products_df["water_norm"]  = (products_df["total_water_L"] / 10).clip(0,1)
products_df["energy_norm"] = (products_df["total_energy_MJ"] / 20).clip(0,1)
products_df["waste_norm"]  = (products_df["total_waste_score"] / 5).clip(0,1)

# =============================
# PACKAGING SCORE (0-100)
# =============================
products_df["packaging_score"] = (
    (1-products_df["carbon_norm"])*0.35 +
    (1-products_df["water_norm"])*0.25 +
    (1-products_df["energy_norm"])*0.25 +
    (1-products_df["waste_norm"])*0.15
)*100

products_df["packaging_score"] = products_df["packaging_score"].round(1)

# =============================
# INGREDIENT SCORE (CATEGORY AWARE)
# =============================

def ingredient_score(row):
    cat = row["category"].lower()

    # Beauty
    if cat in ["cream","shampoo","body wash","sunscreen"]:
        score = 100 - (
            40*row["microplastics"] +
            35*row["petroleum"] +
            25*row["silicones"]
        )

    # Food & Drinks
    else:
        score = 100 - (
            35*row["ultra_processed"] +
            25*row["high_sugar"] +
            20*row["palm_oil"] +
            20*row["animal_based"]
        )

    return max(0, min(100, score))

products_df["ingredient_score"] = products_df.apply(ingredient_score, axis=1)

# =============================
# BONUS SCORE
# =============================
products_df["bonus_score"] = 60 + (
    20*products_df["recyclable_packaging"] +
    20*products_df["eco_certified"]
)

products_df["bonus_score"] = products_df["bonus_score"].clip(0,100)

# =============================
# FINAL ECOSCORE
# =============================
products_df["eco_score"] = (
    0.50*products_df["packaging_score"] +
    0.40*products_df["ingredient_score"] +
    0.10*products_df["bonus_score"]
).round(1)

# =============================
# FINAL SUMMARY
# =============================
summary_df = products_df[[
    "name",
    "brand",
    "category",
    "total_carbon_kg",
    "total_water_L",
    "total_energy_MJ",
    "total_waste_score",
    "packaging_score",
    "ingredient_score",
    "bonus_score",
    "eco_score",
    *ALL_FLAGS
]].copy()



# -------------------------
# Navigation state
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "Home"

def go(page_name: str):
    st.session_state.page = page_name

# -------------------------
# Sticky header (always visible)
# -------------------------
st.markdown('<div class="sticky-header">', unsafe_allow_html=True)

st.markdown(
    """
    <h1 style="text-align:center; font-size:72px; margin:0; color:#9cb380; text-shadow: 2px 2px 4px rgba(45, 80, 22, 0.3);">
        🌱 EcoLens
    </h1>
    <p style="text-align:center; font-size:18px; color:#c5d4b8; margin-top:6px; margin-bottom:14px;">
        Make smarter, sustainable buying decisions
    </p>
    """,
    unsafe_allow_html=True
)

c1, c2, c3, c4 = st.columns([1,1,1,1])
with c1:
    st.button("🌿 GreenScore", use_container_width=True, on_click=go, args=("GreenScore",))
with c2:
    st.button("🤖 AI Chatbot", use_container_width=True, on_click=go, args=("Chatbot",))
with c3:
    st.button("🌏Impact Dashboard", use_container_width=True, on_click=go, args=("Impact Dashboard",))
with c4:
    st.button("🧭 Your Next Steps", use_container_width=True, on_click=go, args=("NextSteps",))


st.markdown("</div>", unsafe_allow_html=True)
st.write("")  # spacer

# -------------------------
# HOME
# -------------------------
if st.session_state.page == "Home":

    left, right = st.columns([1.2, 1.8], gap="large")

    with left:
        st.markdown("""
            <div style="height:420px; overflow:hidden; border-radius:16px; box-shadow: 0 8px 24px rgba(45, 80, 22, 0.2);">
                <img src="https://images.openai.com/static-rsc-3/L_9-L2VXhvFW5NZZvI6VLjA1QxHDiDeV5vyXsgKqM2ycJVtMFds_HEsJfhXYdziNs9fdDa4f0k4koZsaN3gehTxDddohscLt0wYAfwvMxRE?purpose=fullsize"
                     style="width:100%; height:100%; object-fit:cover;">
            </div>
        """, unsafe_allow_html=True)
    
    with right:
        st.markdown(
            """<div style="height:420px; display:flex; flex-direction:column; justify-content:center;">
    <h2 style="font-size:35px; margin-bottom:18px; color:#9cb380;">What is EcoLens?</h2>
    <p style="font-size:20px; line-height:1.7; max-width:600px; color:#c5d4b8;">
    EcoLens helps people understand the real environmental impact of the products they buy, so they can make more informed and sustainable choices.
    </p>
    </div>""",
            unsafe_allow_html=True
        )

    st.header("The Hidden Cost of Everyday Products", anchor=False)
    st.write("Every year, the world produces over 400 million tonnes of plastic waste, and nearly half of this comes from single-use packaging like bottles, bags, wrappers, and cartons. Only around 9% of all plastic ever produced has been recycled, while the rest ends up in landfills, incinerators, or in the environment.")
    st.write("Packaging alone can account for 20–40% of a product's total environmental footprint, yet this hidden cost is rarely visible when we shop. Most of the time, consumers only see branding and marketing claims, not the true environmental impact behind a product.")

    st.header("The Problem", anchor=False)
    st.write("Sustainability labels are vague and poorly regulated, so consumers often rely on marketing language instead of real data. Many of these claims are misleading, allowing greenwashing to go unnoticed. Because people lack the time and expertise to properly assess environmental impact, they make well-intentioned but poor choices. Additionally, there is no standardized way to verify eco-claims, and most existing apps reduce sustainability to simple green or red labels, hiding the real environmental costs of everyday products.")

    st.header("Small Choices, Big Impact", anchor=False)
    st.write("A single purchase may feel insignificant, but when millions of people repeat small decisions every day, the impact becomes massive. If just 1 million people replaced one single-use plastic bottle per day, over 7,000 tonnes of plastic waste could be prevented each year. EcoLens makes these invisible impacts visible, so your everyday choices can become part of a much bigger change.")

    st.header("✨ Key Features", anchor=False)

    components.html("""
<div style="
    background: linear-gradient(135deg, #2d5016 0%, #3d6b1f 100%);
    border-radius:18px;
    padding:44px 38px;
    margin-top:18px;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
    box-shadow: 0 8px 24px rgba(45, 80, 22, 0.3);
">
  <div style="display:flex; gap:34px; align-items:center;">

    <div style="flex:1.2;">
      <h2 style="margin:0 0 14px 0; font-size:38px; color:#f5f1e8;">
        🌿 GreenScore Tracker
      </h2>

      <p style="margin:0 0 14px 0; font-size:18px; line-height:1.7; color:#e8f5e9;">
        Scan personal-care products and get a transparent sustainability score with clear reasons.
      </p>

      <ul style="margin:0; padding-left:20px; font-size:20px; line-height:1.7; color:#e8f5e9;">
        <li>Product Scan</li>
        <li>Score breakdown (ingredients, packaging, claims)</li>
        <li>Better alternatives for your purpose</li>
      </ul>
    </div>

    <div style="flex:1; display:flex; justify-content:flex-end;">
      <div style="
          width:520px;
          height:320px;
          border-radius:16px;
          overflow:hidden;
          box-shadow: 0 10px 30px rgba(0,0,0,0.35);
          background: rgba(245,241,232,0.06);
          border: 2px solid rgba(156,179,128,0.2);
      ">
        <img src="https://www.iberdrola.com/documents/20125/40513/huella-de-carbono-746x419.jpg/f61f98a2-7c51-27f9-31d2-41b1dafe6bf7?t=1738248418273"
             style="width:100%; height:100%; object-fit:cover;">
      </div>
    </div>

  </div>
</div>
""", height=420)


    
    #-------------------------
    # AI Chatbot
    #-------------------------

    components.html("""
    <div style="
        background: linear-gradient(135deg, #4d7b2f 0%, #5d8b3f 100%);
        border-radius:18px;
        padding:44px 38px;
        margin-top:22px;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
        box-shadow: 0 8px 24px rgba(45, 80, 22, 0.3);
    ">
      <div style="display:flex; gap:34px; align-items:center;">
    
        <!-- LEFT IMAGE -->
        <div style="flex:1; display:flex; justify-content:flex-start;">
          <div style="
              width:520px;
              height:320px;
              border-radius:16px;
              overflow:hidden;
              box-shadow: 0 10px 30px rgba(0,0,0,0.35);
              background: rgba(245,241,232,0.06);
              border: 2px solid rgba(156,179,128,0.2);
          ">
            <img src="https://beetroot.co/wp-content/uploads/sites/2/2024/12/Cover_AI-chatbots-in-GreenTech.png"
                 style="width:100%; height:100%; object-fit:cover;">
          </div>
        </div>
    
        <!-- RIGHT TEXT -->
        <div style="flex:1.2;">
          <h2 style="margin:0 0 14px 0; font-size:38px; color:#f5f1e8;">
            🤖 AI Chatbot
          </h2>
    
          <p style="margin:0 0 14px 0; font-size:18px; line-height:1.7; color:#e8f5e9;">
            Ask questions in plain English and get smart, personalized sustainability advice instantly.
          </p>
    
          <ul style="margin:0; padding-left:20px; font-size:18px; line-height:1.7; color:#e8f5e9;">
            <li>Ask about ingredients and claims</li>
            <li>Get product recommendations</li>
            <li>Tips for safer / sustainable swaps</li>
          </ul>
        </div>
    
      </div>
    </div>
    """, height=420)

    #---------------------
    # Impact Score
    #---------------------
  
    components.html("""
    <div style="
        background: linear-gradient(135deg, #2d5016 0%, #3d6b1f 100%);
        border-radius:18px;
        padding:44px 38px;
        margin-top:22px;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
        box-shadow: 0 8px 24px rgba(45, 80, 22, 0.3);
    ">
      <div style="display:flex; gap:34px; align-items:center;">
    
        <!-- LEFT TEXT -->
        <div style="flex:1.2;">
          <h2 style="margin:0 0 14px 0; font-size:38px; color:#f5f1e8;">
            🌲 Impact Score
          </h2>
    
          <p style="margin:0 0 14px 0; font-size:18px; line-height:1.7; color:#e8f5e9;">
            See the real environmental impact of every purchase in clear, easy-to-understand metrics.
          </p>
    
          <ul style="margin:0; padding-left:20px; font-size:18px; line-height:1.7; color:#e8f5e9;">
            <li>Trends in Purchases</li>
            <li>Impact Log</li>
            <li>Compare products side-by-side</li>
            <li>Visualize your eco progress over time</li>
          </ul>
        </div>
    
        <!-- RIGHT IMAGE -->
        <div style="flex:1; display:flex; justify-content:flex-end;">
          <div style="
              width:520px;
              height:320px;
              border-radius:16px;
              overflow:hidden;
              box-shadow: 0 10px 30px rgba(0,0,0,0.35);
              background: rgba(245,241,232,0.06);
              border: 2px solid rgba(156,179,128,0.2);
          ">
            <img src="https://greenscoreapp.com/wp-content/uploads/2024/09/Empowering-Sustainability-Through-Innovation-image2-Green-Score.webp"
                 style="width:100%; height:100%; object-fit:cover;">
          </div>
        </div>
    
      </div>
    </div>
    """, height=420)

    #-------------------------
    # Your Next Steps
    #-------------------------

    components.html("""
    <div style="
        background: linear-gradient(135deg, #4d7b2f 0%, #5d8b3f 100%);
        border-radius:18px;
        padding:44px 38px;
        margin-top:22px;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
        box-shadow: 0 8px 24px rgba(45, 80, 22, 0.3);
    ">
      <div style="display:flex; gap:34px; align-items:center;">
    
        <!-- LEFT IMAGE -->
        <div style="flex:1; display:flex; justify-content:flex-start;">
          <div style="
              width:520px;
              height:320px;
              border-radius:16px;
              overflow:hidden;
              box-shadow: 0 10px 30px rgba(0,0,0,0.35);
              background: rgba(245,241,232,0.06);
              border: 2px solid rgba(156,179,128,0.2);
          ">
            <img src="https://www.shutterstock.com/image-photo/desk-displays-esg-metrics-sustainable-260nw-2672441077.jpg"
                 style="width:100%; height:100%; object-fit:cover;">
          </div>
        </div>
    
        <!-- RIGHT TEXT -->
        <div style="flex:1.2;">
          <h2 style="margin:0 0 14px 0; font-size:38px; color:#f5f1e8;">
            Your Next Steps
          </h2>
    
          <p style="margin:0 0 14px 0; font-size:18px; line-height:1.7; color:#e8f5e9;">
            Clear, practical steps you can take to meaningfully reduce your environmental impact.
          </p>
    
          <ul style="margin:0; padding-left:20px; font-size:18px; line-height:1.7; color:#e8f5e9;">
            <li>Better Alternatives</li>
            <li>Eco-friendly suggestions</li>
            <li>Microhabits</li>
          </ul>
        </div>
    
      </div>
    </div>
    """, height=420)

# -------------------------
# GREEN SCORE PAGE
# -------------------------
elif st.session_state.page == "GreenScore":
    st.button("← Back to Home", on_click=go, args=("Home",))
    st.title("🌿 GreenScore")    
    # Check if user clicked an alternative product
    if "impact_history" not in st.session_state:
        st.session_state.impact_history = pd.DataFrame(columns=[
            "Product", "Category", "Eco Score",
            "Carbon (kg)", "Water (L)", "Energy (MJ)", "Waste Score"
        ])
    if "logged_keys" not in st.session_state:
        st.session_state.logged_keys = set()
    
    # -----------------------------
    # Step 7: USER INPUT + DISPLAY
    # -----------------------------
    st.subheader("📸 Scan Product (optional)")
    
    image_file = st.camera_input("Take a photo of the product")
    
    if image_file:
        image = Image.open(image_file)
    
        with st.spinner("Reading packaging text..."):
            all_text = ocr_image(image)
        
        with st.spinner("Identifying product..."):
            detected_name = extract_product_name(all_text)
            matched_name, confidence = fuzzy_match_product(detected_name, summary_df)
        
        st.success(f"Detected: {matched_name}")
        st.session_state.selected_product = matched_name
    
    # -----------------------------
    # PRODUCT SEARCH (SINGLE SOURCE OF TRUTH)
    # -----------------------------
    product_options = sorted(summary_df["name"].unique())
    preselected_product = None
    
    # Priority:
    # 1. Alternative click
    # 2. Previously selected product
    if "selected_alternative" in st.session_state:
        preselected_product = st.session_state.selected_alternative
    elif "selected_product" in st.session_state:
        preselected_product = st.session_state.selected_product
    
    # -----------------------------
    # SINGLE SELECTBOX (NO DOUBLE CLICK)
    # -----------------------------
    if preselected_product in product_options:
        product_input = st.selectbox(
            "🔍 Search for a product",
            options=product_options,
            index=product_options.index(preselected_product),
            key="product_selectbox",
            placeholder="Start typing to search..."
        )
    else:
        product_input = st.selectbox(
            "🔍 Search for a product",
            options=product_options,
            index=None,
            key="product_selectbox",
            placeholder="Start typing to search..."
        )
    
    # -----------------------------
    # CLEAN UP ONE-TIME FLAGS
    # -----------------------------

    
    # -----------------------------
    # PERSIST SELECTION (IMMEDIATE)
    # -----------------------------
    if product_input:
        st.session_state.selected_product = product_input
        result = summary_df[summary_df["name"] == product_input]
        if result.empty:
            st.error("❌ Product not found in database.")
        else:
            r = result.iloc[0]
                st.divider()
        if "selected_alternative" in st.session_state:
            del st.session_state["selected_alternative"]
        # Clear selected alternative AFTER it has been applied

            
            # ---------- ECO SCORE ----------
            st.markdown("### 🌿 Eco Score")
            
            # Create a more visually appealing score display
            score_col1, score_col2 = st.columns([2, 3])
            
            with score_col1:
                # Large score display
                st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #2d5016 0%, #3d6b1f 100%);
                        border-radius: 18px;
                        padding: 30px;
                        text-align: center;
                        box-shadow: 0 8px 20px rgba(45, 80, 22, 0.3);
                    ">
                        <h1 style="color: #f5f1e8; margin: 0; font-size: 4em;">{r['eco_score']}</h1>
                        <p style="color: #c5d4b8; margin: 5px 0 0 0; font-size: 1.1em;">out of 100</p>
                    </div>
                """, unsafe_allow_html=True)
            
            with score_col2:
                # Score interpretation
                if r['eco_score'] >= 80:
                    badge_color = "#2d5016"
                    badge_text = "Excellent"
                    emoji = "🌟"
                elif r['eco_score'] >= 60:
                    badge_color = "#4d7b2f"
                    badge_text = "Good"
                    emoji = "👍"
                elif r['eco_score'] >= 40:
                    badge_color = "#d4a373"
                    badge_text = "Moderate"
                    emoji = "⚠️"
                else:
                    badge_color = "#a85232"
                    badge_text = "Needs Improvement"
                    emoji = "❗"
                
                st.markdown(f"""
                    <div style="padding: 20px 0;">
                        <div style="
                            background-color: {badge_color};
                            color: #f5f1e8;
                            padding: 15px 25px;
                            border-radius: 14px;
                            display: inline-block;
                            font-size: 1.3em;
                            font-weight: bold;
                            margin-bottom: 15px;
                            box-shadow: 0 4px 12px rgba(45, 80, 22, 0.2);
                        ">
                            {emoji} {badge_text}
                        </div>
                        <p style="color: #9cb380; margin-top: 10px; line-height: 1.6;">
                            This score reflects the overall environmental impact across carbon, water, energy, and waste metrics.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            
            # Progress bar with custom styling
            st.markdown(f"""
                <div style="margin: 20px 0;">
                    <div style="
                        background-color: #3d4a35;
                        border-radius: 12px;
                        height: 14px;
                        overflow: hidden;
                    ">
                        <div style="
                            background: linear-gradient(90deg, #2d5016 0%, #4d7b2f 50%, #7c9070 100%);
                            width: {r['eco_score']}%;
                            height: 100%;
                            border-radius: 12px;
                            transition: width 0.5s ease;
                        "></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
            st.divider()
    
            # ---------- METRICS ----------
            st.markdown("### 📊 Environmental Impact Breakdown")
            
            col1, col2, col3, col4 = st.columns(4)
    
            with col1:
                st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #f5f1e8 0%, #faf8f3 100%);
                        border-left: 4px solid #d4a373;
                        border-radius: 12px;
                        padding: 20px 15px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(45, 80, 22, 0.1);
                    ">
                        <div style="font-size: 2em; margin-bottom: 10px;">🌫</div>
                        <div style="color: #5d4e37; font-size: 0.85em; margin-bottom: 5px; font-weight: 600;">Carbon Footprint</div>
                        <div style="color: #2d1810; font-size: 1.5em; font-weight: bold;">{r['total_carbon_kg']}</div>
                        <div style="color: #5d4e37; font-size: 0.75em;">kg CO₂e</div>
                    </div>
                """, unsafe_allow_html=True)
    
            with col2:
                st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #e8f5e9 0%, #f1f8f3 100%);
                        border-left: 4px solid #4d7b2f;
                        border-radius: 12px;
                        padding: 20px 15px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(45, 80, 22, 0.1);
                    ">
                        <div style="font-size: 2em; margin-bottom: 10px;">💧</div>
                        <div style="color: #2d5016; font-size: 0.85em; margin-bottom: 5px; font-weight: 600;">Water Usage</div>
                        <div style="color: #1a3d0f; font-size: 1.5em; font-weight: bold;">{r['total_water_L']}</div>
                        <div style="color: #2d5016; font-size: 0.75em;">Liters</div>
                    </div>
                """, unsafe_allow_html=True)
    
            with col3:
                st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #fff9e6 0%, #fffcf0 100%);
                        border-left: 4px solid #d4a373;
                        border-radius: 12px;
                        padding: 20px 15px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(45, 80, 22, 0.1);
                    ">
                        <div style="font-size: 2em; margin-bottom: 10px;">⚡</div>
                        <div style="color: #6b4423; font-size: 0.85em; margin-bottom: 5px; font-weight: 600;">Energy Use</div>
                        <div style="color: #3d2815; font-size: 1.5em; font-weight: bold;">{r['total_energy_MJ']}</div>
                        <div style="color: #6b4423; font-size: 0.75em;">MJ</div>
                    </div>
                """, unsafe_allow_html=True)
    
            with col4:
                st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #f5f1e8 0%, #faf8f3 100%);
                        border-left: 4px solid #7c9070;
                        border-radius: 12px;
                        padding: 20px 15px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(45, 80, 22, 0.1);
                    ">
                        <div style="font-size: 2em; margin-bottom: 10px;">🗑</div>
                        <div style="color: #3d4a35; font-size: 0.85em; margin-bottom: 5px; font-weight: 600;">Waste Impact</div>
                        <div style="color: #1a2318; font-size: 1.5em; font-weight: bold;">{r['total_waste_score']}</div>
                        <div style="color: #3d4a35; font-size: 0.75em;">Score</div>
                    </div>
                """, unsafe_allow_html=True)

                        # ---------- INGREDIENT FLAGS (only show present ones) ----------
            st.markdown("### 🧪 Ingredient Flags")
            
            flag_defs = [
                {
                    "key": "microplastics",
                    "title": "Microplastics",
                    "emoji": "🧬",
                    "present": int(r["microplastics"]) == 1,
                    "why": "Microplastics can persist in waterways and harm aquatic life when washed down drains."
                },
                {
                    "key": "silicones",
                    "title": "Silicones",
                    "emoji": "🧴",
                    "present": int(r["silicones"]) == 1,
                    "why": "Some silicones are persistent and can contribute to long-lasting pollution in the environment."
                },
                {
                    "key": "petroleum",
                    "title": "Petroleum-derived",
                    "emoji": "🛢️",
                    "present": int(r["petroleum"]) == 1,
                    "why": "Petroleum-based ingredients come from fossil fuels, increasing reliance on non-renewable resources."
                },
            ]
            
            present_flags = [f for f in flag_defs if f["present"]]
            
            if present_flags:
                cols = st.columns(len(present_flags))
                for col, flag in zip(cols, present_flags):
                    with col:
                        st.markdown(f"""
                            <div style="
                                background: linear-gradient(135deg, #fff4e6 0%, #f5f1e8 100%);
                                border-left: 4px solid #d4a373;
                                border-radius: 12px;
                                padding: 18px 14px;
                                box-shadow: 0 4px 12px rgba(45, 80, 22, 0.10);
                                min-height: 155px;
                            ">
                                <div style="font-size: 1.8em; margin-bottom: 6px;">{flag["emoji"]}</div>
                                <div style="font-weight: 700; font-size: 1.05em; color: #1a2318;">{flag["title"]} — Present</div>
                                <div style="margin-top: 10px; font-size: 0.9em; line-height: 1.45; color: #3d4a35;">
                                    {flag["why"]}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✅ No ingredient red flags detected for this product (based on our database).")
    
            st.markdown("<br>", unsafe_allow_html=True)
    
            # ---------- OPTIONAL DETAILS ----------
            with st.expander("📊 View detailed data"):
                st.dataframe(result, use_container_width=True)
        
            st.divider()
            
            st.subheader("🛒 Purchase Logging")
            
            if st.button("✅ Log this product as purchased", use_container_width=True):
                log_key = f"{product_input}_{r['eco_score']}"
            
                if log_key not in st.session_state.logged_keys:
                    st.session_state.impact_history.loc[len(st.session_state.impact_history)] = {
                        "Product": product_input,
                        "Category": r["category"],
                        "Eco Score": r["eco_score"],
                        "Carbon (kg)": r["total_carbon_kg"],
                        "Water (L)": r["total_water_L"],
                        "Energy (MJ)": r["total_energy_MJ"],
                        "Waste Score": r["total_waste_score"]
                    }
                    st.session_state.logged_keys.add(log_key)
                    st.success("🎉 Product logged! Your Impact Dashboard has been updated.")
                else:
                    st.info("This product is already logged as purchased.")
            
            
            st.subheader("🌿 Greener Alternatives")
            st.caption("Click any product to view its full eco score")
            
            alternatives = get_greener_alternatives(product_input, summary_df, max_alternatives=5)
            
            # ✅ CASE 1: NO greener alternatives
            if not alternatives:
                st.success("🎉 Great choice! This is already one of the greenest options in its category.")
            
            # ✅ CASE 2: Greener alternatives exist
            else:
                for alt in alternatives:
                    col1, col2 = st.columns([4, 1])
            
                    with col1:
                        st.markdown(
                            f"""
                            <div style="
                                background: linear-gradient(135deg, #e8f5e9 0%, #f5f1e8 100%);
                                border-left: 5px solid #2d5016;
                                border-radius: 14px;
                                padding: 18px;
                                margin-bottom: 14px;
                                box-shadow: 0 4px 12px rgba(45, 80, 22, 0.15);
                            ">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div>
                                        <strong style="color:#1a3d0f; font-size:17px;">{alt['name']}</strong><br>
                                        <span style="color:#4d7b2f; font-size:14px;">✨ {alt['improvement']}</span>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="color:#2d5016; font-size:26px; font-weight:700;">
                                            {alt['eco_score']}
                                        </div>
                                        <div style="color:#5d4e37; font-size:12px;">
                                            +{alt['score_diff']:.1f} points
                                        </div>
                                    </div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            
                    with col2:
                        if st.button("View →", key=f"view_{alt['name']}", use_container_width=True):
                            st.session_state['selected_alternative'] = alt['name']
                            st.rerun()



            # =============================
            # AI DEEP DIVE EXPLANATION
            # =============================
            # =============================
            # AI PRODUCT CHATBOT
            # =============================
            st.divider()
            st.subheader("🤖 AI Insight: Explore This Product")

            st.caption(
                "Ask in-depth questions about this product's ingredients, impacts, and "
                "how to make better purchase choices."
            )

            from openai import OpenAI
            client = OpenAI(api_key=st.secrets["OpenAIKey"])

            # -----------------------------
            # INIT / RESET PRODUCT CHAT MEMORY
            # -----------------------------
            if (
                "product_ai_messages" not in st.session_state
                or st.session_state.get("product_chat_product") != product_input
            ):
                st.session_state.product_chat_product = product_input
                
                # Use the actual selected product data (r) instead of hardcoded first product
                st.session_state.product_ai_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a product-focused sustainability assistant.\n\n"
                            "You help users understand a SINGLE product in depth.\n\n"
                            "You may answer questions about:\n"
                            "- why this product scores the way it does\n"
                            "- ingredient and material impacts\n"
                            "- microplastics, silicones, petroleum, etc.\n"
                            "- what makes this product better or worse than alternatives\n"
                            "- what to look for when buying a greener option next time\n\n"
                            "Rules:\n"
                            "- Focus only on purchase-related advice\n"
                            "- No lifestyle tips\n"
                            "- Be specific to THIS product\n"
                            "- Do not invent data\n\n"
                            f"PRODUCT CONTEXT:\n"
                            f"Name: {r['name']}\n"
                            f"Category: {r['category']}\n"
                            f"Eco Score: {r['eco_score']} / 100\n"
                            f"Carbon: {r['total_carbon_kg']} kg CO₂e\n"
                            f"Water: {r['total_water_L']} L\n"
                            f"Energy: {r['total_energy_MJ']} MJ\n"
                            f"Waste Score: {r['total_waste_score']}\n"
                            f"Microplastics: {bool(int(r['microplastics']))}\n"
                            f"Silicones: {bool(int(r['silicones']))}\n"
                            f"Petroleum-derived: {bool(int(r['petroleum']))}"
                        ),
                    }
                ]

            # -----------------------------
            # DISPLAY CHAT
            # -----------------------------
            for msg in st.session_state.product_ai_messages[1:]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # -----------------------------
            # USER QUESTION INPUT
            # -----------------------------
            product_question = st.chat_input(
                "Ask about ingredients, impacts, or better alternatives for this product…"
            )

            if product_question:
                st.session_state.product_ai_messages.append(
                    {"role": "user", "content": product_question}
                )

                with st.chat_message("user"):
                    st.markdown(product_question)

                # -----------------------------
                # AI RESPONSE
                # -----------------------------
                with st.chat_message("assistant"):
                    with st.spinner("Thinking about this product… 🌍"):
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            temperature=0.4,
                            messages=st.session_state.product_ai_messages,
                        )

                        ai_reply = response.choices[0].message.content
                        st.markdown(ai_reply)

                st.session_state.product_ai_messages.append(
                    {"role": "assistant", "content": ai_reply}
                )


            

# -------------------------
# CHATBOT PAGE
# -------------------------

elif st.session_state.page == "Chatbot":
    import streamlit as st
    from openai import OpenAI
    # -----------------------------
    # INIT OPENAI CLIENT
    # -----------------------------
    client = OpenAI(api_key=st.secrets["OpenAIKey"])
    # -----------------------------
    # PAGE SETUP
    # -----------------------------
    st.title("🤖 Eco Assistant")
    st.caption("Ask me about sustainability, eco scores, or greener choices 🌱")
    # -----------------------------
    # CHAT MEMORY
    # -----------------------------
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful sustainability assistant focused ONLY on environmental and sustainability topics. "
                    "You ONLY answer questions related to:\n"
                    "- Sustainability and eco-friendly practices\n"
                    "- Environmental impact and climate change\n"
                    "- Green products and eco scores\n"
                    "- Waste reduction and recycling\n"
                    "- Carbon footprint and water usage\n"
                    "- Energy conservation and renewable energy\n"
                    "- Sustainable living and eco-conscious choices\n\n"
                    "If a user asks about topics unrelated to environment or sustainability "
                    "(like sports, entertainment, general knowledge, coding, etc.), "
                    "politely respond: 'I'm specifically designed to help with environmental and sustainability questions. "
                    "Could you ask me something related to eco-friendly living, green products, or environmental impact instead? 🌱'\n\n"
                    "For valid sustainability questions, give clear, practical, beginner-friendly answers. "
                    "Be concise and encouraging."
                )
            }
        ]
    # -----------------------------
    # DISPLAY CHAT
    # -----------------------------
    for msg in st.session_state.messages[1:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    # -----------------------------
    # USER INPUT
    # -----------------------------
    user_input = st.chat_input("Ask something eco-related...")
    if user_input:
        # show user message
        st.session_state.messages.append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user"):
            st.markdown(user_input)
        # -----------------------------
        # OPENAI RESPONSE
        # -----------------------------
        with st.chat_message("assistant"):
            with st.spinner("Thinking 🌍"):
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=st.session_state.messages,
                    temperature=0.6
                )
                assistant_reply = response.choices[0].message.content
                st.markdown(assistant_reply)
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_reply}
        )






# -------------------------
# TOTAL IMPACT PAGE
# -------------------------
elif st.session_state.page == "Impact Dashboard":

    import pandas as pd
    import plotly.express as px
    from openai import OpenAI
    import streamlit as st

    # -----------------------------
    # NAV
    # -----------------------------
    st.button("← Back to Home", on_click=go, args=("Home",))
    st.title("🌍 Your Sustainability Impact")
    st.caption("A living story of how your choices shape the planet 🌱")

    # -----------------------------
    # OPENAI CLIENT
    # -----------------------------
    client = OpenAI(api_key=st.secrets["OpenAIKey"])

    def explain_with_ai(title, data, products):
        prompt = f"""
You are an AI sustainability analyst embedded inside a purchase-impact dashboard.

Context:
- The user logs products they buy
- Each product has an Eco Score, carbon, water, energy, and waste impact
- The dashboard only tracks PURCHASES (not lifestyle habits)

Graph title:
{title}

Products involved:
{products}

User data (aggregated from logged products):
{data}

Your tasks:

1. Explain what this graph reveals about the USER'S PURCHASE PATTERNS.
   - Mention specific impact categories (carbon, water, energy, waste)
   - Point out what is unusually high or low
   - Be concrete and data-driven (not generic)

2. Suggest 3 IMPROVEMENTS RELATED ONLY TO FUTURE PURCHASES.
   - Suggest product alternatives, material swaps, or category changes
   - Example: “Switch from X-type products to Y-type products”
   - You MAY suggest searching for lower-impact alternatives
   - DO NOT suggest lifestyle actions (no showers, lights, transport, etc.)

Rules:
- No generic eco tips
- No guilt or moralising
- Friendly, insightful, specific
- Assume a curious student user
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35
        )

        return response.choices[0].message.content

    # -----------------------------
    # REQUIRE HISTORY
    # -----------------------------
    if "impact_history" not in st.session_state or st.session_state.impact_history.empty:
        st.info("Analyse products to start building your impact story 🌱")
        st.stop()

    history = st.session_state.impact_history.copy()
    st.divider()

    # =============================
    # 🌱 SUMMARY METRICS
    # =============================
    avg_score = history["Eco Score"].mean()
    total_score = history["Eco Score"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average Eco Score", f"{avg_score:.1f} / 100")
    c2.metric("Products Logged", len(history))
    c3.metric("High-Eco Choices", (history["Eco Score"] >= 80).sum())
    c4.metric("Total Eco Score", int(total_score))

    st.divider()

    # =============================
    # 📈 ECOSCORE TREND
    # =============================
    st.markdown("## 📈 Your EcoScore Journey")

    trend_fig = px.line(
        history.reset_index(),
        x=history.reset_index().index,
        y="Eco Score",
        markers=True,
        color_discrete_sequence=["#2d5016"]
    )

    st.plotly_chart(trend_fig, use_container_width=True)

    if st.button("🤖 Let AI explain this EcoScore trend"):
        with st.spinner("AI analysing your progress 🌱"):
            delta = history["Eco Score"].iloc[-1] - history["Eco Score"].iloc[0]

            summary = {
                "starting_score": float(history["Eco Score"].iloc[0]),
                "latest_score": float(history["Eco Score"].iloc[-1]),
                "average_score": round(avg_score, 1),
                "trend": "improving" if delta > 5 else "declining" if delta < -5 else "stable"
            }

            products = history["Product"].tolist()

            ai_text = explain_with_ai(
                "EcoScore trend over time",
                summary,
                products
            )

            explanation, actions = ai_text.split("2.", 1)
            st.info(explanation.strip())
            st.success("2." + actions.strip())

    st.divider()

    # =============================
    # 📊 IMPACT BREAKDOWN
    # =============================
    st.markdown("## 📊 What Impacts You the Most")

    impact_avg = history[
        ["Carbon (kg)", "Water (L)", "Energy (MJ)", "Waste Score"]
    ].mean().reset_index()

    impact_avg.columns = ["Impact Type", "Average Value"]

    impact_fig = px.bar(
        impact_avg,
        x="Impact Type",
        y="Average Value",
        color="Impact Type",
        color_discrete_sequence=["#2d5016", "#3d6b1f", "#4d7b2f", "#7c9070"]
    )

    st.plotly_chart(impact_fig, use_container_width=True)

    if st.button("🤖 Let AI explain this impact breakdown"):
        with st.spinner("Understanding your impact 🌍"):
            impact_dict = dict(
                zip(impact_avg["Impact Type"], impact_avg["Average Value"])
            )

            products = history["Product"].unique().tolist()

            ai_text = explain_with_ai(
                "Average environmental impact by purchase",
                impact_dict,
                products
            )

            explanation, actions = ai_text.split("2.", 1)
            st.info(explanation.strip())
            st.success("2." + actions.strip())

    st.divider()

    # =============================
    # 🔄 PRODUCT COMPARISON (SAME CATEGORY ONLY)
    # =============================
    st.markdown("## 🔄 Compare Products by Impact")

    # Step 1 — Choose category first
    compare_category = st.selectbox(
        "Select a category to compare within",
        sorted(history["Category"].unique())
    )

    # Step 2 — Show only products from that category
    category_products = history[
        history["Category"] == compare_category
    ]["Product"].unique()

    compare_products = st.multiselect(
        "Select products",
        category_products,
        default=list(category_products[:2])
    )

    if len(compare_products) >= 2:
        compare_df = history[history["Product"].isin(compare_products)]

        impact_cols = ["Carbon (kg)", "Water (L)", "Energy (MJ)", "Waste Score"]
        normalized = compare_df.copy()

        for col in impact_cols:
            max_val = normalized[col].max()
            normalized[col] = normalized[col] / max_val if max_val > 0 else 0

        stacked_fig = px.bar(
            normalized,
            x="Product",
            y=impact_cols,
            barmode="stack",
            color_discrete_sequence=["#2d5016", "#3d6b1f", "#4d7b2f", "#7c9070"]
        )

        st.plotly_chart(stacked_fig, use_container_width=True)

        # AI explanation
        if st.button("🤖 Let AI explain this product comparison"):
            with st.spinner("Comparing smarter choices 🌱"):
                comparison_summary = (
                    compare_df.groupby("Product")[impact_cols]
                    .mean()
                    .to_dict()
                )

                ai_text = explain_with_ai(
                    "Product impact comparison",
                    comparison_summary
                )

                explanation, actions = ai_text.split("2.", 1)
                st.info(explanation.strip())
                st.success("2." + actions.strip())

    else:
        st.info("Select at least two products from the same category 🌱")

    st.divider()



    # =============================
    # 📜 HISTORY TABLE
    # =============================
    st.markdown("## 📜 Your Impact Log")
    st.dataframe(history[::-1], use_container_width=True)

    if st.button("🗑️ Clear Impact History"):
        st.session_state.impact_history = st.session_state.impact_history.iloc[0:0]

        if "logged_keys" in st.session_state:
            st.session_state.logged_keys.clear()

        st.success("Impact history cleared 🌱")
        st.rerun()


# -------------------------
# YOUR NEXT STEPS PAGE
# -------------------------
elif st.session_state.page == "NextSteps":

    st.button("← Back to Home", on_click=go, args=("Home",))
    st.title("🧭 Your Next Steps")
    st.caption("Clear, practical actions to reduce your impact")

    st.markdown("<br>", unsafe_allow_html=True)

    # ============================
    # SECTION 1 — ECO ALTERNATIVES
    # ============================

    st.subheader("🌿 Switch to Better Alternatives")

    category = st.selectbox(
        "Select a product category",
        ["", "Shampoo", "Cream", "Sunscreen", "Body Wash"]
    )

    BEST_SUBS = {
        "Shampoo": [
            "Ethique Shampoo Bar",
            "Earth Rhythm Shampoo Bar",
            "Bare Anatomy Concentrated Shampoo"
        ],
        "Cream": [
            "Minimalist Marula Oil Moisturizer",
            "Earth Rhythm Phyto Clear Moisturizer",
            "Plum Green Tea Moisturizer"
        ],
        "Sunscreen": [
            "Raw Beauty Wellness Sunscreen Stick",
            "Minimalist SPF 50 (50g)",
            "Dot & Key Sunscreen Stick"
        ],
        "Body Wash": [
            "Ethique Solid Body Wash Bar",
            "Earth Rhythm Body Wash Bar",
            "Plum BodyLovin Body Wash Bar"
        ]
    }

    if category != "":
        c1, c2, c3 = st.columns(3)

        for i, prod in enumerate(BEST_SUBS[category]):
            with [c1, c2, c3][i]:
                st.markdown(f"""
                <div style="
                    background:#102a13;
                    border-radius:16px;
                    padding:24px;
                    text-align:center;
                    box-shadow:0 6px 16px rgba(0,0,0,0.25);
                    height:170px;
                    display:flex;
                    flex-direction:column;
                    justify-content:center;
                ">
                    <h4 style="color:white;margin-bottom:10px;">{prod}</h4>
                    <p style="color:rgba(255,255,255,0.7);font-size:14px;">
                    Lower packaging & ingredient impact
                    </p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # =================================
    # SECTION 2 — IF YOU ALREADY BOUGHT
    # =================================

    st.subheader("♻️ If You Already Bought a Regular Product")

    c1, c2, c3 = st.columns(3)

    # BOX 1 — USE LESS
    with c1:
        st.markdown("""
        <div style="
            background:#1b2f1f;
            border-radius:16px;
            padding:26px;
            height:260px;
            box-shadow:0 6px 16px rgba(0,0,0,0.25);
        ">
            <h4 style="color:white;">Use Less</h4>
            <ul style="color:rgba(255,255,255,0.85); line-height:1.7;">
                <li>Use smaller amounts</li>
                <li>Avoid double cleansing</li>
                <li>Don’t overapply</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # BOX 2 — EXTEND LIFE
    with c2:
        st.markdown("""
        <div style="
            background:#1b2f1f;
            border-radius:16px;
            padding:26px;
            height:260px;
            box-shadow:0 6px 16px rgba(0,0,0,0.25);
        ">
            <h4 style="color:white;">Extend Product Life</h4>
            <ul style="color:rgba(255,255,255,0.85); line-height:1.7;">
                <li>Finish the product fully</li>
                <li>Use refills when possible</li>
                <li>Store properly</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # BOX 3 — DISPOSE SMARTLY
    with c3:
        st.markdown("""
        <div style="
            background:#1b2f1f;
            border-radius:16px;
            padding:26px;
            height:260px;
            box-shadow:0 6px 16px rgba(0,0,0,0.25);
        ">
            <h4 style="color:white;">Dispose Smartly</h4>
            <ul style="color:rgba(255,255,255,0.85); line-height:1.7;">
                <li>Rinse container</li>
                <li>Recycle correctly</li>
                <li>Reuse for storage</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ============================
    # SECTION 3 — DAILY MICRO HABITS
    # ============================

    st.subheader("🌱 Everyday Micro-Habits")

    c1, c2, c3 = st.columns(3)

    habits = [
        "Buy refills",
        "Prefer bars over liquids",
        "Reduce, Reuse Recycle",
        "Choose multipurpose products",
        "Carry your own bottle",
        "Support Green Businesses"
    ]

    for i, h in enumerate(habits):
        with [c1, c2, c3][i % 3]:
            st.markdown(f"""
            <div style="
                background:#0f766e;
                color:white;
                border-radius:14px;
                padding:18px;
                text-align:center;
                margin-bottom:14px;
                box-shadow:0 4px 10px rgba(0,0,0,0.25);
            ">
                {h}
            </div>
            """, unsafe_allow_html=True)
