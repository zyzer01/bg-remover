from flask import Flask, render_template, request, send_file, url_for
import os
import io
import uuid
from PIL import Image, ImageFilter
from rembg import remove, new_session
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'static/outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize rembg session with improved model
session = new_session("u2net_human_seg")  # You can also try "u2netp" or "u2net" for different quality/speed

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/remove_background', methods=['POST'])
def remove_background():
    if 'file' not in request.files:
        return render_template('index.html', error='No file selected')
    
    file = request.files['file']
    
    if file.filename == '':
        return render_template('index.html', error='No file selected')
    
    if file and allowed_file(file.filename):
        try:
            # Read the image
            input_image = Image.open(file.stream)
            
            # Get parameters from form
            alpha_matting = 'alpha_matting' in request.form
            alpha_matting_foreground_threshold = int(request.form.get('foreground_threshold', 240))
            alpha_matting_background_threshold = int(request.form.get('background_threshold', 10))
            alpha_matting_erode_size = int(request.form.get('erode_size', 10))
            
            post_process = request.form.get('post_process', 'none')
            
            # Remove background with improved parameters
            output_image = remove(
                input_image,
                session=session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
                alpha_matting_background_threshold=alpha_matting_background_threshold,
                alpha_matting_erode_size=alpha_matting_erode_size
            )
            
            # Post-processing for edge improvement
            if post_process == 'sharpen':
                # Apply a sharpening filter to the alpha channel
                r, g, b, a = output_image.split()
                a = a.filter(ImageFilter.SHARPEN)
                output_image = Image.merge('RGBA', (r, g, b, a))
            elif post_process == 'smooth':
                # Smooth the alpha channel edges
                r, g, b, a = output_image.split()
                a = a.filter(ImageFilter.GaussianBlur(0.5))
                output_image = Image.merge('RGBA', (r, g, b, a))
            elif post_process == 'enhance':
                # Edge enhancement
                r, g, b, a = output_image.split()
                a = a.filter(ImageFilter.EDGE_ENHANCE)
                output_image = Image.merge('RGBA', (r, g, b, a))
            
            # Generate unique filename
            filename = f"{uuid.uuid4().hex}.png"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            
            # Save the output image with maximum quality
            output_image.save(output_path, format="PNG", quality=100)
            
            # Return the result page
            return render_template('result.html', 
                                  image_path=url_for('static', filename=f'outputs/{filename}'),
                                  filename=filename)
        except Exception as e:
            return render_template('index.html', error=f'Error processing image: {str(e)}')
    
    return render_template('index.html', error='Invalid file type. Please upload a PNG or JPEG file.')

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)