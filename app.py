import streamlit as st
import openai
from PIL import Image
import io
import os
from openai import OpenAI
client = OpenAI()


# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Motor Claim OCR", layout="centered")
openai.api_key = os.getenv("OPENAI_API_KEY")
# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def extract_info_from_image(image_bytes):
    from openai import OpenAI
    import io
    from PIL import Image

    client = OpenAI()

    try:
        # Detect image format
        img = Image.open(io.BytesIO(image_bytes))
        format = img.format.lower()
        mime = f"image/{format}"
        filename = f"uploaded.{format}"

        # Upload file
        uploaded = client.files.create(
            file=(filename, io.BytesIO(image_bytes), mime),
            purpose="vision"
        )

        # OCR Vision request
        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {
                    "role": "system",
                    "content": "Extract Motor Insurance Claim Form fields into JSON."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text":
                                "Extract: policy_number, claimant_name, date_of_accident, "
                                "vehicle_number, description. Use null if missing."
                        },
                        {
                            "type": "input_image",
                            "image": {
                                "file_id": uploaded.id   # ✅ FIXED
                            }
                        }
                    ]
                }
            ]
        )

        return response.output_text

    except Exception as e:
        return {"error": str(e)}

    

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("📄 Motor Insurance Claim OCR App")
st.write("Upload a Motor Insurance Claim Form photo. The system will extract key fields.")

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:

    # Read image bytes ONCE
    image_bytes = uploaded_file.read()

    # Display image from bytes (not uploaded_file, which is now consumed)
    img = Image.open(io.BytesIO(image_bytes))
    st.image(img, caption="Uploaded Image", use_column_width=True)

    if st.button("Extract Details"):
        with st.spinner("Extracting using OpenAI Vision..."):
            
            # Pass image bytes — NOT the file object
            extraction_raw = extract_info_from_image(image_bytes)

        st.subheader("Raw Extraction Result")
        st.json(extraction_raw)

        # Ask user to confirm or provide missing details
        st.subheader("Confirm / Complete Details")
        fields = ["policy_number", "claimant_name", "date_of_accident",
                  "vehicle_number", "description"]

        user_inputs = {}
        for f in fields:
            user_inputs[f] = st.text_input(f.replace("_", " ").title())

        if st.button("Submit Final Details"):
            st.success("Details saved!")
            st.json(user_inputs)

st.write("---")
st.caption("Powered by Streamlit + OpenAI Vision OCR")

