# Product Image AI – Product Extraction and Background Cleaner

## New product-cleanup features
- Optional second AI segmentation pass using `u2net_human_seg` to detect and subtract hands, arms, and people from the foreground mask.
- Zero-shadow cleanup option thresholds low-confidence foreground-mask pixels that commonly contain soft cast/contact shadows.
- Adjustable mask threshold so users can balance shadow removal against preserving fine or soft product edges.
- Pure white JPG output or transparent PNG output.
- Visible product RGB pixels are retained from the source image; the AI mask controls which pixels remain visible.
- Batch upload, ZIP input, per-file error reporting, and ZIP export remain supported.

## Workflow
1. Install requirements and start the Streamlit app.
2. Choose whether to remove detected people/hands and enable zero-shadow cleanup.
3. Adjust the cleanup threshold if fine product edges are being clipped.
4. Choose pure white JPG or transparent PNG output.
5. Upload images or a ZIP and click **Extract products**.
6. Inspect every preview, then download the output ZIP.

## Important limitations
- The general `u2net` model and `u2net_human_seg` model are segmentation models, not a prompt-guided product detector. They improve removal of detected people/hands but cannot guarantee that every unrelated object or animal will be removed when it touches or resembles the foreground subject.
- If a hand covers part of a product, subtracting the hand mask can also remove the hidden product pixels. This version does not invent or reconstruct the hidden product section. Perfect recovery requires a separate generative inpainting step and may still be inaccurate.
- Zero-shadow mode removes low-confidence mask pixels. A hard shadow that the model classifies as solid foreground can remain; raising the threshold may also clip soft product edges, transparent parts, or fine details.
- The app preserves visible source pixels rather than recolouring or redesigning them. Inspect all previews, especially reflective, transparent, white, black, and intricate products.
- First-time model downloads may require internet access. Both models are downloaded/cached by `rembg` when first used.

## Setup (Windows PowerShell)
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Safety limits
- 25 MB per image
- 250 MB total uncompressed batch
- 500 files per ZIP
- 100 million pixels per image
