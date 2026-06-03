import requests
from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# SQLite database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model to store saved Mermaid links
class SavedDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Diagram {self.description}>'

# Inject saved links globally into the base layout's navbar dropdown
@app.context_processor
def inject_saved_links():
    links = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return dict(saved_links=links)

@app.route('/')
def index():
    # If a saved diagram URL is selected, we pass it along. 
    # Otherwise, default to the local reverse proxy base.
    current_url = request.args.get('url', '/mermaid-proxy/')
    return render_template('index.html', current_url=current_url)

@app.route('/save', methods=['POST'])
def save_diagram():
    url = request.form.get('url')
    description = request.form.get('description')
    
    if url and description:
        new_diagram = SavedDiagram(url=url, description=description)
        db.session.add(new_diagram)
        db.session.commit()
    
    # Redirect back home while preserving the layout state you just saved
    return redirect(url_for('index', url=url))

# REVERSE PROXY ROUTE: Intercepts Mermaid, strips X-Frame-Options/CSP, and renders safely
@app.route('/mermaid-proxy/', defaults={'path': ''})
@app.route('/mermaid-proxy/<path:path>')
def mermaid_proxy(path):
    mermaid_base_url = "http://192.168.1.249:9000"
    target_url = f"{mermaid_base_url}/{path}"
    
    # Append query string parameters/states if present
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"
        
    try:
        # Fetch the resource directly from your local Mermaid server
        resp = requests.get(target_url, headers={key: value for key, value in request.headers if key != 'Host'})
        
        # Exclude headers that block iframe framing or cause encoding conflicts
        excluded_headers = [
            'content-encoding', 'content-length', 'transfer-encoding', 
            'connection', 'x-frame-options', 'content-security-policy'
        ]
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
    except requests.exceptions.RequestException as e:
        return Response(f"Failed to connect to Mermaid server at {mermaid_base_url}: {e}", status=502)

if __name__ == '__main__':
    # Initialize the SQLite database tables
    with app.app_context():
        db.create_all()
    # Runs the application on all interfaces (publicly accessible on port 5001)
    app.run(host='0.0.0.0', port=5010, debug=True)
