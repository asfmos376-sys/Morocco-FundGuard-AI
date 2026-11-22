"""Read and validate the four published metric tables."""
from pathlib import Path

import pandas as pd

from src.validation import CATEGORY, DATE, parse_dates, parse_numeric, validate_keys

WORKBOOK = Path(__file__).resolve().parents[1] / "data" / "OPCVM_2026_Consolide (1).xlsx"
ASSETS = "Actif_Net_OPCVM"
INDICES = "Indices_Performance"
HOLDINGS = "Actif_Categorie_Valeurs"
FLOWS = "Souscriptions_Rachats"
AMOUNT = "Montant"
COUNT = "Nombre OPCVM"
SHARE = "Structure (%)"
VARIATIONS = (
    "Variation hebdomadaire (%)", "Variation mensuelle (%)", "Variation annuelle (%)"
)
SUBS = "Volume de souscriptions"
REDS = "Volume de rachats"
PROVENANCE = (DATE, "Fichier xlsx", "Fichier d’origine", "Ligne export", CATEGORY)
FIELDS = {
    ASSETS: (COUNT, AMOUNT, SHARE, *VARIATIONS),
    INDICES: ("Indice", *VARIATIONS, "Catégorie source"),
    HOLDINGS: (AMOUNT, SHARE, *VARIATIONS),
    FLOWS: (SUBS, REDS, "Ligne rachats"),
}


def load_workbook(path=WORKBOOK):
    tables = pd.read_excel(
        path, sheet_name=list(FIELDS), engine="openpyxl", dtype=object,
        keep_default_na=False, na_values=[""],
    )
    for sheet, frame in tables.items():
        expected = (*PROVENANCE, *FIELDS[sheet])
        if tuple(frame.columns) != expected or frame.empty:
            raise ValueError(f"{sheet} has unexpected headers or no records.")
        frame[DATE] = parse_dates(frame[DATE])
        for column in ("Ligne export", *FIELDS[sheet]):
            if column != "Catégorie source":
                frame[column] = parse_numeric(frame[column], column)
        try:
            validate_keys(frame)
        except ValueError as error:
            raise ValueError(f"{sheet}: {error}") from error
        tables[sheet] = frame.sort_values(DATE, kind="stable").reset_index(drop=True)
    return tables
