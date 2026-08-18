import sys
import uvicorn

# Windows domyslnie otwiera konsole w starym codepage (np. cp1250), ktory
# nie obsluguje emoji uzywanych w logach startowych (app/config.py itp.) -
# bez tego `python run.py` wywala sie od razu z UnicodeEncodeError.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
