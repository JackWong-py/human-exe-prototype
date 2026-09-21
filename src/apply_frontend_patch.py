import shutil
import sys

PATH = "app/api.py"
text = open(PATH, encoding="utf-8").read()
if "DIST = " in text:
    print("app/api.py already serves the React app. Nothing to do.")
    sys.exit(0)

edits = [
    ("from fastapi.responses import HTMLResponse, JSONResponse\n",
     "from fastapi.responses import FileResponse, HTMLResponse, JSONResponse\nfrom fastapi.staticfiles import StaticFiles\n"),
    ("app.include_router(suggest_router)\n",
     "app.include_router(suggest_router)\n\n"
     "# The React app, built with `npm run build` into ./dist. If it is not built, the plain pages still work.\n"
     "DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), \"dist\")\n"
     "if os.path.isdir(os.path.join(DIST, \"assets\")):\n"
     "    app.mount(\"/assets\", StaticFiles(directory=os.path.join(DIST, \"assets\")), name=\"assets\")\n"),
    ('@app.get("/", include_in_schema=False)\ndef index():\n    return report()\n',
     '@app.get("/", include_in_schema=False)\ndef index():\n'
     '    page = os.path.join(DIST, "index.html")\n'
     '    if os.path.exists(page):\n'
     '        return FileResponse(page)\n'
     '    return report()\n\n\n'
     '@app.get("/favicon.svg", include_in_schema=False)\ndef favicon():\n'
     '    icon = os.path.join(DIST, "favicon.svg")\n'
     '    if os.path.exists(icon):\n'
     '        return FileResponse(icon)\n'
     '    return JSONResponse({"error": "no icon"}, status_code=404)\n'),
]
for old, new in edits:
    if old not in text:
        sys.exit("app/api.py is not the expected version (could not find:\n" + old + ")\nNothing was changed. Ask E for help.")
    text = text.replace(old, new, 1)

shutil.copyfile(PATH, PATH + ".bak")
open(PATH, "w", encoding="utf-8").write(text)
print("app/api.py updated. Backup: app/api.py.bak")
print("Next: npm run build, then start the backend and open http://localhost:8000/")