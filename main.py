  <div class=\"uploads\" id=\"uploads\"></div>
  <div class=\"preview\" id=\"preview\"></div>
  <div class=\"report\" id=\"report\"></div>
  <button onclick=\"resetDashboard()\">🔄 Reset</button>
  <button onclick=\"downloadReport()\">💾 Download Report</button>

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
      entry.innerHTML = `🖼️ ${filename} (${img.naturalWidth}x${img.naturalHeight}) <button onclick=\"deleteImage('${filename}', this)\">🗑 Delete</button>`;
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
    lastTaskId = "";
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
  });
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
