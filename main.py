from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
import json
from image_analysis_pipeline import process_directory
from flat_patch_detector import detect_flat_patches, generate_overlay_image
from celery_worker import run_ocr
from receipt_cropper import crop_receipt_region

app = Flask(__name__)
UPLOAD_FOLDER = "images"
OVERLAY_FOLDER = "overlays"
REPORT_FILE = "forensic_reports.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OVERLAY_FOLDER, exist_ok=True)

HTML_UI = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Image Forensics Dashboard</title>
  <style>
    body { font-family: sans-serif; padding: 2em; max-width: 700px; margin: auto; }
    input[type=\"file\"] { margin-bottom: 1em; }
    button { margin: 0.5em 0; padding: 0.5em 1em; }
    .preview img { max-width: 100%; margin: 1em 0; border: 1px solid #ccc; border-radius: 6px; }
    pre { background: #f4f4f4; padding: 1em; border-radius: 5px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>🔍 Image Forensics Dashboard</h1>
  <input type=\"file\" id=\"imageInput\" accept=\"image/*\">
  <br>
  <button onclick=\"uploadImage()\">📤 Upload Image</button>
  <button onclick=\"runAnalysis()\">🧪 Run Analysis</button>
  <button onclick=\"fetchReport()\">📄 View Report</button>
  <div class=\"uploads\" id=\"uploads\"></div>
  <div class=\"preview\" id=\"preview\"></div>
  <div class=\"report\" id=\"report\"></div>
  <button onclick=\"resetDashboard()\">🔄 Reset</button>
  <button onclick=\"downloadReport()\">💾 Download Report</button>

  <script>
  const API_BASE = "";
  let lastFilename = "";

  function uploadImage() {
    const input = document.getElementById("imageInput");
    if (!input.files.length) return alert("Please select an image");

    const formData = new FormData();
    formData.append("image", input.files[0]);

    fetch(`${API_BASE}/upload`, { method: "POST", body: formData })
      .then(res => res.json())
      .then(data => {
        lastFilename = data.filename;
        document.getElementById("preview").innerHTML = `<p>✅ ${data.message}</p><img src='/images/${data.filename}' alt='preview'>`;
        updateUploadedList(data.filename);
      })
      .catch(err => alert("Upload failed"));
  }

  function updateUploadedList(filename) {
    const container = document.getElementById("uploads");
    const entry = document.createElement("div");
    const img = new Image();
    img.onload = () => {
      entry.innerHTML = `🖼️ ${filename} (${img.naturalWidth}x${img.naturalHeight}) <button onclick=\"deleteImage('${filename}', this)\">🗑 Delete</button> <a href='/overlays/${filename}' target='_blank'>🔍 View Overlay</a>`;
      container.appendChild(entry);
    };
    img.onerror = () => {
      entry.innerHTML = `🖼️ ${filename} (dimensions unavailable) <button onclick=\"deleteImage('${filename}', this)\">🗑 Delete</button>`;
      container.appendChild(entry);
    };
    img.src = `/images/${filename}`;
  }

  function runAnalysis() {
    fetch(`${API_BASE}/analyze`, { method: "POST" })
      .then(res => res.json())
      .then(data => {
        document.getElementById("preview").innerHTML = `<p>✅ ${data.message}</p>`;
      })
      .catch(err => alert("Analysis failed"));
  }

  function fetchReport() {
    fetch(`${API_BASE}/report`)
      .then(res => res.json())
      .then(data => {
        const flagged = data.reports ? data.reports.filter(r => r.flagged) : [];
        document.getElementById("report").innerHTML = `
          <h2>📄 Report</h2>
          <pre>${JSON.stringify(flagged, null, 2)}</pre>
        `;
      })
      .catch(err => alert("Could not fetch report"));
  }

  function resetDashboard() {
    document.getElementById("uploads").innerHTML = "";
    document.getElementById("preview").innerHTML = "";
    document.getElementById("report").innerHTML = "";
    lastFilename = "";
    window.latestOCRText = "";
  }

  function downloadReport() {
    fetch(`${API_BASE}/report`)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "forensic_report.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(() => alert("Failed to download report"));
  }

  function deleteImage(filename, btn) {
    fetch(`${API_BASE}/delete-image/${filename}`, { method: "DELETE" })
      .then(res => res.json())
      .then(data => {
        btn.parentElement.remove();
        document.getElementById("preview").innerHTML = `<p>🗑️ ${data.message}</p>`;
      })
      .catch(() => alert("Failed to delete image"));
  }
  </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_UI)

@app.route("/upload", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    try:
        from PIL import Image
        with Image.open(path) as img:
            max_dim = 1600
            if img.width > max_dim or img.height > max_dim:
                scale = min(max_dim / img.width, max_dim / img.height)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size)
                img.save(path)
    except Exception as e:
        print(f"Image resizing failed: {e}")

    return jsonify({"message": f"Image '{file.filename}' uploaded successfully.", "filename": file.filename})

@app.route("/analyze", methods=["POST"])
def analyze():
    flat_patch_summary = {}
    for filename in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            crop_receipt_region(path)
        except Exception as e:
            print(f"Cropping failed for {filename}: {e}")

        try:
            patches = detect_flat_patches(path, patch_size=40, std_threshold=2.0)
            suspicious = len(patches) > 0
            if suspicious:
                overlay_path = os.path.join(OVERLAY_FOLDER, filename)
                generate_overlay_image(path, patches, overlay_path)
                flat_patch_summary[filename] = {
                    "suspicious_flat_regions": True,
                    "overlay_image_url": f"/overlays/{filename}"
                }
        except Exception as e:
            print(f"Patch detection error for {filename}: {e}")

    process_directory(UPLOAD_FOLDER, output_report=REPORT_FILE)

    try:
        with open(REPORT_FILE, "r") as f:
            data = json.load(f)
        for entry in data.get("reports", []):
            filename = entry.get("filename")
            if filename in flat_patch_summary:
                entry["Flat_Patch_Overlay"] = flat_patch_summary[filename]
        with open(REPORT_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error updating report with patch data: {e}")

    return jsonify({"message": "Analysis complete.", "report": REPORT_FILE})

@app.route("/report", methods=["GET"])
def get_report():
    if not os.path.exists(REPORT_FILE):
        return jsonify({"error": "No report found."}), 404
    with open(REPORT_FILE, "r") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/delete-image/<filename>", methods=["DELETE"])
def delete_image(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    overlay_path = os.path.join(OVERLAY_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
        if os.path.exists(overlay_path):
            os.remove(overlay_path)
        return jsonify({"message": f"Deleted '{filename}'"})
    return jsonify({"error": "File not found"}), 404

@app.route("/images/<filename>", methods=["GET"])
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/overlays/<filename>", methods=["GET"])
def get_overlay(filename):
    return send_from_directory(OVERLAY_FOLDER, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
