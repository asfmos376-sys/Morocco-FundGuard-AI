"""Verified OPCVM question answering with explicit report and category scope."""
from dataclasses import dataclass

import re

import pandas as pd

from src.anomalies import (
    ANOMALY, DEFAULT_MINIMUM, DEFAULT_THRESHOLD, DEFAULT_WINDOW, OBSERVED, SCORE, STATUS,
    calculated_weekly_change, detect_anomalies,
)
from src.copilot_language import ALIASES, LANGUAGES, TERMS, has, language_for, normalize, report_dates
from src.data_loader import AMOUNT, ASSETS, FLOWS, INDICES, PROVENANCE, REDS, SUBS, VARIATIONS
from src.explanations import explain
from src.metrics import NET_FLOW, TOTAL, add_net_flows
from src.smartflow import CALCULATED, PUBLISHED
from src.validation import CATEGORY, DATE

SETTINGS = dict(window=DEFAULT_WINDOW, minimum=DEFAULT_MINIMUM, threshold=DEFAULT_THRESHOLD)

# Stable labels and source column names accompany every result.
COPY = {
    "unsupported": (
        "I can answer supported questions about OPCVM assets, indices, flows and SmartFlow alerts.",
        "Je peux répondre aux questions prises en charge sur les actifs, indices, flux et alertes SmartFlow.",
        "يمكنني الإجابة عن الأسئلة المدعومة حول الأصول والمؤشرات والتدفقات وتنبيهات SmartFlow.",
        "N9der njawb 3la actif net, indices, souscriptions, rachats w alertes SmartFlow.",
    ),
    "advice": (
        "I can show published OPCVM data and statistical alerts. Investment decisions need your own assessment.",
        "Je peux présenter les données OPCVM et les alertes statistiques. Les décisions de placement vous appartiennent.",
        "يمكنني عرض بيانات صناديق الاستثمار والتنبيهات الإحصائية. قرارات الاستثمار تتطلب تقييمك الخاص.",
        "N9der nwerri données OPCVM w alertes statistiques. Décision dyal investissement katb9a dyalk.",
    ),
    "category": (
        "Specify a workbook category, TOTAL, or all categories.",
        "Précisez une catégorie du classeur, TOTAL ou toutes les catégories.",
        "حدد فئة من الملف أو إجمالي السوق أو جميع الفئات.",
        "7edded catégorie men fichier, TOTAL, wlla ga3 categories.",
    ),
    "date": (
        "Specify an exact report date as YYYY-MM-DD or DD/MM/YYYY.",
        "Précisez une date de rapport au format AAAA-MM-JJ ou JJ/MM/AAAA.",
        "حدد تاريخ التقرير بصيغة YYYY-MM-DD أو DD/MM/YYYY.",
        "3ti date dyal rapport b format YYYY-MM-DD wlla DD/MM/YYYY.",
    ),
    "missing_date": (
        "There is no report on the requested date.",
        "Aucun rapport à la date demandée.",
        "لا يوجد تقرير في التاريخ المطلوب.",
        "Ma kayn ta rapport f had date.",
    ),
    "missing": (
        "The requested metric is unavailable for these categories or reports.",
        "L’indicateur demandé est indisponible pour ces catégories ou rapports.",
        "المؤشر المطلوب غير متاح لهذه الفئات أو التقارير.",
        "Had indicateur ma kaynch l had catégories wlla rapports.",
    ),
    "ambiguous": (
        "Please ask about one metric at a time and specify the comparison scope.",
        "Posez une question sur un seul indicateur et précisez le périmètre.",
        "اسأل عن مؤشر واحد وحدد نطاق المقارنة.",
        "Sowel 3la indicateur wa7ed w 7edded comparaison.",
    ),
    "compare": (
        "For a comparison, name at least two categories or give two report dates.",
        "Pour comparer, indiquez au moins deux catégories ou deux dates de rapport.",
        "للمقارنة، حدد فئتين على الأقل أو تاريخين للتقرير.",
        "Bach t9aren, 3ti jouj catégories wlla jouj dates dyal rapport.",
    ),
    "alert_choice": (
        "Specify one category and one report date for the alert.",
        "Précisez une catégorie et une date de rapport pour l’alerte.",
        "حدد فئة واحدة وتاريخ تقرير واحد للتنبيه.",
        "3ti catégorie wa7da w date wa7da dyal l’alerte.",
    ),
    "no_alert": (
        "SmartFlow did not flag this observation under its default settings.",
        "SmartFlow n’a pas signalé cette observation avec ses paramètres par défaut.",
        "لم يصدر SmartFlow تنبيهاً لهذه المشاهدة بالإعدادات الافتراضية.",
        "SmartFlow ma 3tach alerte l had observation b paramètres par défaut.",
    ),
    "reported": (
        "Workbook results for the selected scope.",
        "Résultats du classeur pour le périmètre sélectionné.",
        "نتائج الملف للنطاق المحدد.",
        "Résultats men fichier l had catégories w dates.",
    ),
    "ranking": (
        "Net asset ranking among the selected fund categories.",
        "Classement des actifs nets parmi les catégories sélectionnées.",
        "ترتيب صافي الأصول ضمن فئات الصناديق المحددة.",
        "Classement dyal actif net f catégories li khtariti.",
    ),
    "alerts": (
        "SmartFlow alerts in the selected scope",
        "Alertes SmartFlow dans le périmètre sélectionné",
        "تنبيهات SmartFlow في النطاق المحدد",
        "Alertes SmartFlow f had catégories w dates",
    ),
    "alert": (
        "SmartFlow flagged this observation under its default settings.",
        "SmartFlow a signalé cette observation avec ses paramètres par défaut.",
        "أصدر SmartFlow تنبيهاً لهذه المشاهدة بالإعدادات الافتراضية.",
        "SmartFlow 3ta alerte l had observation b paramètres par défaut.",
    ),
    "assets_limit": (
        "Original workbook scale. Currency is unspecified.",
        "Échelle originale du classeur. La devise est non précisée.",
        "القيم بمقياس الملف الأصلي. العملة غير محددة.",
        "Échelle dyal fichier. Devise ma m7eddadach.",
    ),
    "index_limit": (
        "Published index levels. The index base is unspecified, and index levels alone do not establish relative returns.",
        "Niveaux publiés. La base est non précisée et les niveaux seuls ne déterminent pas les rendements relatifs.",
        "مستويات المؤشر المنشورة. أساس المؤشر غير محدد ولا تكفي المستويات وحدها لمقارنة العوائد.",
        "Niveaux publiés. Base ma m7eddadach, w niveaux bo7dhom ma kaybeynouch rendement relatif.",
    ),
    "flows_limit": (
        "Published per report. The unit and flow period are unspecified, so volumes are shown without time aggregation.",
        "Valeurs par rapport. L’unité et la période sont non précisées, donc les volumes ne sont pas agrégés dans le temps.",
        "قيم كل تقرير. الوحدة والفترة غير محددتين، لذا لا تُجمع الأحجام عبر الزمن.",
        "Valeurs par rapport. Unité w période ma m7eddadinch, donc volumes bla somme 3la dates.",
    ),
    "change_limit": (
        "Published percent change on the workbook scale.",
        "Variation publiée en pourcentage sur l’échelle du classeur.",
        "التغير المنشور بالنسبة المئوية وفق مقياس الملف.",
        "Variation publiée b pourcentage dyal fichier.",
    ),
    "alert_limit": (
        "SmartFlow defaults apply. The score measures historical deviation and carries no financial risk probability.",
        "Paramètres SmartFlow par défaut. Le score mesure l’écart historique et ne représente pas une probabilité de risque financier.",
        "تُستخدم إعدادات SmartFlow الافتراضية. تقيس الدرجة الانحراف التاريخي ولا تمثل احتمال خطر مالي.",
        "Paramètres SmartFlow par défaut. Score kay9is écart historique, bla probabilité dyal risque financier.",
    ),
}


@dataclass
class Response:
    intent: str
    answer: str
    source: str = ""
    reports: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    metric: str = ""
    unit: str = ""
    limitation: str = ""
    evidence: pd.DataFrame | None = None


def answer_question(question, tables, language_adapter=None, *, language_override=None):
    """Resolve a template and answer from validated tables only."""
    language = language_override or language_for(question, language_adapter)

    def say(key):
        return COPY[key][LANGUAGES.index(language)]

    text = normalize(question)
    flags = {key for key, aliases in TERMS.items() if has(text, aliases)}
    if "advice" in flags:
        return Response("unsupported", say("advice"))
    if "unsupported" in flags or not flags & {"assets", "index", "flows", "anomaly", "weekly", "monthly"}:
        return Response("unsupported", say("unsupported"))
    if len(flags & {"index", "flows", "anomaly"}) > 1 or {"weekly", "monthly"} <= flags:
        return Response("clarify", say("ambiguous"))
    try:
        dates = report_dates(question)
    except (ValueError, OverflowError):
        return Response("clarify", say("date"))
    if (not dates and re.search(r"\b(?:19|20)\d{2}\b", text)) or len(dates) > 2:
        return Response("clarify", say("date"))
    if dates and "latest" in flags:
        return Response("clarify", say("ambiguous") + " " + say("date"))

    available = tables[ASSETS][CATEGORY].drop_duplicates().tolist()
    categories = tuple(cat for cat in available if has(text, ALIASES.get(cat, (cat,))))
    if "anomaly" in flags:
        return answer_alerts(tables[ASSETS], flags, dates, categories, available, language, say)

    sheet, fields, unit, limit = ASSETS, [AMOUNT], "Workbook scale", "assets_limit"
    intent = "net_assets"
    if "index" in flags:
        sheet, fields, unit, limit = INDICES, ["Indice"], "Index level", "index_limit"
        intent = "index"
    elif "flows" in flags:
        sheet, fields, unit, limit = FLOWS, [SUBS, REDS], "Workbook scale", "flows_limit"
        intent = "flows"
        if "net_flow" in flags:
            fields.append(NET_FLOW)
    if flags & {"weekly", "monthly"}:
        if sheet == FLOWS:
            return Response("unsupported", say("unsupported") + " " + say("flows_limit"))
        fields = [VARIATIONS[int("monthly" in flags)]]
        unit, limit, intent = "%", "change_limit", "change"

    ranking = flags & {"high", "low"}
    if ranking and (sheet != ASSETS or fields != [AMOUNT]):
        return Response("clarify", say("ambiguous"))
    if "all" in flags and not categories:
        categories = tuple(cat for cat in tables[sheet][CATEGORY].unique() if cat != TOTAL)
    if ranking and not categories:
        categories = tuple(cat for cat in available if cat != TOTAL)
    if not categories:
        return Response("clarify", say("category") + " " + ", ".join(available))

    frame = tables[sheet]
    if NET_FLOW in fields:
        frame = add_net_flows(frame)
    dates = dates or (frame[DATE].max(),)
    missing_dates = tuple(date for date in dates if not frame[DATE].eq(date).any())
    if missing_dates:
        return Response("unavailable", say("missing_date"), sheet, iso_dates(missing_dates),
                        categories, ", ".join(fields), unit, say(limit))
    records = frame.loc[frame[DATE].isin(dates) & frame[CATEGORY].isin(categories)]
    present = records.set_index([DATE, CATEGORY]).index
    missing = [(d, c) for d in dates for c in categories if (d, c) not in present]
    if missing:
        pairs = ", ".join(f"{d:%Y-%m-%d} · {c}" for d, c in missing)
        return Response("unavailable", f"{say('missing')} {pairs}", sheet, iso_dates(dates),
                        categories, ", ".join(fields), unit, say(limit))

    if ranking:
        if len(dates) != 1 or TOTAL in categories or len(categories) < 2:
            return Response("clarify", say("ambiguous"))
        values = records[AMOUNT].dropna()
        if values.size != len(records):
            return Response("unavailable", say("missing"), sheet, iso_dates(dates), categories,
                            AMOUNT, unit, say(limit))
        records = pd.concat([
            records.loc[records[AMOUNT].eq(values.max())].assign(Rank="Highest")
            if "high" in ranking else records.iloc[:0],
            records.loc[records[AMOUNT].eq(values.min())].assign(Rank="Lowest")
            if "low" in ranking else records.iloc[:0],
        ])
        intent = "ranking"
        fields = ["Rank", *fields]
    elif "compare" in flags and len(dates) * len(categories) < 2:
        return Response("clarify", say("compare"))
    elif intent == "net_assets" and (len(dates) > 1 or "compare" in flags):
        intent = "compare_assets"

    columns = [DATE, CATEGORY, *fields, PROVENANCE[2], PROVENANCE[3]]
    evidence = records[columns].sort_values(DATE, kind="stable").reset_index(drop=True)
    answer = say("ranking" if ranking else "reported")
    if len(evidence) == 1:
        row = evidence.iloc[0]
        values = " · ".join(
            f"{field} = {row[field]:,.3f}{'%' if unit == '%' else ''}"
            for field in fields if field != "Rank" and pd.notna(row[field])
        )
        if values:
            answer = f"{row[CATEGORY]} · {row[DATE]:%Y-%m-%d} · {values}"
    if len(evidence) > 1 and not ranking:
        highlights = evidence.head(6)
        values = "; ".join(
            f"{row[CATEGORY]} {row[DATE]:%Y-%m-%d} · "
            + ", ".join(
                f"{field} = {row[field]:,.3f}{'%' if unit == '%' else ''}"
                for field in fields if pd.notna(row[field])
            )
            for _, row in highlights.iterrows()
            if row[fields].notna().any()
        )
        if values:
            answer = f"{answer} {values}"
    if ranking:
        answer += " " + "; ".join(
            f"{row['Rank']} · {row[CATEGORY]} · {row[AMOUNT]:,.3f}"
            for _, row in evidence.iterrows()
        )
    note = say(limit)
    if evidence[[field for field in fields if field != "Rank"]].isna().any().any():
        note += " " + say("missing")
    return Response(intent, answer, sheet, iso_dates(dates), categories,
                    ", ".join(field for field in fields if field != "Rank"), unit, note, evidence)


def iso_dates(dates):
    return tuple(date.strftime("%Y-%m-%d") for date in sorted(dates))


def answer_alerts(assets, flags, dates, categories, available, language, say):
    if {"calculated", "published"} <= flags or "monthly" in flags:
        return Response("clarify", say("ambiguous"))
    explanation = "explain" in flags
    if explanation and (len(dates) != 1 or len(categories) != 1):
        return Response("clarify", say("alert_choice"))
    if not categories:
        categories = tuple(cat for cat in available if cat != TOTAL)
    published = "published" in flags
    metric = PUBLISHED if published else CALCULATED
    frame = assets if published else calculated_weekly_change(assets)
    field = VARIATIONS[0] if published else OBSERVED
    scored = detect_anomalies(frame, field, **SETTINGS)
    if not dates and "latest" in flags:
        dates = (assets[DATE].max(),)
    if dates and any(not assets[DATE].eq(date).any() for date in dates):
        return Response("unavailable", say("missing_date"), ASSETS, iso_dates(dates), categories,
                        metric, "%", say("alert_limit"))
    scope = dates or (assets[DATE].min(), assets[DATE].max())
    records = scored.loc[
        scored[CATEGORY].isin(categories) & scored[DATE].between(min(scope), max(scope))
    ]
    flagged = records.loc[records[STATUS].eq(ANOMALY)]
    reports = iso_dates(scope)
    columns = [DATE, CATEGORY, OBSERVED, SCORE, STATUS, PROVENANCE[2], PROVENANCE[3]]
    limitations = say("alert_limit")
    if explanation:
        if flagged.empty:
            return Response("unavailable", say("no_alert"), ASSETS, reports, categories, metric,
                            "%", limitations, records[columns])
        row = flagged.iloc[0]
        _, narrative, evidence, xai_limits = explain(
            row, metric, **SETTINGS, language=language if language in {"en", "fr"} else "en",
        )
        if language in {"ar", "darija"}:
            narrative = say("alert") + f" {row[OBSERVED]:.3f}% · |z| {abs(row[SCORE]):.3f} > {DEFAULT_THRESHOLD:.3f}."
        else:
            limitations = xai_limits
        return Response("explain_alert", narrative, ASSETS, reports, categories, metric, "%",
                        limitations, pd.DataFrame(evidence, columns=["Field", "Value"]).astype(str))
    answer = f"{say('alerts')} · {len(flagged)}"
    return Response("anomaly_summary", answer, ASSETS, reports, categories, metric, "%",
                    limitations, flagged[columns].sort_values(DATE, ascending=False))
