import requests
import pandas as pd
from collections import Counter
from typing import List, Tuple, Dict, Any
from tqdm import tqdm

def fetch_epmc_articles(query: str,
                        from_year: int = 2024,
                        to_year: int = 2025,
                        max_results: int = 2000) -> pd.DataFrame:
    
    """Fetches articles from Europe PMC.
    https://europepmc.org/RestfulWebService#!/Europe32PMC32Articles32RESTful32API/search_articles_get

    Parameters
    ----------
    query : str
        Search query
    from_year : int
        From year, default 2024
    to_year : int
        To year, default 2025
    max_results : int
        Maximum number of results to fetch, default 2000

    Returns
    -------
    pd.DataFrame
        DataFrame of articles with columns:
        ['id', 'source', 'pmid', 'pmcid', 'doi', 'title', 'abstract', 'pubYear', 'primary_url']
        e.g. 
          id          source    pmid      pmcid  doi                            title                     abstract       pubYear  primary_url
          41366037    MED       41366037         10.1038/s41598-025-31533-w     Network pharmacology...   This study...  2025     https://doi.org/10.1038/s41598-025-31533-w
    """

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search" # RestFul API endpoint
    all_rows = []                                                   # Accumulated results
    page_size = 1000                                                # Max allowed per page. WebService limits extraction to 1000 per request. Do not increase beyond 1000.
    page = 0                                                        # To store page number  
    
    pbar = tqdm(total=max_results, desc="Fetching articles", unit="articles")
    
    while len(all_rows) < max_results:                              # Loop until we reach max_results, default 2000. Increasing this may lead to timeouts.  
        params = {
            "query": f"{query} AND PUB_YEAR:[{from_year} TO {to_year}]",
            "format": "json",
            "pageSize": page_size,
            "page": page,
            "resultType": "core",                                   # core: returns full metadata for a given publication ID; including abstract, full text links, and MeSH terms
        }
        
        response = requests.get(url, params=params, timeout=30)
        if not response.ok:
            print(f"Request failed on page {page}: {response.status_code}")
            break
            
        results = response.json()                                  # Parse JSON response into a dictionary 
        articles = results.get("resultList", {}).get("result", []) # Extract articles and return as a list of dictionaries
        
        if not articles:  # No more results
            break
            
        # Process current page
        for art in articles:                                        # Loop through each article dictionary
            if len(all_rows) >= max_results:                        # Check if we've reached max_results
                break
        
            # Extract primary URL of the article
            primary_url = ""
            
            # First preference : fullTextUrl if available 
            ft_list = art.get("fullTextUrlList", {})                # Get fullTextUrlList dictionary
            if ft_list and ft_list.get("fullTextUrl"):              # If fullTextUrl key exists
                first_ft_url = ft_list["fullTextUrl"][0].get("url") # Extract URL
                if first_ft_url:                                    # If URL is not empty  
                    primary_url = first_ft_url                      # Set as primary URL       
            
            # Fallback : canonical links if no full text
            if not primary_url:
                pmcid = (art.get("pmcid") or "").strip()            # Extract PMCID if available
                pmid = (art.get("pmid") or "").strip()              # Extract PMID if available
                doi = (art.get("doi") or "").strip()                # Extract DOI if available
                
                # PMC123456 → "123456"  → https://europepmc.org/article/PMC/123456
                # MEDABC123 → "ABC123"  → https://europepmc.org/article/MED/ABC123
                # 123456    → "123456"  → https://europepmc.org/article/PMC/123456

                if pmcid:
                    core = pmcid.replace("PMC", "") if pmcid.upper().startswith("PMC") else pmcid
                    primary_url = f"https://europepmc.org/article/PMC/{core}"
                elif pmid:
                    primary_url = f"https://europepmc.org/abstract/MED/{pmid}"
                elif doi:
                    primary_url = f"https://doi.org/{doi}"
            # Collect all relevant fields into a row : extract needed fields from article dictionary with "" as default if key not present 
            all_rows.append({
                "id": art.get("id", ""),
                "source": art.get("source", ""),
                "pmid": art.get("pmid", ""),
                "pmcid": art.get("pmcid", ""),
                "doi": art.get("doi", ""),
                "title": art.get("title", ""),
                "abstract": art.get("abstractText", art.get("abstract", "")),
                "pubYear": art.get("pubYear", ""),
                "primary_url": primary_url,  
            })
        
        page += 1
        pbar.update(len(articles))
        pbar.set_postfix({"page": page, "total": len(all_rows)})
    
    pbar.close()  # Clean up progress bar
    
    df = pd.DataFrame(all_rows[:max_results])  # Trim to requested max
    return df