import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

import pandas as pd

def _ensure_list_of_dicts(posts: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(p) for p in posts]

def export_to_json(
    posts: Iterable[Mapping[str, Any]], output_path: Path
) -> Path:
    output_path = output_path.with_suffix(".json")
    data = _ensure_list_of_dicts(posts)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path

def export_to_csv(
    posts: Iterable[Mapping[str, Any]], output_path: Path
) -> Path:
    output_path = output_path.with_suffix(".csv")
    df = pd.DataFrame(_ensure_list_of_dicts(posts))
    df.to_csv(output_path, index=False)
    return output_path

def export_to_excel(
    posts: Iterable[Mapping[str, Any]], output_path: Path
) -> Path:
    output_path = output_path.with_suffix(".xlsx")
    df = pd.DataFrame(_ensure_list_of_dicts(posts))
    df.to_excel(output_path, index=False)
    return output_path

def export_to_html(
    posts: Iterable[Mapping[str, Any]], output_path: Path
) -> Path:
    output_path = output_path.with_suffix(".html")
    df = pd.DataFrame(_ensure_list_of_dicts(posts))
    html_table = df.to_html(index=False, border=0, classes="instagram-posts")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Instagram Posts Export</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 20px; }}
    table.instagram-posts {{ border-collapse: collapse; width: 100%; }}
    table.instagram-posts th, table.instagram-posts td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; text-align: left; font-size: 14px; }}
    table.instagram-posts th {{ background-color: #f7f7f7; }}
    tr:nth-child(even) {{ background-color: #fafafa; }}
    a {{ color: #0366d6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Instagram Posts Export</h1>
  {html_table}
</body>
</html>
"""
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)
    return output_path

def export_posts(
    posts: Iterable[Mapping[str, Any]],
    output_dir: Path,
    base_filename: str,
    formats: List[str],
) -> Dict[str, Path]:
    """
    Export posts into given formats.

    Args:
        posts: Iterable of post dictionaries.
        output_dir: Directory to save the exported files.
        base_filename: Base name (without extension) for the export files.
        formats: List of formats e.g. ["json", "csv", "excel", "html"].

    Returns:
        Mapping of format name -> resulting file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    base_path = output_dir / base_filename
    results: Dict[str, Path] = {}

    normalized_formats = {fmt.lower() for fmt in formats}

    if "json" in normalized_formats:
        results["json"] = export_to_json(posts, base_path)

    if "csv" in normalized_formats:
        results["csv"] = export_to_csv(posts, base_path)

    if "excel" in normalized_formats or "xlsx" in normalized_formats:
        results["excel"] = export_to_excel(posts, base_path)

    if "html" in normalized_formats:
        results["html"] = export_to_html(posts, base_path)

    return results