import os
import re
import json
import base64
import zlib
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

MMD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_diagrams')
os.makedirs(MMD_FOLDER, exist_ok=True)

class SavedDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)

@app.context_processor
def inject_saved_links():
    links = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return dict(saved_links=links)

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text.strip().replace(' ', '_'))

def export_url_to_mmd_file(diagram_id, description, url_string):
    """Parses a Mermaid editor URL state and saves the raw code to a .mmd file."""
    try:
        mermaid_code = None
        if 'pako:' in url_string:
            encoded_state = url_string.split('pako:')[1].split('?')[0].split('#')[0]
            # Convert URL-safe base64 back to standard base64 strings
            normalized_b64 = encoded_state.replace('-', '+').replace('_', '/')
            normalized_b64 += '=' * (-len(normalized_b64) % 4)
            
            compressed_data = base64.b64decode(normalized_b64)
            # -15 drops the zlib wrapper headers to parse raw pako deflate streams
            decompressed = zlib.decompress(compressed_data, -15)
            state_json = json.loads(decompressed.decode('utf-8'))
            mermaid_code = state_json.get('code', '')
            
        elif '#/edit/' in url_string and 'pako:' not in url_string:
            encoded_state = url_string.split('#/edit/')[1].split('?')[0]
            encoded_state = encoded_state.replace('-', '+').replace('_', '/')
            encoded_state += '=' * (-len(encoded_state) % 4)
            mermaid_code = base64.b64decode(encoded_state).decode('utf-8')

        if mermaid_code:
            safe_filename = f"{diagram_id}_{slugify(description)}.mmd"
            file_path = os.path.join(MMD_FOLDER, safe_filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            print(f"[SUCCESS] Written file: {safe_filename}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to extract and write .mmd file: {e}")
    return False

def convert_mmd_text_to_mermaid_url(mmd_text):
    """Encodes raw plain-text Mermaid code into a compressed Live Editor URL configuration."""
    state = {
        "code": mmd_text.strip(),
        "mermaid": '{"theme": "default"}',
        "autoSync": True,
        "updateDiagram": True,
        "updateEditor": True
    }
    
    json_bytes = json.dumps(state, ensure_ascii=False).encode('utf-8')
    
    # CRITICAL: wbits=-15 strips the zlib headers/checksums, matching JS raw Pako deflate output.
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY)
    compressed = compressor.compress(json_bytes) + compressor.flush()
    
    # Convert standard Base64 string to URL safe format used by Mermaid Live Editor
    encoded_base64 = base64.b64encode(compressed).decode('utf-8')
    url_safe_b64 = encoded_base64.replace('+', '-').replace('/', '_').replace('=', '')
    
    return f"http://192.168.1.249:9000/#/edit/pako:{url_safe_b64}"


@app.route('/')
def index():
    current_url = request.args.get('url', 'http://192.168.1.249:9000')
    return render_template('index.html', current_url=current_url)

@app.route('/save', methods=['POST'])
def save_diagram():
    url = request.form.get('url')
    description = request.form.get('description')
    notes = request.form.get('notes')
    
    if url and description:
        new_diagram = SavedDiagram(url=url, description=description, notes=notes)
        db.session.add(new_diagram)
        db.session.commit()
        export_url_to_mmd_file(new_diagram.id, new_diagram.description, url)
    
    return redirect(url_for('index', url=url))

@app.route('/upload-mmd', methods=['POST'])
def upload_mmd():
    description = request.form.get('description')
    notes = request.form.get('notes')
    uploaded_file = request.files.get('file')
    
    if uploaded_file and description:
        mmd_text = uploaded_file.read().decode('utf-8')
        generated_url = convert_mmd_text_to_mermaid_url(mmd_text)
        
        new_diagram = SavedDiagram(url=generated_url, description=description, notes=notes)
        db.session.add(new_diagram)
        db.session.commit()
        export_url_to_mmd_file(new_diagram.id, new_diagram.description, generated_url)
        
    return redirect(url_for('manage'))

@app.route('/manage')
def manage():
    diagrams = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return render_template('manage.html', diagrams=diagrams)

@app.route('/edit/<int:id>', methods=['POST'])
def edit_diagram(id):
    diagram = SavedDiagram.query.get_or_404(id)
    diagram.description = request.form.get('description')
    diagram.url = request.form.get('url')
    diagram.notes = request.form.get('notes')
    db.session.commit()
    
    export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
    return redirect(url_for('manage'))

@app.route('/delete/<int:id>', methods=['POST'])
def delete_diagram(id):
    diagram = SavedDiagram.query.get_or_404(id)
    try:
        safe_filename = f"{diagram.id}_{slugify(diagram.description)}.mmd"
        file_path = os.path.join(MMD_FOLDER, safe_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Could not delete local file: {e}")
        
    db.session.delete(diagram)
    db.session.commit()
    return redirect(url_for('manage'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5011, debug=True)
