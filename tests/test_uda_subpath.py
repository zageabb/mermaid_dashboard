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
