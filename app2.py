import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd
import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types


# Function to fetch exchange rate data from free API
def get_exchange_rate(from_currency, to_currency):
    # Primary URL
    primary_url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{from_currency.lower()}.json"
    # Fallback URL
    fallback_url = f"https://latest.currency-api.pages.dev/v1/currencies/{from_currency.lower()}.json"

    try:
        response = requests.get(primary_url)
        if response.status_code != 200:
            response = requests.get(fallback_url)

        data = response.json()
        current_rate = data[from_currency.lower()][to_currency.lower()]
        return current_rate
    except Exception as e:
        st.error(f"Failed to fetch exchange rate: {e}")
        return None


# Function to get historical data for chart (last 30 days for better visualization)
def get_historical_rates(from_currency, to_currency, days=7):
    rates = []
    dates = []

    for i in range(days, 0, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/{from_currency.lower()}.json"
        fallback_url = f"https://{date}.currency-api.pages.dev/v1/currencies/{from_currency.lower()}.json"

        try:
            response = requests.get(url)
            if response.status_code != 200:
                response = requests.get(fallback_url)

            if response.status_code == 200:
                data = response.json()
                rate = data[from_currency.lower()][to_currency.lower()]
                rates.append(rate)
                dates.append(date)
        except:
            # Skip if data for this date is not available
            continue

    return dates, rates


# Function to query for news articles using Google Search via Gemini
def query_for_news(from_currency, to_currency):
    # Configure client
    client = genai.Client(
        api_key=st.secrets["API_KEY"]  # In production, use environment variables
    )

    model = "gemini-2.0-flash"
    user_query = f"""
    Search for 4 recent news articles about {from_currency} and {to_currency} exchange rates or economic factors affecting these currencies.

    Return the results in JSON format like this:
    ```json
    [
        {{
            "title": "Article title",
            "source": "Source name",
            "date": "Publication date",
            "summary": "2-3 line summary of the article",
            "url": "article url"
        }},
        ...
    ]
    ```

    Return only the JSON without any additional text or explanation.
    """

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_query)],
        ),
    ]

    tools = [
        types.Tool(
            google_search=types.GoogleSearch()
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        tools=tools,
        response_mime_type="text/plain",
    )

    try:
        result = ""
        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
        ):
            result += chunk.text

        # Extract JSON from the response
        json_start = result.find("```json")
        json_end = result.rfind("```")

        if json_start != -1 and json_end != -1:
            json_text = result[json_start + 7:json_end].strip()
            news_articles = json.loads(json_text)
            return news_articles
        else:
            try:
                # Try parsing the whole thing as JSON
                return json.loads(result)
            except:
                st.error("Failed to parse news response")
                return []
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return []


# Create enhanced chart with Plotly
# Create enhanced chart with Plotly
def create_currency_chart(dates, rates, from_currency, to_currency):
    # Create DataFrame
    df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'rate': rates
    })

    # Calculate percentage change from first day
    first_rate = df['rate'].iloc[0]
    df['percent_change'] = ((df['rate'] - first_rate) / first_rate) * 100

    # Create a figure with secondary y-axis
    fig = go.Figure()

    # Add candlestick-like visualization to highlight daily changes
    for i in range(1, len(df)):
        color = 'rgba(0, 255, 213, 0.7)' if df['rate'].iloc[i] >= df['rate'].iloc[i - 1] else 'rgba(255, 107, 129, 0.7)'
        fig.add_trace(go.Scatter(
            x=[df['date'].iloc[i], df['date'].iloc[i]],
            y=[df['rate'].iloc[i - 1], df['rate'].iloc[i]],
            mode='lines',
            line=dict(color=color, width=8),
            showlegend=False
        ))

    # Add line trace for overall trend
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['rate'],
        mode='lines+markers',
        name=f'Exchange Rate',
        line=dict(color='rgba(74, 144, 226, 0.8)', width=2, shape='spline'),
        marker=dict(size=6, color='rgba(255, 255, 255, 0.9)', line=dict(width=1, color='rgba(74, 144, 226, 1)')),
        hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br><b>Rate:</b> %{y:.6f}<extra></extra>'
    ))

    # Add percentage change trace on secondary y-axis
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['percent_change'],
        mode='lines',
        name='% Change',
        line=dict(color='rgba(255, 209, 102, 0.8)', width=1, dash='dot'),
        yaxis='y2',
        hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br><b>Change:</b> %{y:.2f}%<extra></extra>'
    ))

    # Calculate appropriate y-axis range to focus on changes
    min_rate = df['rate'].min() * 0.998  # Slightly below minimum
    max_rate = df['rate'].max() * 1.002  # Slightly above maximum

    # Update layout with modern styling
    fig.update_layout(
        title=f'{from_currency}/{to_currency} Exchange Rate Trend',
        title_font=dict(size=22, color='white'),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        plot_bgcolor='rgba(17, 25, 40, 0.6)',
        paper_bgcolor='rgba(17, 25, 40, 0)',
        hovermode='x unified',
        margin=dict(l=20, r=20, t=60, b=20),
        height=460,
        yaxis=dict(
            title=dict(
                text=f'{to_currency} per {from_currency}',
                font=dict(size=14)
            ),
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.1)',
            range=[min_rate, max_rate],
            tickformat='.6f' if max_rate - min_rate < 0.1 else '.4f'
        ),
        yaxis2=dict(
            title=dict(
                text='Percent Change (%)',
                font=dict(size=14, color='rgba(255, 209, 102, 0.8)')
            ),
            anchor='x',
            overlaying='y',
            side='right',
            showgrid=False,
            zeroline=True,
            zerolinecolor='rgba(255, 255, 255, 0.3)',
            tickfont=dict(color='rgba(255, 209, 102, 0.8)')
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.1)',
            tickformat='%b %d'
        ),
        font=dict(color='white')
    )

    # Add range selector
    fig.update_xaxes(
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=list([
                dict(count=7, label="7d", step="day", stepmode="backward"),
                dict(count=14, label="14d", step="day", stepmode="backward"),
                dict(step="all", label="All")
            ]),
            font=dict(color='white'),
            bgcolor='rgba(74, 144, 226, 0.4)',
            activecolor='rgba(74, 144, 226, 0.8)'
        )
    )

    # Add annotations for market direction
    overall_change = ((df['rate'].iloc[-1] - df['rate'].iloc[0]) / df['rate'].iloc[0]) * 100
    direction = "↑" if overall_change > 0 else "↓"
    color = "rgba(0, 255, 213, 1)" if overall_change > 0 else "rgba(255, 107, 129, 1)"

    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.01, y=0.98,
        text=f"{direction} {abs(overall_change):.2f}% in {len(df)} days",
        font=dict(size=16, color=color),
        showarrow=False
    )

    # Add animated transitions
    fig.update_layout(transition_duration=500)

    return fig


# Custom CSS for modern UI
def load_css():
    st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .app-header {
        text-align: center;
        padding: 30px 0;
        margin-bottom: 30px;
        background: linear-gradient(180deg, rgba(17, 25, 40, 0.8), rgba(17, 25, 40, 0));
        border-radius: 0 0 30px 30px;
    }
    .currency-input {
        background: rgba(31, 41, 55, 0.7);
        border-radius: 15px;
        padding: 25px;
        margin-bottom: 30px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    .chart-container {
        margin-top: 20px;
        background: rgba(31, 41, 55, 0.5);
        border-radius: 15px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)


# --- Streamlit App ---
def main():
    st.set_page_config(
        page_title="Currency Intelligence Hub",
        page_icon="💱",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    load_css()

    # App Header - Using Streamlit's native components
    st.markdown(
        "<h1 style='text-align: center; font-size: 42px; background: linear-gradient(90deg, #4dd0e1, #64ffda); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Currency Intelligence Hub</h1>",
        unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 16px; color: #9e9e9e; margin-top: -15px;'>Real-time exchange rates, trends, and market insights</p>",
        unsafe_allow_html=True)

    # Currency selection container
    st.markdown("<div class='currency-input'>", unsafe_allow_html=True)

    currencies = ["USD", "EUR", "GBP", "JPY", "CNY", "INR", "AUD", "CAD", "CHF", "SGD"]

    # Use Streamlit columns for layout
    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        from_currency = st.selectbox("From Currency", currencies, index=0)

    with col2:
        st.markdown(
            "<div style='display: flex; justify-content: center; align-items: center; height: 100%; font-size: 28px; color: #4dd0e1;'>➡️</div>",
            unsafe_allow_html=True)

    with col3:
        to_currency = st.selectbox("To Currency", currencies, index=1)

    search_button = st.button("Analyze Currency Pair", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if search_button or 'last_search' in st.session_state:
        # Store the last search in session state
        if search_button:
            st.session_state['last_search'] = (from_currency, to_currency)
        else:
            from_currency, to_currency = st.session_state['last_search']

        # Create two columns for layout
        left_col, right_col = st.columns([1, 1])

        with left_col:
            with st.spinner("Fetching exchange rate data..."):
                # Get current exchange rate
                current_rate = get_exchange_rate(from_currency, to_currency)

                if current_rate:
                    # Get yesterday's rate for comparison
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    yesterday_url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{yesterday}/v1/currencies/{from_currency.lower()}.json"
                    fallback_yesterday_url = f"https://{yesterday}.currency-api.pages.dev/v1/currencies/{from_currency.lower()}.json"

                    try:
                        response = requests.get(yesterday_url)
                        if response.status_code != 200:
                            response = requests.get(fallback_yesterday_url)

                        if response.status_code == 200:
                            data = response.json()
                            yesterday_rate = data[from_currency.lower()][to_currency.lower()]
                            change = current_rate - yesterday_rate
                            percent_change = (change / yesterday_rate) * 100
                    except:
                        change = 0
                        percent_change = 0

                    # Currency card container
                    with st.container():
                        # Using Streamlit components instead of HTML
                        st.subheader("Current Exchange Rate")

                        # Exchange rate display
                        st.markdown(
                            f"<h1 style='font-size: 42px; font-weight: bold; background: linear-gradient(90deg, #4dd0e1, #00bfa5); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>1 {from_currency} = {current_rate:.6f} {to_currency}</h1>",
                            unsafe_allow_html=True)

                        # Daily change
                        if 'change' in locals() and 'percent_change' in locals():
                            change_color = "#00e676" if change >= 0 else "#ff5252"
                            st.markdown(
                                f"<p style='font-size: 18px; color: {change_color};'>{'+' if change >= 0 else ''}{change:.6f} ({'+' if percent_change >= 0 else ''}{percent_change:.2f}%) from yesterday</p>",
                                unsafe_allow_html=True)

                        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")

                    # Get historical data for 30 days for better visualization
                    dates, rates = get_historical_rates(from_currency, to_currency, days=30)

                    if dates and rates:
                        # Create enhanced chart with Plotly
                        fig = create_currency_chart(dates, rates, from_currency, to_currency)

                        # Display chart
                        st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
                        st.plotly_chart(fig, use_container_width=True,
                                        config={'displayModeBar': True, 'responsive': True})
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.error("Could not retrieve sufficient historical data for chart")

        with right_col:
            with st.spinner("Fetching latest news..."):
                # Get news articles
                news_articles = query_for_news(from_currency, to_currency)

                # Using Streamlit container instead of HTML div
                with st.container():
                    st.subheader(f"Market Insights: {from_currency}/{to_currency}")
                    st.caption("Latest news and analysis affecting this currency pair")

                if news_articles and len(news_articles) > 0:
                    # Display each news article in its own container
                    for article in news_articles:
                        with st.container():
                            # Using Streamlit expander for news article
                            with st.expander(article.get('title', 'No Title'), expanded=True):
                                st.markdown(f"**Source:** {article.get('source', 'Unknown Source')}")
                                st.caption(f"Published: {article.get('date', 'Recent')}")
                                st.write(article.get('summary', 'No summary available'))
                                st.markdown(f"[Read more]({article.get('url', '#')})")
                else:
                    st.info("No recent news articles found for these currencies.")


if __name__ == "__main__":
    main()