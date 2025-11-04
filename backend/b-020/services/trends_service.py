from datetime import datetime
from typing import List, Dict, Any
from pytrends.request import TrendReq
import pandas as pd

from utils.cache import trends_cache
from config import SETTINGS


def _dataframe_to_timeseries(df: pd.DataFrame, keyword: str) -> List[Dict[str, Any]]:
    series = []
    if df is None or df.empty or keyword not in df.columns:
        return series
    for idx, row in df.iterrows():
        try:
            if isinstance(idx, (pd.Timestamp, datetime)):
                ts = idx.to_pydatetime()
            else:
                ts = pd.to_datetime(idx).to_pydatetime()
            series.append({
                'date': ts.isoformat(),
                'value': float(row[keyword]) if pd.notna(row[keyword]) else 0.0,
                'is_partial': bool(row.get('isPartial')) if 'isPartial' in df.columns else False
            })
        except Exception:
            # Skip malformed rows
            continue
    return series


def _df_top_n(df: pd.DataFrame, key_label: str = 'query', value_label: str = 'value', n: int = 10) -> List[Dict[str, Any]]:
    items = []
    if df is None or df.empty:
        return items
    for _, row in df.head(n).iterrows():
        item = {}
        if key_label in row:
            item['query'] = row[key_label]
        elif 'query' in row:
            item['query'] = row['query']
        else:
            # Fallback to first column
            item['query'] = str(row.iloc[0])
        if value_label in row:
            val = row[value_label]
        elif 'value' in row:
            val = row['value']
        else:
            # Fallback to second column if exists
            val = row.iloc[1] if len(row) > 1 else None
        item['value'] = float(val) if pd.notna(val) else None
        items.append(item)
    return items


def get_trends(keywords: List[str], geo: str = 'US', timeframe: str = 'now 7-d', tz: int = 360) -> Dict[str, Any]:
    cache_key = f"trends::{','.join(sorted(keywords))}::{geo}::{timeframe}::{tz}"
    cached = trends_cache.get(cache_key)
    if cached is not None:
        return cached

    pytrends = TrendReq(hl='en-US', tz=tz)

    result: Dict[str, Any] = {'meta': {'geo': geo, 'timeframe': timeframe, 'tz': tz}, 'data': {}}
    try:
        pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
        iot_df = pytrends.interest_over_time()
    except Exception as e:
        # Retry without geo if failure
        try:
            pytrends.build_payload(keywords, timeframe=timeframe)
            iot_df = pytrends.interest_over_time()
        except Exception as e2:
            raise RuntimeError(f"Failed to fetch trends data: {e2}") from e

    # Interest by region
    try:
        by_region = pytrends.interest_by_region(geo=geo, resolution='REGION', inc_low_vol=True)
    except Exception:
        try:
            by_region = pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True)
        except Exception:
            by_region = None

    # Related queries
    try:
        rq = pytrends.related_queries()
    except Exception:
        rq = {}

    for kw in keywords:
        kw_data = {
            'interest_over_time': _dataframe_to_timeseries(iot_df, kw),
            'interest_by_region': [],
            'related_queries': {'top': [], 'rising': []},
        }
        # Process interest by region: top 10 regions for the keyword
        try:
            if by_region is not None and not by_region.empty and kw in by_region.columns:
                region_df = by_region[[kw]].sort_values(by=kw, ascending=False).head(10)
                for idx, row in region_df.iterrows():
                    region_name = None
                    if isinstance(idx, tuple):
                        region_name = ", ".join(str(x) for x in idx)
                    else:
                        region_name = str(idx)
                    kw_data['interest_by_region'].append({
                        'region': region_name,
                        'value': float(row[kw]) if pd.notna(row[kw]) else 0.0
                    })
        except Exception:
            pass

        # Related queries
        try:
            if isinstance(rq, dict) and kw in rq:
                rq_kw = rq.get(kw) or {}
                top_df = rq_kw.get('top')
                rising_df = rq_kw.get('rising')
                kw_data['related_queries']['top'] = _df_top_n(top_df, key_label='query', value_label='value', n=10)
                kw_data['related_queries']['rising'] = _df_top_n(rising_df, key_label='query', value_label='value', n=10)
        except Exception:
            pass

        result['data'][kw] = kw_data

    trends_cache.set(cache_key, result, ttl=SETTINGS['CACHE_TRENDS_TTL'])
    return result

