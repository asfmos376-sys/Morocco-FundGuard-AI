"""Deterministic explanations of SmartFlow statistical decisions."""
from math import isfinite

import pandas as pd

from src.anomalies import ANOMALY, CENTER, HISTORY, INSUFFICIENT, MAD, MISSING, OBSERVED, SCORE, STATUS, UNDEFINED
from src.data_loader import ASSETS
from src.validation import CATEGORY, DATE

LABELS = {
    "en": (
        "Report date", "Category", "Metric", "Source sheet", "Original file", "Export line",
        "Observed change", "Historical median", "Historical MAD", "Difference from median",
        "Robust z-score", "Absolute threshold", "Rolling window capacity", "Minimum prior values",
        "Valid prior values used",
    ),
    "fr": (
        "Date du rapport", "Catégorie", "Indicateur", "Feuille source", "Fichier d’origine",
        "Ligne d’export", "Variation observée", "Médiane historique", "MAD historique",
        "Écart à la médiane", "Score z robuste", "Seuil absolu", "Taille maximale de la fenêtre",
        "Minimum de valeurs antérieures", "Valeurs antérieures valides utilisées",
    ),
}

TEXT = {
    "en": {
        ANOMALY: "SmartFlow flagged this observation because |{score}| exceeds {threshold}.",
        INSUFFICIENT: "A score requires {minimum} prior valid observations. This window has only {count}.",
        MISSING: "The observed change is unavailable, so SmartFlow cannot score this report.",
        UNDEFINED: "The median or MAD is unavailable, or the robust score cannot be computed from the baseline.",
        "zero": "Historical MAD is zero. Division by zero leaves the robust score undefined.",
        "normal": "The absolute score |{score}| is at or below {threshold}.",
        "deviation": "The change of {observed} differs from the historical median of {center} by {difference}.",
        "limits": "This comparison describes statistical deviation within the selected historical window. "
                  "It provides neither a causal attribution nor a financial risk probability.",
        "title": "SmartFlow statistical decision report",
    },
    "fr": {
        ANOMALY: "SmartFlow a signalé cette observation car |{score}| dépasse {threshold}.",
        INSUFFICIENT: "Le score exige {minimum} observations antérieures valides. La fenêtre en contient seulement {count}.",
        MISSING: "La variation observée est indisponible. SmartFlow ne peut donc pas calculer de score pour ce rapport.",
        UNDEFINED: "La médiane ou la MAD est indisponible, ou le score robuste ne peut pas être calculé à partir de la référence.",
        "zero": "La MAD historique est nulle. La division par zéro laisse le score robuste indéfini.",
        "normal": "Le score absolu |{score}| est inférieur ou égal à {threshold}.",
        "deviation": "La variation de {observed} s’écarte de la médiane historique de {center} de {difference}.",
        "limits": "Cette comparaison décrit un écart statistique dans la fenêtre historique sélectionnée. "
                  "Elle ne fournit ni attribution causale ni probabilité de risque financier.",
        "title": "Rapport de décision statistique SmartFlow",
    },
}

METRIC_FR = {
    "Calculated seven-day net asset change": "Variation calculée de l’actif net sur sept jours",
    "Published weekly net asset change": "Variation hebdomadaire publiée de l’actif net",
}


def baseline_for(scored, row):
    """Recover the same prior valid points used by the scoring engine."""
    prior = scored.loc[
        scored[CATEGORY].eq(row[CATEGORY])
        & scored[DATE].lt(row[DATE])
        & scored[OBSERVED].notna(),
        [DATE, OBSERVED, STATUS, HISTORY, SCORE],
    ]
    return prior.sort_values(DATE).tail(int(row[HISTORY]))


def rank_alerts(alerts):
    """Rank within the active selection by descending absolute robust score."""
    return alerts.assign(**{"Score magnitude": alerts[SCORE].abs()}).sort_values(
        ["Score magnitude", DATE, CATEGORY], ascending=[False, True, True],
    )


def finite(value):
    return pd.notna(value) and isfinite(value)


def number(value, unit=""):
    return f"{value:.3f}{unit}" if finite(value) else "—"


def explain(row, metric, *, window, minimum, threshold, language="en"):
    """Return localized prose and evidence with shared numeric formatting."""
    observed, center, spread, score = (row[field] for field in (OBSERVED, CENTER, MAD, SCORE))
    difference = observed - center if finite(observed) and finite(center) else None
    count = int(row[HISTORY])
    status = row[STATUS]
    strings = TEXT[language]
    values = {
        "score": number(score), "threshold": number(threshold), "minimum": minimum, "count": count,
        "observed": number(observed, "%"), "center": number(center, "%"),
        "difference": number(difference, " pp"),
    }
    if status in (INSUFFICIENT, MISSING):
        decision = status
    elif not finite(score):
        decision = "zero" if finite(spread) and spread == 0 else UNDEFINED
    else:
        decision = ANOMALY if status == ANOMALY else "normal"

    narrative = strings[decision].format(**values)
    if finite(difference):
        narrative = f"{strings['deviation'].format(**values)} {narrative}"
    if finite(score) and number(abs(score)) == number(threshold) and abs(score) != threshold:
        narrative = narrative.replace(
            strings[decision].format(**values),
            "SmartFlow compares the unrounded score magnitude with the threshold. "
            + ("The score exceeds the threshold." if status == ANOMALY else "The score is below the threshold.")
            if language == "en" else
            "SmartFlow compare la valeur absolue du score non arrondi au seuil. "
            + ("Le score dépasse le seuil." if status == ANOMALY else "Le score est inférieur au seuil."),
        )
    metric_label = METRIC_FR.get(metric, metric) if language == "fr" else metric
    evidence = tuple(zip(LABELS[language], (
        row[DATE].strftime("%Y-%m-%d"), row[CATEGORY], metric_label, ASSETS,
        row.get("Fichier d’origine", "—"), row.get("Ligne export", "—"),
        values["observed"], values["center"], number(spread, " pp"), values["difference"],
        values["score"], f"> {values['threshold']}", window, minimum, count,
    )))
    return strings["title"], narrative, evidence, strings["limits"]


def text_report(explanation):
    title, narrative, evidence, limitations = explanation
    rows = "\n".join(f"{label} · {value}" for label, value in evidence)
    return f"{title}\n\n{narrative}\n\n{rows}\n\n{limitations}\n"
