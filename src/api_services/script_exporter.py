"""
Módulo Especializado para Formatação e Exportação de Roteiros.
Responsável por converter roteiros de tradução em:
- Documentos Microsoft Word RTF estilizados (com tabela de cores e fontes)
- Arquivos de texto puro limpos (Clean TXT) para revisores externos
"""

import os
import re
from src.utils.fs_security import sanitize_filename


def parse_script_into_pages(content: str) -> list[dict]:
    """Interpreta as linhas do roteiro estruturado e extrai páginas e balões com tags."""
    lines = content.splitlines()
    pages = []
    curr_page = None
    active_field = None

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            active_field = None
            continue

        clean_header = re.sub(r'^[\s=\-#]+|[\s=\-#]+$', '', trimmed).strip()
        p_match = re.match(r'^(?:P[ÁAáa\ufffd\?]?GINA|PAGE)\s*(\d+)(?:[:\s-]+(.*))?$', clean_header, re.IGNORECASE)
        if p_match:
            if curr_page:
                pages.append(curr_page)
            p_num = p_match.group(1)
            p_name = p_match.group(2).strip() if p_match.group(2) else f"Página {p_num}"
            curr_page = {
                "num": p_num,
                "name": p_name,
                "balloons": []
            }
            active_field = None
            continue

        if trimmed.startswith(('#', '===', '---')):
            active_field = None
            continue

        if not curr_page:
            continue

        if trimmed.startswith(('[EN]:', '[EN]')):
            active_field = "en"
        elif trimmed.startswith(('[BR]', '[PT]')):
            br_match = re.match(r'^\[(?:BR|PT)\](?:\s*\(([^)]+)\))?:\s*(.*)$', trimmed, re.IGNORECASE)
            tag = br_match.group(1) if br_match and br_match.group(1) else ""
            br_text = br_match.group(2) if br_match else re.sub(r'^\[(?:BR|PT)\]:?\s*', '', trimmed, flags=re.IGNORECASE)
            curr_page["balloons"].append({"tag": tag, "text": br_text.strip()})
            active_field = "br"
        elif re.match(r'^\[\d+\]:?\s*(.*)$', trimmed):
            num_match = re.match(r'^\[\d+\]:?\s*(.*)$', trimmed)
            raw_text = num_match.group(1).strip() if num_match else trimmed
            tag_match = re.match(r'^\(([^)]+)\)\s*(.*)$', raw_text)
            tag = tag_match.group(1) if tag_match else ""
            txt = tag_match.group(2) if tag_match else raw_text
            curr_page["balloons"].append({"tag": tag, "text": txt.strip()})
            active_field = "br"
        elif active_field == "br" and curr_page["balloons"]:
            prev_txt = curr_page["balloons"][-1]["text"]
            curr_page["balloons"][-1]["text"] = f"{prev_txt}\n{trimmed}".strip() if prev_txt else trimmed

    if curr_page:
        pages.append(curr_page)

    return pages


def _escape_rtf(text: str) -> str:
    """Escapa caracteres ASCII reservados e converte caracteres Unicode para entidades RTF \\uN?."""
    res = []
    for ch in text:
        if ch == '\r':
            continue
        if ch == '\n':
            res.append(r"\line ")
            continue
        code = ord(ch)
        if code < 128:
            if ch in ('\\', '{', '}'):
                res.append('\\' + ch)
            else:
                res.append(ch)
        else:
            res.append(f"\\u{code}?")
    return "".join(res)


def format_as_rtf(pages: list[dict], base_name: str) -> tuple[str, str]:
    """Gera RTF estilizado compatível com Microsoft Word, LibreOffice e WordPad."""
    rtf_lines = [
        r"{\rtf1\ansi\ansicpg1252\deff0\nouicompat\deflang1046",
        r"{\fonttbl{\f0\fnil\fcharset0 Segoe UI;}{\f1\fnil\fcharset0 Consolas;}}",
        r"{\colortbl ;\red120\green50\blue200;\red100\green100\blue100;\red30\green30\blue30;\red180\green80\blue20;}",
        r"\viewkind4\uc1",
        rf"\pard\sa200\sl276\slmult1\b\fs32 {_escape_rtf(base_name)}\b0\fs20\par",
        r"\pard\sa120\cf2 Roteiro de Tradução formatado para Revisão e Letreiramento\cf0\par",
        r"\par"
    ]

    for p in pages:
        p_title = _escape_rtf(f"PÁGINA {p['num']}: {p['name']}")
        rtf_lines.append(rf"\pard\sa100\sb200\b\fs24\cf1 --- {p_title} ---\cf0\b0\fs20\par")
        if not p["balloons"]:
            rtf_lines.append(r"\pard\sa60\li300\i\cf2 [Página sem falas / Arte pura]\cf0\i0\par")
        else:
            for b_idx, b in enumerate(p["balloons"], 1):
                tag_str = _escape_rtf(f"({b['tag']}) ") if b["tag"] else ""
                text_str = _escape_rtf(b["text"] if b["text"] and b["text"] != "[PENDENTE]" else "[TRADUÇÃO PENDENTE]")
                is_pend = not b["text"] or b["text"] == "[PENDENTE]"
                if is_pend:
                    rtf_lines.append(rf"\pard\sa60\li300\b\cf1 [{b_idx}]\b0  \cf4 {text_str}\cf0\par")
                else:
                    rtf_lines.append(rf"\pard\sa60\li300\b\cf1 [{b_idx}]\b0  {tag_str}\cf3 {text_str}\cf0\par")
        rtf_lines.append(r"\par")

    rtf_lines.append("}")
    export_content = "\n".join(rtf_lines)
    clean_base = sanitize_filename(base_name, fallback="roteiro")
    filename = f"{clean_base}_revisao.rtf"
    return export_content, filename


def format_as_clean_txt(pages: list[dict], base_name: str) -> tuple[str, str]:
    """Gera texto puro limpo sem anotações de tags internas."""
    txt_lines = [
        "=" * 80,
        f"ROTEIRO DE TRADUÇÃO: {base_name}",
        "=" * 80,
        ""
    ]
    for p in pages:
        txt_lines.append(f"--- PÁGINA {p['num']}: {p['name']} ---")
        if not p["balloons"]:
            txt_lines.append("  [Página sem falas / Arte pura]")
        else:
            for b_idx, b in enumerate(p["balloons"], 1):
                tag_str = f"({b['tag']}) " if b["tag"] else ""
                txt_str = b["text"] if b["text"] and b["text"] != "[PENDENTE]" else "[TRADUÇÃO PENDENTE]"
                txt_lines.append(f"[{b_idx}] {tag_str}{txt_str}")
        txt_lines.append("")
    export_content = "\n".join(txt_lines)
    clean_base = sanitize_filename(base_name, fallback="roteiro")
    filename = f"{clean_base}_limpo.txt"
    return export_content, filename


def export_script_to_format(content: str, base_name: str, export_format: str = "clean_txt") -> dict:
    """Orquestra a conversão de um script carregado para o formato desejado (rtf ou clean_txt)."""
    pages = parse_script_into_pages(content)

    if export_format == "rtf":
        export_content, filename = format_as_rtf(pages, base_name)
    else:
        export_content, filename = format_as_clean_txt(pages, base_name)

    return {
        "success": True,
        "content": export_content,
        "filename": filename,
        "format": export_format
    }
