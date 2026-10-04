from datetime import datetime, timezone, timedelta
import json
import os
import re

from dateutil import parser
import feedparser

# Feeds list from target country
RSS_FEEDS = [
    {"source": "ABC News (AU)", "url": "https://www.abc.net.au/news/feed/51120/rss.xml"},
    {"source": "news.com.au", "url": "https://www.news.com.au/content-feeds/latest-news-national/"},
    {"source": "Guardian Australia", "url": "https://www.theguardian.com/australia-news/rss"},
    {"source": "Sydney Morning Herald", "url": "https://www.smh.com.au/rss/feed.xml"},
    {"source": "The Age", "url": "https://www.theage.com.au/rss/feed.xml"},
    {"source": "SBS News", "url": "https://www.sbs.com.au/news/feed"},
    {"source": "The Conversation (AU)", "url": "https://theconversation.com/au/articles.atom"},
    {"source": "Crikey", "url": "https://www.crikey.com.au/feed/"},
]

CATEGORIES = ["Diplomacy", "Military", "Energy", "Economy", "Local Events"]
COUNTRY_NAME = "australia"
COUNTRY_KEYWORDS = ["australia", "australian", "canberra", "sydney", "melbourne", "brisbane", "perth", "albanese"]

KEYWORD_RULES = {
    "Diplomacy": ["foreign", "diplomat", "treaty", "ambassador", "sanction", "bilateral", "summit", "china", "us", "pacific", "embassy", "trade deal"],
    "Military": ["defence", "defense", "military", "navy", "army", "air force", "aukus", "warship", "troops", "missile", "sub-marine", "security"],
    "Energy": ["energy", "coal", "gas", "solar", "wind", "grid", "power", "emissions", "renewable", "electricity", "mining", "climate"],
    "Economy": ["economy", "inflation", "rba", "interest rate", "tax", "market", "finance", "gdp", "treasury", "housing", "business", "bank"],
}

def parse_date(entry):
    """Extract and parse published date into a timezone-aware UTC datetime."""
    for attr in ("published", "updated", "created"):
        if hasattr(entry, attr):
            try:
                dt = parser.parse(getattr(entry, attr))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)

def categorize_story(title, summary=""):
    """Assign story to one of the 5 allowed categories based on keyword matching."""
    text = f"{title} {summary}".lower()
    
    for category, keywords in KEYWORD_RULES.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords):
            return category
            
    return "Local Events"

def fetch_and_parse_news():
    now = datetime.now(timezone.utc)
    max_age = timedelta(days=7)
    
    categorized_stories = {cat: [] for cat in CATEGORIES}

    for feed_info in RSS_FEEDS:
        feed = feedparser.parse(feed_info["url"])
        
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            
            if not title or not link:
                continue
            
            pub_date = parse_date(entry)
            
            # Filter out stories older than 7 days
            if (now - pub_date) > max_age:
                continue

            # Ensure host country is primary context/subject
            combined_text = f"{title} {summary}".lower()
            if not any(kw in combined_text for kw in COUNTRY_KEYWORDS):
                continue

            category = categorize_story(title, summary)

            story = {
                "title": title,
                "source": feed_info["source"],
                "url": link,
                "published_date": pub_date.isoformat(),
                "category": category
            }

            # Avoid duplicates across sources
            if not any(s["url"] == link or s["title"] == title for s in categorized_stories[category]):
                categorized_stories[category].append(story)

    return categorized_stories

def update_json_file(new_categorized_stories, output_filepath):
    """Load existing JSON (if available) and maintain up to 20 stories per category."""
    existing_data = {cat: [] for cat in CATEGORIES}
    now = datetime.now(timezone.utc)
    max_age = timedelta(days=7)

    if os.path.exists(output_filepath):
        try:
            with open(output_filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for cat in CATEGORIES:
                    # Keep existing entries that are less than 7 days old
                    valid_entries = []
                    for item in loaded.get(cat, []):
                        item_date = parser.parse(item["published_date"])
                        if (now - item_date) <= max_age:
                            valid_entries.append(item)
                    existing_data[cat] = valid_entries
        except Exception:
            pass

    final_data = {}

    for cat in CATEGORIES:
        merged = existing_data[cat]
        existing_urls = {item["url"] for item in merged}

        # Append newly found stories
        for story in new_categorized_stories[cat]:
            if story["url"] not in existing_urls:
                merged.append(story)
                existing_urls.add(story["url"])

        # Sort by published date (newest first)
        merged.sort(key=lambda x: parser.parse(x["published_date"]), reverse=True)

        # Retain at most 20 stories (oldest entries fall off first)
        final_data[cat] = merged[:20]

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    output_path = f"docs/{COUNTRY_NAME}_news.json"
    stories = fetch_and_parse_news()
    update_json_file(stories, output_path)
