#!/usr/bin/env python3

import html
import shutil
import subprocess
from datetime import date
from pathlib import Path

import yaml
from weasyprint import HTML


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build"


def esc(value):
    return html.escape(str(value), quote=True)


def human(value):
    if not value:
        return "Nestanoveno"

    parsed_date = date.fromisoformat(str(value))
    return f"{parsed_date.day}. {parsed_date.month}. {parsed_date.year}"


def page(title, body, prefix="", reading=False):
    main_class = "reading" if reading else ""

    return f"""<!doctype html>
<html lang="cs">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>{esc(title)} | CCA</title>

    <link rel="stylesheet" href="{prefix}assets/web.css">
</head>
<body>
    <header>
        <nav>
            <a class="brand" href="{prefix}index.html">
                Czech Cubing Association
                <small>Dokumentace</small>
            </a>

            <a href="https://czechcubingassociation.cz/">
                Hlavní web CCA
            </a>
        </nav>
    </header>

    <main class="{main_class}">
        {body}
    </main>

    <footer>
        Czech Cubing Association ·
        <a href="mailto:info@czechcubingassociation.cz">
            info@czechcubingassociation.cz
        </a>
    </footer>
</body>
</html>
"""


# Příprava výstupní složky

if OUT.exists():
    shutil.rmtree(OUT)

OUT.mkdir()

shutil.copytree(ROOT / "assets", OUT / "assets")
shutil.copytree(ROOT / "documents", OUT / "sources")

config = yaml.safe_load(
    (ROOT / "site.yml").read_text(encoding="utf-8")
)


# Zpracování dokumentů

rows = []

for source in sorted((ROOT / "documents").glob("*.md")):
    text = source.read_text(encoding="utf-8")
    parts = text.split("---", 2)

    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"{source.name}: chybí YAML záhlaví")

    meta = yaml.safe_load(parts[1])

    required_keys = (
        "title",
        "subtitle",
        "version",
        "status",
        "owner",
        "updated",
        "effective",
    )

    for key in required_keys:
        if key not in meta:
            raise ValueError(f"{source.name}: chybí {key}")

    human(meta["updated"])
    human(meta["effective"])

    if meta["status"] != "Návrh" and not meta["effective"]:
        raise ValueError(
            f"{source.name}: schválený dokument potřebuje účinnost"
        )

    content = subprocess.run(
        ["pandoc", "--from=markdown", "--to=html5"],
        input=parts[2],
        text=True,
        check=True,
        capture_output=True,
    ).stdout

    stem = source.stem
    target = OUT / "documents"
    target.mkdir(exist_ok=True)

    metadata = f"""
        Verze {esc(meta["version"])} · {esc(meta["status"])}<br>
        Odpovědnost: {esc(meta["owner"])}<br>
        Aktualizace: {human(meta["updated"])} ·
        Účinnost: {human(meta["effective"])}
    """

    notice = (
        "Pracovní návrh. Dokument nebyl schválen a není účinný."
        if meta["status"] == "Návrh"
        else ""
    )

    # Generování PDF

    pdf_css = (ROOT / "assets/pdf.css").read_text(encoding="utf-8")

    if not notice:
        pdf_css = pdf_css.replace(" · pracovní návrh", "")

    pdf_html = f"""<!doctype html>
<html lang="cs">
<head>
    <meta charset="utf-8">

    <title>{esc(meta["title"])}</title>

    <style>
        {pdf_css}
    </style>
</head>
<body>
    

    <h1>{esc(meta["title"])}</h1>

    <p class="subtitle">
        {esc(meta["subtitle"])}
    </p>

    <div class="metadata">
        {metadata}
    </div>

    <p class="notice">
        {notice}
    </p>

    {content}
</body>
</html>
"""

    HTML(
        string=pdf_html,
        base_url=str(ROOT),
    ).write_pdf(target / f"{stem}.pdf")

    # Webová verze dokumentu

    body = f"""
        <p>
            <a href="../index.html">Všechny dokumenty</a>
            ·
            <a href="{stem}.pdf">Otevřít PDF</a>
        </p>

        <h1>{esc(meta["title"])}</h1>

        <p class="english">
            {esc(meta["subtitle"])}
        </p>

        <div class="document-meta">
            {metadata}
        </div>

        <p>{notice}</p>

        {content}
    """

    (target / f"{stem}.html").write_text(
        page(
            title=meta["title"],
            body=body,
            prefix="../",
            reading=True,
        ),
        encoding="utf-8",
    )

    # Odkaz na GitHub

    github = ""

    if config.get("repository"):
        repo = config["repository"]
        branch = config["branch"]

        github = f"""
            <a
                class="text-link"
                href="https://github.com/{esc(repo)}/blob/{esc(branch)}/documents/{esc(source.name)}"
            >
                GitHub
            </a>
        """

    # Položka dokumentu na hlavní stránce

    rows.append(
        f"""
        <article class="document">
            <div>
                <h3>
                    <a href="documents/{stem}.html">
                        {esc(meta["title"])}
                    </a>
                </h3>

                <p class="english">
                    {esc(meta["subtitle"])}
                </p>

                <div class="meta">
                    <span>Verze {esc(meta["version"])}</span>
                    <span class="status">{esc(meta["status"])}</span>
                    <span>Aktualizace {human(meta["updated"])}</span>
                    <span>Účinnost: {human(meta["effective"])}</span>
                </div>
            </div>

            <div class="actions">
                <a class="pdf" href="documents/{stem}.pdf">
                    PDF
                </a>

                <a class="text-link" href="sources/{source.name}">
                    Markdown
                </a>

                {github}
            </div>
        </article>
        """
    )


# Obsah hlavní stránky
# Po schválení dokumentů upravte upozornění podle skutečného stavu.

intro = """
    

    <p class="intro">
        Dokumenty Czech Cubing Association.
        U každého dokumentu je uvedena jeho verze, stav a datum účinnosti.
    </p>

    <h2>Dokumenty</h2>
"""


# Uložení hlavní stránky

(OUT / "index.html").write_text(
    page(
        title="Dokumentace",
        body=intro + "".join(rows),
    ),
    encoding="utf-8",
)

(OUT / ".nojekyll").touch()

print(f"Hotovo: {len(rows)} dokumenty v {OUT}")