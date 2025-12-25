from __future__ import annotations

from typing import Dict, Any, List, Optional
import json

from google import genai
from google.genai import Client

from .llm_prompts import build_article_prompt, build_corpus_prompt  

# ---------- JSON parsing utility ----------

def try_parse_json(text: str) -> Dict[str, Any]:
    """
    Function to transform LLM output text into a JSON dictionary. 
        
    Parameters
    ----------
    text : str
        The raw text output from the LLM.

    Returns
    -------
    Dict[str, Any]
        Parsed JSON dictionary or error information if parsing fails.
    """
    text = text.strip()                                                  # Clean up whitespace
    if "{" in text and "}" in text:                                      # Check for valid JSON
        candidate = text[text.find("{"): text.rfind("}") + 1]            # Extract JSON substring
    else:
        candidate = text                                                 # Use full text if no braces found as fallback 
    try:
        import json                                                      # Import here to avoid top-level dependency if unused
        return json.loads(candidate)                                     # Attempt to parse JSON
    except Exception:
        return {"error": "Failed to parse JSON", "raw": text}            # Return error info on failure


# ---------- LLM-facing helpers ----------

def llm_analyze_article_gemini(
    client: genai.Client,
    title: str,
    abstract: str,
    article_id: str,
    target: str,
    model_id: str = "gemini-2.5-flash",
) -> Dict[str, Any]:

    """
    Function to call Gemini LLM to analyze a single article for a given target. 
        
    Parameters
    ----------
    client : genai.Client
        The Gemini API client.
    title : str
        The article title.
    abstract : str
        The article abstract.
    article_id : str
        Unique identifier for the article.
    target : str
        The target name to focus the analysis on.
    model_id : str
        The Gemini model ID to use. Default is "gemini-2.5-flash

    Returns
    -------
    Dict[str, Any]
        Parsed JSON dictionary or error information if parsing fails.
    """
    
    prompt = build_article_prompt(title, abstract, article_id, target)       # Build the prompt for the article
    # Call Gemini model
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
    )
    # Extract text from response
    text = response.text or ""
    return try_parse_json(text)


def aggregate_across_articles(
    client: genai.Client,
    per_article_results: List[Dict[str, Any]],
    target: str,
    model_id: str = "gemini-2.5-flash",
) -> Dict[str, Any]:

    """
    Function to call Gemini LLM to analyze the corpus of articles for a given target. 
        
    Parameters
    ----------
    client : genai.Client
        The Gemini API client.
    per_article_results : List[Dict[str, Any]]
        List of per-article analysis results.
    target : str
        The target name to focus the analysis on.
    model_id : str
        The Gemini model ID to use. Default is "gemini-2.5-flash

    Returns
    -------
    Dict[str, Any]
        Parsed JSON dictionary or error information if parsing fails.
    """

    prompt = build_corpus_prompt(per_article_results, target)             # Build the prompt for corpus-level analysis
    # Call Gemini model
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
    )
    text = response.text or ""                                           # Extract text from response
    return try_parse_json(text) 