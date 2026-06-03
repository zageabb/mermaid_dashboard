from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Using SQLite for simplicity; creates a 'database.db' file locally
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model to store your Mermaid URLs and descriptions
class SavedDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Diagram {self.description}>'

# Context processor to make saved links available to the navbar dropdown globally
@app.context_processor
def inject_saved_links():
    links = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return dict(saved_links=links)

@app.route('/')
def index():
    # Get the URL to load from query string, default to your local Mermaid home
    current_url = request.args.get('url', 'http://192.168.1.249:9000')
    return render_template('index.html', current_url=current_url)

@app.route('/save', methods=['POST'])
def save_diagram():
    url = request.form.get('url')
    description = request.form.get('description')
    
    if url and description:
        new_diagram = SavedDiagram(url=url, description=description)
        db.session.add(new_diagram)
        db.session.commit()
    
    # Redirect back to the index, keeping the current URL loaded
    return redirect(url_for('index', url=url))

if __name__ == '__main__':
    # Create the database tables if they don't exist
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=11000)
