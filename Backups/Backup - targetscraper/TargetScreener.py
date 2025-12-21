# %%
import requests
import pandas as pd
from collections import Counter
from typing import List, Tuple, Dict, Any
from tqdm import tqdm

# ---------- 1. Fetch articles from Europe PMC ----------


# %%
def fetch_epmc_articles(query: str,
                        from_year: int = 2024,
                        to_year: int = 2025,
                        max_results: int = 2000) -> pd.DataFrame:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    all_rows = []
    page_size = 1000  # Max allowed per page
    page = 0
    
    while len(all_rows) < max_results:
        params = {
            "query": f"{query} AND PUB_YEAR:[{from_year} TO {to_year}]",
            "format": "json",
            "pageSize": page_size,
            "page": page,
            "resultType": "core",
        }
        
        response = requests.get(url, params=params, timeout=30)
        if not response.ok:
            print(f"Request failed on page {page}: {response.status_code}")
            break
            
        results = response.json()
        articles = results.get("resultList", {}).get("result", [])
        
        if not articles:  # No more results
            break
            
        # Process current page
        for art in articles:
            if len(all_rows) >= max_results:
                break

            urls = []

            # 1) direct fullTextUrlList if present
            ft_list = art.get("fullTextUrlList", {})
            if ft_list:
                for u in ft_list.get("fullTextUrl", []):
                    url_val = u.get("url")
                    if url_val:
                        urls.append(url_val)

            # 2) canonical Europe PMC / DOI links from IDs
            pmcid = (art.get("pmcid") or "").strip()
            pmid  = (art.get("pmid") or "").strip()
            doi   = (art.get("doi") or "").strip()

            if pmcid:
                core = pmcid.replace("PMC", "") if pmcid.upper().startswith("PMC") else pmcid
                urls.append(f"https://europepmc.org/article/PMC/{core}")
            if pmid:
                urls.append(f"https://europepmc.org/abstract/MED/{pmid}")
            if doi:
                urls.append(f"https://doi.org/{doi}")

            # de‑duplicate while preserving order
            seen = set()
            urls = [u for u in urls if not (u in seen or seen.add(u))]
            # -------------------------------------

            all_rows.append({
                "id": art.get("id", ""),
                "source": art.get("source", ""),
                "pmid": art.get("pmid", ""),
                "pmcid": art.get("pmcid", ""),
                "doi": art.get("doi", ""),
                "title": art.get("title", ""),
                "abstract": art.get("abstractText", art.get("abstract", "")),
                "pubYear": art.get("pubYear", ""),
                "urls": urls,          # <- NEW COLUMN
                "primary_url": urls[0] if urls else "",  # convenient single link
            })
        
        page += 1
        print(f"Fetched page {page} ({len(articles)} articles, total: {len(all_rows)})")
    
    df = pd.DataFrame(all_rows[:max_results])  # Trim to requested max
    return df

# %%
ANN_URL = "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds"


def get_gene_annotations_for_articles(article_ids: List[str],
                                      chunk_size: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    """
    Call annotationsByArticleIds in small chunks to avoid 414 and API limits. [web:74]
    Returns mapping articleId -> list of gene/protein annotations.
    """
    print("Fetching gene annotations for articles...")
    out: Dict[str, List[Dict[str, Any]]] = {}

    # Convert range to list for tqdm
    chunks = list(range(0, len(article_ids), chunk_size))
    for start in tqdm(chunks, desc="Processing article ID chunks"):
        chunk = article_ids[start:start + chunk_size]
        params = {
            "articleIds": ",".join(chunk),
            "type": "Gene_Proteins",
            "section": "Abstract",
            "provider": "Europe PMC",
            "format": "JSON",
        }
   #     print(f"Annotations API Request params: {params}")
        r = requests.get(ANN_URL, params=params, timeout=60)
        if not r.ok:
            tqdm.write(f"Annotations API error {r.status_code} for chunk starting at {start}: {r.url}")
            continue
   #     print(f"Annotations API Request text: {r.text}")

        data = r.json()  # list of {"articleId": "...", "annotations": [...]}
        if isinstance(data, dict):
            data = data.get("annotationsByArticle", [])

        for entry in data:
            source = entry.get("source")
            ext_id = entry.get("extId")
            if source and ext_id:
                 aid = f"{source}:{ext_id}"
            else:
                aid = ext_id or source  # fallback if one is missing
            anns = entry.get("annotations", [])
            gene_anns = [a for a in anns if a.get("type", "").lower().startswith("gene_proteins")]
            out[aid] = gene_anns
    #        print(f"Article ID: {aid}, Gene Annotations: {(gene_anns)}")
    #print(f"Fetched gene annotations for {len(out)} articles.")
    #print(f"Sample articleId and annotations: {list(out.items())}")
    return out


# %%
def build_article_id_token(row: pd.Series) -> str:
    """
    Build a Europe PMC annotations API ID of the form 'SOURCE:ext_id'. [web:88][web:124]

    Priority:
      1) MED:PMID   for PubMed records
      2) PMC:PMCID  for full-text PubMed Central (remove leading 'PMC' if present)
      3) source:id  as a generic fallback (e.g. PPR:xxxx, AGR:xxxx).
    """
    pmid = (row.get("pmid") or "").strip()
    pmcid = (row.get("pmcid") or "").strip()
    source = (row.get("source") or "").strip()
    eid = (row.get("id") or "").strip()

    # PubMed
    if pmid:
        return f"MED:{pmid}"

    # PubMed Central (pmcid often like 'PMC1234567')
    if pmcid:
        core = pmcid.replace("PMC", "") if pmcid.upper().startswith("PMC") else pmcid
        return f"PMC:{core}"

    # Other sources (preprints, Agricola, etc.) [web:70][web:59]
    if source and eid:
        return f"{source}:{eid}"

    return ""


# %%
from collections import Counter, defaultdict
from typing import List, Tuple, Dict, Any, Set
from urllib.parse import urlparse

def _extract_uniprot_accession(uri: str) -> str:
    path = urlparse(uri).path.strip("/")
    parts = path.split("/")
    return parts[1] if len(parts) > 1 else parts[0]

def build_top_targets_from_epmc(df_articles: pd.DataFrame,
                                top_k: int = 100
                                ) -> Tuple[List[Tuple[str, int]], Dict[str, Any]]:
    print("Building articleIdTokens...")
    df = df_articles.copy()
    df["articleIdToken"] = df.apply(build_article_id_token, axis=1)
    df = df[df["articleIdToken"] != ""]
    tokens = df["articleIdToken"].tolist()
    print(f"Have {len(tokens)} articles with usable IDs")
    print("Sample articleIdTokens:", tokens)

    freq = Counter()
    ann_map = get_gene_annotations_for_articles(tokens, chunk_size=8)
    print(f"Fetched annotations for {len(ann_map)} articles")
    if ann_map:
        first_key = next(iter(ann_map))
        print("Sample annotations for one article:", first_key, ann_map[first_key])
    else:
        print("No annotations returned for any article.")

    # 1) First pass: count by accession/name
    print("First pass: counting target frequencies...") 
    for aid, anns in tqdm(ann_map.items(),desc="Counting annotations"):
        for ann in anns:
            tags = ann.get("tags") or []
            if not tags:
                continue
            tag = tags[0]
            name = (tag.get("name") or "").strip()
            uri = (tag.get("uri") or "").strip()
            if not uri and not name:
                continue
            acc = _extract_uniprot_accession(uri) if uri else ""
            key = acc.lower() if acc else name.lower()
            freq[key] += 1

    top_targets = freq.most_common(top_k)
    print("top_targets sample:", top_targets)
    print("type(top_targets):", type(top_targets))

    # 2) Build a lookup of which keys we care about
    top_keys: Set[str] = {k for k, _ in top_targets}

    # 3) Second pass: build rich metadata per target
    print("Second pass: building target metadata...")
    target_info: Dict[str, Dict[str, Any]] = {}
    for aid, anns in tqdm(ann_map.items(),desc="Building target metadata"):
        for ann in anns:
            tags = ann.get("tags") or []
            if not tags:
                continue
            tag = tags[0]
            name = (tag.get("name") or "").strip()
            uri = (tag.get("uri") or "").strip()
            if not uri and not name:
                continue
            acc = _extract_uniprot_accession(uri) if uri else ""
            key = acc.lower() if acc else name.lower()

            if key not in top_keys:
                continue

            if key not in target_info:
                target_info[key] = {
                    "name": name,
                    "accession": acc,
                    "uniprot_url": uri,
                    "frequency": 0,
                    "articles": set(),   # use set to avoid duplicates
                }

            target_info[key]["frequency"] += 1
            target_info[key]["articles"].add(aid)

    # 4) Convert article sets to sorted lists for serialization
    for key, info in target_info.items():
        articles_set = info["articles"]
        info["articles"] = sorted(articles_set)
        info["n_articles"] = len(articles_set)

    return top_targets, target_info


# %%
# Build mapping from articleIdToken -> URLs / primary_url
df_with_tokens = df_articles.copy()
df_with_tokens["articleIdToken"] = df_with_tokens.apply(build_article_id_token, axis=1)

id_to_primary = (
    df_with_tokens
    .set_index("articleIdToken")["primary_url"]
    .to_dict()
)


# %%
# Example usage:
df_articles = fetch_epmc_articles("obesity targets", 2023, 2025,500)
print(f"Fetched {len(df_articles)} articles from Europe PMC.")
top_targets, target_info = build_top_targets_from_epmc(df_articles, top_k=500)

rows = []
for key, count in top_targets:
    info = target_info.get(key, {})
    article_tokens = info.get("articles", [])

    article_links = []
    for aid in article_tokens:
        primary = id_to_primary.get(aid, "")
        if primary:
            article_links.append({
                "articleIdToken": aid,
                "primary_url": primary,
            })

    rows.append({
        "name": info.get("name", key),
        "accession": info.get("accession"),
        "frequency": info.get("frequency", count),
        "uniprot_url": info.get("uniprot_url"),
        "n_articles": info.get("n_articles", 0),
        "articles": article_tokens,
        "article_links": article_links,  # now carries per‑article URLs
    })


# %%
print(pd.DataFrame(rows).head(200))

# %%
import pandas as pd
import json

# rows already built above
df_rows = pd.DataFrame(rows)

# If you have list/dict columns (e.g. articles, article_links), stringify them
for col in ["articles", "article_links"]:
    if col in df_rows.columns:
        df_rows[col] = df_rows[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)

# Write to CSV
df_rows.to_csv("epmc_top_targets.csv", index=False)


# %%



