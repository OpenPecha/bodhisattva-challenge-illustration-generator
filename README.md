<h1 align="center">
  <br>
  <a href="https://openpecha.org"><img src="https://avatars.githubusercontent.com/u/82142807?s=400&u=19e108a15566f3a1449bafb03b8dd706a72aebcd&v=4" alt="OpenPecha" width="150"></a>
  <br>
</h1>

## Bodhisattva Challenge Illustration Generator

Tooling that turns daily Bodhisattva Challenge verse/practice text into finished
social-media post images: batch-generates line-art illustrations with Gemini,
then composes them with text into branded 1080x1920 posts (English, Tibetan,
and Hindi).

## Owner(s)
- [@ngawangtrinley](https://github.com/ngawangtrinley)
- [@mikkokotila](https://github.com/mikkokotila)
- [@evanyerburgh](https://github.com/evanyerburgh)


## Table of contents
<p align="center">
  <a href="#project-description">Project description</a> •
  <a href="#who-this-project-is-for">Who this project is for</a> •
  <a href="#project-dependencies">Project dependencies</a> •
  <a href="#instructions-for-use">Instructions for use</a> •
  <a href="#contributing-guidelines">Contributing guidelines</a> •
  <a href="#how-to-get-help">How to get help</a> •
  <a href="#terms-of-use">Terms of use</a>
</p>
<hr>

## Project description

This project automates production of the daily **Bodhisattva Challenge** posts
for [@WeBuddhist](https://twitter.com/WeBuddhist). It has three stages, each a
standalone CLI script under `src/illustration_generator/`:

1. **`generate_illustrations.py`** — Parses a `Verse_and_challenge.md` file
   (verses in Tibetan with English practice/explanation), submits a batch job
   to Gemini 3 Pro Image to generate three line-art illustrations per verse
   (verse-only, practice-only, combined), and saves them per-verse with
   transparent backgrounds.
2. **`compose_challenge_post.py`** — Composes a single-language (English)
   daily "challenge" post: title, bold practice, illustration, left-aligned
   verse with right-aligned verse id citation, and the `@WeBuddhist` handle,
   rendered onto a background template.
3. **`compose_multilang_post.py`** — Composes the same style of post in three
   languages (English, Tibetan, Hindi) from one `day_NN_sharable_image_text.md`
   file containing all three language sections, producing one image per
   language under `data/output/<language>/day{N}.png`.
4. **`generate_preview_post.py`** — Generates an alternate "preview" post
   layout (verse + explanation + bottom-anchored illustration) matching a
   reference template, with an optional `--compare` mode to measure pixel
   difference against a reference image.


## Who this project is for
This project is intended for the OpenPecha/WeBuddhist team producing the daily
Bodhisattva Challenge social media content, who want to generate illustrations
and compose branded post images from markdown source text.


## Project dependencies
Before using this project, ensure you have:
* Python >= 3.8 (Tibetan/Hindi text uses `list[str]`/`str | None` syntax, so 3.10+ recommended)
* A **Gemini API key** (set as the `GEMINI_KEY` environment variable) for `generate_illustrations.py`
* **Pillow built with `libraqm`** for correct Tibetan/Devanagari text shaping
  (used by `compose_multilang_post.py`). Verify with:
  ```bash
  python -c "import PIL.features as f; print(f.check('raqm'))"
  ```
* Bundled fonts under `src/illustration_generator/fonts/` (already included in the repo)


## Instructions for use

### Install
```bash
pip install -e .
# or with dev/test dependencies
pip install -e ".[dev]"
```

### Configure
Export your Gemini API key (only required for `generate_illustrations.py`):
```bash
export GEMINI_KEY="your-api-key-here"
```

### Run

**1. Generate illustrations from a verse markdown file:**
```bash
python -m illustration_generator.generate_illustrations path/to/Verse_and_challenge.md
```
Creates one `verse_<N>/` folder per verse next to the markdown file, each with
`illustration_1.png` (verse), `illustration_2.png` (practice), and
`illustration_3.png` (combined), all with transparent backgrounds.

**2. Compose a single-language challenge post:**
```bash
# from a daily folder containing a 06_July.md and one illustration PNG
python -m illustration_generator.compose_challenge_post path/to/06_July_folder

# or pass files explicitly
python -m illustration_generator.compose_challenge_post path/to/06_July.md path/to/illustration.png
```

**3. Compose multi-language (English/Tibetan/Hindi) posts:**
```bash
python -m illustration_generator.compose_multilang_post \
  path/to/day_20_sharable_image_text.md \
  path/to/illustration_or_dir \
  --output path/to/output_dir
```
Outputs `output_dir/english/day20.png`, `output_dir/tibetan/day20.png`, and
`output_dir/hindi/day20.png` (default output dir is `data/output/`).

**4. Generate a preview-style post:**
```bash
python -m illustration_generator.generate_preview_post path/to/06_July_folder
# optionally compare against a reference image
python -m illustration_generator.generate_preview_post path/to/06_July_folder --compare data/17.jpg
```

### Troubleshoot

<table>
  <tr>
   <td>Issue</td>
   <td>Solution</td>
  </tr>
  <tr>
   <td><code>GEMINI_KEY environment variable not set</code></td>
   <td>Export <code>GEMINI_KEY</code> with a valid Gemini API key before running <code>generate_illustrations.py</code>.</td>
  </tr>
  <tr>
   <td>Tibetan/Devanagari text renders incorrectly (no stacking/conjuncts)</td>
   <td>Rebuild Pillow with <code>libraqm</code> support; verify with the snippet in <a href="#project-dependencies">Project dependencies</a>.</td>
  </tr>
  <tr>
   <td><code>No date markdown file like 06_July.md found</code> / <code>Multiple date markdown files found</code></td>
   <td>Ensure the target folder has exactly one markdown file matching the expected naming pattern.</td>
  </tr>
  <tr>
   <td><code>Missing required field(s)</code> when parsing markdown</td>
   <td>Confirm the markdown file has the expected headings (e.g. <code>Practice of the day</code>, <code>Verse of the day</code>, <code>Verse id</code>).</td>
  </tr>
</table>


## Contributing guidelines
If you'd like to help out, check out our [contributing guidelines](/CONTRIBUTING.md).


## How to get help
* File an issue.
* Email us at openpecha[at]gmail.com.
* Join our [discord](https://discord.com/invite/7GFpPFSTeA).


## Terms of use
This project is licensed under the [MIT License](/LICENSE.md).
