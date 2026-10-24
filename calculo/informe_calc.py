"""Arma la memoria de cálculo en el mismo formato de informe del bot (spec JSON -> Word / HTML)."""
from pathlib import Path

DX = 8504  # ancho útil en DXA


def num(x, nd=2):
    if x is None or x == "":
        return "–"
    if isinstance(x, str):
        return x
    return f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".") if abs(x) >= 1000 else f"{x:.{nd}f}".replace(".", ",")


def est(e):
    """Los resultados que no cumplen o requieren revisión salen resaltados."""
    if e in (None, ""):
        return "–"
    return f"[[{e}]]" if (e.startswith("NO") or e.startswith("REVISAR") or e.startswith("AUMENTAR")) else e


def tabla(header, rows, widths=None):
    n = len(header)
    b = {"type": "table", "header": header, "rows": [[("" if c is None else str(c)) for c in r] for r in rows]}
    b["widths"] = widths or _anchos(header, b["rows"])
    return b


def _anchos(header, rows):
    """Anchos proporcionales al contenido (las columnas de estado y las de texto largo reciben más espacio)."""
    n = len(header)
    pesos = []
    for i in range(n):
        col = [r[i] for r in rows if i < len(r)]
        palabra = max((len(w) for w in header[i].replace("/", " ").split()), default=3)
        largo = max([len(c.replace("[[", "").replace("]]", "").replace("**", "")) for c in col] + [3])
        if any("CUMPLE" in c or c in ("OK", "REVISAR") for c in col):
            largo = max(largo, 9)
        pesos.append(max(palabra + 1, min(largo, 18)) + 2)
    tot = sum(pesos)
    w = [max(560, int(DX * p / tot)) for p in pesos]
    w[-1] += DX - sum(w)
    return w


def P(t):
    return {"type": "p", "text": t}


def bar(phi, s):
    return f"φ{int(phi)} c/{num(s, 1) if s else '–'}" if phi else "–"


def seccion(titulo, *bloques):
    return {"titulo": titulo, "bloques": [b for b in bloques if b]}


def build_spec(Pr, R, opts=None, figuras=None, ia=None):
    opts = opts or {}
    M, C, S1, S2 = R["materiales"], R["cargas"], R["sismo1"], R["sismo2"]
    d = Pr["datos"]
    sec = []
    # 1 objeto
    obj = (ia or {}).get("objeto") or (f"El presente informe presenta la memoria de cálculo estructural de **{d.get('obra') or 'la obra'}**"
                                         f"{(' (' + d['ubicacion'] + ')') if d.get('ubicacion') else ''}, elaborada a partir de la Planilla Unificada de Cálculo Estructural. "
                                         "Se verifican losas, vigas, columnas, acción sísmica, muros resistentes y fundaciones conforme a los reglamentos CIRSOC 101, CIRSOC 201 e INPRES-CIRSOC 103.")
    sec.append(seccion("Objeto", P(obj)))
    sec.append(seccion("Normativa y criterios de cálculo", {"type": "bullets", "items": [
        "CIRSOC 101-2005: cargas permanentes y sobrecargas.", "CIRSOC 201-2005: proyecto y dimensionamiento de estructuras de hormigón armado (combinaciones de carga 9-1 a 9-3, flexión, corte, flexocompresión y fundaciones).",
        "INPRES-CIRSOC 103 Parte I (2013, adenda 2018): método estático de acción sísmica. Parte III: construcciones de mampostería.", "Unidades: kN, m, MPa y kPa; cm y mm solo para secciones y armaduras."]}))
    # 3 datos
    filas = [["Obra", d.get("obra") or "–"], ["Ubicación", d.get("ubicacion") or "–"], ["Hormigón", f"{d['clase_H']} – f'c = {num(M['fc'], 0)} MPa – Ec = {num(M['Ec'], 0)} MPa"], ["Acero longitudinal / estribos", f"{d['acero_long']} (fy = {num(M['fy'], 0)} MPa) / {d['acero_est']} (fyt = {num(M['fyt'], 0)} MPa)"],
             ["Peso unitario H°A°", f"{num(n_(d['gHA']))} kN/m³"], ["Recubrimientos libres (vigas y columnas / losas / fundaciones)", f"{num(n_(d['cc_vc']), 0)} / {num(n_(d['cc_l']), 0)} / {num(n_(d['cc_z']), 0)} mm"],
             ["Tensión admisible del suelo / profundidad de fundación", f"{num(n_(d['s_adm']), 0)} kPa / {num(n_(d['Df']))} m"], ["Mampostería", f"{d['mamp_tipo']}, mortero {d['mortero']}: f'm = {num(M['fm'])} MPa, f'v = {num(M['fv'], 3)} MPa, Em = {num(M['Em'], 0)} MPa"]]
    sec.append(seccion("Datos generales y materiales", tabla(["Dato", "Valor"], filas, [3600, 4904])))
    # 4 cargas
    bl = []
    for k, nom in (("T", "TECHO"), ("E", "ENTREPISO")):
        rows = [[c["desc"][:110], num(c["qcalc"])] for c in C["capas"][k]] + [["**Carga permanente D (sin peso propio de la losa)**", f"**{num(C['D_' + k])}**"]]
        bl += [P(f"**Nivel {nom}** – capas de carga permanente [kN/m²]:"), tabla(["Material", "q [kN/m²]"], rows, [6504, 2000])]
    bl.append(P(f"Sobrecargas: techo Lr = {num(C['Lr_T'])} kN/m² ({(C.get('desc_Lr_T') or '')[:70]}); entrepiso L = {num(C['L_E'])} kN/m² ({(C.get('desc_L_E') or '')[:70]}). Factor de L en combinaciones: {num(C['fL'])}."))
    cr = [["D' = D + γH°A°·h_est", num(C["Dp_T"]), num(C["Dp_E"])], ["U1 = 1,4·D'", num(C["U_T"][0]), num(C["U_E"][0])], ["U2 = 1,2·D' + 1,6·L + 0,5·Lr", num(C["U_T"][1]), num(C["U_E"][1])],
          ["U3 = 1,2·D' + 1,6·Lr + fL·L", num(C["U_T"][2]), num(C["U_E"][2])], ["**qu = máx(U1; U2; U3)**", f"**{num(C['qu_T'])}**", f"**{num(C['qu_E'])}**"], ["Servicio D' + L + Lr", num(C["qs_T"]), num(C["qs_E"])]]
    bl += [P(f"Combinaciones de carga (CIRSOC 201 §9.2), con espesor de losa estimado h = {num(C['h_est'] * 100, 0)} cm [kN/m²]:"), tabla(["Combinación", "TECHO", "ENTREPISO"], cr, [4504, 2000, 2000])]
    sec.append(seccion("Análisis de cargas y combinaciones", *bl))
    # 5 losas
    if R["losas"]:
        a = [[l["id"], l["nivel"].capitalize(), l["esquema"], num(l["L"]), num(l["h"], 0), num(l["hmin"], 1), num(l["qu"]), num(l["Mup"]), num(l["Mun"]), num(l["Vu"]), est(l["ok_h"])] for l in R["losas"]]
        b = [[l["id"], num(l["flex_t"]["d"], 1), num(l["flex_t"]["As_req"]), bar(l["flex_t"]["phi"], l["flex_t"]["sep"]), num(l["flex_t"]["phiMn"]), est(l["flex_t"]["estado"]), num(l["flex_a"]["As_req"]) if l["Mun"] else "–", bar(l["flex_a"]["phi"], l["flex_a"]["sep"]) if l["Mun"] else "–",
              est(l["flex_a"]["estado"]), est(l["corte"]["estado"]), est(l["reparto"]["estado"])] for l in R["losas"]]
        sec.append(seccion("Losas macizas armadas en una dirección",
                           P("Franja de 1 m. Mu en kNm/m, Vu en kN/m, h en cm. qu incluye el peso propio de la losa."), tabla(["Losa", "Nivel", "Esquema", "L [m]", "h [cm]", "h mín [cm]", "qu [kN/m²]", "Mu(+)", "Mu(−)", "Vu", "Altura"], a),
                           P("Armadura (As en cm²/m):"), tabla(["Losa", "d [cm]", "As req. (+)", "Adopt. (+)", "φMn", "Tramo", "As req. (−)", "Adopt. (−)", "Apoyo", "Corte", "Reparto"], b)))
    # 6 viguetas y correas
    bl = []
    if R["viguetas"]:
        bl += [P("Viguetas pretensadas (cargas de servicio, momento admisible de catálogo):"), tabla(["Vigueta", "Nivel", "Serie", "L [m]", "Sep. [m]", "q [kN/m²]", "M [kNm]", "M adm [kNm]", "Verificación"],
                                                                                                    [[v["id"], v["nivel"].capitalize(), v["serie"], num(v["L"]), num(v["sep"]), num(v["q"]), num(v["M"]), num(v["Madm"]), est(v["estado"])] for v in R["viguetas"]])]
    if R["correas"]:
        bl += [P("Correas de madera (tensiones admisibles, cargas de servicio):"), tabla(["Correa", "Sección", "L [m]", "q [kN/m]", "σ [MPa]", "Fb [MPa]", "τ [MPa]", "Fv [MPa]", "Flecha [mm]", "Verif."],
                                                                                         [[c["id"], c["seccion"][:40], num(c["L"]), num(c["q"]), num(c["sig"]), num(c["Fb"]), num(c["tau"], 3), num(c["Fv"], 2), f"{num(c['delta'])} / {num(c['lim'], 1)}", est(c["estado"])] for c in R["correas"]])]
    if bl:
        sec.append(seccion("Viguetas y correas", *bl))
    # 7 vigas
    if R["vigas"]:
        a = [[v["id"], v["esquema"], f"{num(v['bw'], 0)}×{num(v['h'], 0)}", num(v["L"]), num(v["qu"]), num(v["Mup"]), num(v["Mun"]), num(v["Vu"]), est(v["ok_h"])] for v in R["vigas"]]
        b = []
        for v in R["vigas"]:
            for k, nom in (("flex_apoyo", "Apoyo (−)"), ("flex_tramo", "Tramo (+)")):
                f_ = v[k]
                b.append([v["id"], nom, num(f_["Mu"]), f"{int(f_['n'])}φ{int(f_['phi'])}" if f_.get("phi") else "–", num(f_.get("As_req")), num(f_.get("As_prov")), num(f_.get("phiMn")), num(f_.get("cd"), 3), est(f_["estado"])])
        c = [[v["id"], num(v["corte"].get("Vud")), num(v["corte"].get("phiVc")), num(v["corte"].get("Vs")), f"φ{int(v['phi_e'])}, {int(v['corte']['ramas']) if v['corte'].get('ramas') else '–'} ramas c/{num(v['corte'].get('sep'), 1)}", num(v["corte"].get("smax"), 1), est(v["corte"]["estado"])] for v in R["vigas"]]
        sec.append(seccion("Vigas de hormigón armado", P("Esfuerzos por coeficientes aproximados de CIRSOC 201 §8.3.3. Mu en kNm, Vu en kN, qu en kN/m, As en cm²."),
                           tabla(["Viga", "Esquema", "bw×h [cm]", "L [m]", "qu", "Mu(+)", "Mu(−)", "Vu", "Altura"], a), P("Flexión:"), tabla(["Viga", "Sección", "Mu", "Armadura", "As req.", "As adopt.", "φMn", "c/d", "Verif."], b),
                           P("Corte (Vu a una distancia d del apoyo):"), tabla(["Viga", "Vu(d) [kN]", "φVc [kN]", "Vs [kN]", "Estribos", "s máx [cm]", "Verif."], c)))
    # 8 columnas
    if R["columnas"]:
        a = [[c["id"], f"{num(c['b'], 0)}×{num(c['h'], 0)}", num(c["lu"]), num(c["pp"], 1), num(c["Pu"], 1), num(c["Mu"], 1), est(c["ok_esb"]), num(c["lam"], 1)] for c in R["columnas"]]
        b = [[c["id"], f"{int(c['n_tot'])}φ{int(c['phi'])}" if c.get("phi") else "–", num(c.get("rho")), num(c.get("phiPn_max"), 0), num(c.get("phiMn"), 1), num(c.get("util"), 2), est(c["ok_pm"]), est(c["ok_cuantia"]), est(c["ok_est"])] for c in R["columnas"]]
        bl = [P("Pu = qu·área tributaria + reacciones de vigas + carga del nivel superior + peso propio mayorado. Verificación por diagrama de interacción P–M (compatibilidad de deformaciones)."),
              tabla(["Columna", "b×h [cm]", "lu [m]", "Peso propio [kN]", "Pu [kN]", "Mu [kNm]", "Esbeltez", "k·lu/r"], a), tabla(["Columna", "Armadura", "ρ [%]", "φPn,máx [kN]", "φMn(Pu) [kNm]", "Mu/φMn", "P–M", "Cuantía", "Estribos"], b)]
        for f_ in (figuras or []):
            bl.append({"type": "figure", "path": f_["path"], "caption": f_["caption"], "widthCm": 11})
        sec.append(seccion("Columnas de hormigón armado", *bl))
    # 9 sismo
    pr = [["Zona sísmica / tipo espectral / grupo", f"{S1['zona']} / {S1['tipo']} / {S1['grupo']} (γr = {num(S1['gr'])})"], ["Sistema estructural", f"{S1['sistema']} (R = {num(S1['R'])}; Cd = {num(S1['Cd'])}; Ωo = {num(S1['Wo'])})"],
          ["as / Ca / Cv", f"{num(S1['as_'], 2)} g / {num(S1['Ca'], 3)} / {num(S1['Cv'], 3)}"], ["T1 / T2 / T3", f"{num(S1['T1'], 3)} / {num(S1['T2'], 3)} / {num(S1['T3'], 0)} s"],
          ["Período aproximado Ta y adoptado T", f"{num(S1['Ta'], 3)} s / {num(S1['T'], 3)} s ({S1['rama']})"], ["C calculado / C mínimo", f"{num(S1['C_calc'], 4)} / {num(S1['Cmin'], 4)}"],
          ["**Coeficiente sísmico adoptado C**", f"**{num(S1['C'], 4)}**"], ["**Peso sísmico W / Corte basal V0 = C·W**", f"**{num(S1['W'], 1)} kN / {num(S1['V0'], 1)} kN**"]]
    nv = [[l["nombre"] or "–", num(l["hk"]), num(l["W_losa"], 1), num(l["W_muros"], 1), num(l["W_otros"], 1), num(l["W"], 1), num(l["F"], 1), num(l["V"], 1)] for l in S1["niveles"] if l["A"] > 0 or l["W"] > 0]
    sec.append(seccion("Acción sísmica – método estático (INPRES-CIRSOC 103 Parte I)", tabla(["Parámetro", "Valor"], pr, [3400, 5104]), P("Pesos por nivel W = D + f1·L y distribución del corte basal [kN]:"),
                       tabla(["Nivel", "hk [m]", "W losa/cubierta", "W muros", "W otros", "W nivel", "Fk", "Vk"], nv)))
    # 10 distribución y muros
    el = [[e["id"], e["dir"], num(e["R"], 0), num(e["off"], 2), num(e["Vd"], 1), num(e["Ft1"], 1), num(e["Ft2"], 1), num(e["Vu"], 1)] for e in S2["elementos"]]
    cmr = [["Centro de masa XcM / YcM", f"{num(S2['XcM'], 3)} / {num(S2['YcM'], 3)} m"], ["Centro de rigidez XcR / YcR", f"{num(S2['XcR'], 3)} / {num(S2['YcR'], 3)} m"], ["Excentricidades estáticas ex / ey", f"{num(S2['ex'], 3)} / {num(S2['ey'], 3)} m"],
           ["Excentricidad accidental", f"{S2['irregularidad']}: eax = {num(S2['eax'], 3)} m; eay = {num(S2['eay'], 3)} m"], ["Fuerza sísmica por dirección", f"F = {num(S2['F'], 1)} kN"]]
    bl = [tabla(["Dato", "Valor"], cmr, [3400, 5104]), P("Reparto en los elementos resistentes (R en kN/m; Vu = V directo + máx(0; Ft1; Ft2), en kN):"), tabla(["Elemento", "Dir.", "R [kN/m]", "Dist. al CR [m]", "V directo", "Ft caso 1", "Ft caso 2", "V total"], el)]
    mm = R["muros"]["mamposteria"]
    if mm:
        bl += [P("Muros de mampostería – corte (Parte III): Vn = (f'v + 0,40·fo)·Ag ≤ 2·f'v·Ag; φ = 0,80."), tabla(["Muro", "Ag [m²]", "N mín. [kN]", "fo [MPa]", "Vu [kN]", "φVn [kN]", "Vu/φVn", "Verif."],
                                                                                                    [[m["id"], num(m["Ag"]), num(m["Nmin"], 1), num(m["fo"], 3), num(m["Vu"], 1), num(m["phiVn"], 1), num(m["ratio"], 2), est(m["estado"])] for m in mm])]
    tb = R["muros"]["tabiques"]
    if tb:
        bl += [P("Tabiques de hormigón armado – corte (CIRSOC 201 §11.10):"), tabla(["Tabique", "Vu [kN]", "Vc [kN]", "Vs [kN]", "φVn [kN]", "ρt", "Verif."], [[t["id"], num(t["Vu"], 1), num(t["Vc"], 1), num(t["Vs"], 1), num(t["phiVn"], 1), num(t["rho"], 4), est(t["estado"])] for t in tb])]
    sec.append(seccion("Distribución en planta, torsión y muros resistentes", *bl))
    # 11 voladizos
    V = R["voladizos"]
    if V["columnas"] or V["componentes"]:
        bl = []
        if V["columnas"]:
            bl += [P(f"Columnas en voladizo (R = {num(V['R'])}; C = {num(V['C'], 4)}):"), tabla(["Columna", "b×h [cm]", "H [m]", "Q1 [kN]", "Fs1 [kN]", "Fs2 [kN]", "Mu [kNm]", "φMn [kNm]", "Verif."],
                                                                                                  [[c["id"], f"{num(c['b'], 0)}×{num(c['h'], 0)}", num(c["H"]), num(c["Q1"], 1), num(c["Fs1"]), num(c["Fs2"]), num(c["Mu"]), num(c.get("phiMn")), est(c["estado"])] for c in V["columnas"]])]
        if V["componentes"]:
            bl += [P("Componentes no estructurales y equipos:"), tabla(["Componente", "Wp [kN]", "z [m]", "ap", "Rp", "Ip", "Cp", "Fp [kN]"], [[c["desc"], num(c["Wp"], 1), num(c["z"], 1), num(c["ap"]), num(c["Rp"]), num(c["Ip"]), num(c["Cp"], 3), num(c["Fp"], 2)] for c in V["componentes"]])]
        sec.append(seccion("Columnas en voladizo y componentes no estructurales", *bl))
    # 12 fundaciones
    Fu = R["fundaciones"]
    bl = []
    if Fu["cimientos"]:
        bl += [P("Cimientos corridos (cargas de servicio por metro de muro):"), tabla(["Muro", "N [kN/m]", "Ancho nec. [cm]", "Ancho adopt. [cm]", "Altura [cm]", "σ [kPa]", "α [°]", "Verif."],
                                                                                      [[c["id"], num(c["N"], 1), num(c["Bnec"], 0), num(c["B"], 0), num(c["hc"], 0), num(c.get("sigma"), 1), num(c.get("alpha"), 1), est(c["estado"])] for c in Fu["cimientos"]])]
    if Fu["bases"]:
        bl += [P("Bases aisladas: tensión del suelo (P servicio ≈ Pu/1,4):"), tabla(["Base", "Pu [kN]", "P serv. [kN]", "B nec. [cm]", "B adopt. [cm]", "h [cm]", "σ [kPa]", "Verif."],
                                                                                [[b["id"], num(b["Pu"], 1), num(b["Ps"], 1), num(b["Breq"], 0), num(b["B"], 0), num(b["h"], 0), num(b.get("sigma"), 1), est(b["estado"])] for b in Fu["bases"]])]
        fl = [[b["id"], num(b["flex"]["qu"], 1), num(b["flex"]["Mu"], 1), num(b["flex"].get("As_req")), num(b["flex"].get("As_min")), bar(b["flex"].get("phi"), b["flex"].get("sep")), num(b["flex"].get("phiMn"), 1), est(b["flex"]["estado"]),
              est(b["corte"]["ok1"]) if "corte" in b else "–", est(b["corte"]["okp"]) if "corte" in b else "–"] for b in Fu["bases"] if "flex" in b]
        if fl:
            bl += [P("Flexión, corte y punzonado (CIRSOC 201 cap. 15 y §11.12):"), tabla(["Base", "qu neta [kPa]", "Mu [kNm]", "As req. [cm²]", "As mín. [cm²]", "Armadura", "φMn [kNm]", "Flexión", "Corte", "Punz."], fl)]
    if bl:
        sec.append(seccion("Fundaciones", *bl))
    # 13 resumen + conclusiones
    rs = R["resumen"]
    tab = [[nm, c["total"], c["cumple"], c["no"], c["revisar"], est(c["estado"])] for nm, c in rs["modulos"]] + [["**TOTAL**", rs["total"]["total"], rs["total"]["cumple"], rs["total"]["no"], rs["total"]["revisar"], est(rs["total"]["estado"])]]
    sec.append(seccion("Resumen de verificaciones", tabla(["Módulo", "Verificaciones", "Cumple", "No cumple", "Revisar", "Estado"], tab, [3304, 1200, 1000, 1000, 1000, 1000])))
    if (ia or {}).get("conclusiones"):
        concl = [f"[[{t}]]" for t in ia["conclusiones"]]
    else:
        malos = [nm for nm, c in rs["modulos"] if c["estado"] == "NO CUMPLE"]
        rev = [nm for nm, c in rs["modulos"] if c["estado"] == "REVISAR"]
        concl = [f"Se verificaron {rs['total']['total']} condiciones de diseño: {rs['total']['cumple']} cumplen, {rs['total']['no']} no cumplen y {rs['total']['revisar']} requieren revisión."]
        concl.append("Las verificaciones implementadas se satisfacen con los datos cargados." if not malos and not rev else "Requieren ajuste de dimensiones o armaduras: " + (", ".join(malos) if malos else "ninguno") + "." + (" A revisar: " + ", ".join(rev) + "." if rev else ""))
        concl.append(f"Acción sísmica: C = {num(S1['C'], 3)} y corte basal V0 = {num(S1['V0'], 1)} kN para un peso sísmico W = {num(S1['W'], 1)} kN.")
    concl.append("Alcance: no incluye viento, nieve, torsión en vigas, vigas T, losas en dos direcciones, análisis de pórticos ni detallado sismorresistente. Los resultados deben ser verificados por el profesional responsable.")
    sec.append(seccion("Conclusiones", {"type": "numbered", "items": concl}))
    return {"tipo_label": "MEMORIA DE CÁLCULO", "subtitulo": "ESTRUCTURAS", "codigo": opts.get("codigo") or "[código]", "revision": opts.get("revision") or d.get("revision") or "00", "fecha": opts.get("fecha") or d.get("fecha") or "",
            "titulo": f"Memoria de cálculo estructural – {d.get('obra') or 'obra'}", "secciones": sec}


def n_(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def diagramas(R, carpeta):
    """Gráficos P–M de las columnas (requiere matplotlib; si no está instalado se omiten)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out = []
    for c in R["columnas"]:
        if "puntos" not in c:
            continue
        fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=130)
        ax.plot([p["phiMn"] for p in c["puntos"]], [p["phiPn"] for p in c["puntos"]], color="#047857", lw=2, label="Diagrama φPn–φMn")
        ax.plot([c["Mu"]], [c["Pu"]], "D", color="#C00000", ms=7, label="Solicitación (Mu; Pu)")
        ax.axhline(0, color="#999", lw=0.6)
        ax.set_xlabel("φMn [kNm]")
        ax.set_ylabel("φPn [kN]")
        ax.set_title(f"Columna {c['id']} ({int(c['b'])}×{int(c['h'])} cm)", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        nombre = f"diag_{c['id']}.png"
        fig.savefig(Path(carpeta) / nombre)
        plt.close(fig)
        out.append({"path": nombre, "caption": f"Figura: diagrama de interacción de la columna {c['id']}"})
    return out
