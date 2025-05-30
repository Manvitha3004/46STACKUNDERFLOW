import yfinance as yf
from textblob import TextBlob
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import json
import os
import logging
import re
import traceback
from collections import Counter, defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("market_analyzer.log"), logging.StreamHandler()]
)
logger = logging.getLogger("MarketAnalyzer")

class MarketAnalyzer:
    def __init__(self):
        self.market_indicators = {
            "^GSPC": "S&P 500",
            "^DJI": "Dow Jones",
            "^IXIC": "NASDAQ",
            "^RUT": "Russell 2000",
            "^VIX": "VIX",
            "^NSEI": "Nifty 50",  # Added Indian index
            "^BSESN": "Sensex"    # Added Indian index
        }
        
        self.sector_etfs = {
            "XLK": "Technology",
            "XLF": "Financials",
            "XLE": "Energy",
            "XLV": "Healthcare",
            "XLI": "Industrials",
            "XLP": "Consumer Staples",
            "XLY": "Consumer Discretionary",
            "XLB": "Materials",
            "XLU": "Utilities",
            "XLRE": "Real Estate"
        }
        
        # Cache for financial data
        self.data_cache = {}
        self.cache_expiry = timedelta(hours=1)  # 1 hour in seconds
        
        # Create data directories
        self.data_dir = "data/analysis"
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_from_cache(self, cache_key):
        """Helper method to safely retrieve data from cache"""
        if cache_key in self.data_cache:
            cache_time, cached_data = self.data_cache[cache_key]
            if isinstance(cache_time, str):
                try:
                    cache_time = datetime.strptime(cache_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return None
            
            if datetime.now() - cache_time < self.cache_expiry:
                return cached_data
        return None

    def _store_in_cache(self, cache_key, data):
        """Helper method to safely store data in cache"""
        self.data_cache[cache_key] = (datetime.now(), data)

    def analyze_security(self, ticker):
        """Comprehensive security analysis with improved error handling"""
        try:
            cache_key = f"{ticker}_security_{datetime.now().strftime('%Y%m%d_%H')}"
            
            # Check cache with improved datetime handling
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                logger.info(f"Using cached security data for {ticker}")
                return cached_data
            
            logger.info(f"Analyzing security data for {ticker}")
            
            # Initialize yfinance with error handling
            try:
                # Don't use cache.clear() as it might not exist in all yfinance versions
                security = yf.Ticker(ticker)
                # Test if we can get basic data
                hist_test = security.history(period='1d')
                if hist_test.empty:
                    logger.warning(f"No historical data available for {ticker}")
                    return self._create_empty_security_data(ticker, "No historical data available")
            except Exception as e:
                logger.error(f"Error initializing ticker {ticker}: {str(e)}")
                return self._create_empty_security_data(ticker, f"Failed to retrieve security: {str(e)}")
            
            # Get security info with error handling
            try:
                info = security.info
            except Exception as e:
                logger.error(f"Error getting info for {ticker}: {str(e)}")
                info = {}
            
            # Get historical data for different timeframes
            data = self._get_historical_data(security)
            
            # Get key statistics
            stats = self._calculate_statistics(info)
            
            # Get company-specific metrics
            company_metrics = self._extract_company_metrics(info, ticker)
            
            # Get sector and industry context
            sector_context = self._get_sector_context(info.get('sector'))
            
            # Get market context
            market_context = self._get_market_context()
            
            # Get price patterns and technical indicators
            technical_analysis = self._get_technical_analysis(data)
            
            # Prepare result
            result = {
                'data': data,
                'info': info,
                'stats': stats,
                'company_metrics': company_metrics,
                'sector_context': sector_context,
                'market_context': market_context,
                'technical_analysis': technical_analysis
            }
            
            # Store in cache with proper datetime
            self._store_in_cache(cache_key, result)
            
            # Save analysis to file
            self._save_analysis(ticker, result)
            
            return result

        except Exception as e:
            logger.error(f"Error in security analysis for {ticker}: {str(e)}")
            logger.error(traceback.format_exc())
            return self._create_empty_security_data(ticker, f"Analysis error: {str(e)}")

    def _get_historical_data(self, security):
        """Helper method to get historical data with error handling"""
        data = {}
        timeframes = {
            'today': {'period': '1d', 'interval': '5m'},
            'week': {'period': '5d', 'interval': '1h'},
            'month': {'period': '1mo', 'interval': '1d'},
            'year': {'period': '1y', 'interval': '1d'}
        }
        
        for timeframe, params in timeframes.items():
            try:
                df = security.history(period=params['period'], interval=params['interval'])
                if df.empty:
                    logger.warning(f"No {timeframe} data available")
                    data[timeframe] = pd.DataFrame()
                else:
                    data[timeframe] = df
            except Exception as e:
                logger.error(f"Error getting {timeframe} data: {str(e)}")
                data[timeframe] = pd.DataFrame()
                
        return data

    def _calculate_statistics(self, info):
        """Calculate key statistics from security info"""
        return {
            'Market Cap': info.get('marketCap'),
            'PE Ratio': info.get('trailingPE'),
            'EPS': info.get('trailingEps'),
            'Dividend Yield': info.get('dividendYield'),
            '52 Week High': info.get('fiftyTwoWeekHigh'),
            '52 Week Low': info.get('fiftyTwoWeekLow'),
            'Average Volume': info.get('averageVolume'),
            'Beta': info.get('beta')
        }

    def _create_empty_security_data(self, ticker, error_message):
        """Create an empty security data structure with error information"""
        return {
            'error': error_message,
            'ticker': ticker,
            'data': {
                'today': pd.DataFrame(),
                'week': pd.DataFrame(),
                'month': pd.DataFrame(),
                'year': pd.DataFrame()
            },
            'info': {},
            'market_context': self._get_market_context(),
            'success': False
        }

    def _save_analysis(self, ticker, analysis_data):
        """Save analysis results to a file with improved formatting"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{ticker}_{timestamp}.txt"
            filepath = os.path.join(self.data_dir, filename)
            
            # Create a readable summary for storage
            summary = [f"=== Market Analysis for {ticker} ==="]
            summary.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            summary.append("")
            
            # Company Information
            if 'info' in analysis_data and analysis_data['info']:
                info = analysis_data['info']
                summary.append("Company Information:")
                summary.append(f"Name: {info.get('longName', ticker)}")
                summary.append(f"Sector: {info.get('sector', 'Unknown')}")
                summary.append(f"Industry: {info.get('industry', 'Unknown')}")
                summary.append(f"Website: {info.get('website', 'Unknown')}")
                summary.append("")
            
            # Price Information
            if 'data' in analysis_data and 'today' in analysis_data['data']:
                today_data = analysis_data['data']['today']
                if not today_data.empty:
                    summary.append("Price Information:")
                    current_price = today_data['Close'].iloc[-1]
                    open_price = today_data['Open'].iloc[0]
                    price_change = current_price - open_price
                    price_change_pct = (price_change / open_price) * 100
                    
                    summary.append(f"Current Price: ${current_price}")
                    summary.append(f"Change: {price_change}")
                    summary.append(f"Change %: {price_change_pct}%")
                    summary.append(f"Day Range: ${today_data['Low'].min()} - ${today_data['High'].max()}")
                    summary.append("")
            
            # Volume Information
            if 'data' in analysis_data and 'today' in analysis_data['data']:
                today_data = analysis_data['data']['today']
                if not today_data.empty and 'Volume' in today_data.columns:
                    summary.append("Volume Information:")
                    current_volume = today_data['Volume'].sum()
                    avg_volume = today_data['Volume'].mean()
                    volume_change = ((current_volume - avg_volume) / avg_volume) * 100
                    
                    summary.append(f"Current Volume: {current_volume}")
                    summary.append(f"Average Volume: {avg_volume}")
                    summary.append(f"Volume Change: {volume_change}%")
                    summary.append("")
            
            # Key Factors
            summary.append("Key Factors Affecting Price:")
            summary.append("")
            
            # Market Context
            if 'market_context' in analysis_data:
                summary.append("Market Context:")
                context = analysis_data['market_context']
                for index_name, index_data in context.items():
                    if isinstance(index_data, dict) and 'change_pct' in index_data:
                        summary.append(f"- {index_name}: {index_data['change_pct']}%")
                summary.append("")
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(summary))
            
            logger.info(f"Analysis saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving analysis for {ticker}: {str(e)}")
            logger.error(traceback.format_exc())




    # def compute_price_news_correlation(self, security_data, news_analysis, days=10):
    #     """
    #     Compute correlation between price movements and negative news
        
    #     Args:
    #         security_data: Dictionary with security data including historical prices
    #         news_analysis: Dictionary with news sentiment analysis
    #         days: Number of days to analyze (default: 10)
            
    #     Returns:
    #         Dictionary with correlation data and statistics
    #     """
    #     try:
    #         if not security_data or 'data' not in security_data:
    #             return {'error': 'No security data available'}
                
    #         # Try to get data from week, month, or year depending on availability
    #         if 'week' in security_data['data'] and not security_data['data']['week'].empty:
    #             price_data = security_data['data']['week']
    #         elif 'month' in security_data['data'] and not security_data['data']['month'].empty:
    #             price_data = security_data['data']['month']
    #         elif 'year' in security_data['data'] and not security_data['data']['year'].empty:
    #             price_data = security_data['data']['year']
    #         else:
    #             return {'error': 'No historical price data available'}
            
    #         # Limit to requested number of days
    #         price_data = price_data.iloc[-days:] if len(price_data) > days else price_data
            
    #         # Group news by date
    #         news_by_date = defaultdict(lambda: {'total': 0, 'negative': 0, 'neutral': 0, 'positive': 0})
            
    #         if news_analysis and 'sentiments' in news_analysis:
    #             for item in news_analysis['sentiments']:
    #                 if 'timestamp' not in item:
    #                     continue
                        
    #                 # Extract date from timestamp
    #                 date_str = None
    #                 try:
    #                     # Handle different timestamp formats
    #                     timestamp = item['timestamp']
    #                     if ' ' in timestamp:
    #                         date_str = timestamp.split(' ')[0]  # Format: "2025-04-12 09:30"
    #                     elif 'T' in timestamp:
    #                         date_str = timestamp.split('T')[0]  # Format: "2025-04-12T09:30:00"
    #                     else:
    #                         date_str = timestamp  # Already date only
    #                 except:
    #                     continue
                    
    #                 if not date_str:
    #                     continue
                    
    #                 # Count news by sentiment
    #                 news_by_date[date_str]['total'] += 1
                    
    #                 sentiment = item.get('sentiment', 0)
    #                 if sentiment < -0.1:
    #                     news_by_date[date_str]['negative'] += 1
    #                 elif sentiment > 0.1:
    #                     news_by_date[date_str]['positive'] += 1
    #                 else:
    #                     news_by_date[date_str]['neutral'] += 1
            
    #         # Build correlation data
    #         correlation_data = []
            
    #         for i in range(len(price_data)):
    #             date = price_data.index[i].strftime('%Y-%m-%d')
    #             price = price_data['Close'].iloc[i]
                
    #             news_counts = news_by_date.get(date, {'total': 0, 'negative': 0, 'neutral': 0, 'positive': 0})
                
    #             correlation_data.append({
    #                 'date': date,
    #                 'price': price,
    #                 'total_news': news_counts['total'],
    #                 'negative_news': news_counts['negative'],
    #                 'neutral_news': news_counts['neutral'],
    #                 'positive_news': news_counts['positive']
    #             })
            
    #         # Calculate correlation coefficient if enough data points
    #         correlation_coef = None
    #         if len(correlation_data) >= 3:
    #             prices = [item['price'] for item in correlation_data]
    #             neg_news = [item['negative_news'] for item in correlation_data]
                
    #             # Calculate correlation if there's variation in the data
    #             if len(set(prices)) > 1 and len(set(neg_news)) > 1:
    #                 import numpy as np
    #                 correlation_coef = np.corrcoef(prices, neg_news)[0, 1]
            
    #         return {
    #             'data': correlation_data,
    #             'correlation_coefficient': correlation_coef,
    #             'days_analyzed': len(correlation_data)
    #         }
            
    #     except Exception as e:
    #         logger.error(f"Error computing price-news correlation: {str(e)}")
    #         logger.error(traceback.format_exc())
    #         return {'error': f'Error in correlation calculation: {str(e)}'}
    
    def compute_price_news_correlation(self, security_data, news_items):
        """
        Compute correlation between price movements and negative news
        
        Args:
            security_data: Dictionary containing security price data
            news_items: List of news items with sentiment scores
            
        Returns:
            Dictionary containing correlation analysis
        """
        try:
            # Initialize result structure
            result = {
                'correlation_coefficient': None,
                'days_analyzed': 0,
                'data': [],
                'error': None
            }
            
            # Check for valid inputs
            if not security_data or 'data' not in security_data:
                result['error'] = "No security data available"
                return result
                
            if not news_items:
                result['error'] = "No news items available"
                return result
            
            # Try to get data from week, month, or year depending on availability
            if 'week' in security_data['data'] and not security_data['data']['week'].empty:
                price_data = security_data['data']['week']
            elif 'month' in security_data['data'] and not security_data['data']['month'].empty:
                price_data = security_data['data']['month']
            elif 'year' in security_data['data'] and not security_data['data']['year'].empty:
                price_data = security_data['data']['year']
            else:
                result['error'] = 'No historical price data available'
                return result
            
            # Get most recent dates (up to 10 days)
            days_to_analyze = min(10, len(price_data))
            price_data = price_data.iloc[-days_to_analyze:]
            
            # Group news by date
            news_by_date = {}
            
            # Process news items from news_analysis
            if isinstance(news_items, dict) and 'sentiments' in news_items:
                for item in news_items['sentiments']:
                    if 'timestamp' not in item:
                        continue
                        
                    # Extract date from timestamp
                    try:
                        timestamp = item['timestamp']
                        if ' ' in timestamp:
                            date_str = timestamp.split(' ')[0]  # Format: "2025-04-12 09:30"
                        elif 'T' in timestamp:
                            date_str = timestamp.split('T')[0]  # Format: "2025-04-12T09:30:00"
                        else:
                            date_str = timestamp[:10]  # Format: "2025-04-12"

                        if len(date_str) < 10:  # Make sure we have a valid date
                            continue
                            
                        # Initialize date entry if not exists
                        if date_str not in news_by_date:
                            news_by_date[date_str] = {'total': 0, 'negative': 0, 'neutral': 0, 'positive': 0}
                            
                        # Count news by sentiment
                        news_by_date[date_str]['total'] += 1
                        sentiment = item.get('sentiment', 0)
                        
                        if sentiment < -0.1:
                            news_by_date[date_str]['negative'] += 1
                        elif sentiment > 0.1:
                            news_by_date[date_str]['positive'] += 1
                        else:
                            news_by_date[date_str]['neutral'] += 1
                    except:
                        continue
            # Process raw news items
            else:
                for item in news_items:
                    if not item or 'timestamp' not in item:
                        continue
                        
                    try:
                        timestamp = item['timestamp']
                        if ' ' in timestamp:
                            date_str = timestamp.split(' ')[0]
                        elif 'T' in timestamp:
                            date_str = timestamp.split('T')[0]
                        else:
                            date_str = timestamp[:10]

                        if len(date_str) < 10:
                            continue
                            
                        if date_str not in news_by_date:
                            news_by_date[date_str] = {'total': 0, 'negative': 0, 'neutral': 0, 'positive': 0}
                            
                        news_by_date[date_str]['total'] += 1
                        
                        # Get sentiment if available, otherwise perform simple sentiment analysis
                        if 'sentiment' in item:
                            sentiment = item['sentiment']
                        else:
                            # Simple sentiment calculation using TextBlob if available
                            try:
                                from textblob import TextBlob
                                text = f"{item.get('title', '')} {item.get('summary', '')}"
                                sentiment = TextBlob(text).sentiment.polarity
                            except:
                                sentiment = 0  # Default neutral sentiment
                        
                        if sentiment < -0.1:
                            news_by_date[date_str]['negative'] += 1
                        elif sentiment > 0.1:
                            news_by_date[date_str]['positive'] += 1
                        else:
                            news_by_date[date_str]['neutral'] += 1
                    except:
                        continue
            
            # Build correlation data
            correlation_data = []
            prices = []
            neg_news_counts = []
            
            for i in range(len(price_data)):
                date = price_data.index[i].strftime('%Y-%m-%d')
                price = float(price_data['Close'].iloc[i])
                
                # Get news counts for this date
                news_counts = news_by_date.get(date, {'total': 0, 'negative': 0, 'neutral': 0, 'positive': 0})
                neg_news = news_counts['negative']
                
                correlation_data.append({
                    'date': date,
                    'price': price,
                    'total_news': news_counts['total'],
                    'negative_news': neg_news,
                    'neutral_news': news_counts['neutral'],
                    'positive_news': news_counts['positive']
                })
                
                prices.append(price)
                neg_news_counts.append(neg_news)
            
            # Calculate correlation coefficient if enough data points with variation
            if len(prices) >= 2:
                # Check if there's variation in both price and news
                if len(set(prices)) > 1 and sum(neg_news_counts) > 0:
                    try:
                        import numpy as np
                        correlation_coef = np.corrcoef(prices, neg_news_counts)[0, 1]
                        # Handle potential NaN from constant values
                        if np.isnan(correlation_coef):
                            correlation_coef = 0
                        result['correlation_coefficient'] = correlation_coef
                    except Exception as e:
                        logger.error(f"Error calculating correlation: {str(e)}")
                        # Fallback to simple correlation calculation
                        if len(prices) == len(neg_news_counts) and len(prices) > 0:
                            mean_price = sum(prices) / len(prices)
                            mean_news = sum(neg_news_counts) / len(neg_news_counts)
                            
                            numerator = sum((prices[i] - mean_price) * (neg_news_counts[i] - mean_news) 
                                            for i in range(len(prices)))
                            denom_price = sum((p - mean_price) ** 2 for p in prices)
                            denom_news = sum((n - mean_news) ** 2 for n in neg_news_counts)
                            
                            if denom_price > 0 and denom_news > 0:
                                correlation_coef = numerator / ((denom_price * denom_news) ** 0.5)
                                result['correlation_coefficient'] = correlation_coef
            
            result['data'] = correlation_data
            result['days_analyzed'] = len(correlation_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error computing price-news correlation: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'error': f'Error in correlation calculation: {str(e)}',
                'correlation_coefficient': None,
                'days_analyzed': 0,
                'data': []
            }    
    
    def analyze_news_impact(self, news_items):
        """Analyze news impact and sentiment with improved categorization"""
        try:
            if not news_items:
                logger.warning("No news items to analyze")
                return self._get_empty_news_analysis()
                
            # Filter out empty or invalid news items
            valid_news_items = [item for item in news_items if item and 'title' in item and item['title']]
                    
            if not valid_news_items:
                logger.warning("No valid news items to analyze after filtering")
                return self._get_empty_news_analysis()
            
            logger.info(f"Analyzing impact of {len(valid_news_items)} news items")
            
            analysis = {
                'sentiments': [],
                'topics': defaultdict(int),
                'entities': defaultdict(set),
                'keywords': [],
                'average_sentiment': 0,
                'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
                'sources': defaultdict(int),
                'sentiment_label': 'Neutral'  # Default sentiment label
            }

            # Keywords for topic classification
            topic_keywords = {
                'earnings': ['earnings', 'revenue', 'profit', 'loss', 'quarter', 'financial', 'eps', 'income', 'guidance'],
                'merger_acquisition': ['merger', 'acquisition', 'takeover', 'deal', 'buyout', 'purchase', 'acquire'],
                'product_launch': ['launch', 'release', 'new product', 'update', 'unveil', 'introduce', 'announcement'],
                'leadership': ['ceo', 'executive', 'appoint', 'resign', 'management', 'leader', 'director', 'board'],
                'legal_regulatory': ['lawsuit', 'court', 'legal', 'sue', 'settlement', 'regulation', 'compliance', 'fine'],
                'market_trend': ['market', 'index', 'dow', 'nasdaq', 's&p', 'bull', 'bear', 'trend', 'correction'],
                'technology_innovation': ['tech', 'technology', 'innovation', 'patent', 'ai', 'artificial intelligence', 'research'],
                'economic_indicators': ['fed', 'inflation', 'interest rate', 'economy', 'growth', 'recession', 'gdp'],
                'analyst_rating': ['analyst', 'upgrade', 'downgrade', 'rating', 'target', 'buy', 'sell', 'hold', 'overweight'],
                'competition': ['competitor', 'rivalry', 'market share', 'outperform', 'versus', 'competition'],
                'international': ['global', 'international', 'foreign', 'overseas', 'export', 'import', 'tariff', 'trade']
            }
            
            # Process each news item
            total_sentiment = 0
            keyword_counter = Counter()
            news_items_with_sentiment = []
            
            for item in valid_news_items:
                # News content preparation
                title = item['title']
                summary = item.get('summary', '')
                content = f"{title} {summary}"
                
                # Sentiment analysis
                blob = TextBlob(content)
                sentiment_score = blob.sentiment.polarity
                
                # Categorize sentiment
                sentiment_category = 'neutral'
                if sentiment_score > 0.2:
                    sentiment_category = 'positive'
                    analysis['sentiment_distribution']['positive'] += 1
                elif sentiment_score < -0.2:
                    sentiment_category = 'negative'
                    analysis['sentiment_distribution']['negative'] += 1
                else:
                    analysis['sentiment_distribution']['neutral'] += 1
                
                # Extract keywords
                words = re.findall(r'\b[A-Za-z][A-Za-z\-]{2,}\b', content.lower())
                filtered_words = [w for w in words if len(w) > 3 and w not in [
                    'this', 'that', 'these', 'those', 'there', 'their', 'they',
                    'what', 'when', 'where', 'which', 'while', 'with', 'would',
                    'about', 'above', 'after', 'again', 'against', 'could', 'should',
                    'from', 'have', 'having', 'here', 'more', 'once', 'only', 'same', 'some',
                    'such', 'than', 'then', 'through'
                ]]
                keyword_counter.update(filtered_words)
                
                # Topic classification
                content_lower = content.lower()
                detected_topics = []
                for topic, keywords in topic_keywords.items():
                    if any(keyword in content_lower for keyword in keywords):
                        analysis['topics'][topic] += 1
                        detected_topics.append(topic)
                
                # Create sentiment item
                sentiment_item = {
                    'title': title,
                    'sentiment': sentiment_score,
                    'sentiment_category': sentiment_category,
                    'source': item.get('source', 'Unknown'),
                    'url': item.get('url', ''),
                    'timestamp': item.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'topics': detected_topics
                }
                
                # Process entities if available
                if 'entities' in item:
                    sentiment_item['entities'] = item['entities']
                    for entity_type, entities in item['entities'].items():
                        if isinstance(entities, list):  # Ensure entities is a list
                            analysis['entities'][entity_type].update(entities)
                
                # Update source count
                analysis['sources'][item.get('source', 'Unknown')] += 1
                
                analysis['sentiments'].append(sentiment_item)
                news_items_with_sentiment.append((sentiment_item, sentiment_score))
                total_sentiment += sentiment_score

            # Calculate average sentiment
            if valid_news_items:
                analysis['average_sentiment'] = total_sentiment / len(valid_news_items)
                
                # Set overall sentiment label
                if analysis['average_sentiment'] > 0.1:
                    analysis['sentiment_label'] = 'Positive'
                elif analysis['average_sentiment'] < -0.1:
                    analysis['sentiment_label'] = 'Negative'
                else:
                    analysis['sentiment_label'] = 'Neutral'
                
                # Add news items sorted by sentiment impact
                analysis['news_items'] = [item[0] for item in sorted(news_items_with_sentiment, 
                                                                    key=lambda x: abs(x[1]), 
                                                                    reverse=True)]
            
            # Get top keywords
            analysis['keywords'] = [item for item, count in keyword_counter.most_common(20)]
            
            # Convert sets to lists for JSON serialization
            for entity_type in analysis['entities']:
                analysis['entities'][entity_type] = list(analysis['entities'][entity_type])
            
            return analysis

        except Exception as e:
            logger.error(f"Error in news analysis: {str(e)}")
            logger.error(traceback.format_exc())
            return self._get_empty_news_analysis()

    def _get_empty_news_analysis(self):
        """Return empty news analysis structure"""
        return {
            'sentiments': [],
            'topics': defaultdict(int),
            'entities': {'tickers': [], 'companies': [], 'people': [], 'topics': []},
            'keywords': [],
            'average_sentiment': 0,
            'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
            'sources': {},
            'sentiment_label': 'Neutral',
            'news_items': []
        }

    def generate_explanation(self, security_data, news_analysis, ticker):
        """Generate detailed market analysis explanation"""
        try:
            if not security_data:
                return f"Unable to generate analysis for {ticker} due to missing market data."
                
            logger.info(f"Generating explanation for {ticker}")
            
            explanation_parts = []
            
            # 1. Price movement summary
            price_summary = self._generate_price_summary(security_data, ticker)
            if price_summary:
                explanation_parts.append(price_summary)
            
            # 2. News impact summary
            news_summary = self._generate_news_summary(news_analysis, ticker)
            if news_summary:
                explanation_parts.append(news_summary)
            
            # 3. Market context
            market_context = self._generate_market_context(security_data)
            if market_context:
                explanation_parts.append(market_context)
            
            # 4. Sector performance
            sector_context = self._generate_sector_summary(security_data)
            if sector_context:
                explanation_parts.append(sector_context)
            
            # 5. Technical indicators
            technical_summary = self._generate_technical_summary(security_data)
            if technical_summary:
                explanation_parts.append(technical_summary)
            
            # 6. Key takeaway
            key_takeaway = self._generate_key_takeaway(security_data, news_analysis, ticker)
            if key_takeaway:
                explanation_parts.append(key_takeaway)
            
            return "\n\n".join(explanation_parts)

        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            logger.error(traceback.format_exc())
            return f"Analysis for {ticker} is currently unavailable. Please try again later."

    def _generate_price_summary(self, security_data, ticker):
        """Generate price movement summary"""
        try:
            if not security_data or 'data' not in security_data or 'today' not in security_data['data']:
                return None
                
            today_data = security_data['data']['today']
            if today_data.empty:
                return None
                
            current_price = today_data['Close'].iloc[-1]
            open_price = today_data['Open'].iloc[0]
            price_change = current_price - open_price
            price_change_pct = (price_change / open_price) * 100
            
            day_high = today_data['High'].max()
            day_low = today_data['Low'].min()
            
            direction = "up" if price_change > 0 else "down"
            magnitude = "slightly" if abs(price_change_pct) < 1 else "significantly" if abs(price_change_pct) > 3 else "moderately"
            
            summary = f"{ticker} is {direction} {magnitude} by {abs(price_change_pct):.2f}% today, currently trading at ${current_price:.2f}."
            summary += f" The stock opened at ${open_price:.2f} and has ranged from ${day_low:.2f} to ${day_high:.2f} during the session."
            
            # Add volume information if available
            if 'Volume' in today_data.columns:
                current_volume = today_data['Volume'].sum()
                if 'stats' in security_data and 'Average Volume' in security_data['stats']:
                    avg_volume = security_data['stats']['Average Volume']
                    if avg_volume and avg_volume > 0:
                        volume_ratio = current_volume / avg_volume
                        volume_desc = "higher than" if volume_ratio > 1.2 else "lower than" if volume_ratio < 0.8 else "in line with"
                        summary += f" Trading volume is {volume_desc} average."
            
            return summary
        except Exception as e:
            logger.error(f"Error generating price summary: {str(e)}")
            return None

    def _generate_news_summary(self, news_analysis, ticker):
        """Generate news impact summary"""
        try:
            if not news_analysis or 'sentiments' not in news_analysis or not news_analysis['sentiments']:
                return f"No significant news for {ticker} was found."
                
            sentiments = news_analysis['sentiments']
            avg_sentiment = news_analysis['average_sentiment']
            sentiment_desc = "positive" if avg_sentiment > 0.2 else "negative" if avg_sentiment < -0.2 else "neutral"
            
            # Count news by source
            sources_count = len(news_analysis['sources'])
            
            # Get dominant topics
            topics = news_analysis['topics']
            top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:3]
            
            summary = f"Recent news sentiment for {ticker} is overall {sentiment_desc} with {len(sentiments)} articles from {sources_count} sources."
            
            if top_topics:
                topics_text = ", ".join([f"{topic.replace('_', ' ')}" for topic, count in top_topics if count > 0])
                if topics_text:
                    summary += f" Key topics include {topics_text}."
            
            # Get most significant news items (highest sentiment magnitude)
            significant_news = sorted(sentiments, key=lambda x: abs(x['sentiment']), reverse=True)[:2]
            if significant_news:
                summary += " Notable headlines:"
                for item in significant_news:
                    sentiment_word = "positive" if item['sentiment'] > 0.2 else "negative" if item['sentiment'] < -0.2 else "neutral"
                    summary += f"\n- \"{item['title']}\" ({item['source']}, {sentiment_word})"
            
            return summary
        except Exception as e:
            logger.error(f"Error generating news summary: {str(e)}")
            return None

    def _generate_market_context(self, security_data):
        """Generate market context summary"""
        try:
            if 'market_context' not in security_data or not security_data['market_context']:
                return None
                
            context = security_data['market_context']
            
            # Get major indices performance
            indices_perf = []
            for index_name, data in context.items():
                if isinstance(data, dict) and 'change_pct' in data:
                    direction = "up" if data['change_pct'] > 0 else "down"
                    indices_perf.append(f"{index_name} is {direction} {abs(data['change_pct']):.2f}%")
            
            if indices_perf:
                summary = "Market Context: " + ", ".join(indices_perf) + "."
                
                # Determine market sentiment
                up_count = sum(1 for name, data in context.items() 
                             if isinstance(data, dict) and 'change_pct' in data and data['change_pct'] > 0)
                down_count = sum(1 for name, data in context.items() 
                               if isinstance(data, dict) and 'change_pct' in data and data['change_pct'] < 0)
                
                if up_count > down_count:
                    summary += " The broader market is showing positive momentum today."
                elif down_count > up_count:
                    summary += " The broader market is trending lower today."
                else:
                    summary += " Market sentiment is mixed today."
                
                return summary
            return None
        except Exception as e:
            logger.error(f"Error generating market context: {str(e)}")
            return None

    def _generate_sector_summary(self, security_data):
        """Generate sector performance summary"""
        try:
            if 'sector_context' not in security_data or not security_data['sector_context']:
                return None
                
            sector_context = security_data['sector_context']
            sector = security_data.get('info', {}).get('sector', None)
            
            if sector and sector in sector_context:
                sector_perf = sector_context[sector]
                direction = "up" if sector_perf > 0 else "down"
                
                summary = f"Sector Performance: The {sector} sector is {direction} {abs(sector_perf):.2f}% today."
                
                # Compare with stock performance
                if 'data' in security_data and 'today' in security_data['data']:
                    today_data = security_data['data']['today']
                    if not today_data.empty:
                        current_price = today_data['Close'].iloc[-1]
                        open_price = today_data['Open'].iloc[0]
                        price_change_pct = ((current_price - open_price) / open_price) * 100
                        
                        if (price_change_pct > 0 and sector_perf > 0) or (price_change_pct < 0 and sector_perf < 0):
                            relative = "outperforming" if abs(price_change_pct) > abs(sector_perf) else "underperforming"
                            summary += f" The stock is {relative} its sector."
                        else:
                            summary += " The stock is moving contrary to its sector today."
                
                return summary
            return None
        except Exception as e:
            logger.error(f"Error generating sector summary: {str(e)}")
            return None

    def _generate_technical_summary(self, security_data):
        """Generate technical indicators summary"""
        try:
            if 'technical_analysis' not in security_data or not security_data['technical_analysis']:
                return None
                
            tech_analysis = security_data['technical_analysis']
            
            if tech_analysis.get('signals'):
                signals = tech_analysis['signals']
                buy_signals = sum(1 for signal, value in signals.items() if value == 'buy')
                sell_signals = sum(1 for signal, value in signals.items() if value == 'sell')
                neutral_signals = sum(1 for signal, value in signals.items() if value == 'neutral')
                
                if buy_signals > sell_signals and buy_signals > neutral_signals:
                    signal_summary = "bullish"
                elif sell_signals > buy_signals and sell_signals > neutral_signals:
                    signal_summary = "bearish"
                else:
                    signal_summary = "neutral"
                
                summary = f"Technical Analysis: Technical indicators are showing {signal_summary} signals."
                
                # Add key indicators
                key_indicators = []
                if 'rsi' in tech_analysis:
                    rsi = tech_analysis['rsi']
                    rsi_desc = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
                    key_indicators.append(f"RSI is {rsi:.1f} ({rsi_desc})")
                
                if 'macd' in tech_analysis:
                    macd = tech_analysis['macd']
                    macd_desc = "bullish" if macd > 0 else "bearish"
                    key_indicators.append(f"MACD is {macd_desc}")
                
                if key_indicators:
                    summary += " " + ", ".join(key_indicators) + "."
                
                return summary
            return None
        except Exception as e:
            logger.error(f"Error generating technical summary: {str(e)}")
            return None

    def _generate_key_takeaway(self, security_data, news_analysis, ticker):
        """Generate key takeaway conclusion"""
        try:
            # Extract price movement
            price_change_pct = None
            if 'data' in security_data and 'today' in security_data['data']:
                today_data = security_data['data']['today']
                if not today_data.empty:
                    current_price = today_data['Close'].iloc[-1]
                    open_price = today_data['Open'].iloc[0]
                    price_change_pct = ((current_price - open_price) / open_price) * 100
            
            # Extract news sentiment
            avg_sentiment = news_analysis.get('average_sentiment', 0)
            
            # Extract market trend
            market_trend = 0
            if 'market_context' in security_data:
                market_context = security_data['market_context']
                market_changes = [data.get('change_pct', 0) for data in market_context.values() 
                                if isinstance(data, dict) and 'change_pct' in data]
                if market_changes:
                    market_trend = sum(market_changes) / len(market_changes)
            
            # Extract sector trend
            sector_trend = 0
            if 'sector_context' in security_data:
                sector_context = security_data['sector_context']
                sector = security_data.get('info', {}).get('sector', None)
                if sector and sector in sector_context:
                    sector_trend = sector_context[sector]
            
            # Determine key factor
            key_factor = None
            factor_description = None
            
            # News is the key factor
            if abs(avg_sentiment) > 0.3 and ((price_change_pct > 0 and avg_sentiment > 0) or 
                                          (price_change_pct < 0 and avg_sentiment < 0)):
                key_factor = "news"
                sentiment_desc = "positive" if avg_sentiment > 0 else "negative"
                factor_description = f"recent {sentiment_desc} news"
                
                # Add specific news topics if available
                topics = news_analysis.get('topics', {})
                top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:1]
                if top_topics and top_topics[0][1] > 0:
                    factor_description += f" related to {top_topics[0][0].replace('_', ' ')}"
            
            # Market is the key factor
            elif abs(market_trend) > 1.0 and ((price_change_pct > 0 and market_trend > 0) or 
                                          (price_change_pct < 0 and market_trend < 0)):
                key_factor = "market"
                trend_desc = "positive" if market_trend > 0 else "negative"
                factor_description = f"overall {trend_desc} market movement"
            
            # Sector is the key factor
            elif abs(sector_trend) > 1.5 and ((price_change_pct > 0 and sector_trend > 0) or 
                                          (price_change_pct < 0 and sector_trend < 0)):
                key_factor = "sector"
                trend_desc = "strength" if sector_trend > 0 else "weakness"
                sector = security_data.get('info', {}).get('sector', "its sector")
                factor_description = f"{sector} sector {trend_desc}"
            
            # Company-specific is the key factor (default if no other factors identified)
            else:
                key_factor = "company"
                factor_description = "company-specific factors"
                
                # Check for earnings-related news
                if 'topics' in news_analysis and news_analysis['topics'].get('earnings', 0) > 0:
                    factor_description = "recent earnings or financial news"
            
            # Generate the takeaway
            if price_change_pct is not None and factor_description:
                direction = "gain" if price_change_pct > 0 else "decline"
                takeaway = f"Key Takeaway: The primary driver behind {ticker}'s {direction} today appears to be {factor_description}."
                
                # Add recommendation context
                if key_factor == "news" and abs(avg_sentiment) > 0.3:
                    takeaway += " Investors should monitor for additional news developments."
                elif key_factor == "market":
                    takeaway += " The stock is currently moving with the broader market trend."
                elif key_factor == "sector":
                    takeaway += f" Watch other stocks in the {security_data.get('info', {}).get('sector', 'same')} sector for similar patterns."
                
                return takeaway
            
            return None
        except Exception as e:
            logger.error(f"Error generating key takeaway: {str(e)}")
            return None
    # Add these methods to your MarketAnalyzer class

    def _get_market_context(self):
        """Get broader market context with improved error handling and caching"""
        context = {}
        
        for symbol, name in self.market_indicators.items():
            try:
                # Check cache
                cache_key = f"{symbol}_market_{datetime.now().strftime('%Y%m%d_%H')}"
                cached_data = self._get_from_cache(cache_key)
                if cached_data is not None:
                    context[name] = cached_data
                    continue
                
                # Get new data
                index = yf.Ticker(symbol)
                data = index.history(period='1d')
                if not data.empty:
                    current_price = data['Close'].iloc[-1]
                    open_price = data['Open'].iloc[0]
                    change_pct = ((current_price - open_price) / open_price) * 100
                    result = {
                        'change_pct': change_pct,
                        'price': current_price,
                        'volume': data['Volume'].iloc[-1] if 'Volume' in data.columns else 0
                    }
                    context[name] = result
                    
                    # Cache the result
                    self._store_in_cache(cache_key, result)
            except Exception as e:
                logger.error(f"Error getting market data for {name}: {str(e)}")
                continue
                
        return context

    def _get_sector_context(self, sector):
        """Get sector performance context with improved caching"""
        if not sector:
            return {}
            
        sector_performance = {}
        
        # Sector to ETF mapping
        sector_mapping = {
            'Technology': 'XLK',
            'Financial': 'XLF',
            'Financials': 'XLF',
            'Energy': 'XLE',
            'Healthcare': 'XLV',
            'Health Care': 'XLV',
            'Industrial': 'XLI',
            'Industrials': 'XLI',
            'Consumer Staples': 'XLP',
            'Consumer Discretionary': 'XLY',
            'Materials': 'XLB',
            'Utilities': 'XLU',
            'Real Estate': 'XLRE',
            'Communication Services': 'XLC'
        }
        
        try:
            if sector in sector_mapping:
                etf_ticker = sector_mapping[sector]
                cache_key = f"{etf_ticker}_sector_{datetime.now().strftime('%Y%m%d_%H')}"
                
                # Check cache
                cached_data = self._get_from_cache(cache_key)
                if cached_data is not None:
                    sector_performance[sector] = cached_data
                    return sector_performance
                
                # Get new data
                etf = yf.Ticker(etf_ticker)
                data = etf.history(period='1d')
                if not data.empty:
                    current_price = data['Close'].iloc[-1]
                    open_price = data['Open'].iloc[0]
                    change_pct = ((current_price - open_price) / open_price) * 100
                    sector_performance[sector] = change_pct
                    
                    # Cache the result
                    self._store_in_cache(cache_key, change_pct)
        except Exception as e:
            logger.error(f"Error getting sector data for {sector}: {str(e)}")
        
        # Get all sector ETFs for context
        for etf_symbol, etf_sector in self.sector_etfs.items():
            if etf_sector != sector:  # Skip the main sector, we already have it
                try:
                    # Check cache first
                    cache_key = f"{etf_symbol}_sector_{datetime.now().strftime('%Y%m%d_%H')}"
                    cached_data = self._get_from_cache(cache_key)
                    if cached_data is not None:
                        sector_performance[etf_sector] = cached_data
                        continue
                    
                    # Get new data
                    etf = yf.Ticker(etf_symbol)
                    data = etf.history(period='1d')
                    if not data.empty:
                        current_price = data['Close'].iloc[-1]
                        open_price = data['Open'].iloc[0]
                        change_pct = ((current_price - open_price) / open_price) * 100
                        sector_performance[etf_sector] = change_pct
                        
                        # Cache the result
                        self._store_in_cache(cache_key, change_pct)
                except Exception as e:
                    logger.error(f"Error getting sector data for {etf_sector}: {str(e)}")
                    continue
        
        return sector_performance  
    
    
    
    def _get_technical_analysis(self, price_data):
        """Calculate basic technical indicators"""
        if not price_data or 'week' not in price_data or price_data['week'].empty:
            return {}
            
        # Use weekly data for technical analysis
        df = price_data['week'].copy()
        
        # Ensure we have enough data points
        if len(df) < 10:
            return {}
            
        analysis = {}
        
        # Calculate SMA (Simple Moving Average)
        try:
            df['SMA_5'] = df['Close'].rolling(window=5).mean()
            df['SMA_10'] = df['Close'].rolling(window=10).mean()
            
            last_close = df['Close'].iloc[-1]
            last_sma5 = df['SMA_5'].iloc[-1]
            last_sma10 = df['SMA_10'].iloc[-1]
            
            analysis['sma'] = {
                'sma5': last_sma5,
                'sma10': last_sma10,
                'sma5_signal': 'buy' if last_close > last_sma5 else 'sell',
                'sma10_signal': 'buy' if last_close > last_sma10 else 'sell',
                'crossover': 'bullish' if last_sma5 > last_sma10 else 'bearish'
            }
        except Exception as e:
            logger.error(f"Error calculating SMA: {str(e)}")
        
        # Calculate RSI (Relative Strength Index)
        try:
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            last_rsi = df['RSI'].iloc[-1]
            
            analysis['rsi'] = last_rsi
            analysis['rsi_signal'] = 'sell' if last_rsi > 70 else 'buy' if last_rsi < 30 else 'neutral'
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
        
        # Calculate MACD (Moving Average Convergence Divergence)
        try:
            df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
            
            df['MACD'] = df['EMA_12'] - df['EMA_26']
            df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
            
            last_macd = df['MACD'].iloc[-1]
            last_signal = df['Signal_Line'].iloc[-1]
            last_hist = df['MACD_Histogram'].iloc[-1]
            
            analysis['macd'] = last_macd
            analysis['macd_signal'] = 'buy' if last_macd > last_signal else 'sell'
            analysis['macd_histogram'] = last_hist
        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
        
        # Bollinger Bands
        try:
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['Std_Dev'] = df['Close'].rolling(window=20).std()
            
            df['Upper_Band'] = df['SMA_20'] + (df['Std_Dev'] * 2)
            df['Lower_Band'] = df['SMA_20'] - (df['Std_Dev'] * 2)
            
            last_close = df['Close'].iloc[-1]
            last_upper = df['Upper_Band'].iloc[-1]
            last_lower = df['Lower_Band'].iloc[-1]
            
            analysis['bollinger'] = {
                'upper': last_upper,
                'middle': df['SMA_20'].iloc[-1],
                'lower': last_lower,
                'signal': 'sell' if last_close > last_upper else 'buy' if last_close < last_lower else 'neutral'
            }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
        
        # Aggregate signals
        analysis['signals'] = {
            'sma': analysis.get('sma', {}).get('sma5_signal', 'neutral'),
            'rsi': analysis.get('rsi_signal', 'neutral'),
            'macd': analysis.get('macd_signal', 'neutral'),
            'bollinger': analysis.get('bollinger', {}).get('signal', 'neutral')
        }
        
        return analysis  

    def _extract_company_metrics(self, info, ticker):
        """Extract company-specific metrics from ticker info"""
        metrics = {
            'name': info.get('longName', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'country': info.get('country', 'Unknown'),
            'employees': info.get('fullTimeEmployees', None)
        }
        
        # Financial metrics
        metrics['financial'] = {
            'market_cap': info.get('marketCap', None),
            'revenue': info.get('totalRevenue', None),
            'profit_margin': info.get('profitMargins', None),
            'operating_margin': info.get('operatingMargins', None),
            'return_on_equity': info.get('returnOnEquity', None),
            'return_on_assets': info.get('returnOnAssets', None),
            'debt_to_equity': info.get('debtToEquity', None)
        }
        
        # Valuation metrics
        metrics['valuation'] = {
            'pe_ratio': info.get('trailingPE', None),
            'forward_pe': info.get('forwardPE', None),
            'price_to_sales': info.get('priceToSalesTrailing12Months', None),
            'price_to_book': info.get('priceToBook', None),
            'enterprise_to_revenue': info.get('enterpriseToRevenue', None),
            'enterprise_to_ebitda': info.get('enterpriseToEbitda', None)
        }
        
        return metrics