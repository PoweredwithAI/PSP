import pandas as pd
from urllib.parse import urlparse

def build_article_id_token(row: pd.Series) -> str:
    """
    Function to build article IDs (form 'SOURCE:ext_id')needed by Europe PMC annotations API to return gene/protein annotations
    
    Priority:
      1) MED:PMID   for PubMed records
      2) PMC:PMCID  for full-text PubMed Central (remove leading 'PMC' if present)
      3) source:id  as a generic fallback (e.g. PPR:xxxx, AGR:xxxx).
    
    Parameters
    ----------
    row : pd.Series
        Row from articles DataFrame with columns: ['id', 'source', 'pmid', 'pmcid', ...]
    
    Returns
    -------
    str
        Article ID token in the form 'SOURCE:ext_id' or empty string if no valid ID found.
        e.g.
            'MED:41366037'          # for PubMed article with PMID 41366037
            'PMC:1234567'           # for PubMed Central article with PMCID PMC1234567
            'PPR:ABC12345'          # for other sources like Preprints
    """
    pmid = (row.get("pmid") or "").strip()                       # Extract PMID if available
    pmcid = (row.get("pmcid") or "").strip()                     # Extract PMCID if available   
    source = (row.get("source") or "").strip()                   # Extract source (e.g. MED, PMC, PPR, AGR, etc.)
    eid = (row.get("id") or "").strip()                          # Extract ext_id  if available

    # Priority 1: PubMed 
    if pmid:
        return f"MED:{pmid}"
    # Priority 2: PubMed Central
    if pmcid:
        core = pmcid.replace("PMC", "") if pmcid.upper().startswith("PMC") else pmcid    # Remove leading 'PMC' if present
        return f"PMC:{core}"
    # Priority 3: Other sources (preprints, Agricola, etc.) 
    if source and eid:
        return f"{source}:{eid}"
    return ""                                                                             # No valid ID found

def _extract_uniprot_accession(uri: str) -> str:
    """
    Function to build gene/protein IDs (form 'Uniprot url') to work as a unique key for targets
        
    Parameters
    ----------
    uri : str
        URI to Uniprot record.
            e.g.  https://www.uniprot.org/uniprotkb/Q9I8A9/entry --> Q9I8A9
    Returns
    -------
    str
        Uniprot accession extracted from the URI.
        
    """
    path = urlparse(uri).path.strip("/")                                                   # Extract path from URL and remove leading/trailing slashes
    parts = path.split("/")                                                                # Split path into parts                                            
    return parts[1] if len(parts) > 1 else parts[0]                                        # Return second part if exists, else first part (e.g. for /uniprotkb/Q9I8A9/entry or /Q9I8A9)
