"""Rebuild fictional, text-based invoices from the sample source data."""
import argparse
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--sample', help='Build only one sample id')
args = parser.parse_args()
samples = json.loads((ROOT / 'data/samples.json').read_text())
for sample in samples:
    if args.sample and sample['id'] != args.sample:
        continue
    c = canvas.Canvas(str(OUT / f"{sample['id']}-invoice.pdf"), pagesize=(612, 792))
    c.setTitle(f"Fictional invoice - {sample['name']}")
    c.setFillColor(HexColor('#f4efe6')); c.rect(0, 0, 612, 792, fill=1, stroke=0)
    c.setFillColor(HexColor('#4b1521')); c.rect(0, 636, 612, 156, fill=1, stroke=0)
    c.setFillColor(HexColor('#fff3e7')); c.setFont('Helvetica-Bold', 10)
    c.drawString(44, 750, 'FICTIONAL DEMO INVOICE')
    c.setFont('Times-Roman', 27); c.drawString(44, 700, sample['invoice'].splitlines()[1])
    c.setFont('Helvetica', 11); c.drawString(44, 667, 'Prepared for classroom testing only')
    y = 586
    for line in sample['invoice'].splitlines()[2:]:
        c.setFillColor(HexColor('#201d1b')); c.setFont('Helvetica', 12)
        if line.startswith('Total:'):
            c.setFillColor(HexColor('#dfe7dc')); c.rect(36, y-13, 540, 37, fill=1, stroke=0)
            c.setFillColor(HexColor('#4b1521')); c.setFont('Helvetica-Bold', 15)
        c.drawString(44, y, line); y -= 44
    c.setFillColor(HexColor('#6d655d')); c.setFont('Helvetica', 9)
    c.drawString(44, 66, 'All organizations and payment details are invented. Do not submit payment.')
    c.drawString(44, 48, 'Payment Request Checker | Gen AI and Business'); c.drawRightString(568, 48, '1 / 1')
    c.save()
