import requests
import pandas as pd
from collections import Counter
from typing import List, Tuple, Dict, Any
from tqdm import tqdm

ANN_URL = "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds"                             # Annotations API endpoint


def get_gene_annotations_for_articles(article_ids: List[str],
                                      chunk_size: int = 8) -> Dict[str, List[Dict[str, Any]]]:

    """Call annotationsByArticleIds in small chunks to avoid 414 and API limits.
    https://europepmc.org/AnnotationsApi#!/annotations45api45controller/getAnnotationsArticlesByIdsUsingGET

    Parameters
    ----------
    article_ids : List[str]
        List of article IDs in the form 'SOURCE:ext_id' (e.g. 'MED:12345678', 'PMC:87654321')
    chunk_size : int
        Number of article IDs to include per API call, default 8 which is the maximum allowed. Do not increase beyond 8.

    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        e.g. {"article_id" : list of gene/protein annotations as below}.
 
        Example response structure: {
            "article_id": [
                {
                "annotations": [
                    {
                    "exact": "string",
                    "fileName": "string",
                    "frequency": 0,
                    "id": "string",
                    "postfix": "string",
                    "prefix": "string",
                    "provider": "string",
                    "section": "string",
                    "subType": "string",
                    "tags": [
                        {
                        "name": "string",             # Indicates normalized gene/protein tag
                        "uri": "string"               # URI to Uniprot
                        }
                    ],
                    "type": "string"
                    }
                ],
                "extId": "string",
                "fullTextIdList": [
                    "string"
                ],
                "pmcid": "string",
                "source": "MED"
                }
            ]
            }
    """

    print("Fetching gene annotations for articles...")
    out: Dict[str, List[Dict[str, Any]]] = {}

    # Convert range to list for tqdm
    chunks = list(range(0, len(article_ids), chunk_size))
    for start in tqdm(chunks, desc="Processing article ID chunks"):     
        chunk = article_ids[start:start + chunk_size]
        params = {
            "articleIds": ",".join(chunk),
            "type": "Gene_Proteins",                                 # Filter for gene/protein annotations only
            "section": "Abstract",                                   # Limit to abstract section to keep managable size and avoid accessing full text
            "provider": "Europe PMC",                                # Annotations from Europe PMC used. We can also use "OpenTargets" (jointly or standalone) if needed.
            "format": "JSON",                                        # Request JSON response   
        }
   
        r = requests.get(ANN_URL, params=params, timeout=60)         # Call Annotations API
        if not r.ok:                                                 # Check for request errors                       
            tqdm.write(f"Annotations API error {r.status_code} for chunk starting at {start}: {r.url}")
            continue
   
        data = r.json()                                              # list of {"articleId": "...", "annotations": [...]}
        if isinstance(data, dict):                                   # Handle case where response is a dict with "annotationsByArticle" key
            data = data.get("annotationsByArticle", [])

        for entry in data:                                           # Process each article
            source = entry.get("source")                             # e.g. 'MED', 'PMC'
            ext_id = entry.get("extId")                              # e.g. '12345678', '87654321'
            if source and ext_id:
                 aid = f"{source}:{ext_id}"                          # e.g. 'MED:12345678', 'PMC:87654321'
            else:
                aid = ext_id or source                               # fallback if one is missing
            anns = entry.get("annotations", [])                      # List of all annotations for this article
            gene_anns = [a for a in anns if a.get("type", "").lower().startswith("gene_proteins")] # Filter for gene/protein annotations only
            out[aid] = gene_anns                                     # Store in output dictionary
    return out