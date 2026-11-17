"""Pure-Python standards-compliant PDF 1.4 report generator for MassCommAI analytics."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.schemas.analytics import (
    GlobalKPIsResponse,
    PerformanceBreakdownsResponse,
    CampaignFunnelResponse,
    AIInsightItem,
)


def _escape_pdf(text: str) -> str:
    """Escapes special characters in PDF literal text and sanitizes unsupported unicode."""
    if not text:
        return ""
    # Standardize unicode characters into standard Latin-1 representation
    cleaned = (
        str(text)
        .replace("\u2022", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("\t", " ")
        .replace("\n", " ")
    )
    # Escape PDF parenthesis and backslashes
    escaped = cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped


def generate_analytics_pdf(
    kpis: GlobalKPIsResponse,
    breakdowns: Optional[PerformanceBreakdownsResponse] = None,
    funnel: Optional[CampaignFunnelResponse] = None,
    insights: Optional[List[AIInsightItem]] = None,
    filter_params: Optional[Dict[str, Any]] = None,
    campaign_name: Optional[str] = None,
) -> bytes:
    """
    Generates an executive-ready, multi-section PDF 1.4 report byte-stream.
    Includes KPIs, channel breakdown, language metrics, conversion funnel, and AI insights.
    Guarantees zero external binary dependencies.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    filters_desc = "Scope: Full Historical Window | All Channels | All Languages"
    if filter_params:
        parts = []
        if filter_params.get("start_date") or filter_params.get("end_date"):
            s = filter_params.get("start_date", "Beginning")
            e = filter_params.get("end_date", "Present")
            parts.append(f"Window: {s} to {e}")
        if filter_params.get("campaign_id"):
            parts.append(f"Campaign ID: #{filter_params['campaign_id']}")
        if filter_params.get("channel"):
            parts.append(f"Channel: {filter_params['channel']}")
        if filter_params.get("language"):
            parts.append(f"Language: {filter_params['language']}")
        if filter_params.get("segment_id"):
            parts.append(f"Segment ID: #{filter_params['segment_id']}")
        if parts:
            filters_desc = " | ".join(parts)

    stream: List[str] = []

    # 1. Header Banner Box (Brand Blue)
    # Coordinates: x=40, y=760, width=515, height=50
    stream.append("0.08 0.32 0.68 rg")  # Brand Blue
    stream.append("40 755 515 50 re f")

    # Document Header Title
    doc_title = f"MassCommAI Analytics Report: {campaign_name}" if campaign_name else "MassCommAI - Executive Analytics & Performance Report"
    stream.append("BT /F2 15 Tf 1 1 1 rg 52 780 Td (" + _escape_pdf(doc_title[:65]) + ") Tj ET")
    stream.append("BT /F1 9 Tf 0.85 0.92 1.0 rg 52 764 Td (Public Awareness and Civic Communication Intelligence - " + _escape_pdf(now_str) + ") Tj ET")

    # 2. Filter Summary Bar
    stream.append("0.94 0.96 0.98 rg")
    stream.append("40 725 515 22 re f")
    stream.append("0.80 0.85 0.90 rg 40 725 515 1 re f")
    stream.append("BT /F2 8.5 Tf 0.2 0.3 0.4 rg 48 732 Td (APPLIED FILTERS:) Tj /F1 8.5 Tf 0.3 0.3 0.3 rg 10 0 Td (" + _escape_pdf(filters_desc[:90]) + ") Tj ET")

    # 3. Section: Key Performance Indicators
    stream.append("BT /F2 11 Tf 0.08 0.25 0.55 rg 40 705 Td (1. Executive KPI Summary) Tj ET")
    stream.append("0.85 0.85 0.85 rg 40 698 515 0.75 re f")

    # KPI 2-Column Grid
    stream.append("BT /F1 9 Tf 0.15 0.15 0.15 rg")
    stream.append("48 682 Td")
    stream.append("(" + _escape_pdf(f"Total Campaigns: {kpis.total_campaigns:<8} | Total Messages Sent: {kpis.total_messages_sent:,}") + ") Tj 0 -13 Td")
    stream.append("(" + _escape_pdf(f"Delivered to Citizens: {kpis.total_delivered:,} (Delivery Rate: {kpis.delivery_rate}%)") + ") Tj 0 -13 Td")
    stream.append("(" + _escape_pdf(f"Total Reach (Unique Citizens): {kpis.total_reach:,} | Failed / Bounced: {kpis.status_counts.failed:,} ({kpis.bounce_rate}%)") + ") Tj 0 -13 Td")
    stream.append("(" + _escape_pdf(f"Average Open Rate: {kpis.average_open_rate}% | Click-Through Rate (CTR): {kpis.average_click_through_rate}%") + ") Tj 0 -13 Td")
    stream.append("(" + _escape_pdf(f"Inbound Citizen Response Rate: {kpis.response_rate}% | Public Feedback Participation: {kpis.participation_rate}%") + ") Tj")
    stream.append("ET")

    current_y = 605

    # 4. Section: Conversion Funnel (if present)
    if funnel and funnel.stages:
        stream.append(f"BT /F2 11 Tf 0.08 0.25 0.55 rg 40 {current_y} Td (2. Campaign Conversion Funnel) Tj ET")
        stream.append(f"0.85 0.85 0.85 rg 40 {current_y - 7} 515 0.75 re f")
        current_y -= 22

        funnel_text = " -> ".join([f"{s.stage}: {s.count:,} ({s.conversion_from_top}%)" for s in funnel.stages])
        stream.append(f"BT /F1 8.5 Tf 0.2 0.2 0.2 rg 48 {current_y} Td (" + _escape_pdf(funnel_text[:110]) + ") Tj ET")
        current_y -= 14
        stream.append(f"BT /F2 8.5 Tf 0.1 0.4 0.2 rg 48 {current_y} Td (Overall End-to-End Conversion Rate: {funnel.overall_conversion_rate}%) Tj ET")
        current_y -= 24

    # 5. Section: Channel Performance
    if breakdowns and breakdowns.by_channel:
        stream.append(f"BT /F2 11 Tf 0.08 0.25 0.55 rg 40 {current_y} Td (3. Communication Channel Performance) Tj ET")
        stream.append(f"0.85 0.85 0.85 rg 40 {current_y - 7} 515 0.75 re f")
        current_y -= 20

        # Channel Table Header
        stream.append(f"0.92 0.94 0.96 rg 40 {current_y - 3} 515 15 re f")
        stream.append(f"BT /F2 8 Tf 0.1 0.2 0.3 rg 48 {current_y} Td (" + _escape_pdf(f"{'Channel':<15} {'Sent':<10} {'Delivered':<12} {'Opens':<10} {'Clicks':<10} {'Replies':<10} {'Open Rate':<10} {'CTR':<8}") + ") Tj ET")
        current_y -= 15

        stream.append("BT /F1 8 Tf 0.2 0.2 0.2 rg")
        stream.append(f"48 {current_y} Td")
        for ch_name, ch_data in list(breakdowns.by_channel.items())[:6]:
            row = f"{ch_name:<15} {ch_data.sent:<10} {ch_data.delivered:<12} {ch_data.opens:<10} {ch_data.clicks:<10} {ch_data.replies:<10} {ch_data.open_rate:>6.1f}%    {ch_data.ctr:>5.1f}%"
            stream.append(f"({_escape_pdf(row)}) Tj 0 -12 Td")
            current_y -= 12
        stream.append("ET")
        current_y -= 12

    # 6. Section: Language Breakdown
    if breakdowns and breakdowns.by_language and current_y > 180:
        stream.append(f"BT /F2 11 Tf 0.08 0.25 0.55 rg 40 {current_y} Td (4. Multilingual Broadcast Share & Engagement) Tj ET")
        stream.append(f"0.85 0.85 0.85 rg 40 {current_y - 7} 515 0.75 re f")
        current_y -= 20

        stream.append("BT /F1 8 Tf 0.2 0.2 0.2 rg")
        stream.append(f"48 {current_y} Td")
        for lang_code, ldata in list(breakdowns.by_language.items())[:5]:
            label = "English" if lang_code == "en" else "Hindi" if lang_code == "hi" else "Tamil" if lang_code == "ta" else lang_code.upper()
            row = f"Language: {label:<10} | Messages: {ldata.messages:<6} | Delivered: {ldata.delivered:<6} | Open Rate: {ldata.open_rate:>5.1f}% | Response Rate: {ldata.response_rate:>5.1f}%"
            stream.append(f"({_escape_pdf(row)}) Tj 0 -12 Td")
            current_y -= 12
        stream.append("ET")
        current_y -= 12

    # 7. Section: AI Insights
    if insights and current_y > 110:
        stream.append(f"BT /F2 11 Tf 0.08 0.25 0.55 rg 40 {current_y} Td (5. Actionable AI & Analytical Insights) Tj ET")
        stream.append(f"0.85 0.85 0.85 rg 40 {current_y - 7} 515 0.75 re f")
        current_y -= 18

        stream.append("BT /F1 8 Tf 0.25 0.25 0.25 rg")
        stream.append(f"48 {current_y} Td")
        for ins in insights[:4]:
            text = f"[{ins.type.upper()}] {ins.title}: {ins.description}"
            stream.append(f"({_escape_pdf(text[:110])}) Tj 0 -12 Td")
            current_y -= 12
        stream.append("ET")

    # Footer Notice
    stream.append("0.85 0.85 0.85 rg 40 45 515 0.75 re f")
    stream.append("BT /F1 7.5 Tf 0.4 0.4 0.4 rg 40 33 Td (Generated by MassCommAI Analytics Reporting Engine - Confidentially Prepared for Verified Administrators) Tj ET")

    raw_stream = "\n".join(stream)
    content_bytes = raw_stream.encode("latin-1", errors="replace")

    objects: List[bytes] = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page (A4: 595 x 842 pt)
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << "
        b"/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
        b"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
        b">> >> >>"
    )
    # 4: Contents Stream
    objects.append(f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1") + content_bytes + b"\nendstream")

    out: List[bytes] = [b"%PDF-1.4\n"]
    xref: List[int] = [0]
    pos = len(out[0])
    for i, obj in enumerate(objects, 1):
        xref.append(pos)
        block = f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
        out.append(block)
        pos += len(block)

    xref_pos = pos
    xref_table = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for offset in xref[1:]:
        xref_table += f"{offset:010d} 00000 n \n".encode("latin-1")
    out.append(xref_table)
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    out.append(trailer)

    return b"".join(out)
