import os
import json
from typing import Dict, Any, List

import pandas as pd
from google import genai

from .llm_client import llm_analyze_article_gemini, aggregate_across_articles
from .llm_prompts import QUESTIONS

# ---------- Public API ----------

def analyze_articles(
    df_articles: pd.DataFrame,
    target_name: str | None = None,
    api_key: str | None = None,
    model_id: str = "gemini-2.5-flash",
    max_articles: int = 10,
) -> tuple[pd.DataFrame, Dict[str, Any]]:

    """

    Function to analyze a set of articles using Gemini LLM for a specified target. 

    Parameters
    ----------
        df_articles : pd.DataFrame
            DataFrame of articles with columns: ['title', 'abstract', 'article_id' (optional)]
        target_name : str | None
            The target name to focus the analysis on. If None, it will be taken from 'target_name' column in df_articles.
        api_key : str | None
            The Gemini API key. If None, it will be read from environment variable 'GOOGLE_API_KEY' or 'GEMINI_API_KEY'.
        model_id : str
            The Gemini model ID to use. Default is "gemini-2.5-flash".
        max_articles : int
            Maximum number of articles to analyze. Default is 10.

    Returns
    -------
        Dict[str, Any]
            Parsed JSON dictionary or error information if parsing fails.
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

    for _, row in df_articles.head(max_articles).iterrows():   # Loop through each article row till max_articles or DataFrame end
        title = str(row.get("title", "")).strip()              # Extract title and strip leading or trailing whitespace 
        abstract = str(row.get("abstract", "")).strip()        # Extract abstract and strip leading or trailing whitespace
        article_id = str(row.get("article_id", "")).strip()    # Extract article_id and strip leading or trailing whitespace
        if not title or not abstract:
            continue
        # Call Gemini LLM for per-article analysis    
        analysis = llm_analyze_article_gemini(client, title, abstract, article_id, target_name)
        analysis["title"] = title                               # Add title to analysis result
        per_article_results.append(analysis)                    # Append to results list

    df_per_article = pd.DataFrame(per_article_results)      # Convert per-article results to DataFrame

    corpus_result = aggregate_across_articles(client, per_article_results, target_name)  # Aggregate across articles

    return df_per_article, corpus_result

# ---------- Export utilities ----------

CATEGORY_LABELS = {
    "disease_linkage": "Disease linkage",
    "validation_strength": "Validation strength",
    "druggability_safety": "Druggability & safety",
    "novelty_prioritization": "Novelty & prioritization",
}

def per_article_long(df_per_article: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df_per_article.iterrows():
        article_id = r.get("article_id", "")
        for key, label in CATEGORY_LABELS.items():
            block = r.get(key) or {}
            if not isinstance(block, dict):
                continue
            rows.append(
                {
                    "article_id": article_id,
                    "category": label,
                    "answer": block.get("answer", ""),
                    "confidence": block.get("confidence", ""),
                    "evidence": "\n".join(block.get("evidence") or []),
                }
            )
    return pd.DataFrame(rows)

def corpus_to_df(
    corpus_result: Dict[str, Any],
) -> pd.DataFrame:

    """

    Function to flatten corpus_results into rows: section, question, answer, evidence, confidence and convert to DataFrame. 

    Parameters
    ----------
        corpus_result : Dict[str, Any]
            The aggregated corpus result from Gemini LLM.

    Returns
    -------
        pd.DataFrame
            DataFrame containing the flattened corpus results.
    """
    rows: list[Dict[str, Any]] = []                   # List to hold rows for CSV

    for section, q_list in QUESTIONS.items():       # Loop through each section and its questions
        if section not in corpus_result:            # Skip if section not in result
            continue
        sec_block = corpus_result.get(section, {})              # Extract section block
        sec_answer = sec_block.get("answer", "")                # Extract answer and confidence
        sec_conf = sec_block.get("confidence", "")
        evid_list = sec_block.get("evidence", []) or []         # Extract evidence list
        evid_joined = "\n".join(map(str, evid_list))            # Join evidence list with newlines

        for q in q_list:
            # Append row for each question in the section
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

    return pd.DataFrame(rows)
