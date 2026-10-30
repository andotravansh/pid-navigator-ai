# pid-navigator-ai
AI-powered P&amp;ID interpretation, process flow tracing, and engineering assistance.
# P&ID Navigator

An AI-assisted workspace for studying Piping and Instrumentation Diagrams (P&IDs),
aimed at process engineers and engineering students. This is an early foundation:
it supports viewing and a manually built process model. Automatic recognition is
planned, not implemented.

## Features currently implemented

- Upload PDF, PNG, JPG/JPEG and WebP files with validation (size, content type,
  corruption, encrypted PDFs, extension/content mismatch).
- PDF page selection and rendering at a chosen DPI.
- Zoom and pan inspection.
- Optional OpenCV preprocessing (grayscale, CLAHE contrast, resize, adaptive
  threshold). The original image is never modified.
- Manual entry of equipment and connections with status
  (confirmed / proposed / uncertain) and evidence records.
- Process graph (NetworkX): lookup by tag, path finding, upstream/downstream,
  disconnected groups, and a status-aware diagram.
- Educational deviation explorer using only verified, confirmed data.
- Optional Gemini Q&A grounded in the entered data.

## Planned for future releases

- OCR of equipment and instrument tags.
- Symbol and equipment detection.
- Line tracing and automatic connection candidates.
- Evidence overlays on the drawing and confidence display.
- Control-loop explanation from verified instrument data.

## Windows setup

Requirements: Windows, VS Code, Git, Python (3.14 targeted; see note below).

```powershell
cd path\to\pid-navigator-ai
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Python 3.14 note:** Not every package may publish Python 3.14 wheels at all
times. If installation fails, create the environment with Python 3.12 or 3.13:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Launch

```powershell
streamlit run app.py
```

## Run tests

```powershell
python -m pytest -q
```

Tests need no API key and no internet connection.

## Optional Gemini setup

1. Create an API key in Google AI Studio.
2. Copy the template: `Copy-Item .env.example .env`
3. Edit `.env` and set `GEMINI_API_KEY`. Never commit `.env`.
4. Optionally set `GEMINI_MODEL`. Model names change, so check Google's current list.

The integration uses the `google-genai` SDK. It was written from documentation
knowledge and has not been verified against the live API in this repository's
first release; verify it with your own key. Free-tier quotas may apply, and
rate-limit errors are reported in the UI. The drawing image is sent only if you
tick the opt-in checkbox on the AI tab.

## Architecture

```
app.py                      Streamlit UI (tabs, session state)
modules/document_reader.py  Validation, PDF/image loading, page rendering
modules/image_processor.py  Optional OpenCV preprocessing
modules/pid_parser.py       Pydantic records, tag parsing, extractor interface
modules/process_graph.py    NetworkX graph with verification statuses
modules/ai_interpreter.py   Optional Gemini wrapper (config separated from logic)
modules/safety_analyzer.py  Educational deviation explorer
tests/                      Offline unit tests
```

Data flow: upload (bytes, in memory) -> `document_reader` -> optional
`image_processor` -> viewer. The process graph is filled by manual entry today and
by extractors in the future; `ai_interpreter` and `safety_analyzer` read only that
graph.

## Known limitations

- No automatic detection of tags, symbols, equipment, or connections.
- The graph reflects only what you enter; it is not a validated plant model.
- Instrument tag parsing is syntactic (`TK-101` also matches the pattern).
- Safety explorer hazard text is generic; safeguards are matched by type/tag
  letters among verified items and need engineering review.
- Large PDFs are rendered one page at a time, capped at 9000 px on the longest side.
- Package compatibility with Python 3.14 was not verified in this repository.

## Privacy and engineering-safety disclaimer

Uploaded drawings are held in memory for the current session and are not saved to
disk by default. API keys are read from the environment and never logged or
displayed. Content is sent to Google only if you configure a key and opt in.
Do not upload confidential drawings to any external service unless your
organisation's policy allows it.

This software is for education and exploration. It is not a substitute for
qualified engineering review, HAZOP/LOPA studies, or applicable codes and
standards. Do not rely on its output for safety-critical decisions.