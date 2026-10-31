import subprocess
from pathlib import Path


def latex_escape(value: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(c, c) for c in value)


def render_tex(data: dict) -> str:
    p = data.get("personal_details", {})
    lines = [
        r"\documentclass[10pt]{article}",
        r"\usepackage[margin=0.65in]{geometry}",
        r"\usepackage{enumitem}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        "{\\Large \\textbf{" + latex_escape(p.get("name", "Candidate")) + r"}}\\par",
        latex_escape(p.get("email", "")) + r"\\",
        r"\section*{Summary}",
        latex_escape(data.get("tailored_summary", "")),
        r"\section*{Skills}",
        latex_escape(", ".join(data.get("skills", []))),
        r"\section*{Experience}",
    ]
    for item in data.get("experience", []):
        lines += [
            r"\textbf{"
            + latex_escape(item.get("title", ""))
            + "} -- "
            + latex_escape(item.get("company", ""))
            + r"\\",
            r"\begin{itemize}[leftmargin=*]",
        ]
        lines += [
            r"\item " + latex_escape(b.get("text", b) if isinstance(b, dict) else str(b))
            for b in item.get("bullets", [])
        ]
        lines += [r"\end{itemize}"]
    lines += [r"\end{document}"]
    return "\n".join(lines)


def compile_pdf(tex: str, output_dir: Path, timeout: int = 30) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / "resume.tex"
    tex_path.write_text(tex, encoding="utf-8")
    if not __import__("shutil").which("tectonic"):
        raise RuntimeError("Tectonic is not installed; download the .tex file or install Tectonic.")
    result = subprocess.run(
        ["tectonic", "--outdir", str(output_dir), str(tex_path)],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-4000:])
    return output_dir / "resume.pdf"
