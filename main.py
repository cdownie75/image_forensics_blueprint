from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
import json
from image_analysis_pipeline import process_directory
from celery_worker import run_ocr

app = Flask(__name__)
UPLOAD_FOLDER = "images"
REPORT_FILE = "forensic_reports.json"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_UI = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Image Forensics UI</title>
  <style>
    body { font-family: sans-serif; padding: 2em; max-width: 700px; margin: auto; }
    input[type=\"file\"] { margin-bottom: 1em; }
    button { margin: 0.5em 0; padding: 0.5em 1em; }
    .preview img { max-width: 100%; margin: 1em 0; border: 1px solid #ccc; border-radius: 6px; }
    pre { background: #f4f4f4; padding: 1em; border-radius: 5px; overflow-x: auto; }
    #spinner { display: none; margin-top: 10px; font-style: italic; color: gray; }
  </style>
</head>
<body>
  <h1>🔍 Image Forensics Dashboard</h1>
  <input type=\"file\" id=\"imageInput\" accept=\"image/*\">
  <br>
  <button onclick=\"uploadImage()\">📤 Upload Image</button>
  <button onclick=\"runAnalysis()\">🧪 Run Analysis</button>
  <button onclick=\"fetchReport()\">📄 View Report</button>
  <button onclick=\"runOCR()\">🔠 Run OCR</button>

  <div id=\"spinner\">⏳ Processing OCR...</div>
  <div class=\"uploads\" id=\"uploads\"></div>
  <div class=\"preview\" id=\"preview\"></div>
  <div class=\"report\" id=\"report\"></div>
  <button onclick=\"resetDashboard()\">🔄 Reset</button>
  <button onclick=\"downloadOCR()\">💾 Download OCR Result</button>

  <script>
  const API_BASE = "";
  let lastFilename = "";
  let lastTaskId = "";

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
      entry.innerHTML = `🖼️ ${filename} (${img.naturalWidth}x${img.naturalHeight}) <button onclick="deleteImage('${filename}', this)">🗑 Delete</button>`;
      container.appendChild(entry);
    };
    img.onerror = () => {
      entry.innerHTML = `🖼️ ${filename} (dimensions unavailable) <button onclick="deleteImage('${filename}', this)">🗑 Delete</button>`;
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
        const flagged = data.reports.filter(r => r.flagged);
        document.getElementById("report").innerHTML = `
          <h2>📄 Report</h2>
          <pre>${JSON.stringify(flagged, null, 2)}</pre>
        `;
      })
      .catch(err => alert("Could not fetch report"));
  }

  function runOCR() {
    if (!lastFilename) return alert("Upload an image first.");
    document.getElementById("spinner").style.display = "block";

    fetch(`${API_BASE}/ocr`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: lastFilename })
    })
      .then(res => res.json())
      .then(data => {
        lastTaskId = data.task_id;
        setTimeout(checkOCRStatus, 3000);
      });
  }

  function checkOCRStatus() {
    if (!lastTaskId) return;
    fetch(`${API_BASE}/ocr-status/${lastTaskId}`)
      .then(res => res.json())
      .then(data => {
        if (data.status === "success") {
          document.getElementById("spinner").style.display = "none";
          window.latestOCRText = data.result;
          document.getElementById("report").innerHTML = `<h2>🔠 OCR Result</h2><pre>${data.result}</pre>`;
        } else if (data.status === "pending") {
          setTimeout(checkOCRStatus, 3000);
        } else {
          document.getElementById("spinner").style.display = "none";
          document.getElementById("report").innerHTML = `<p>❌ OCR failed: ${data.error || data.status}</p>`;
        }
      });
  }

  function resetDashboard() {
    document.getElementById("uploads").innerHTML = "";
    document.getElementById("preview").innerHTML = "";
    document.getElementById("report").innerHTML = "";
    lastFilename = "";
    lastTaskId = "";
    window.latestOCRText = "";
  }

  function downloadOCR() {
    const text = window.latestOCRText;
    if (!text) return alert("No OCR result to download");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${lastFilename || 'ocr_result'}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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

    # Resize image to 25% of original size to save memory
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
    # Resize all images to max 1600px before re-analysis
    from PIL import Image
    for filename in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            with Image.open(path) as img:
                max_dim = 1600
                if img.width > max_dim or img.height > max_dim:
                    scale = min(max_dim / img.width, max_dim / img.height)
                    new_size = (int(img.width * scale), int(img.height * scale))
                    img = img.resize(new_size)
                    img.save(path)
        except Exception as e:
            print(f"Resize error for {filename}: {e}")

    process_directory(UPLOAD_FOLDER, output_report=REPORT_FILE)
    return jsonify({"message": "Analysis complete.", "report": REPORT_FILE})

@app.route("/report", methods=["GET"])
def get_report():
    if not os.path.exists(REPORT_FILE):
        return jsonify({"error": "No report found."}), 404
    with open(REPORT_FILE, "r") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/ocr", methods=["POST"])
def start_ocr():
    filename = request.json.get("filename")
    if not filename:
        return jsonify({"error": "Filename not provided"}), 400

    image_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404

    task = run_ocr.delay(image_path)
    return jsonify({"message": "OCR task started", "task_id": task.id})

@app.route("/ocr-status/<task_id>", methods=["GET"])
def ocr_status(task_id):
    task = run_ocr.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"status": "pending"})
    elif task.state == "SUCCESS":
        return jsonify({"status": "success", "result": task.result})
    elif task.state == "FAILURE":
        return jsonify({"status": "failure", "error": str(task.info)})
    else:
        return jsonify({"status": task.state})

@app.route("/delete-image/<filename>", methods=["DELETE"])
def delete_image(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"message": f"Deleted '{filename}'"})
    return jsonify({"error": "File not found"}), 404

@app.route("/images/<filename>", methods=["GET"])
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
