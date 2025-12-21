import streamlit as st
import pandas as pd
from targetscraper.d01_data.load_data import fetch_epmc_articles
from targetscraper.d03_processing.create_master_table import build_top_targets_from_epmc

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

    # Sidebar: user‑controllable inputs
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

    # Display only if data exists
    if st.session_state.df_articles is not None:
        # Articles section
        st.subheader("📄 Articles")
        st.markdown(f"Total articles fetched: **{len(st.session_state.df_articles)}**")
        st.dataframe(
            st.session_state.df_articles[["title", "pubYear", "primary_url"]],
            column_config={"primary_url": st.column_config.LinkColumn("Article Link")},
            hide_index=True
        )

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
        if selected:
            idx = st.session_state.df_targets[st.session_state.df_targets["name"] == selected].index[0]
            st.markdown(f"Articles mentioning {selected}")
            for aid, url in st.session_state.df_targets.loc[idx, "article_links"]:
                st.markdown(f"[{aid}]({url})")

    # Footer - always visible
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown("**🔗 [GitHub](https://github.com/yourusername/targetscraper)**")
    
    with col2:
        st.markdown("**🙏 Europe PMC + UniProt + Streamlit**")
    
    with col3:
        st.markdown("**🎯 Literature-based target discovery**")
    
    st.caption("v1.0 | Built for drug discovery research")

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

