"""UDA and LAN routing for Mermaid Dashboard."""
from app import app, db

def test_prefix_and_lan():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    with app.app_context():
        db.create_all()
        client=app.test_client()
        for route in ("/", "/manage"):
            local=client.get(route)
            assert local.status_code == 200
            headers={"X-Forwarded-Prefix":"/apps/mermaid-dashboard",
                     "X-Forwarded-Host":"tanyaanne.ddns.net",
                     "X-Forwarded-Proto":"https"}
            proxied=client.get(route, headers=headers)
            assert proxied.status_code == 200
            html=proxied.get_data(as_text=True)
            assert '<base href="/apps/mermaid-dashboard/">' in html
            assert 'href="/manage"' not in html
        assert '/apps/mermaid-dashboard/manage' in client.get("/", headers=headers).get_data(as_text=True)


def test_canvas_uses_public_editor_instead_of_dead_lan_port():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        client = app.test_client()
        response = client.get("/")
        html = response.get_data(as_text=True)
        assert 'src="/apps/mermaid-display-app/"' in html
        assert '192.168.1.249:9000' not in html


def test_legacy_editor_link_is_wrapped_by_public_editor():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        client = app.test_client()
        response = client.get("/?url=http://192.168.1.249:9000/%23/edit/pako:abc")
        html = response.get_data(as_text=True)
        assert '/apps/mermaid-display-app/?url=' in html
        assert 'pako%3Aabc' in html
