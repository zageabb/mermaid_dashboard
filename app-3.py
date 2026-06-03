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
        if 'pako:' in url_string:
            encoded_state = url_string.split('pako:')[1].split('?')[0].split('#')[0]
            encoded_state += '=' * (-len(encoded_state) % 4)
            compressed_data = base64.urlsafe_b64decode(encoded_state)
            decompressed = zlib.decompress(compressed_data, -15)
            state_json = json.loads(decompressed.decode('utf-8'))
            mermaid_code = state_json.get('code', '')
        elif '#/edit/' in url_string and 'pako:' not in url_string:
            encoded_state = url_string.split('#/edit/')[1].split('?')[0]
            encoded_state += '=' * (-len(encoded_state) % 4)
            mermaid_code = base64.b64decode(encoded_state).decode('utf-8')
        else:
            return False

        if mermaid_code:
            safe_filename = f"{diagram_id}_{slugify(description)}.mmd"
            with open(os.path.join(MMD_FOLDER, safe_filename), 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            return True
    except Exception as e:
        print(f"Error exporting file: {e}")
    return False

def convert_mmd_text_to_mermaid_url(mmd_text):
    """Encodes raw plain-text Mermaid code into a compressed Live Editor URL configuration."""
    # This matches the standard structure expected by the Mermaid Live Editor state machine
    state = {
        "code": mmd_text.strip(),
        "mermaid": '{"theme": "default"}',
        "autoSync": True,
        "updateDiagram": True
    }
    
    # Serialize to JSON, compress using deflate (pako), and encode to safe base64
    json_str = json.dumps(state, ensure_ascii=False).encode('utf-8')
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(json_str) + compressor.flush()
    encoded_base64 = base64.urlsafe_b64encode(compressed).decode('utf-8').replace('=', '')
    
    # Return full target editor URL path string
    return f"http://192.168.1.249:9000/#/edit/pako:{encoded_base64}"


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

# NEW: Route to accept file uploads, convert to state URL, and log in DB
@app.route('/upload-mmd', methods=['POST'])
def upload_mmd():
    description = request.form.get('description')
    notes = request.form.get('notes')
    uploaded_file = request.files.get('file')
    
    if uploaded_file and description:
        # Read plain-text contents of uploaded file
        mmd_text = uploaded_file.read().decode('utf-8')
        
        # Reverse compilation step: text -> compressed URL path string
        generated_url = convert_mmd_text_to_mermaid_url(mmd_text)
        
        # Save straight to tracking index
        new_diagram = SavedDiagram(url=generated_url, description=description, notes=notes)
        db.session.add(new_diagram)
        db.session.commit()
        
        # Re-save file inside backend storage workspace properly named
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
