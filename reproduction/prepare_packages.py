"""Offline agent-edition adapter. No network, Git, credentials or submission.

Requires byte-pinned bundled inputs and an explicit private outgoing directory.
Only agent front matter, figure routes, platform grouping and reversible prose
citation formatting change; scientific text is never shortened or padded.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPOSITORY = "https://github.com/Teylersf/electron-only-equation-audit"
AGENT_REPOSITORY = "https://github.com/Teylersf/electron-only-equation-agent-publication"
AGENT_NAME = "Lattice Audit Agent"
AGENT_ID = "agent_29b9bf7a"
IDENTITY = "gist:7c74312cf47dcc31c789a8b1c3dedd25"
HEADINGS = ["Introduction", "Related Work", "Methodology", "Results", "Discussion", "Limitations", "Conclusion"]
TAGS = ["electron-only-reconnection", "equation-consistency", "KREHM", "free-energy", "Hermite-projection", "reproducibility"]
MATH = re.compile(r"\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|(?<![\\$])\$(?!\$).*?(?<!\\)\$(?!\$)", re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
SCRIPT_BYTES = Path(__file__).read_bytes()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

def words(text):
    return len(re.findall(r"\b[\w'-]+\b", text))

def section_map(text):
    matches = list(re.finditer(r"^## (.+)$", text, re.M))
    result = {}
    for i, match in enumerate(matches):
        if match[1] in result:
            raise ValueError("Duplicate canonical top-level section")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[match[1]] = text[match.end():end].strip()
    return result

def scientific_sections(parsed):
    numbered = [(h, b) for h, b in parsed.items() if re.fullmatch(r"[1-6]\. .+", h)]
    if [int(h.split(".", 1)[0]) for h, _ in numbered] != list(range(1, 7)):
        raise ValueError("Expected exactly canonical scientific sections 1 through 6")
    if list(parsed) != ["Abstract", *(h for h, _ in numbered), "References"]:
        raise ValueError("Unrecognized, reordered or omitted top-level section; no appendix is expected")
    return numbered

def protected(text):
    return {
        "math": MATH.findall(text),
        "tables": re.findall(r"(?m)^(?:[ \t]*\|[^\n]*\|[ \t]*(?:\n|$))+", text),
        "quotations": re.findall(r"(?m)^(?:>[^\n]*(?:\n|$))+", text),
        "code_fences": re.findall(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", text),
        "proof_markers": re.findall(r"(?m)^(?:#{3,6}\s+)?(?:\*\*)?Proof\b[^\n]*", text),
        "figures": IMAGE.findall(text),
    }

def paragraphs(text):
    return Counter(block.strip() for block in re.split(r"\n\s*\n", text.strip())
                   if block.strip() and not re.fullmatch(r"#{1,6} .+", block.strip()))

def reference_records(text):
    matches = list(re.finditer(r"^\[(\d+)\] (.+?)(?=\n\n\[\d+\] |\Z)", text, re.M | re.S))
    # These normalized identities are checked against the unchanged complete
    # canonical records below. No abbreviated source author list is invented.
    identities = [
        ("Electron-Only Magnetic Reconnection and Inverse Magnetic-Energy Transfer at Subion Scales", ["Z. Liu", "C. Silva", "L. M. Milanese", "M. Zhou", "N. R. Mandell", "N. F. Loureiro"], 2025, "10.1103/PhysRevLett.134.155201"),
        ("Reduced fluid-kinetic equations for low-frequency dynamics, magnetic reconnection, and electron heating in low-beta plasmas", ["A. Zocco", "A. A. Schekochihin"], 2011, "10.1063/1.3628639"),
        ("Astrophysical gyrokinetics: kinetic and fluid turbulent cascades in magnetized weakly collisional plasmas", ["A. A. Schekochihin", "S. C. Cowley", "W. Dorland", "G. W. Hammett", "G. G. Howes", "E. Quataert", "T. Tatsuno"], 2009, "10.1088/0067-0049/182/1/310"),
        ("GX: a GPU-native gyrokinetic turbulence code for tokamak and stellarator design", ["N. R. Mandell et al."], 2024, "10.1017/S0022377824000631"),
        ("Computational evidence for Equation consistency in electron-only reconnection manuscripts", ["T. Kalin"], 2026, "10.5281/zenodo.23784871"),
    ]
    if len(matches) != len(identities):
        raise ValueError("Review the complete source10 bibliography before preparation")
    refs, originals = [], []
    for i, (match, identity) in enumerate(zip(matches, identities), 1):
        title, authors, year, doi = identity
        record = match[2].strip()
        if int(match[1]) != i or title + "." not in record or "https://doi.org/" + doi not in record:
            raise ValueError("Reference identity no longer matches the verified canonical record")
        if any(a not in record.split(title, 1)[0] for a in authors) or str(year) not in record:
            raise ValueError("Reference author/year identity mismatch")
        originals.append(match[0].strip())
        refs.append({"ref_id": str(i), "type": "external", "title": title, "authors": authors,
                     "year": year, "url": "https://doi.org/" + doi, "doi": doi, "source": "doi"})
    if "\n\n".join(originals) != text:
        raise ValueError("Reference parser failed to preserve every full canonical record")
    return refs, originals

def author_year_citations(text, references):
    """Reformat prose markers reversibly; mathematics and code stay exact."""
    labels = {"1": "Liu et al., 2025", "2": "Zocco and Schekochihin, 2011",
              "3": "Schekochihin et al., 2009", "4": "Mandell et al., 2024",
              "5": "Kalin, 2026"}
    if {r["ref_id"] for r in references} != set(labels):
        raise ValueError("Review author-year map against the complete bibliography")
    protected_spans = [(m.start(), m.end()) for m in MATH.finditer(text)]
    for pattern in [r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", r"`[^`\n]+`"]:
        protected_spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text))
    pattern = re.compile(r"\[([0-9]+(?:\s*,\s*[0-9]+)*)(,\s*[A-Za-z][^\]]*)?\](?!\()")
    parts, ledger, cursor, length = [], [], 0, 0
    for match in pattern.finditer(text):
        if any(match.start() < end and match.end() > start for start, end in protected_spans):
            continue
        ids = [x.strip() for x in match[1].split(",")]
        if any(x not in labels for x in ids):
            raise ValueError("Unresolved prose reference marker")
        prefix = text[cursor:match.start()]
        parts.append(prefix); length += len(prefix)
        rewritten = "[" + "; ".join(labels[x] for x in ids) + (match[2] or "") + "]"
        ledger.append({"canonical": match[0], "adapted": rewritten,
                       "reference_ids": ids, "adapted_start": length,
                       "adapted_end": length + len(rewritten)})
        parts.append(rewritten); length += len(rewritten); cursor = match.end()
    parts.append(text[cursor:])
    converted = "".join(parts)
    if restore_citations(converted, ledger) != text:
        raise ValueError("Author-year transformation is not exactly reversible")
    return converted, ledger

def restore_citations(text, ledger):
    for row in reversed(ledger):
        start, end = row["adapted_start"], row["adapted_end"]
        if text[start:end] != row["adapted"]:
            raise ValueError("Citation reversal locator or text changed")
        text = text[:start] + row["canonical"] + text[end:]
    return text


def safe(name, data):
    """Do not leak local paths, credentials or operational state into outputs."""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe package route")
    if not name.lower().endswith((".png", ".pdf")):
        text = data.decode("utf-8")
        # This generic reproduction runtime is intentionally public in H.
        scrubbed = text.replace("C:/Python 313/python.exe", "PYTHON")
        scrubbed = scrubbed.replace("C:\\Python 313\\python.exe", "PYTHON")
        if name == "reproduction/canonical/.gitignore":
            scrubbed = scrubbed.replace(".publishing-access/", "PRIVATE_IGNORE_PATTERN/")
        if name == "reproduction/canonical/data/computational-artifact-manifest.json":
            scrubbed = scrubbed.replace('".publishing-access/**"', '"PRIVATE_EXCLUSION_PATTERN/**"')
        if re.search(r"(?i)(?:(?<![A-Z0-9])[A-Z]:[\\/]|/mnt/[a-z]/|/home/|/root/|\.publishing-access)", scrubbed):
            raise ValueError("Private location in public file: " + name)
        if re.search(r"(?i)(?:Bearer\s+[A-Za-z0-9._-]{12,}|(?:session_token|access_token|api_key)\s*[=:]\s*[\"']?[A-Za-z0-9._-]{12,}|gh[pousr]_[A-Za-z0-9]{20,})", text):
            raise ValueError("Credential-shaped value in public file: " + name)


def inputs(args):
    raw = (ROOT / "reproduction/pinned-inputs.json").read_bytes()
    if sha(raw) != args.expected_input_inventory_sha256:
        raise ValueError("Mixed-pin input inventory changed")
    inventory = json.loads(raw)
    for key, value in {
        "computational_commit": args.expected_code_commit,
        "computational_tree": args.expected_code_tree,
        "canonical_content_commit": args.canonical_content_commit,
        "computational_file_count": 55, "paper_support_file_count": 17,
        "file_count": 72,
    }.items():
        if inventory.get(key) != value:
            raise ValueError("Input inventory mismatch: " + key)
    rows = inventory["files"]
    if len(rows) != 72 or len({r["package_path"] for r in rows}) != 72:
        raise ValueError("Missing or duplicate copied files")
    copies = {}
    roles = Counter()
    for row in rows:
        route = row["package_path"]
        if route != "reproduction/canonical/" + row["source_path"]:
            raise ValueError("Unexpected copy route")
        data = (ROOT / route).read_bytes()
        if len(data) != row["bytes"] or sha(data) != row["sha256"]:
            raise ValueError("Pinned bytes differ: " + route)
        role = row["role"]
        expected = args.expected_code_commit if role == "immutable_computational_snapshot" else args.canonical_content_commit
        if row["source_revision"] != expected:
            raise ValueError("Wrong source revision")
        safe(route, data)
        copies[route] = data
        roles[role] += 1
    if roles != Counter({"immutable_computational_snapshot": 55, "canonical_paper_and_review_support": 17}):
        raise ValueError("Wrong source scopes")
    comp = {r["source_path"]: r for r in rows if r["role"] == "immutable_computational_snapshot"}
    manifest = json.loads(copies["reproduction/canonical/data/computational-artifact-manifest.json"])
    records = manifest["files"]
    if set(comp) != {r["path"] for r in records} | {"data/computational-artifact-manifest.json"}:
        raise ValueError("Incomplete frozen computational manifest")
    for row in records:
        if comp[row["path"]]["sha256"] != row["sha256"]:
            raise ValueError("Frozen manifest byte mismatch")
    return copies, inventory, raw


def arrangement(numbered):
    first = numbered[0][1].split("\n\n")
    ending = numbered[5][1].split("\n\n")
    if len(first) != 3 or len(ending) != 7:
        raise ValueError("Review the canonical plain-paragraph grouping boundaries")
    if not ending[3].startswith("GX is an identified public solver framework") or not ending[4].startswith("The supported correction concerns"):
        raise ValueError("Review the limitations/conclusion paragraph boundary")
    added = ["### " + numbered[i][0] for i in (1, 2, 3, 5)]
    bodies = [first[0], "\n\n".join(first[1:]),
              added[0] + "\n\n" + numbered[1][1],
              added[1] + "\n\n" + numbered[2][1] + "\n\n" + added[2] + "\n\n" + numbered[3][1],
              numbered[4][1] + "\n\n" + added[3] + "\n\n" + "\n\n".join(ending[:3]),
              ending[3], "\n\n".join(ending[4:])]
    if any(not body for body in bodies):
        raise ValueError("Empty platform group")
    return bodies, added


def main():
    if sys.flags.optimize:
        raise RuntimeError("Ordinary Python required; -O disables preservation assertions")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outgoing-dir", type=Path, required=True)
    for name in ("expected-code-commit", "expected-code-tree", "canonical-content-commit",
                 "expected-manuscript-sha256", "expected-pdf-sha256", "expected-input-inventory-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    outgoing = args.outgoing_dir.resolve()
    canonical = ROOT.parent / "electron-only-equation-audit"
    if outgoing.is_relative_to(ROOT) or outgoing.is_relative_to(canonical):
        raise ValueError("Outgoing API bodies must stay outside both repositories")
    for value in (args.expected_code_commit, args.expected_code_tree, args.canonical_content_commit):
        if not re.fullmatch(r"[a-f0-9]{40}", value):
            raise ValueError("Full source commit/tree pins required")
    for value in (args.expected_manuscript_sha256, args.expected_pdf_sha256, args.expected_input_inventory_sha256):
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Full SHA256 required")
    if args.expected_code_commit == args.expected_code_tree:
        raise ValueError("Commit and tree are distinct objects")
    source, inventory, inventory_raw = inputs(args)
    md = source["reproduction/canonical/paper/manuscript.md"]
    pdf = source["reproduction/canonical/paper/main.pdf"]
    if sha(md) != args.expected_manuscript_sha256 or sha(pdf) != args.expected_pdf_sha256:
        raise ValueError("Paper content pins changed")
    text = md.decode("utf-8")
    if "\r" in text:
        raise ValueError("Canonical LF must stay exact")
    parsed = section_map(text)
    numbered = scientific_sections(parsed)
    science = "\n\n".join(body for _, body in numbered)
    title = re.search(r"^# (.+)$", text, re.M)[1]
    version, date = re.search(r"^Version ([^;\s]+); (.+)$", text, re.M).groups()
    meta_raw = source["reproduction/canonical/submissions/metadata.json"]
    meta = json.loads(meta_raw)
    for key, expected in {"title": title, "abstract": parsed["Abstract"], "author": "Taylor Kalin",
                          "version": "1.0.0", "scientific_code_commit": args.expected_code_commit,
                          "repository": CANONICAL_REPOSITORY, "agentpub_paper_type": "short_communication"}.items():
        if meta.get(key) != expected:
            raise ValueError("Canonical metadata changed: " + key)
    assert "**Taylor Kalin**" in text.split("## Abstract", 1)[0]
    assert args.expected_code_commit in science and "https://doi.org/" + meta["code_doi"] in science
    references, original_refs = reference_records(parsed["References"])
    assert len(references) == 5
    image_routes = {}
    for _, link in IMAGE.findall(science):
        if not re.fullmatch(r"\.\./figures/[a-z-]+\.png", link):
            raise ValueError("Unrecognized figure route")
        filename = link.rsplit("/", 1)[1]
        local = "reproduction/canonical/figures/" + filename
        if local not in source:
            raise ValueError("Figure not pinned")
        remote = "https://raw.githubusercontent.com/Teylersf/electron-only-equation-audit/" + args.expected_code_commit + "/figures/" + filename
        image_routes[link] = (local, remote)
    assert len(image_routes) == 2

    def adapt(body, remote=False):
        for old, pair in image_routes.items():
            body = body.replace("](" + old + ")", "](" + pair[int(remote)] + ")")
        return body

    def restore(body, remote=False):
        for old, pair in image_routes.items():
            body = body.replace("](" + pair[int(remote)] + ")", "](" + old + ")")
        return body

    front = ("# " + title + "\n\n**" + AGENT_NAME + "**\n\n"
             "Authorized agent-only edition. Human operator and canonical author: **Taylor Kalin**.\n\n"
             "AgentPub identity: `" + AGENT_ID + "`; AAES identity: `" + IDENTITY + "`.\n\n"
             "Canonical author: https://taylorkalin.com ; ORCID 0009-0003-9000-9315.\n\n"
             "Version " + version + "; " + date + "\n\n"
             "**Agent-edition disclosure.** All scientific paragraphs, mathematics, equations, derivations, figures, captions, references and original disclosures are retained. "
             "This front byline/disclosure and figure routes are adapted. AgentPub alone additionally groups paragraphs into venue sections and uses reversible documented author-year prose citations. "
             "The canonical author remains Taylor Kalin. Internal AI-assisted checks are not independent human peer review.\n\n")
    paper = front + "## Abstract\n\n" + parsed["Abstract"] + "\n\n" + "\n\n".join(
        "## " + h + "\n\n" + adapt(body) for h, body in numbered) + "\n\n## References\n\n" + parsed["References"] + "\n"
    grouped, added = arrangement(numbered)
    sections, ledgers = [], {}
    for heading, body in zip(HEADINGS, grouped):
        content, ledger = author_year_citations(adapt(body, True), references)
        ledgers[heading] = ledger
        sections.append({"heading": heading, "content": content,
                         "citations": sorted({r for row in ledger for r in row["reference_ids"]}, key=int)})
    restored = "\n\n".join(restore(restore_citations(s["content"], ledgers[s["heading"]]), True) for s in sections)
    for heading in added:
        if restored.count(heading + "\n\n") != 1:
            raise ValueError("Added source heading changed")
        restored = restored.replace(heading + "\n\n", "", 1)
    local = section_map(paper)
    restored_local = "\n\n".join(restore(b) for _, b in scientific_sections(local))
    assert restored == restored_local == science
    assert paragraphs(restored) == paragraphs(science)
    assert protected(restored) == protected(restored_local) == protected(science)
    assert local["Abstract"] == parsed["Abstract"] and local["References"] == parsed["References"]
    tags = re.findall(r"\\tag\{([^{}]+)\}", science)
    assert tags == list(map(str, range(1, 13)))
    schema_raw = (ROOT / "reproduction/agentpub-paper-schema.json").read_bytes()
    limits = json.loads(schema_raw)["paper_types"]["short_communication"]["constraints"]
    caps = {s["heading"]: {"unicode_codepoints": len(s["content"]),
                           "UTF16_code_units": len(s["content"].encode("utf-16-le")) // 2} for s in sections}
    body_words = sum(words(s["content"]) for s in sections)
    guideline_checks = {
        "title": len(title) <= limits["title"]["max_chars"],
        "abstract": words(parsed["Abstract"]) <= limits["abstract"]["max_words"],
        "references": len(references) >= limits["references"]["min_count"],
        "body_words": limits["body_word_count"]["min_words"] <= body_words <= limits["body_word_count"]["max_words"],
        "required_sections": set(limits["sections"]["required"]) <= set(HEADINGS),
        "section_order": [h for h in limits["sections"]["must_appear_in_this_order"] if h in HEADINGS] == HEADINGS,
        "section_character_caps": all(max(c.values()) <= 49000 for c in caps.values()),
        "tags": limits["tags"]["min_count"] <= len(TAGS) <= limits["tags"]["max_count"] and all(len(t) <= limits["tags"]["max_chars_each"] for t in TAGS),
    }
    if not all(guideline_checks.values()):
        raise ValueError("Selected live paper-type constraints failed: " + str(guideline_checks))
    note = ("Authorized agent-only edition by Lattice Audit Agent; human operator and canonical author Taylor Kalin, ORCID 0009-0003-9000-9315. "
            "Canonical: " + CANONICAL_REPOSITORY + "/blob/" + args.canonical_content_commit + "/paper/manuscript.md . "
            "Six canonical sections map losslessly to seven venue groups at plain-paragraph boundaries, in original scientific order; four source subheadings are added. "
            "All scientific text, ordered mathematics, equations, derivations, original figures/full captions, full bibliography and disclosures are retained after reversing declared image routes and author-year substitutions. "
            "AgentPub section prose uses the documented [Author, Year] style; numeric reference IDs remain in citations arrays and the local paper. The complete canonical bibliography follows verbatim below. "
            "No scientific shortening, citation padding or new reference is introduced. Exact model/token usage was not recorded; agent_model='not recorded' and total_tokens=-1 denote missing data, not estimates. "
            "Claims concern arXiv2407.06020v2, its embedded supplement and the authentic publisher CHORUS accepted manuscript; the subscription VOR and final journal supplement were not inspected. "
            "The established KREHM/ERMHD equations and the source Appendix reconciliation are credited; no new plasma model, recovered target code, source numerical-curve failure or new PIC simulation is claimed. "
            "Two complete inline Markdown figure/caption pairs link to the immutable computational H. No undocumented structured-image data keys or raw HTML are guessed. "
            "Complete typeset canonical PDF: " + CANONICAL_REPOSITORY + "/releases/download/v1.0.0/main.pdf . "
            "Computational H is " + args.expected_code_commit + "; paper/build/metadata/review support is separately pinned at " + args.canonical_content_commit + ". "
            "Formal agent reviews require this study's own final Publish.fun disposition; current upstream validation/allowance blockers are not a final rejection or release. Both agent gates remain closed. "
            "Internal AI-assisted reviews are not external human peer review. Offline preparation is not submission, eligibility, acceptance or publication. "
            "Normalized reference fields omit edition/page/inspection qualifications retained in this exact bibliography:\n\n" + parsed["References"])
    payload = {"title": title, "abstract": parsed["Abstract"], "paper_type": "short_communication",
               "authors": [{"agent_id": AGENT_ID, "display_name": AGENT_NAME, "model_type": "not recorded"}],
               "sections": sections, "references": references, "tags": TAGS,
               "metadata": {"agent_model": "not recorded", "agent_platform": "Codex desktop", "total_tokens": -1, "submission_note": note}}
    now = datetime.now(timezone.utc).isoformat()
    context = {"prepared_at_utc": now, "publication_state": "local_prepared_not_submitted", "canonical_version": version,
               "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
               "canonical_content_commit": args.canonical_content_commit, "canonical_manuscript_sha256": sha(md),
               "AgentPub_submission_gate_open": False, "AAES_submission_gate_open": False,
               "own_Publishfun_final_disposition_verified": False, "formal_submission_performed": False,
               "public_agent_repository_verified": False,
               "note": "Conservative offline state. Root owns the first Publish.fun submission and live disposition. A preflight never opens a formal gate. No acceptance, closure, release or agent eligibility is inferred."}
    metadata = {"aaes_version": "4.2", "title": title, "abstract": parsed["Abstract"], "canonical_version": version,
                "author_ids": [IDENTITY], "submitted_at": now, "timestamp_scope": "local preparation, not registration",
                "tags": TAGS, "agentpub_paper_type": "short_communication",
                "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
                "canonical_content_commit": args.canonical_content_commit,
                "generation_environment": {"model": "not recorded", "tools": ["Python", "exact rational Fourier convolution", "Gaussian/Hermite projection", "NumPy", "Matplotlib"],
                    "prompt_strategy": "Edition-specific complete target-source reading, bounded primary-theory checks, independent exact algebra, retained positive controls and complete internal mathematical/citation/visual review.",
                    "notes": "Lattice Audit Agent; human operator and canonical author Taylor Kalin. Self-funded. No estimated model/token usage, target-run recovery or independent human peer review."},
                "novelty_statement": "A bounded consistency comment on named preprint/accepted-manuscript displays: continuity sign, pressure units, quadratic density-energy weight and collisionless Hermite projection. Reconciliations credit established KREHM and the source Appendix; the source's rate and conditional decay algebra are retained. Exact synthetic controls do not identify the actual solver equations, reject source curves or establish a new plasma model."}
    claims = [
        {"text": "The inspected main continuity sign and missing pressure coefficient are inconsistent with the stated Appendix reduction under the same dimensional/bracket conventions.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 2, Eqs. (1)-(4); exact finite-Gamma linear-symbol controls after restoring pressure units.", "confidence_note": "Named arXiv v2 and accepted-manuscript displays only; a different declared dependent variable must be carried consistently. No actual solver instability or VOR claim."},
        {"text": "Changing only the density energy to the printed doubled coefficient breaks the stated unweighted quadratic invariant for an exact two-dimensional periodic state.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 3, Eqs. (5)-(8); full generalized-flux inertia retained, exact ledger and arbitrarily small positive-density scaling.", "confidence_note": "Instantaneous synthetic state, not a source heating trajectory; the source Figure 8 implementation may already use the consistent coefficient."},
        {"text": "The supplied collisionless Hermite streaming and forcing signs disagree with projection under its stated Gaussian/physicists-Hermite/temperature convention.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 4, Eqs. (9)-(10); 81 orthogonality checks, nine drive projections and six neighboring streaming magnitudes.", "confidence_note": "Collisions excluded and rephasing counterarguments addressed. No failed Landau damping or uninspected numerical implementation is inferred."},
        {"text": "The source Appendix reconnection-rate algebra and conditional merger/critical-balance exponents remain supported.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 5, Eqs. (11)-(12); independent rate and exponent positive controls and finite-beta qualification.", "confidence_note": "Phenomenological assumptions and different speed normalizations retained; no new PIC experiment or empirical high-beta-rate validation."},
        {"text": "The immutable 55-file software package preserves exact synthetic controls and source-bound independent review records.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 6; 60 periodic states, 24 linear symbols and Gaussian/Hermite controls, software DOI 10.5281/zenodo.23784871.", "confidence_note": "No original fields, full input decks or exact target GX run were recovered; no new source simulation or external human peer review."},
    ]
    registration = {"source": "github:Teylersf/electron-only-equation-agent-publication",
                    "submission": {"kind": "paper", "maturity": "final"},
                    "project": {"title": title, "summary": parsed["Abstract"], "status": "active",
                                "research_question": "Are the named manuscript governing displays, quadratic invariant and projected hierarchy mutually consistent under their declared conventions?"},
                    "claims": claims}
    blocks = protected(science)
    checks = {"prepared_at_utc": now, "canonical_version": version,
              "preparer_sha256": sha(SCRIPT_BYTES), "pinned_input_inventory_sha256": sha(inventory_raw),
              "canonical_manuscript_sha256": sha(md), "canonical_PDF_sha256": sha(pdf), "canonical_metadata_sha256": sha(meta_raw),
              "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
              "canonical_content_commit": args.canonical_content_commit, "code_doi": meta["code_doi"],
              "copied_pinned_files": inventory["files"], "copy_counts": {"computational_H": 55, "paper_build_metadata_and_review_release": 17, "total": 72},
              "canonical_scientific_sections": 6, "platform_sections": HEADINGS,
              "mapping": "Original scientific order: Intro section 1 paragraph 1; Related Work section 1 paragraphs 2-3; Methodology section 2; Results sections 3-4; Discussion section 5 plus section 6 verification paragraphs 1-3; Limitations section 6 paragraph 4; Conclusion remaining section 6 paragraphs 5-7.",
              "added_platform_headings": added,
              "full_scientific_text_exact_after_declared_reversal": True, "ordered_paragraphs_and_protected_blocks_preserved": True,
              "abstract_and_full_bibliography_exact": True, "canonical_bibliography_verbatim_in_payload_metadata": True,
              "math_segments": len(blocks["math"]), "protected_block_counts": {k: len(v) for k, v in blocks.items()},
              "numbered_equation_tags": tags, "figures": len(image_routes), "references": len(references),
              "scientific_section_bodies": [{"heading": h, "sha256": sha(b.encode())} for h, b in numbered],
              "citation_format": {"documented_style": "[Author, Year]", "instructions_URL": "https://api.agentpub.org/v1/instructions",
                  "reversal_ledger_by_section": ledgers, "local_numeric_markers_unchanged": True, "math_code_link_labels_excluded": True},
              "figure_interface": {"inline_Markdown_pairs_preserved": 2, "structured_figures_submitted": 0,
                  "note": "Live schema declares optional figures[].data as an unspecified object; no image-data keys are invented. The full PDF is the typeset fallback, separately from API-text preservation."},
              "section_character_counts": caps, "body_regex_words": body_words,
              "body_whitespace_words": sum(len(s["content"].split()) for s in sections), "guideline_checks": guideline_checks,
              "paper_type": "short_communication", "schema_snapshot_sha256": sha(schema_raw),
              "agentpub_payload_sha256": sha(encode(payload)), "AAES_registration_sha256": sha(encode(registration)),
              "AAES_bounded_claims": len(claims), "model_or_token_usage_estimated": False, "unknown_token_sentinel": -1,
              "formal_agent_gates_open": False, "canonical_inputs_unchanged": True,
              "permitted_changes": ["agent front byline/disclosure", "figure routes", "lossless paragraph grouping and four source headings", "AgentPub-only reversible author-year prose markers"],
              "nonprivate_runtime_locator_allowlist": ["C:/Python 313/python.exe"]}
    readme = f"""# {title}

Agent edition by **{AGENT_NAME}**. Human operator and canonical author: **Taylor Kalin**.

Version {version}. The [canonical manuscript]({CANONICAL_REPOSITORY}/blob/{args.canonical_content_commit}/paper/manuscript.md) retains Taylor's byline. All scientific paragraphs, ordered mathematics, numbered equations, derivations, original figures/full captions, bibliography and disclosures are preserved. Only agent front matter, declared image routes, lossless platform grouping and reversible AgentPub-only author-year prose citations are adapted.

- [Complete agent paper](paper.md)
- [Complete typeset canonical PDF]({CANONICAL_REPOSITORY}/releases/download/v1.0.0/main.pdf)
- [Identity metadata](metadata.json)
- [Preservation proof](reproduction/adapter-checks.json)
- [Mixed-pin reproduction](reproduction/README.md)
- [Closed-gate context](reproduction/submission-context.json)

The claims concern named arXiv v2 and publisher accepted-manuscript equations, plus the supplement embedded in arXiv v2. The subscription journal VOR and final journal supplement were not inspected. The standard KREHM/ERMHD framework and source Appendix reconciliation are credited. Exact synthetic controls do not identify the actual solver implementation, reject source numerical curves, reproduce source runs or establish a new plasma model. Positive reconnection-rate/conditional decay checks and all qualifications remain intact.

This edition preserves {len(blocks['math'])} mathematical segments, {len(tags)} numbered equations, {len(blocks['tables'])} Markdown tables, two complete figure/caption pairs and five references. Exactly **55 computational files** come from H `{args.expected_code_commit}` (distinct tree `{args.expected_code_tree}`); **17 paper/build/metadata/review-support files** come from release `{args.canonical_content_commit}`. Frozen review/source copies already included in H are retained, and historical draft-review records are supporting QA observations rather than draft manuscripts. The H README describes its historical computational-only scope; it is not claimed to equal the later canonical administrative README. Software DOI: https://doi.org/{meta['code_doi']} .

AgentPub uses short_communication with seven sections and reversible author-year citations. This local paper retains the exact numeric markers and full canonical bibliography. No scientific text, reference or caption is dropped or padded. Two inline Markdown figures retain complete captions and immutable H image URLs in the platform body. The full PDF is a typeset fallback; no undocumented structured-image keys or raw HTML are introduced. Exact model/token use is unknown; the explicit -1 token sentinel is missing data, not an estimate.

**Offline prepared; not formally submitted.** Both agent gates remain closed. This study's upstream Publish.fun validation/allowance blocker is not a final rejection, acceptance or release. Another study's outcome cannot open this gate. GitHub/software/AiraXiv preprints and AI-assisted internal checking are distinct from formal editorial decisions and external human peer review. Public agent-repository availability and identity eligibility are not certified by preparation.

Original code: MIT. Original text/figures: CC BY 4.0. Attributed works retain their rights. The frozen computational license title omits the manuscript-label suffix; it identifies the same project, with original bytes retained. Authorized AAES identity: [{IDENTITY}](https://gist.github.com/Teylersf/7c74312cf47dcc31c789a8b1c3dedd25).
"""
    command = ("python reproduction/prepare_packages.py --outgoing-dir OUTSIDE_PUBLIC_REPOS "
               "--expected-code-commit " + args.expected_code_commit + " --expected-code-tree " + args.expected_code_tree +
               " --canonical-content-commit " + args.canonical_content_commit +
               " --expected-manuscript-sha256 " + sha(md) + " --expected-pdf-sha256 " + sha(pdf) +
               " --expected-input-inventory-sha256 " + sha(inventory_raw))
    reproduction = f"""# Reproduction and preservation

55 exact computational source/code/data/review files are bundled at H {args.expected_code_commit}, distinct tree {args.expected_code_tree}. Seventeen final paper/TeX/build/metadata/review-support files are pinned separately at release {args.canonical_content_commit}. Every path, role, byte count and SHA256 is recorded in pinned-inputs.json. Historical prior-review records are identified as history; the final all-page receipt binds the final manuscript/PDF. Third-party PDFs and private operational records are excluded.

Run the offline adapter from this agent repository with ordinary Python 3; no Git, canonical checkout, credentials, PDF source, network or scientific producer execution is required. Place outgoing API bodies outside both public repositories.

```text
{command}
```

The adapter verifies all 72 pinned blobs, exact 55-file manifest coverage (54+self), paper/metadata hashes and the entire scientific text after reversing only declared routes, added source headings and prose citation substitutions. All 12 numbered equations, both complete figure/caption pairs, full bibliography and original disclosures remain. Local paper.md and agent-paper.md retain numeric citations; AgentPub alone uses the documented author-year style, with a complete reversal ledger. There is no scientific shortening, numeric truncation, citation padding or whitespace-based cap workaround.

The seven venue sections preserve original scientific order. Source section 1 is split into Introduction/Related Work; Methodology contains section 2; Results 3-4; Discussion 5 plus verification paragraphs at the start of 6; Limitations the next GX/reproducibility paragraph; Conclusion the remaining conclusions/availability/disclosures. Four source subheadings are separately recorded and exactly removable. The source equations and proofs remain complete; no claim depends on a platform viewer rendering table math or Markdown images. Use the canonical PDF for complete typesetting.

To reproduce scientific controls, use canonical/REPRODUCIBILITY.md and canonical/COMPUTATIONAL_METHODS.md. The original producer and separate verifiers remain byte-exact at H; this adapter does not execute them. The archived README correctly describes its historical code-only release and is not substituted with the newer canonical administrative README.

**Git transport:** all copied blobs are -text; JSON/CSV and original Markdown line endings must remain exact. The immutable copied .gitignore ignores its own paper/submissions descendants. Future publication must force-add every 72 inventory path explicitly and verify the public Git archive; do not rewrite frozen ignore/attribute files to change this. This preparer performs no Git operation.

Official AgentPub instructions/schema are cached primary format evidence reused offline, not a fresh live check. The selected short_communication constraints require 1500-4000 body words and five references; every section is conservatively capped at 49000 Unicode/UTF16 units. No nonstoring check or formal call is made by this script. The agent root metadata timestamp denotes preparation, not AAES registration. Model/token usage is unrecorded and not estimated.

Both formal agent gates remain false. The separate scoped publishing client must verify this study's own final Publish.fun disposition before any future formal review. A quota/validation failure, another study's rejection, GitHub preprint or software DOI is insufficient. Canonical authorship remains Taylor Kalin; authorized agent-only byline is Lattice Audit Agent with Taylor as human operator. Internal AI-assisted review is not external human peer review.
"""
    attrs = "* text=auto eol=lf\n*.json -text\n*.csv -text\n*.png binary\n*.pdf binary\nreproduction/canonical/** -text\nreproduction/canonical/** whitespace=-blank-at-eol\n"
    products = {"paper.md": paper.encode(), "agent-paper.md": paper.encode(), "metadata.json": encode(metadata),
                "README.md": readme.encode(), "reproduction/README.md": reproduction.encode(),
                "reproduction/adapter-checks.json": encode(checks), "reproduction/canonical-preservation-v1.0.0.json": encode(checks),
                "reproduction/submission-context.json": encode(context), ".gitattributes": attrs.encode(),
                ".gitignore": b"__pycache__/\n*.pyc\n.private/\n",
                "LICENSE-CODE": source["reproduction/canonical/LICENSE-CODE"],
                "LICENSE-MANUSCRIPT": source["reproduction/canonical/LICENSE-MANUSCRIPT"]}
    for name, data in products.items():
        safe(name, data)
    if Path(__file__).read_bytes() != SCRIPT_BYTES or (ROOT / "reproduction/agentpub-paper-schema.json").read_bytes() != schema_raw:
        raise ValueError("Adapter/schema changed during preparation")
    if inputs(args)[0] != source:
        raise ValueError("Source bytes changed during preparation")
    for name, data in products.items():
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    outgoing.mkdir(parents=True, exist_ok=True)
    (outgoing / "electron-only-agentpub-payload.json").write_bytes(encode(payload))
    (outgoing / "electron-only-aaes-registration.json").write_bytes(encode(registration))
    assert all((ROOT / name).read_bytes() == data for name, data in products.items())
    print(json.dumps({"prepared": True, "files": 72, "math": len(blocks['math']), "equations": len(tags),
                      "figures": 2, "references": 5, "body_regex_words": body_words,
                      "max_section_UTF16": max(c['UTF16_code_units'] for c in caps.values()),
                      "payload_sha256": checks['agentpub_payload_sha256'], "gates_open": False}))


if __name__ == "__main__":
    main()

