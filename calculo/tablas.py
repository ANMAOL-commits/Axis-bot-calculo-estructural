"""Tablas normativas usadas por el motor de cálculo (mismos valores que la planilla unificada)."""
import json
from pathlib import Path

HORMIGON = {"H-17": 17, "H-20": 20, "H-25": 25, "H-30": 30, "H-35": 35, "H-40": 40}
ACERO = {"ADN 420": 420, "ADN 420 S": 420, "AL 220": 220}
T95 = {"Losa maciza en una dirección": {"Simplemente apoyado": 20, "Un extremo continuo": 24, "Ambos extremos continuos": 28, "Voladizo": 10},
       "Viga o losa nervurada en una dirección": {"Simplemente apoyado": 16, "Un extremo continuo": 18.5, "Ambos extremos continuos": 21, "Voladizo": 8}}
# CIRSOC 201 §8.3.3: (M(+), M(−), V)
ESQ = {"Simplemente apoyada": (1 / 8, 0, 0.5), "Continua 2 tramos – tramo extremo": (1 / 11, 1 / 9, 0.575), "Continua 3+ tramos – tramo extremo": (1 / 11, 1 / 10, 0.575),
       "Continua – tramo interior": (1 / 16, 1 / 11, 0.5), "Voladizo": (0, 0.5, 1.0)}
VIGUETAS = {"Serie 0": 5.61, "Serie 1a": 8.03, "Serie 2a": 10.89, "Serie 3a": 11.92, "Serie 4a": 13.62, "Serie 5a": 16.05, "Serie 6a": 18.59, "Serie 7a": 20.01, "Serie 8a": 23.49, "Serie 9a": 26.03}
# Mampostería (INPRES-CIRSOC 103 Parte III) – f'm y f'v por mampuesto y mortero
MORT = ["E", "I", "N", "NA"]
FM = {"Ladrillos cerámicos macizos": [2.75, 2.25, 1.75, 0.65], "Bloques huecos portantes cerámicos": [2.25, 1.75, 1.40, 0.52], "Bloques huecos portantes de hormigón": [2.25, 1.75, 1.40, 0.52]}
FV = {"Ladrillos cerámicos macizos": [0.26, 0.22, 0.19, 0.07], "Bloques huecos portantes cerámicos": [0.22, 0.19, 0.15, 0.055], "Bloques huecos portantes de hormigón": [0.22, 0.19, 0.15, 0.055]}
# INPRES-CIRSOC 103 Parte I: zona -> (as, T3, Cu, (Ca1,Cv1),(Ca2,Cv2),(Ca3,Cv3))
ZONAS = {1: (0.08, 3, 1.70, (0.09, 0.13), (0.12, 0.18), (0.19, 0.26)), 2: (0.15, 5, 1.60, (0.18, 0.25), (0.22, 0.32), (0.30, 0.50)),
         3: (0.25, 8, 1.45, (0.29, 0.39), (0.32, 0.47), (0.35, 0.74)), 4: (0.35, 13, 1.40, (0.37, 0.51), (0.40, 0.59), (0.36, 0.90))}
CRX = {"Pórticos de H°A° (resisten el 100% del corte)": (0.0466, 0.90), "Pórticos de acero (resisten el 100% del corte)": (0.0724, 0.80),
       "Pórticos de acero con diagonales excéntricas": (0.0731, 0.75), "Otros sistemas (mampostería, tabiques de H°A°, etc.)": (0.0488, 0.75)}
GRUPOS = {"Grupo A₀": 1.5, "Grupo A": 1.3, "Grupo B": 1.0, "Grupo C": 0.8}
F1 = {"Azoteas y techos inaccesibles": 0, "Viviendas, oficinas, hoteles": 0.25,
      "Locales con aglomeración habitual": 0.5, "Tanques de agua, silos": 1.0}
_R = json.loads((Path(__file__).parent / "r_table.json").read_text(encoding="utf8"))
RTAB = {lab: (R, Cd, Wo) for lab, R, Cd, Wo in _R}
