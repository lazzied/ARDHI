import json
import copy
import re

# 1. THE TEMPLATE (Now a list of dictionaries inside the "lab_report" key)
TEMPLATE = {
    "lab_report": [
        {"attribute": "pH", "iso_method": "NF EN ISO 10390 (2022)", "unit": "---", "value": None},
        {"attribute": "Conductivité", "iso_method": "ISO 11265 (2025)", "unit": "mS/Cm", "value": None},
        {"attribute": "Salinité", "iso_method": "ISO 11265 (2025)", "unit": "%", "value": None},
        {"attribute": "Humidité", "iso_method": "MA ISO 11465 (2025)", "unit": "%", "value": None},
        {"attribute": "Matière sèche", "iso_method": "MA ISO 11465 (2025)", "unit": "%", "value": None},
        {"attribute": "Matière Organique", "iso_method": "RODIER (2009)", "unit": "%", "value": None},
        {"attribute": "Azote total", "iso_method": "ISO 13878 (2020)", "unit": "%", "value": None},
        {"attribute": "Rapport C/N", "iso_method": "RODIER (2009)", "unit": "---", "value": None},
        {"attribute": "Souffre", "iso_method": "ISO 15178 (2000)", "unit": "%", "value": None},
        {"attribute": "Taux de carbone", "iso_method": "ISO 10694 (2020)", "unit": "%", "value": None},
        {"attribute": "Carbonates de Calcium", "iso_method": "ISO 10693 (2021)", "unit": "%", "value": None},
        {"attribute": "Phosphore", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Potassium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Magnésium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Calcium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Manganèse", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Bore", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Cuivre", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Fer", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Zinc", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Molybdène", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Calcium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Magnésium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Potassium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Phosphore échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Sodium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": None},
        {"attribute": "Calcaire actif", "iso_method": "NF X 31-106 (2002)", "unit": "%", "value": None},
    ]
}

REGION_COORDS = {
    "fertile_tell_loam_n.json":           (36.68, 9.05),   # Béja farmland west of city
    "medjerda_valley_alluvial.json":      (36.57, 9.72),   # Medjerda floodplain fields
    "alkaline_sahel_olive_grove.json":    (35.74, 10.55),  # Olive groves SW of Sousse
    "alkaline_enfidha_plain.json":        (36.08, 10.25),  # Enfidha agricultural plain
    "calcareous_zaghouan_hillslope.json": (36.32, 10.02),  # Zaghouan hillside terraces
    "degraded_eroded_cap_bon.json":       (36.78, 10.85),  # Cap Bon vineyard/farmland
    "degraded_overirrigated_beja.json":   (36.65, 9.38),   # Irrigated fields NW Béja
    "organic_rich_kroumirie_forest.json": (36.72, 8.55),   # Kroumirie forest edge farmland
    "organic_rich_mogods_hillside.json":  (37.05, 9.12),   # Mogods hillside terraces
    "saline_irrigated_sfax_plain.json":   (34.68, 10.62),  # Sfax olive/farm perimeter
}

# 2. RAW DATA (Remains the same)
RAW_PROFILES = [
    # label                           oc   ph   ec   ccb   ca_ex  mg_ex  k_ex  na_ex
    ("Fertile Tell loam (N)",         2.4, 6.8, 0.4,  1.2,  3.65,  0.78,  0.14, 0.04),
    ("Medjerda valley alluvial",      2.1, 7.2, 0.6,  3.5,  4.63,  0.90,  0.15, 0.08),
    ("Alkaline Sahel olive grove",    0.9, 8.3, 1.2,  9.5,  6.32,  0.74,  0.09, 0.38),
    ("Alkaline Enfidha plain",        1.1, 8.0, 1.0,  6.8,  5.70,  0.83,  0.11, 0.27),
    ("Calcareous Zaghouan hillslope", 1.2, 7.8, 0.8, 11.0,  6.68,  0.76,  0.11, 0.15),
    ("Degraded eroded Cap Bon",       0.5, 7.5, 1.1,  4.5,  3.47,  0.61,  0.08, 0.20),
    ("Degraded overirrigated Beja",   0.6, 7.8, 3.8,  2.8,  3.03,  0.97,  0.07, 1.82),
    ("Organic-rich Kroumirie forest", 3.8, 5.8, 0.3,  0.1,  1.25,  0.48,  0.13, 0.03),
    ("Organic-rich Mogods hillside",  2.9, 6.1, 0.4,  0.2,  1.69,  0.57,  0.12, 0.04),
    ("Saline irrigated Sfax plain",   0.7, 7.9, 8.4,  3.8,  3.74,  1.41,  0.07, 3.43),
]

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

# 3. GENERATION LOOP
for row in RAW_PROFILES:
    label, oc, ph, ec, ccb, ca_ex, mg_ex, k_ex, na_ex = row
    
    # Fresh copy
    profile_data = copy.deepcopy(TEMPLATE)
    
    # Helper to update values in the list efficiently
    def set_val(attr_name, val):
        for item in profile_data["lab_report"]:
            if item["attribute"] == attr_name:
                item["value"] = val
                break

    # Map raw values
    set_val("Taux de carbone", oc)
    set_val("pH", ph)
    set_val("Conductivité", ec)
    set_val("Carbonates de Calcium", ccb)
    set_val("Calcium échangeable", ca_ex)
    set_val("Magnésium échangeable", mg_ex)
    set_val("Potassium échangeable", k_ex)
    set_val("Sodium échangeable", na_ex)
    
    filename = f"engines/OCR_processing/test_reports/report_generator/generated_lab_reports/{slugify(label)}.json"
    
    # Ensure directory exists (optional but recommended)
    # os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    print(f"Generated: {filename}")