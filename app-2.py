from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Updated Model with an added 'notes' column
class SavedDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # <-- New notes field

@app.context_processor
def inject_saved_links():
    links = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return dict(saved_links=links)

@app.route('/')
def index():
    current_url = request.args.get('url', 'http://192.168.1.249:9000')
    return render_template('index.html', current_url=current_url)

# Updated save route to handle notes
@app.route('/save', methods=['POST'])
def save_diagram():
    url = request.form.get('url')
    description = request.form.get('description')
    notes = request.form.get('notes')
    
    if url and description:
        new_diagram = SavedDiagram(url=url, description=description, notes=notes)
        db.session.add(new_diagram)
        db.session.commit()
    
    return redirect(url_for('index', url=url))

# NEW: The Management Dashboard Screen
@app.route('/manage')
def manage():
    diagrams = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return render_template('manage.html', diagrams=diagrams)

# NEW: Route to update description and notes
@app.route('/edit/<int:id>', methods=['POST'])
def edit_diagram(id):
    diagram = SavedDiagram.query.get_or_404(id)
    diagram.description = request.form.get('description')
    diagram.url = request.form.get('url')  # <== added to commit URL modification
    diagram.notes = request.form.get('notes')
    db.session.commit()
    return redirect(url_for('manage'))

# NEW: Route to delete an entry
@app.route('/delete/<int:id>', methods=['POST'])
def delete_diagram(id):
    diagram = SavedDiagram.query.get_or_404(id)
    db.session.add(diagram)
    db.session.delete(diagram)
    db.session.commit()
    return redirect(url_for('manage'))

if __name__ == '__main__':
    with app.app_context():
        # This will safely add new columns if the schema changes
        db.create_all()
    app.run(host='0.0.0.0', port=5011, debug=True)
