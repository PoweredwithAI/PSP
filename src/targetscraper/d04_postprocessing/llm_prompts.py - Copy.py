import os
import json
from typing import Dict, Any, List

import pandas as pd
from google import genai


# ---------- Public API ----------

def analyze_articles(
    df_articles: pd.DataFrame,
    target_name: str | None = None,
    api_key: str | None = None,
    model_id: str = "gemini-2.5-flash",
    max_articles: int = 10,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    High-level entrypoint:
    - Use articles from df_articles (must include 'title', 'abstract'; optional 'article_id', 'target_name').
    - Focus on one target (explicit target_name or use first target_name in CSV).
    - Run per-article Gemini analysis and corpus-level aggregation.
    - Return (df_per_article, corpus_result).
    """
    if api_key is None:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No Gemini API key provided. Set GOOGLE_API_KEY/GEMINI_API_KEY or pass api_key.")

    client = genai.Client(api_key=api_key)

    # Work on a copy to avoid mutating caller's DataFrame
    df_articles = df_articles.copy()

    # Determine target
    if target_name is None:
        if "target_name" not in df_articles.columns:
            raise ValueError("target_name not provided and 'target_name' column missing in CSV")
        target_name = str(df_articles["target_name"].dropna().iloc[0]).strip()

    # Ensure article_id
    if "article_id" not in df_articles.columns:
        df_articles["article_id"] = df_articles.index.astype(str)

    per_article_results: List[Dict[str, Any]] = []

    for _, row in df_articles.head(max_articles).iterrows():
        title = str(row.get("title", "")).strip()
        abstract = str(row.get("abstract", "")).strip()
        article_id = str(row.get("article_id", "")).strip()
        if not title or not abstract:
            continue

        analysis = _llm_analyze_article_gemini(client, title, abstract, article_id, target_name)
        analysis["title"] = title
        per_article_results.append(analysis)

    df_per_article = pd.DataFrame(per_article_results)

    corpus_result = _aggregate_across_articles(client, per_article_results, target_name)

    return df_per_article, corpus_result


def export_corpus_to_csv(
    corpus_result: Dict[str, Any],
    csv_path: str,
) -> None:
    """
    Flatten corpus_result into rows: section, question, answer, evidence, confidence.
    """
    rows: list[Dict[str, Any]] = []

    for section, q_list in QUESTIONS.items():
        if section not in corpus_result:
            continue
        sec_block = corpus_result.get(section, {})
        sec_answer = sec_block.get("answer", "")
        sec_conf = sec_block.get("confidence", "")
        evid_list = sec_block.get("evidence", []) or []
        evid_joined = "\n".join(evid_list)

        for q in q_list:
            rows.append(
                {
                    "section": section,
                    "question": q,
                    "answer": sec_answer,
                    "evidence": evid_joined,
                    "confidence": sec_conf,
                }
            )

    if "summary_score" in corpus_result:
        rows.append(
            {
                "section": "summary_score",
                "question": "Overall priority recommendation for this target.",
                "answer": corpus_result.get("summary_score", ""),
                "evidence": "",
                "confidence": "",
            }
        )

    pd.DataFrame(rows).to_csv(csv_path, index=False)


# ---------- Internal helpers & prompts ----------

QUESTIONS: Dict[str, List[str]] = {
    "disease_linkage": [
        "What types of human genetic evidence link this target to the disease (e.g., GWAS loci, rare variants, burden tests, Mendelian forms)? Specify variant IDs, effect direction, and strength of association where reported.",
        "Are there replicated associations in independent cohorts or consortia (e.g., UK Biobank, FinnGen, disease‑specific GWAS), and do they remain significant after correction for multiple testing?",
        "How is the target’s expression or activity altered in relevant tissues, cell types, or disease stages (e.g., fold change in RNA/protein, post‑translational modifications)? Specify assay type, sample origin, and quantitative effect size.",
        "What pathway or network data support a causal role (e.g., upstream regulators, downstream effectors, membership in disease modules, co‑expression networks)? Summarize key nodes and directionality of effects.",
        "Are there context‑specific or contradictory findings (e.g., tissue‑specific opposite effects, differences between acute vs chronic models, species discrepancies, sex/age‑dependent phenotypes)? Describe conditions and underlying hypotheses."
    ],
    "validation_strength": [
        "Which mechanistic experiments directly modulate the target (knockout/knockdown, CRISPR, overexpression, pharmacological tool compounds, biologics) and what phenotypic or biomarker changes are reported (effect sizes, EC50/IC50, p‑values)?",
        "Do the reported phenotypes align with human disease biology (e.g., changes in disease‑relevant pathways, surrogate endpoints, or clinical biomarkers)? Specify concordant and discordant readouts.",
        "What in vivo models (genetic models, xenografts, diet‑induced, toxin‑induced, patient‑derived models) have been used, and what were the quantitative treatment effects (e.g., delta in disease score, survival, biomarker levels, with statistics)?",
        "Is there any evidence from interventional human studies (approved drugs, experimental agents, natural variants, Mendelian randomization) that modulating this target alters disease risk or progression? Summarize dosage, direction, and magnitude of effect.",
        "How robust and reproducible is the evidence (independent labs, orthogonal methods, blinded/randomized designs, preregistration)? Highlight key limitations, confounders, or missing controls that affect confidence in the target–disease link."
    ],
    "druggability_safety": [
        "What structural or sequence information is available (e.g., resolved 3D structures, homology models, domain architecture), and what does it imply about tractability for small molecules, antibodies, PROTACs, RNA‑based, or other modalities?",
        "Are there known ligands, tool compounds, or clinical agents for this target or close homologues? Summarize binding mode, potency, selectivity profile, and chemical liabilities (e.g., PAINS, off‑target panels).",
        "Is the target located in a compartment and tissue where the proposed modality can realistically reach sufficient exposure (e.g., CNS penetration, tumor microenvironment, secreted vs intracellular vs nuclear)?",
        "What is known about the target’s normal physiological role (e.g., essential gene status, developmental functions, immune homeostasis), and which on‑target safety risks are suggested (e.g., immunosuppression, cardiotoxicity, carcinogenicity)?",
        "Are there genetic or pharmacological data indicating intolerability or toxicity when the target is modulated (e.g., human loss‑of‑function phenotypes, adverse events from drugs hitting this target or its family)? Describe dose, duration, and affected systems.",
        "How selective can modulation be given target family homology (e.g., kinome, GPCR, enzyme families), and what are the key off‑target concerns based on sequence/structural similarity, expression pattern overlap, or known polypharmacology?"
    ],
    "novelty_prioritization": [
        "What is the current level of prior art on this target (publication volume, patent activity, presence in Open Targets or other platforms, number and phase of clinical programmes)? Classify as highly validated, partially explored, or largely novel.",
        "How differentiated is the proposed mechanism of action versus existing standard‑of‑care and late‑stage pipelines for this disease (e.g., orthogonal pathway, complementary mechanism, best‑in‑class vs first‑in‑class potential)?",
        "What critical knowledge gaps remain (e.g., unknown human biomarkers, unclear patient selection strategy, lack of translational models, unresolved mechanism in key cell types), and what specific experiments are suggested to de‑risk these?",
        "How feasible is progressing this target given current assayability (robust biochemical/cell assays, available biomarkers, animal models), medicinal chemistry starting points, and anticipated time/effort to reach a decision‑ready data package?",
        "Considering efficacy, safety, tractability, clinical differentiation, and feasibility, what is the overall recommendation for this target (e.g., high‑priority, watch‑list, low‑priority), and what are the key go/no‑go criteria for the next stage?"
    ],
}


def _build_article_prompt(title: str, abstract: str, article_id: str, target: str) -> str:
    context = f"Article ID: {article_id}\nTitle: {title}\nAbstract: {abstract}"

    prompt = f"""You are an expert drug discovery researcher evaluating a single therapeutic target.

Target of interest: {target}

Analyze this biomedical article ONLY for information relevant to this target and the specified disease context.

Article:
{context}

For this article and this target:

- Answer the questions below only if the article provides evidence relevant to the target; otherwise answer "Not addressed in this article".
- When you provide evidence, always include the article_id ("Article ID: ...") in the evidence strings so that scientists can trace back.

For each category, provide:
- Answer: Yes/No/Partial/Not addressed + brief explanation (1-2 sentences)
- Evidence: Key quotes or data supporting the answer (include article_id in each evidence item)
- Confidence: Low/Medium/High

Also list all gene/protein targets mentioned that are synonyms or closely related to the target of interest.

Questions:
"""
    for category, qs in QUESTIONS.items():
        prompt += f"\n## {category.replace('_',' ').title()}\n"
        for q in qs:
            prompt += f"- {q}\n"

    prompt += f"""
Output ONLY valid JSON in this exact schema:
{{
  "target": "{target}",
  "article_id": "{article_id}",
  "overall_targets": ["gene1", "gene2"],
  "disease_linkage": {{"answer": "...", "evidence": ["..."], "confidence": "High"}},
  "validation_strength": {{"answer": "...", "evidence": ["..."], "confidence": "Medium"}},
  "druggability_safety": {{"answer": "...", "evidence": ["..."], "confidence": "Low"}},
  "novelty_prioritization": {{"answer": "...", "evidence": ["..."], "confidence": "Medium"}},
  "summary_score": "High/Medium/Low priority target"
}}
Do not include any text before or after the JSON.
"""
    return prompt


def _try_parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if "{" in text and "}" in text:
        candidate = text[text.find("{"): text.rfind("}") + 1]
    else:
        candidate = text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": text}


def _llm_analyze_article_gemini(
    client: genai.Client,
    title: str,
    abstract: str,
    article_id: str,
    target: str,
) -> Dict[str, Any]:
    prompt = _build_article_prompt(title, abstract, article_id, target)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text or ""
    return _try_parse_json(text)


def _aggregate_across_articles(
    client: genai.Client,
    per_article_results: List[Dict[str, Any]],
    target: str,
) -> Dict[str, Any]:
    corpus_json = json.dumps(per_article_results, indent=2)

    prompt = f"""
You are an expert drug discovery researcher assessing the completeness of evidence for a single target.

Target of interest: {target}

You are given structured per-article summaries (JSON list). Each entry contains:
- article_id
- title
- category-level answers and evidence
- a summary_score for that article

Per-article summaries:
{corpus_json}

Using ALL articles together, answer these questions for this target at the corpus level:

For each category (disease_linkage, validation_strength, druggability_safety, novelty_prioritization), provide:
- Answer: Yes/No/Partial + concise explanation (2-3 sentences) that integrates all relevant articles.
- Evidence: A list of strings, each including article_id and a short quote or data point (e.g., "[article_id=3] GLP-1R knockdown reduced weight gain by 25% in HFD mice, p<0.01").
- Confidence: Low/Medium/High, based on number of independent studies, consistency, and quality.

Then provide an overall summary_score for this target (High/Medium/Low priority) and a brief justification.

Output ONLY valid JSON in this exact schema:
{{
  "target": "{target}",
  "disease_linkage": {{"answer": "...", "evidence": ["..."], "confidence": "High"}},
  "validation_strength": {{"answer": "...", "evidence": ["..."], "confidence": "Medium"}},
  "druggability_safety": {{"answer": "...", "evidence": ["..."], "confidence": "Low"}},
  "novelty_prioritization": {{"answer": "...", "evidence": ["..."], "confidence": "Medium"}},
  "summary_score": "High/Medium/Low priority target"
}}
Do not include any text before or after the JSON.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text or ""
    return _try_parse_json(text)
