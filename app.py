import streamlit as st
from PIL import Image
import io
import base64
from openai import OpenAI
import os

client = OpenAI()

# ---------------------------------------------------
# helper: convert uploaded image → base64 data URL
# ---------------------------------------------------
def extract_info_from_image(image_bytes):
    import base64
    import io
    from PIL import Image
    from openai import OpenAI
    import json

    client = OpenAI()

    try:
        # Detect image format
        img = Image.open(io.BytesIO(image_bytes))
        ext = img.format.lower()

        # Encode to base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/{ext};base64,{b64}"

        # Use standard messages format with vision capability
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the following fields strictly in JSON format:\n"
                                "- policy_number\n"
                                "- claimant_name\n"
                                "- date_of_accident\n"
                                "- vehicle_number\n"
                                "- description\n\n"
                                "Return ONLY the JSON object, no additional text."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            temperature=0.7
        )

        # Parse the response
        result_text = response.choices[0].message.content
        try:
            result_json = json.loads(result_text)
            return result_json
        except json.JSONDecodeError:
            return {"raw_text": result_text}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------
st.set_page_config(page_title="Motor Claim OCR", layout="centered")

st.title("📄 Motor Insurance Claim OCR")
st.write("Upload a Motor Claim Form photo. AI will extract key fields automatically.")

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])

if uploaded_file:

    # Read image bytes once
    image_bytes = uploaded_file.read()

    # Show preview
    img = Image.open(io.BytesIO(image_bytes))
    st.image(img, caption="Uploaded Image", use_column_width=True)

    if st.button("🔍 Extract Details"):
        with st.spinner("Extracting using OpenAI Vision..."):
            extraction_raw = extract_info_from_image(image_bytes)

        st.subheader("📤 Raw Extraction Result")
        st.json(extraction_raw)

        # ---------------------------------------------------
        # Manual verification UI
        # ---------------------------------------------------
        st.subheader("✏️ Confirm / Correct Extracted Details")
        fields = [
            "policy_number",
            "claimant_name",
            "date_of_accident",
            "vehicle_number",
            "description",
        ]

        user_inputs = {}
        for f in fields:
            user_inputs[f] = st.text_input(f.replace("_", " ").title())

        if st.button("✅ Submit Final Details"):
            st.success("Details saved successfully!")
            st.json(user_inputs)

st.write("---")
st.caption("Powered by Streamlit + OpenAI Vision OCR")
