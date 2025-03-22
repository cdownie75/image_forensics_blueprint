import cv2
import numpy as np
import pytesseract
from PIL import Image, ExifTags
import os
import openai
import json
import tiktoken

# --- CONFIGURATION ---
openai.api_key = os.getenv("OPENAI_API_KEY")  # Set your API key in your environment variables
MODEL_GPT3 = "gpt-3.5-turbo"
MODEL_GPT4 = "gpt-4-vision-preview"
COST_PER_1K_TOKENS_GPT3 = 0.0015

# --- TOKEN COUNTING ---
def count_tokens(text, model=MODEL_GPT3):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# --- IMAGE PROCESSING FUNCTIONS ---
def preprocess_image(image_path):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    return gray, edges

def extract_metadata(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            return {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_data.items()}
    except Exception as e:
        return {"Error": str(e)}
    return {}

def histogram_analysis(image):
    hist = cv2.calcHist([image], [0], None, [256], [0, 256])
    hist = hist / hist.max()
    anomaly_threshold = 0.05
    anomalies = np.where(hist > anomaly_threshold)[0]
    return len(anomalies) > 5

def extract_text(image_path):
    try:
        gray_image, _ = preprocess_image(image_path)
        if gray_image is None:
            return "[OCR] Error: could not load or preprocess image."
        text = pytesseract.image_to_string(gray_image)
        return text
    except Exception as e:
        return f"[OCR] Error during text extraction: {str(e)}"

def detect_manipulation(image_path):
    gray, edges = preprocess_image(image_path)
    metadata = extract_metadata(image_path)
    text = extract_text(image_path)
    histogram_tampering = histogram_analysis(gray)
    edge_anomalies = np.count_nonzero(edges) > 5000

    findings = {
        "Metadata_Anomalies": metadata,
        "Text_Extracted": text,
        "Edge_Detection_Anomalies": edge_anomalies,
        "Histogram_Anomalies": histogram_tampering,
    }
    suspicious = edge_anomalies or histogram_tampering
    return findings, suspicious

# --- GPT CALLS ---
def call_gpt35_forensics(findings):
    prompt = f"""
    You are a digital forensic assistant. Based on the analysis results below, generate a clear and concise report explaining whether the image appears manipulated. 

    - Metadata anomalies: {json.dumps(findings['Metadata_Anomalies'], indent=2)}
    - Edge detection anomaly: {findings['Edge_Detection_Anomalies']}
    - Histogram inconsistency: {findings['Histogram_Anomalies']}
    - Extracted OCR text: "{findings['Text_Extracted']}"

    Your output should include:
    1. A short summary of whether manipulation is likely.
    2. A bulleted list of technical red flags.
    3. A recommendation for further analysis (yes/no).
    """
    
    tokens_used = count_tokens(prompt)
    response = openai.ChatCompletion.create(
        model=MODEL_GPT3,
        messages=[{"role": "user", "content": prompt}]
    )
    reply = response['choices'][0]['message']['content']
    reply_tokens = count_tokens(reply)
    total_tokens = tokens_used + reply_tokens
    estimated_cost = (total_tokens / 1000) * COST_PER_1K_TOKENS_GPT3

    return reply, total_tokens, estimated_cost

# --- MAIN BATCH PROCESSOR ---
def process_directory(directory_path, output_report="forensic_reports.json"):
    reports = []
    total_tokens = 0
    total_cost = 0.0

    for filename in os.listdir(directory_path):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(directory_path, filename)
            findings, flagged = detect_manipulation(image_path)

            if flagged:
                gpt35_report, tokens_used, cost = call_gpt35_forensics(findings)
                report_entry = {
                    "filename": filename,
                    "flagged": True,
                    "gpt35_report": gpt35_report,
                    "tokens_used": tokens_used,
                    "estimated_cost_usd": round(cost, 6),
                    "findings": findings
                }
                total_tokens += tokens_used
                total_cost += cost
            else:
                report_entry = {
                    "filename": filename,
                    "flagged": False,
                    "findings": findings
                }
            reports.append(report_entry)

    summary = {
        "total_images": len(reports),
        "flagged_images": len([r for r in reports if r.get("flagged")]),
        "total_tokens_used": total_tokens,
        "estimated_total_cost_usd": round(total_cost, 4)
    }
    output = {
        "summary": summary,
        "reports": reports
    }

    with open(output_report, "w") as f:
        json.dump(output, f, indent=2)

    print("✅ Batch processing complete. Reports saved.")
    print(f"Total tokens used: {total_tokens}")
    print(f"Estimated cost: ${total_cost:.4f}")

if __name__ == "__main__":
    directory = "images"  # Replace with your folder path
    process_directory(directory)
