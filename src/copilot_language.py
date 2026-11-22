"""Conservative multilingual aliases for the FundCopilot question grammar."""
import re
import unicodedata

import pandas as pd

LANGUAGES = ("en", "fr", "ar", "darija")

ALIASES = {
    "Actions": ("actions", "equities", "stocks", "أسهم", "الأسهم", "l ashom"),
    "Diversifiés": ("diversifies", "diversified", "mixed funds", "متنوعة", "المتنوعة"),
    "Monétaire": ("monetaire", "money market", "monetary", "نقدية", "النقدية"),
    "Obligations CT": ("obligations ct", "short term bonds", "سندات قصيرة الأجل"),
    "Obligations MLT": ("obligations mlt", "medium long term bonds", "سندات متوسطة وطويلة الأجل"),
    "Contractuel": ("contractuel", "contractual", "تعاقدية", "التعاقدية"),
    "TOTAL": ("total", "market total", "ensemble du marche", "إجمالي السوق", "السوق كامل"),
}

TERMS = {
    "assets": ("net assets", "net asset", "actif net", "actifs nets", "صافي الأصول", "الأصول الصافية", "actif net dyal"),
    "index": ("performance index", "performance indices", "index", "indices", "indice", "مؤشر", "المؤشر", "مؤشرات"),
    "flows": ("subscriptions", "subscription", "redemptions", "redemption", "souscriptions", "souscription", "rachats", "rachat", "اشتراكات", "اكتتابات", "الاكتتابات", "استردادات", "الاستردادات"),
    "net_flow": ("net subscriptions", "net flows", "souscriptions nettes", "flux nets", "صافي الاكتتابات"),
    "anomaly": ("anomaly", "anomalies", "alert", "alerts", "alerte", "alertes", "شذوذ", "تنبيه", "تنبيهات"),
    "explain": ("explain", "why", "explique", "expliquer", "pourquoi", "اشرح", "لماذا", "3lach", "3lash"),
    "published": ("published", "publie", "publiee", "publiees", "منشور", "منشورة"),
    "calculated": ("calculated", "calcule", "calculee", "محسوب", "محسوبة"),
    "weekly": ("weekly", "hebdomadaire", "hebdomadaires", "اسبوعي", "اسبوعية"),
    "monthly": ("monthly", "mensuel", "mensuelle", "mensuelles", "شهري", "شهرية"),
    "high": ("highest", "largest", "maximum", "plus eleve", "plus elevee", "plus important", "plus grande", "أعلى", "أكبر", "chkon kber"),
    "low": ("lowest", "smallest", "minimum", "plus bas", "plus faible", "plus petit", "أدنى", "أقل", "chkon sgher"),
    "compare": ("compare", "comparison", "versus", "vs", "comparer", "comparaison", "قارن", "مقارنة"),
    "all": ("by category", "by fund category", "all categories", "par categorie", "par categories", "toutes les categories", "حسب الفئة", "حسب الفئات", "جميع الفئات", "ga3 categories"),
    "latest": ("latest", "most recent", "dernier", "derniere", "derniers", "plus recent", "أحدث", "آخر", "akher", "akhir"),
    "advice": ("recommend", "should i", "invest in", "buy", "sell", "investment advice", "conseille", "conseil", "dois je", "devrais je", "investir", "acheter", "vendre", "استثمر", "أشتري", "نصيحة", "nchri", "nbi3"),
    "unsupported": ("forecast", "predict", "prediction", "prevision", "annual", "yearly", "annuelle", "quarterly", "trimestriel", "average", "moyenne", "volatility", "volatilite", "fund level", "individual funds", "market share", "part de marche", "in mad", "en mad", "in usd", "in eur", "en euros", "causality", "fraud", "fraude", "توقع", "سنوي"),
}

DATE_PATTERN = re.compile(r"(?<!\d)(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})(?!\d)")


def normalize(text):
    folded = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", letters, flags=re.UNICODE))


def has(text, aliases):
    padded = f" {text} "
    return any(f" {normalize(alias)} " in padded for alias in aliases)


def language_for(question, adapter=None):
    words = normalize(question)
    if has(words, ("ch7al", "chhal", "dyal", "bghit", "wach", "chkon", "3lach", "akher", "آخر ديال", "ديال", "شحال")):
        return "darija"
    if re.search(r"[\u0600-\u06ff]", question):
        return "ar"
    if has(words, ("quel", "quels", "quelle", "actif net", "actifs nets", "dernier", "derniere",
                   "comparez", "comparer", "explique", "pourquoi", "souscriptions", "rachats",
                   "indice", "hebdomadaire", "mensuelle", "alerte", "alertes", "plus eleve", "plus faible")):
        return "fr"
    if has(words, ("what", "which", "show", "net assets", "index", "subscriptions", "explain", "latest", "highest", "lowest")):
        return "en"
    proposed = adapter(question) if adapter else None
    return proposed if proposed in LANGUAGES else "en"


def report_dates(question):
    dates = []
    for token in DATE_PATTERN.findall(question):
        parts = re.split(r"[-/]", token)
        if len(parts[0]) == 4:
            year, month, day = map(int, parts)
        else:
            day, month, year = map(int, parts)
        dates.append(pd.Timestamp(year, month, day))
    return tuple(dict.fromkeys(dates))
