import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Railway sets PORT automatically; fall back to FLASK_PORT then 5000 for local dev.
    host  = os.environ.get("FLASK_HOST", "0.0.0.0")
    port  = int(os.environ.get("PORT") or os.environ.get("FLASK_PORT") or 5000)
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
    