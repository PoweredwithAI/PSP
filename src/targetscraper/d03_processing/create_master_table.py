import requests
import pandas as pd
from collections import Counter
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
from collections import Counter, defaultdict
from typing import List, Tuple, Dict, Any, Set
from targetscraper.d02_intermediate.create_int_data import get_gene_annotations_for_articles
from targetscraper.utils import build_article_id_token, _extract_uniprot_accession




def build_top_targets_from_epmc(df_articles: pd.DataFrame,
                                top_k: int = 100
                                ) -> Tuple[List[Tuple[str, int]], Dict[str, Any]]:
    """
    Function to transform the article and annotation data from Europe PMC into a list of top targets 
    based on frequency of mentions across articles and number of articles mentioning each target. 
        
    Parameters
    ----------
    df_articles : pd.DataFrame
        DataFrame of articles with columns: ['id', 'source', 'pmid', 'pmcid', 'doi', 'title', 'abstract', 'pubYear', 'primary_url']
    top_k : int
        Number of top targets to return based on frequency. Default is 100.
    Returns
    -------
    Tuple[List[Tuple[str, int]], Dict[str, Any]]
        - top_targets : List of top_k targets as (key, frequency) tuples sorted by frequency descending.
        - target_info : Dictionary mapping target key to metadata including name, accession, uniprot_url, frequency, n_articles, and list of articleIdTokens.

    """
    print("Building articleIdTokens...")
    df = df_articles.copy()                                                               # Copy to avoid modifying original DataFrame
    df["articleIdToken"] = df.apply(build_article_id_token, axis=1)                       # Build articleIdTokens to send to Annotations API
    df = df[df["articleIdToken"] != ""]                                                   # Filter out rows with empty articleIdTokens
    print(f"Filtered to {len(df)} articles with valid articleIdTokens from original {len(df_articles)}.")
    tokens = df["articleIdToken"].tolist()                                                # Extract list of articleIdTokens  
    print("Fetching gene/protein annotations from Europe PMC...")
    freq = Counter()                                                                      # Counter to track target frequencies
    ann_map = get_gene_annotations_for_articles(tokens, chunk_size=8)                     # Fetch gene/protein annotations for articles   
    if ann_map:
        n_anns = sum(len(anns) for anns in ann_map.values())
        print(f"Total gene/protein annotations fetched: {n_anns}")
    else:
        print("No annotations returned for any article.")

    # Extract gene/protein targets and calculate frequency
    print("First pass: counting target frequencies...") 
    for aid, anns in tqdm(ann_map.items(),desc="Counting annotations"):                  # Loop through each article
        for ann in anns:                                                                 # Loop through each annotation
            tags = ann.get("tags") or []                                                 # Extract tags 
            if not tags:
                continue
            for tag in tags:                                                             # Loop through each gene / protein tag 
                name = (tag.get("name") or "").strip()                                   # Extract name if available
                uri = (tag.get("uri") or "").strip()                                     # Extract URI if available
                if not uri and not name:
                    continue
                acc = _extract_uniprot_accession(uri) if uri else ""                     # Extract Uniprot accession if URI available 
                key = acc.lower() if acc else name.lower()                               # Use accession as key if available, else name (case insensitive)
                freq[key] += 1                                                           # Increment frequency counter for this target  

    top_targets = freq.most_common(top_k)                                                # Get top_k targets by frequency
    
    # Build set of keys of top k targets for quick lookup
    top_keys: Set[str] = {k for k, _ in top_targets}

    id_to_primary = df.set_index("articleIdToken")["primary_url"].to_dict()            # Map articleIdToken to primary_url for later use

    # Build metadata for top targets
    print("Second pass: building target metadata...")
    target_info: Dict[str, Dict[str, Any]] = {}                                          # Mapping from target key to metadata  
    for aid, anns in tqdm(ann_map.items(),desc="Building target metadata"):
        for ann in anns:
            tags = ann.get("tags") or []                                                 # Extract tags
            if not tags:                                                                 # Skip if no tags  
                continue
            for tag in tags:                                                            # Loop through each gene / protein tag
                name = (tag.get("name") or "").strip()                                  # Extract name if available
                uri = (tag.get("uri") or "").strip()                                    # Extract URI if available
                if not uri and not name:
                    continue
                acc = _extract_uniprot_accession(uri) if uri else ""                    # Extract Uniprot accession if URI available
                key = acc.lower() if acc else name.lower()                              # Use accession as key if available, else name (case insensitive)   

                if key not in top_keys:                                                # Skip if not in top k targets (to limit computation and memory)
                    continue

                if key not in target_info:                                             # Initialize metadata for this target if not already present
                    target_info[key] = {
                        "key": key,
                        "frequency": 0,
                        "articles": {},  # {aid: primary_url}
                        "name": name,
                        "accession": acc,
                        "uniprot_url": uri
                }

                articles = target_info[key]["articles"]                                 # Get existing articles dict already stored for this target 
                if aid not in articles:                                                 # Initialize list for this article if not already present
                    primary_url = id_to_primary.get(aid, "")                            # Lookup once per article
                    articles[aid] = primary_url                                         # Store primary_url for this articleIdToken

                target_info[key]["frequency"] += 1                                      # Increment frequency for this target

    return top_targets, target_info   
                                                          