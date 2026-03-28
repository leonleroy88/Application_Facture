#!/usr/bin/env python3
"""
Générateur de Factures - Parcours Homère / Léon LEROY
Application web locale pour créer des factures PDF de tutorat.
Lancez ce script puis ouvrez http://localhost:8765 dans votre navigateur.
"""

import json
import os
import sys
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from io import BytesIO
from datetime import datetime

# ── PDF generation ────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

W, H = A4

# Brand colors
NAVY    = colors.HexColor("#1a2744")
GOLD    = colors.HexColor("#c9a84c")
LIGHT   = colors.HexColor("#f7f5f0")
MUTED   = colors.HexColor("#8a8a8a")
WHITE   = colors.white
BORDER  = colors.HexColor("#ddd8ce")

FONT_REGULAR = "Helvetica"
FONT_BOLD    = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"


def build_pdf(data: dict) -> bytes:
    """Génère le PDF de la facture et retourne les bytes."""
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=50*mm, bottomMargin=22*mm,
    )

    def draw_background(canvas, doc):
        """Fond décoratif, header complet en canvas et pied de page."""
        canvas.saveState()

        # ══ HEADER ══════════════════════════════════════════════════════════
        header_h = 42*mm
        # Bande navy
        canvas.setFillColor(NAVY)
        canvas.rect(0, H - header_h, W, header_h, fill=1, stroke=0)
        # Trait doré sous le header
        canvas.setFillColor(GOLD)
        canvas.rect(0, H - header_h - 2*mm, W, 2*mm, fill=1, stroke=0)

        # -- Nom société (grand, blanc)
        canvas.setFont(FONT_BOLD, 20)
        canvas.setFillColor(WHITE)
        canvas.drawString(15*mm, H - 18*mm, "SAS Parcours Homère")

        # -- Adresse & SIRET (petit, bleuté)
        canvas.setFont(FONT_REGULAR, 7.5)
        canvas.setFillColor(colors.HexColor("#b0bcd4"))
        canvas.drawString(15*mm, H - 26*mm, "36 Quai Mullenheim  ·  67000 STRASBOURG")
        canvas.drawString(15*mm, H - 31*mm, "SIRET : 979 635 315 00018  ·  TVA : FR54979635315")

        # -- Numéro de facture (droite, doré)
        inv_number = data.get("invoice_number", "F-2024-00-00")
        issue_date = data.get("issue_date", "")
        canvas.setFont(FONT_REGULAR, 7.5)
        canvas.setFillColor(colors.HexColor("#b0bcd4"))
        canvas.drawRightString(W - 15*mm, H - 13*mm, "FACTURE")
        canvas.setFont(FONT_BOLD, 14)
        canvas.setFillColor(GOLD)
        canvas.drawRightString(W - 15*mm, H - 23*mm, inv_number)
        canvas.setFont(FONT_REGULAR, 7.5)
        canvas.setFillColor(colors.HexColor("#b0bcd4"))
        canvas.drawRightString(W - 15*mm, H - 31*mm, f"Émise le {issue_date}")

        # ══ FOOTER ══════════════════════════════════════════════════════════
        footer_h = 14*mm
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, W, footer_h, fill=1, stroke=0)
        canvas.setFillColor(GOLD)
        canvas.rect(0, footer_h, W, 0.8*mm, fill=1, stroke=0)

        # Léon LEROY (gauche)
        canvas.setFont(FONT_BOLD, 8)
        canvas.setFillColor(WHITE)
        canvas.drawString(15*mm, 5.5*mm, "Léon LEROY EI")
        canvas.setFont(FONT_REGULAR, 7)
        canvas.setFillColor(colors.HexColor("#b0bcd4"))
        canvas.drawString(15*mm, 2*mm, "SIRET : 981 015 670 00012")

        # TVA (centre)
        canvas.setFont(FONT_OBLIQUE, 6.5)
        canvas.setFillColor(colors.HexColor("#8a9ab8"))
        canvas.drawCentredString(W / 2, 3.5*mm, "TVA non applicable — Art. 293 B CGI")

        # SAS Parcours Homère (droite)
        canvas.setFont(FONT_REGULAR, 7)
        canvas.setFillColor(colors.HexColor("#b0bcd4"))
        canvas.drawRightString(W - 15*mm, 5.5*mm, "SAS Parcours Homère")
        canvas.drawRightString(W - 15*mm, 2*mm, "36 Quai Mullenheim · 67000 Strasbourg")

        canvas.restoreState()

    story = []

    # ── EMETTEUR / DESTINATAIRES ───────────────────────────────────────────
    label_style = ParagraphStyle(
        "label",
        fontName=FONT_BOLD, fontSize=6.5, textColor=GOLD,
        spaceAfter=2, leading=9,
    )
    addr_name_style = ParagraphStyle(
        "addrname",
        fontName=FONT_BOLD, fontSize=9.5, textColor=NAVY, leading=13,
    )
    addr_style = ParagraphStyle(
        "addr",
        fontName=FONT_REGULAR, fontSize=8.5, textColor=colors.HexColor("#444"),
        leading=12,
    )
    siret_style = ParagraphStyle(
        "siret",
        fontName=FONT_OBLIQUE, fontSize=7.5, textColor=MUTED, leading=10,
    )

    # Prestataire (gauche)
    prestaire_block = [
        Paragraph("PRESTATAIRE", label_style),
        Paragraph("Léon LEROY EI", addr_name_style),
        Paragraph("60 Rue Galilée<br/>SAINTE MARGUERITE", addr_style),
        Paragraph("SIRET : 981 015 670 00012", siret_style),
    ]

    # Clients (droite) - un bloc par adresse
    clients = data.get("clients", [])

    # Build client column
    client_content = [Paragraph("CLIENT(S)", label_style)]
    for i, c in enumerate(clients):
        if i > 0:
            client_content.append(Spacer(1, 4))
        client_content.append(Paragraph(c.get("name",""), addr_name_style))
        client_content.append(Paragraph(
            c.get("address","").replace("\n","<br/>"), addr_style
        ))

    def make_card(content, bg=LIGHT):
        t = Table([[content]], colWidths=[82*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg),
            ("ROUNDEDCORNERS", [4,4,4,4]),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ]))
        return t

    parties_tbl = Table(
        [[make_card(prestaire_block), Spacer(1,1), make_card(client_content)]],
        colWidths=[82*mm, 11*mm, 82*mm],
    )
    parties_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(parties_tbl)
    story.append(Spacer(1, 7*mm))

    # ── TABLEAU DES PRESTATIONS ───────────────────────────────────────────
    th_style = ParagraphStyle(
        "th", fontName=FONT_BOLD, fontSize=8, textColor=WHITE, leading=11,
    )
    th_right = ParagraphStyle(
        "th_r", fontName=FONT_BOLD, fontSize=8, textColor=WHITE,
        alignment=TA_RIGHT, leading=11,
    )
    td_style = ParagraphStyle(
        "td", fontName=FONT_REGULAR, fontSize=8.5, textColor="#333",
        leading=12,
    )
    td_right = ParagraphStyle(
        "td_r", fontName=FONT_REGULAR, fontSize=8.5, textColor="#333",
        alignment=TA_RIGHT, leading=12,
    )

    rows = []
    # Header row
    rows.append([
        Paragraph("DESCRIPTION", th_style),
        Paragraph("QTÉ", th_right),
        Paragraph("UNITÉ", th_right),
        Paragraph("PRIX HT", th_right),
        Paragraph("REMISE", th_right),
        Paragraph("MONTANT HT", th_right),
    ])

    lines = data.get("lines", [])
    total = 0.0
    for line in lines:
        qty   = float(line.get("qty", 0))
        price = float(line.get("price", 16.0))
        remise_pct = float(line.get("remise", 0))
        amount = qty * price * (1 - remise_pct/100)
        total += amount
        rows.append([
            Paragraph(line.get("description",""), td_style),
            Paragraph(f"{qty:.0f}", td_right),
            Paragraph("Heure", td_right),
            Paragraph(f"{price:.2f} €", td_right),
            Paragraph(f"{remise_pct:.0f}%", td_right),
            Paragraph(f"{amount:.2f} €", td_right),
        ])

    col_widths = [72*mm, 14*mm, 16*mm, 18*mm, 16*mm, 22*mm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    stripe = colors.HexColor("#f0ede6")
    row_styles = [
        # Header
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("ROWBACKGROUND", (0,1), (-1,-1), [WHITE, stripe]),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,0), 0.5, GOLD),
        ("LINEBELOW", (0,1), (-1,-1), 0.3, BORDER),
        ("GRID", (0,0), (-1,-1), 0, colors.white),
    ]
    tbl.setStyle(TableStyle(row_styles))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))

    # ── TOTAL ─────────────────────────────────────────────────────────────
    total_label = ParagraphStyle(
        "totlbl", fontName=FONT_BOLD, fontSize=9.5, textColor=NAVY,
        alignment=TA_RIGHT,
    )
    total_val = ParagraphStyle(
        "totval", fontName=FONT_BOLD, fontSize=14, textColor=WHITE,
        alignment=TA_RIGHT, leading=18,
    )
    tva_style = ParagraphStyle(
        "tva", fontName=FONT_OBLIQUE, fontSize=7, textColor=MUTED,
        alignment=TA_RIGHT,
    )

    total_tbl = Table(
        [
            [
                Paragraph("MONTANT TOTAL TTC", total_label),
                Table(
                    [[Paragraph(f"{total:.2f} €", total_val)]],
                    colWidths=[38*mm],
                    style=TableStyle([
                        ("BACKGROUND", (0,0), (-1,-1), NAVY),
                        ("TOPPADDING", (0,0), (-1,-1), 6),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                        ("LEFTPADDING", (0,0), (-1,-1), 8),
                        ("RIGHTPADDING", (0,0), (-1,-1), 8),
                        ("ROUNDEDCORNERS", [4,4,4,4]),
                    ])
                ),
            ]
        ],
        colWidths=[137*mm, 38*mm],
    )
    total_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("RIGHTPADDING", (0,0), (0,0), 8),
    ]))
    story.append(total_tbl)
    story.append(Paragraph(
        "TVA non applicable — Article 293 B du Code Général des Impôts",
        tva_style
    ))
    story.append(Spacer(1, 5*mm))

    # ── PAIEMENT ──────────────────────────────────────────────────────────
    info_label = ParagraphStyle(
        "il", fontName=FONT_BOLD, fontSize=7, textColor=GOLD,
        spaceAfter=1, leading=9,
    )
    info_val = ParagraphStyle(
        "iv", fontName=FONT_REGULAR, fontSize=8, textColor=NAVY, leading=11,
    )
    info_small = ParagraphStyle(
        "is", fontName=FONT_REGULAR, fontSize=7, textColor=MUTED, leading=10,
    )

    due_date   = data.get("due_date", "")
    delay_days = data.get("delay_days", "30")

    pay_left = [
        Paragraph("MODE DE RÈGLEMENT", info_label),
        Paragraph("Virement bancaire", info_val),
        Spacer(1,4),
        Paragraph("ÉCHÉANCE", info_label),
        Paragraph(due_date, info_val),
        Spacer(1,4),
        Paragraph("DÉLAI DE PAIEMENT", info_label),
        Paragraph(f"{delay_days} jours", info_val),
    ]
    pay_right = [
        Paragraph("COORDONNÉES BANCAIRES", info_label),
        Paragraph("Banque : CIC", info_val),
        Paragraph("IBAN : FR76 3008 7336 5800 0210 8040 138", info_val),
        Paragraph("BIC : CMCIFRPP", info_val),
        Spacer(1,4),
        Paragraph(
            "Escompte : Aucun · Retard : 3× taux légal · Recouvrement : 40 €",
            info_small
        ),
    ]

    pay_tbl = Table(
        [[make_card(pay_left), Spacer(1,1), make_card(pay_right)]],
        colWidths=[82*mm, 11*mm, 82*mm],
    )
    pay_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(pay_tbl)

    # ── BUILD ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=draw_background, onLaterPages=draw_background)
    return buf.getvalue()


# ── HTTP SERVER ───────────────────────────────────────────────────────────────
HTML_UI = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Générateur de Factures — Parcours Homère</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --navy: #1a2744;
    --gold: #c9a84c;
    --gold-light: #e8d4a0;
    --cream: #f7f5f0;
    --border: #ddd8ce;
    --text: #2c2c2c;
    --muted: #8a8a8a;
    --white: #ffffff;
    --danger: #c0392b;
    --success: #27ae60;
    --radius: 10px;
    --shadow: 0 4px 20px rgba(26,39,68,0.08);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--cream);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── HEADER ── */
  header {
    background: var(--navy);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    gap: 16px;
    border-bottom: 3px solid var(--gold);
  }
  .logo-dot {
    width: 10px; height: 10px;
    background: var(--gold);
    border-radius: 50%;
  }
  header h1 {
    font-family: 'Playfair Display', serif;
    color: var(--white);
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  header span {
    color: var(--gold);
    font-size: 0.78rem;
    font-weight: 400;
    margin-left: auto;
    opacity: 0.9;
  }

  /* ── LAYOUT ── */
  .container {
    max-width: 860px;
    margin: 40px auto;
    padding: 0 20px 60px;
  }

  /* ── CARD ── */
  .card {
    background: var(--white);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 28px 32px;
    margin-bottom: 22px;
    border: 1px solid var(--border);
  }
  .card-title {
    font-family: 'Playfair Display', serif;
    font-size: 1rem;
    color: var(--navy);
    font-weight: 700;
    margin-bottom: 18px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--gold-light);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-title .icon {
    width: 6px; height: 6px;
    background: var(--gold);
    border-radius: 50%;
  }

  /* ── FORM ELEMENTS ── */
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 14px;
  }
  .form-row.trio { grid-template-columns: 1fr 1fr 1fr; }
  .form-row.solo { grid-template-columns: 1fr; }

  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  label {
    font-size: 0.71rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  input, textarea, select {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    color: var(--text);
    border: 1.5px solid var(--border);
    border-radius: 7px;
    padding: 9px 12px;
    background: var(--cream);
    transition: border-color 0.2s, box-shadow 0.2s;
    outline: none;
  }
  input:focus, textarea:focus, select:focus {
    border-color: var(--gold);
    box-shadow: 0 0 0 3px rgba(201,168,76,0.12);
    background: var(--white);
  }
  textarea { resize: vertical; min-height: 64px; }

  /* ── CLIENTS ── */
  .client-list { display: flex; flex-direction: column; gap: 12px; }

  .client-item {
    border: 1.5px solid var(--border);
    border-radius: 8px;
    padding: 16px 18px;
    background: var(--cream);
    position: relative;
    transition: border-color 0.2s;
  }
  .client-item:hover { border-color: var(--gold-light); }

  .client-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .client-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--gold);
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .btn-remove {
    background: none;
    border: 1.5px solid #ddd;
    color: var(--muted);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.75rem;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
    transition: all 0.2s;
  }
  .btn-remove:hover {
    background: #fdf0ef;
    border-color: var(--danger);
    color: var(--danger);
  }

  /* ── LINES (tableau) ── */
  .lines-list { display: flex; flex-direction: column; gap: 10px; }

  .line-item {
    border: 1.5px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    background: var(--cream);
    transition: border-color 0.2s;
  }
  .line-item:hover { border-color: var(--gold-light); }

  .line-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .line-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--navy);
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  /* ── BUTTONS ── */
  .btn-add {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin-top: 12px;
    background: none;
    border: 1.5px dashed var(--gold);
    color: var(--gold);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 0.83rem;
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-add:hover {
    background: rgba(201,168,76,0.08);
    border-style: solid;
  }
  .btn-add::before { content: "+"; font-size: 1.1rem; font-weight: 700; }

  .btn-generate {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    width: 100%;
    padding: 15px;
    background: var(--navy);
    color: var(--white);
    border: none;
    border-radius: var(--radius);
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    letter-spacing: 0.03em;
    transition: all 0.25s;
    box-shadow: 0 4px 16px rgba(26,39,68,0.2);
    margin-top: 6px;
  }
  .btn-generate:hover {
    background: #243561;
    transform: translateY(-1px);
    box-shadow: 0 6px 22px rgba(26,39,68,0.28);
  }
  .btn-generate:active { transform: translateY(0); }
  .btn-generate .arrow { font-size: 1.1rem; }

  /* ── STATUS ── */
  #status {
    margin-top: 14px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.87rem;
    font-weight: 500;
    display: none;
    text-align: center;
  }
  #status.success {
    background: #edfaf3;
    color: var(--success);
    border: 1px solid #b2e8ce;
    display: block;
  }
  #status.error {
    background: #fef0ef;
    color: var(--danger);
    border: 1px solid #f0c0bb;
    display: block;
  }
  #status a { color: inherit; font-weight: 700; }

  /* ── TOTAL PREVIEW ── */
  .total-preview {
    background: var(--navy);
    color: var(--white);
    border-radius: 8px;
    padding: 14px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
  }
  .total-preview .label { font-size: 0.8rem; opacity: 0.7; }
  .total-preview .amount {
    font-family: 'Playfair Display', serif;
    font-size: 1.5rem;
    color: var(--gold);
  }

  @media (max-width: 600px) {
    .form-row, .form-row.trio { grid-template-columns: 1fr; }
    header { padding: 16px 20px; }
    .card { padding: 20px 18px; }
  }
</style>
</head>
<body>

<header>
  <div class="logo-dot"></div>
  <h1>Parcours Homère — Générateur de Factures</h1>
  <span>Léon LEROY EI</span>
</header>

<div class="container">

  <!-- INFOS FACTURE -->
  <div class="card">
    <div class="card-title"><span class="icon"></span>Informations de la facture</div>
    <div class="form-row trio">
      <div class="field">
        <label>N° de facture</label>
        <input type="text" id="invoice_number" placeholder="F-2024-12-21" value="">
      </div>
      <div class="field">
        <label>Date d'émission</label>
        <input type="date" id="issue_date" value="">
      </div>
      <div class="field">
        <label>Date d'échéance</label>
        <input type="date" id="due_date" value="">
      </div>
    </div>
  </div>

  <!-- CLIENTS -->
  <div class="card">
    <div class="card-title"><span class="icon"></span>Adresses clients</div>
    <div class="client-list" id="clientList"></div>
    <button class="btn-add" onclick="addClient()">Ajouter une adresse</button>
  </div>

  <!-- LIGNES DE PRESTATION -->
  <div class="card">
    <div class="card-title"><span class="icon"></span>Tableau des prestations</div>
    <div class="lines-list" id="linesList"></div>
    <button class="btn-add" onclick="addLine()">Ajouter une ligne</button>

    <div class="total-preview">
      <span class="label">TOTAL HT</span>
      <span class="amount" id="totalDisplay">0,00 €</span>
    </div>
  </div>

  <!-- GÉNÉRER -->
  <button class="btn-generate" onclick="generate()">
    <span class="arrow">📄</span>
    Générer la facture PDF
  </button>
  <div id="status"></div>

</div>

<script>
let clientCount = 0;
let lineCount   = 0;

// ── Init ─────────────────────────────────────────────────────────────────────
window.onload = () => {
  // Auto-date
  const today = new Date();
  const fmt = d => d.toISOString().split('T')[0];
  document.getElementById('issue_date').value = fmt(today);
  const due = new Date(today); due.setDate(due.getDate() + 30);
  document.getElementById('due_date').value = fmt(due);

  // Invoice number
  const m = String(today.getMonth()+1).padStart(2,'0');
  const y = today.getFullYear();
  document.getElementById('invoice_number').value = `F-${y}-${m}-${String(today.getDate()).padStart(2,'0')}`;

  // Default client
  addClient("Mme Aissaoui", "42 rue des platanes\n67 640 Fergersheim");
  addClient("M et Mme Chouteau", "2 rue Salzmann\n67 000 Strasbourg");

  // Default lines
  addLine("Heure de soutien en Terminale Lycée\nLes Vendredis 06 – 13 – 20 Décembre", 6, 16);
  addLine("Heure de soutien en Première Lycée\nLes Jeudis 05 – 12 – 19 Décembre", 6, 16);
};

// ── Clients ──────────────────────────────────────────────────────────────────
function addClient(name="", address="") {
  clientCount++;
  const id = clientCount;
  const div = document.createElement('div');
  div.className = 'client-item';
  div.id = `client-${id}`;
  div.innerHTML = `
    <div class="client-header">
      <span class="client-label">Adresse ${id}</span>
      <button class="btn-remove" onclick="removeClient(${id})">Supprimer</button>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Nom / Intitulé</label>
        <input type="text" id="c_name_${id}" placeholder="M. et Mme Dupont" value="${escHtml(name)}">
      </div>
      <div class="field">
        <label>Adresse complète</label>
        <textarea id="c_addr_${id}" placeholder="12 rue Example&#10;67000 Strasbourg">${escHtml(address)}</textarea>
      </div>
    </div>`;
  document.getElementById('clientList').appendChild(div);
}

function removeClient(id) {
  const el = document.getElementById(`client-${id}`);
  if (el) el.remove();
}

function getClients() {
  const items = [];
  document.querySelectorAll('.client-item').forEach(el => {
    const idMatch = el.id.match(/client-(\d+)/);
    if (!idMatch) return;
    const i = idMatch[1];
    items.push({
      name: document.getElementById(`c_name_${i}`)?.value || "",
      address: document.getElementById(`c_addr_${i}`)?.value || "",
    });
  });
  return items;
}

// ── Lines ────────────────────────────────────────────────────────────────────
function addLine(desc="", qty=1, price=16, remise=0) {
  lineCount++;
  const id = lineCount;
  const div = document.createElement('div');
  div.className = 'line-item';
  div.id = `line-${id}`;
  div.innerHTML = `
    <div class="line-header">
      <span class="line-label">Ligne ${id}</span>
      <button class="btn-remove" onclick="removeLine(${id})">Supprimer</button>
    </div>
    <div class="form-row solo">
      <div class="field">
        <label>Description</label>
        <textarea id="l_desc_${id}" rows="2" oninput="updateTotal()">${escHtml(desc)}</textarea>
      </div>
    </div>
    <div class="form-row trio">
      <div class="field">
        <label>Quantité (heures)</label>
        <input type="number" id="l_qty_${id}" value="${qty}" min="0" step="0.5" oninput="updateTotal()">
      </div>
      <div class="field">
        <label>Prix unitaire HT (€)</label>
        <input type="number" id="l_price_${id}" value="${price}" min="0" step="0.5" oninput="updateTotal()">
      </div>
      <div class="field">
        <label>Remise (%)</label>
        <input type="number" id="l_remise_${id}" value="${remise}" min="0" max="100" oninput="updateTotal()">
      </div>
    </div>`;
  document.getElementById('linesList').appendChild(div);
  updateTotal();
}

function removeLine(id) {
  const el = document.getElementById(`line-${id}`);
  if (el) { el.remove(); updateTotal(); }
}

function getLines() {
  const items = [];
  document.querySelectorAll('.line-item').forEach(el => {
    const idMatch = el.id.match(/line-(\d+)/);
    if (!idMatch) return;
    const i = idMatch[1];
    items.push({
      description: document.getElementById(`l_desc_${i}`)?.value || "",
      qty:    parseFloat(document.getElementById(`l_qty_${i}`)?.value) || 0,
      price:  parseFloat(document.getElementById(`l_price_${i}`)?.value) || 0,
      remise: parseFloat(document.getElementById(`l_remise_${i}`)?.value) || 0,
    });
  });
  return items;
}

function updateTotal() {
  let total = 0;
  getLines().forEach(l => {
    total += l.qty * l.price * (1 - l.remise/100);
  });
  document.getElementById('totalDisplay').textContent =
    total.toLocaleString('fr-FR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' €';
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function generate() {
  const status = document.getElementById('status');
  status.className = '';
  status.style.display = 'none';

  const issueDateRaw = document.getElementById('issue_date').value;
  const dueDateRaw   = document.getElementById('due_date').value;

  const payload = {
    invoice_number: document.getElementById('invoice_number').value,
    issue_date: formatDateFr(issueDateRaw),
    due_date:   formatDateFr(dueDateRaw),
    delay_days: "30",
    clients: getClients(),
    lines:   getLines(),
  };

  try {
    const resp = await fetch('/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });

    if (resp.ok) {
      const blob = await resp.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url;
      a.download = `${payload.invoice_number || 'facture'}.pdf`;
      a.click();
      status.className  = 'success';
      status.innerHTML  = '✓ Facture générée avec succès ! Le PDF a été téléchargé.';
      status.style.display = 'block';
    } else {
      const err = await resp.text();
      throw new Error(err);
    }
  } catch(e) {
    status.className  = 'error';
    status.innerHTML  = '✗ Erreur : ' + e.message;
    status.style.display = 'block';
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatDateFr(iso) {
  if (!iso) return '';
  const [y,m,d] = iso.split('-');
  const months = ['janvier','février','mars','avril','mai','juin',
                  'juillet','août','septembre','octobre','novembre','décembre'];
  return `${parseInt(d)} ${months[parseInt(m)-1]} ${y}`;
}

function escHtml(str) {
  return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_UI.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body)
                pdf  = build_pdf(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition",
                    f'attachment; filename="{data.get("invoice_number","facture")}.pdf"')
                self.send_header("Content-Length", str(len(pdf)))
                self.end_headers()
                self.wfile.write(pdf)
            except Exception as e:
                msg = str(e).encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
        else:
            self.send_response(404)
            self.end_headers()


def main():
    PORT = 8765
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"""
╔══════════════════════════════════════════════════╗
║   Générateur de Factures — Parcours Homère       ║
║   Léon LEROY EI                                  ║
╠══════════════════════════════════════════════════╣
║  ✓ Serveur démarré sur {url}     ║
║  ✓ Ouverture automatique du navigateur...        ║
║                                                  ║
║  Pour arrêter : Ctrl+C                           ║
╚══════════════════════════════════════════════════╝
""")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Application arrêtée.")


if __name__ == "__main__":
    main()
