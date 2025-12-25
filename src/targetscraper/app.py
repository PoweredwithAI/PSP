import streamlit as st
import pandas as pd
from targetscraper.d01_data.load_data import fetch_epmc_articles
from targetscraper.d03_processing.create_master_table import build_top_targets_from_epmc
from targetscraper.d04_postprocessing.analysis import analyze_articles, corpus_to_df, per_article_long
from targetscraper.utils import build_article_id_token

def add_article_id_tokens(df_articles: pd.DataFrame) -> pd.DataFrame:
    """
    Add articleIdToken column to df_articles using the same
    build_article_id_token logic used in build_top_targets_from_epmc.
    """
    df = df_articles.copy()
    df["articleIdToken"] = df.apply(build_article_id_token, axis=1)
    return df

def build_article_id_token_from_row(row: pd.Series) -> str:
    """
    Rebuilds the Europe PMC articleIdToken used in annotations,
    e.g. MED:41116265 or PMC:1234567, from df_articles row.
    """
    source = (row.get("source") or "").strip()
    pmid = (row.get("pmid") or "").strip()
    pmcid = (row.get("pmcid") or "").strip()
    ext_id = (row.get("id") or "").strip()

    # Prefer explicit pmcid / pmid as Europe PMC does
    if source == "PMC" and pmcid:
        core = pmcid.replace("PMC", "") if pmcid.upper().startswith("PMC") else pmcid
        return f"PMC:{core}"
    if source == "MED" and pmid:
        return f"MED:{pmid}"

    # Fallbacks if annotations used extId alone
    if source and ext_id:
        return f"{source}:{ext_id}"
    if ext_id:
        return ext_id
    return ""


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

@st.cache_data
def build_targets_df(_df_articles: pd.DataFrame, _top_k: int, _query: str, _from_year: int, _to_year: int, _max_results: int) -> pd.DataFrame:
    """Build cached targets DataFrame from articles + top_k + search params"""
    top_targets, target_info = build_top_targets_from_epmc(_df_articles, top_k=_top_k)


    rows = []
    for key, count in top_targets:
        info = target_info.get(key, {})
        n_articles = len(info.get("articles", {}))
        article_links = list(info.get("articles", {}).items())
        rows.append({
            "name": info.get("name", key),
            "accession": info.get("accession"),
            "frequency": info.get("frequency", count),
            "uniprot_url": info.get("uniprot_url"),
            "n_articles": n_articles,
            "article_links": article_links,
        })
    return pd.DataFrame(rows)

def main():
    st.set_page_config(page_title="Target Explorer", layout="wide")
    st.title("🧬 Target Explorer")
    st.markdown("**Annotated from Europe PMC**", unsafe_allow_html=True)

    # Initialize session state
    if 'df_articles' not in st.session_state:
        st.session_state.df_articles = None
    if 'df_targets' not in st.session_state:
        st.session_state.df_targets = None

    # Sidebar Section: user‑controllable inputs
    
    with st.sidebar:
        st.header("🔍 Search Parameters")
        query = st.text_input("", value="obesity targets", label_visibility="collapsed")
        from_year = st.sidebar.number_input("📅 From year", min_value=1900, max_value=2100, value=2023, step=1)
        to_year = st.sidebar.number_input("📅 To year", min_value=1900, max_value=2100, value=2025, step=1)
        max_results = st.sidebar.number_input("📈 Max results", min_value=10, max_value=5000, value=20, step=10)

        top_k = st.sidebar.number_input("🎯 Top targets (K)", min_value=1, max_value=500, value=50, step=5)

        if st.button("🚀 Run search", type="primary", use_container_width=True):
            with st.spinner("Fetching articles and processing targets..."):
                df_articles = fetch_epmc_articles(
                    query=query, from_year=int(from_year), to_year=int(to_year), max_results=int(max_results)
                )
                st.session_state.df_articles = df_articles
                # Pass search params to invalidate cache on new searches
                st.session_state.df_targets = build_targets_df(
                    df_articles, int(top_k), query, int(from_year), int(to_year), int(max_results)
                )
            st.sidebar.success("✅ Search complete!")

    # Article Section

    if st.session_state.df_articles is not None:
        
        st.subheader("📄 Articles")
        st.markdown(f"Total articles fetched: **{len(st.session_state.df_articles)}**")
        st.dataframe(
            st.session_state.df_articles[["title", "pubYear", "primary_url"]],
            column_config={"primary_url": st.column_config.LinkColumn("Article Link")},
            hide_index=True
        )

    # Targets Section

    if st.session_state.df_targets is not None:
        st.subheader("🏆 Top targets")

        
        df_display = st.session_state.df_targets[
        ["name", "frequency", "n_articles", "uniprot_url", "accession", "article_links"]
    ].sort_values("n_articles", ascending=False)
    
        st.dataframe(
            df_display,
            column_config={
                "uniprot_url": st.column_config.LinkColumn("UniProt")
    },
    hide_index=True,
            use_container_width=True
        )
        
        st.subheader("📊 Articles by Target")
        selected = st.selectbox("Target", st.session_state.df_targets["name"])
        st.session_state["selected_target"] = selected

        if selected:
            df_targets = st.session_state.df_targets
            df_articles = st.session_state.df_articles

            target_row = df_targets[df_targets["name"] == selected]
            if not target_row.empty:
                article_links = target_row.iloc[0]["article_links"]  # list of (aid, url)

                st.markdown(f"**Articles mentioning {selected}** ({len(article_links)} found)")
                for aid, url in article_links:
                    st.markdown(f"[{aid}]({url})")

                # --- Build rich table with both article metadata + original IDs/URLs + source ---

                # 1) Build set of articleIdTokens from article_links (exact aids from annotations)
                article_ids = [aid for aid, _ in article_links]
                aid_set = set(article_ids)

                # 2) Add articleIdToken to df_articles using the *same* build_article_id_token
                df_articles_with_tokens = add_article_id_tokens(df_articles)

                # 3) Filter df_articles by tokens that appear in article_links
                mask = df_articles_with_tokens["articleIdToken"].isin(aid_set)
                df_match = df_articles_with_tokens[mask].copy()

                # 4) Base metadata columns (including source and id)
                base_cols = [
                    "source",
                    "id",
                    "title",
                    "abstract",
                    "pubYear",
                    "pmid",
                    "pmcid",
                    "doi",
                    "primary_url",
                    "articleIdToken",
                ]
                base_cols = [c for c in base_cols if c in df_match.columns]
                df_export = df_match[base_cols].copy()

                # 5) Map original article_id + article_url from article_links
                link_map = {aid: url for aid, url in article_links}

                df_export["article_id"] = df_export["articleIdToken"]       # e.g. MED:41032481
                df_export["article_url"] = df_export["article_id"].map(link_map)
                df_export["target_name"] = selected

                # 6) Reorder columns nicely
                col_order = [
                    "target_name",
                    "source",
                    "article_id",    # MED:41032481 / PMC:1234567
                    "article_url",   # from target_info
                    "id",            # numeric ID
                    "title",
                    "abstract",
                    "pubYear",
                    "pmid",
                    "pmcid",
                    "doi",
                    "primary_url",
                    "articleIdToken",
                ]
                col_order = [c for c in col_order if c in df_export.columns]
                df_export = df_export[col_order]

                # Drop redundant duplicates
                drop_cols = ["doi", "primary_url", "articleIdToken"]
                df_export = df_export.drop(columns=[c for c in drop_cols if c in df_export.columns])
                st.markdown("**Articles table to export**")
                st.dataframe(df_export, hide_index=True, use_container_width=True)

                if not df_export.empty:
                    csv_bytes = convert_df_to_csv(df_export)
                    st.download_button(
                        label=f"📥 Download {len(df_export)} articles for {selected} as CSV",
                        data=csv_bytes,
                        file_name=f"{selected.replace(' ', '_').replace('/', '_')}_articles.csv",
                        mime="text/csv",
                        key=f"download-{selected}",
                        use_container_width=True,
                    )
                else:
                    st.info("No matching articles found to export for this target.")


    # ---------------- Target Analysis for prioritization ----------------
    
    if st.session_state.df_targets is not None and st.session_state.df_articles is not None:
        st.subheader("🎯 Target Analysis for prioritization")

        st.markdown(
            """
This section will let you assess the target information across these selected articles across four categories: **Disease Linkage**, **Validation Strength**, **Druggability Safety**, and **Novelty Prioritization**.  
The current model uses Google's Gemini LLM Stack to analyze the articles.

Key criteria analyzed:
- **Disease Linkage**: Genetic evidence, clinical associations, pathway involvement, .
- **Validation Strength**: Experimental validation, functional studies, expression data.
- **Druggability Safety**: Known druggability, safety profiles, toxicity data.
- **Novelty Prioritization**: Novelty score, uniqueness of target, innovation potential.

For running this section, please use a **Google AI Studio API key** as input. Google's free version will allow testing of ~15 articles before limits. You can enter your paid API key without any hesitation. The code will **not store this key beyond your run**. You can always create a key for this application and delete it.

For customization to criteria or tech stack, or deployment at your site, please contact us.
            """,
            unsafe_allow_html=False,
        )

        # Choose target (reuse same selection)
        st.markdown("**Select target for LLM-based prioritization**")
        target_for_llm = st.session_state.get("selected_target")
        if not target_for_llm:
            st.info("Select a target in the '📊 Articles by Target' section above to run LLM-based prioritization.")
            return


        # API key input (hidden)
        api_key_input = st.text_input(
            "Google AI Studio API key",
            type="password",
            help="Used only in this session to call Gemini; not stored server-side.",
        )

        max_articles = st.number_input(
            "Max articles to analyze with LLM. Use upto 10 for free tier.",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
        )

        run_llm = st.button("⚙️ Run target analysis with Gemini")

        if run_llm:
            if not api_key_input.strip():
                st.error("Please enter a valid Google AI Studio API key to run the analysis.")
            else:
                with st.spinner("Running Gemini analysis for the selected target..."):
                    # Build df_export (same as earlier) for the selected target
                    df_targets = st.session_state.df_targets
                    df_articles = st.session_state.df_articles

                    target_row = df_targets[df_targets["name"] == target_for_llm]
                    if target_row.empty:
                        st.error("No matching target found in the targets table.")
                    else:
                        article_links = target_row.iloc[0]["article_links"]  # list[(aid, url)]

                        # Rebuild df_export as before (can refactor into a helper if you like)
                        article_ids = [aid for aid, _ in article_links]
                        aid_set = set(article_ids)
                        df_articles_with_tokens = add_article_id_tokens(df_articles)
                        mask = df_articles_with_tokens["articleIdToken"].isin(aid_set)
                        df_match = df_articles_with_tokens[mask].copy()

                        base_cols = [
                            "source", "id", "title", "abstract", "pubYear",
                            "pmid", "pmcid", "doi", "primary_url", "articleIdToken",
                        ]
                        base_cols = [c for c in base_cols if c in df_match.columns]
                        df_export = df_match[base_cols].copy()

                        link_map = {aid: url for aid, url in article_links}
                        df_export["article_id"] = df_export["articleIdToken"]
                        df_export["article_url"] = df_export["article_id"].map(link_map)
                        df_export["target_name"] = target_for_llm

                        # Run LLM analysis (limit by max_articles)
                        df_for_llm = df_export[["title", "abstract", "article_id", "target_name"]].rename(
                            columns={"target_name": "target_name"}
                        )
                        df_per_article, corpus_result = analyze_articles(
                            df_articles=df_for_llm,
                            target_name=target_for_llm,
                            api_key=api_key_input,
                            model_id="gemini-2.5-flash",
                            max_articles=int(max_articles),
                        )

                        df_corpus = corpus_to_df(corpus_result)

                # Display results if run succeeded
                if run_llm and 'df_per_article' in locals():
                    # Merge article URLs back into per-article df for display
                    df_display_articles = df_per_article.merge(
                        df_export[["article_id", "article_url"]],
                        on="article_id",
                        how="left",
                    )

                    # Reorder so link + article_id are first
                    cols_order = ["article_id", "article_url"] + [
                        c for c in df_display_articles.columns
                        if c not in ("article_id", "article_url")
                    ]
                    df_display_articles = df_display_articles[cols_order]

                    # 1) Long, category-level view (includes all other columns via join key)
                    df_per_article_long = per_article_long(df_display_articles)

                    st.markdown("### 📑 Article-level extraction (by category)")
                    st.dataframe(
                        df_per_article_long,
                        hide_index=True,
                        use_container_width=True,
                    )

                    # 2) Full JSON + metadata table for temp reference and debugging
                    st.markdown("### 📑 Article-level raw results")
                    st.dataframe(
                        df_display_articles,
                        column_config={
                            "article_url": st.column_config.LinkColumn("Article link"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )
                    # 3) Corpus-level summary
                    
                    st.markdown("### 🧩 Corpus-level summary")
                    st.dataframe(df_corpus, hide_index=True, use_container_width=True)

                    # Optional: CSV downloads
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            "📥 Download article-level extraction (CSV)",
                            data=df_display_articles.to_csv(index=False).encode("utf-8"),
                            file_name=f"{target_for_llm.replace(' ', '_')}_article_llm_analysis.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                    with col_b:
                        st.download_button(
                            "📥 Download corpus-level summary (CSV)",
                            data=df_corpus.to_csv(index=False).encode("utf-8"),
                            file_name=f"{target_for_llm.replace(' ', '_')}_corpus_llm_summary.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

    # ---------------- existing footer below here ----------------


    # Footer - always visible
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col3:
        st.markdown('<p style="text-align: right; font-weight: bold;">Contact</p>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 14px;text-align: right">🔗 <a href="https://github.com/PoweredwithAI/PSP">GitHub Repository</a></p>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 14px;text-align: right">🔗 <a href="https://www.linkedin.com/in/akakar/">My LinkedIn</a></p>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<p style="text-align: center; font-weight: bold;">🙏 Europe PMC + UniProt</p>', unsafe_allow_html=True)
    
    with col1:
        st.markdown("**🎯 Literature-based target discovery**")
    
    st.caption("v1.0 | Pioneer Spirit Platform - AI Solutions built for drug discovery and digital health research")

# Clear button (keep at end)
    with st.sidebar:
            if st.button("🗑️ Clear results"):
                # Clear cache + session state
                st.cache_data.clear()
                st.session_state.df_articles = None
                st.session_state.df_targets = None
                st.rerun()

if __name__ == "__main__":
    main()

