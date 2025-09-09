from flask import Flask, request, jsonify, render_template_string
import whisper
from nlp_parser import parse_task_and_time
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Load Whisper model once
model = whisper.load_model("base")

# HTML template for the upload interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Voice Recorder Upload</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
        .result { background: #f0f0f0; padding: 15px; margin: 15px 0; border-radius: 5px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Voice Recorder Upload</h1>
    
    <div class="upload-area">
        <p>Upload your recording from the voice recorder app:</p>
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="file" id="audioFile" accept="audio/*" required>
            <br><br>
            <button type="submit">Process Audio</button>
        </form>
    </div>
    
    <div id="result"></div>

    <script>
        document.getElementById('uploadForm').onsubmit = function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('audioFile');
            const file = fileInput.files[0];
            
            if (!file) {
                alert('Please select a file');
                return;
            }
            
            const formData = new FormData();
            formData.append('audio', file);
            
            document.getElementById('result').innerHTML = '<p>Processing audio...</p>';
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('result').innerHTML = `
                        <div class="result">
                            <h3>Results:</h3>
                            <p><strong>Transcription:</strong> ${data.transcription}</p>
                            <p><strong>Task:</strong> ${data.task}</p>
                            <p><strong>Time:</strong> ${data.time}</p>
                        </div>
                    `;
                } else {
                    document.getElementById('result').innerHTML = `
                        <div class="result" style="background: #ffe6e6;">
                            <p><strong>Error:</strong> ${data.error}</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                document.getElementById('result').innerHTML = `
                    <div class="result" style="background: #ffe6e6;">
                        <p><strong>Error:</strong> ${error}</p>
                    </div>
                `;
            });
        };
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'No audio file provided'})
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Save uploaded file temporarily
        filename = secure_filename(audio_file.filename)
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        audio_file.save(temp_path)
        
        try:
            # Transcribe with Whisper
            print(f"🧠 Transcribing {filename}...")
            result = model.transcribe(temp_path, fp16=False)
            text = result["text"].strip()
            print(f"📝 Transcription: {text}")
            
            # Parse task and time
            task, time_obj = parse_task_and_time(text)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            return jsonify({
                'success': True,
                'transcription': text,
                'task': task,
                'time': str(time_obj) if time_obj else None
            })
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
            
    except Exception as e:
        print(f"❌ Error processing audio: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print("🌐 Starting Voice Recorder Web Server...")
    print("📱 Open http://localhost:5000 in your browser")
    print("🎙️ Use the web recorder app, then upload the file here")
    app.run(debug=True, host='0.0.0.0', port=5000)