"""
Motor de cálculo estructural – réplica en Python de la 'Planilla Unificada de Cálculo Estructural'.
Unidades: kN, m, MPa, kPa (cm y mm solo en secciones y armaduras, como en la planilla).
Normas: CIRSOC 101, CIRSOC 201-2005, INPRES-CIRSOC 103 Partes I y III.
"""
import math
from .tablas import *

PI = math.pi


def n(x):
    try:
        return 0.0 if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return 0.0


def has(x):
    return x is not None and x != ""


def rho_min(fy):
    return 0.002 if fy <= 350 else max(0.0014, 0.0018 * 420 / fy)


def flex(Mu, b, d, fc, fy):
    """Mu [kNm], b [mm], d [mm] -> (Rn, rho|None, As [mm²]|None)."""
    if d is None or d <= 0:
        return 0.0, None, None
    Rn = Mu * 1e6 / (0.9 * b * d * d) if Mu else 0.0
    t = 1 - 2 * Rn / (0.85 * fc)
    if t < 0:
        return Rn, None, None
    rho = 0.85 * fc / fy * (1 - math.sqrt(t))
    return Rn, rho, rho * b * d


def phiMn_(As_mm2, b, d, fc, fy):
    return 0.9 * As_mm2 * fy * (d - As_mm2 * fy / (0.85 * fc * b) / 2) / 1e6


# ------------------------------------------------------------------ materiales y cargas
def materiales(d):
    fc = HORMIGON[d["clase_H"]]
    fy, fyt = ACERO[d["acero_long"]], ACERO[d["acero_est"]]
    fm = FM[d["mamp_tipo"]][MORT.index(d["mortero"])]
    fv = FV[d["mamp_tipo"]][MORT.index(d["mortero"])]
    Em = 1200 * fm
    Gm = (0.2 if d["mamp_tipo"] == "Ladrillos cerámicos macizos" else 0.1) * Em
    return dict(d, fc=fc, fy=fy, fyt=fyt, Ec=4700 * math.sqrt(fc), beta1=0.85 if fc <= 30 else max(0.65, 0.85 - 0.05 * (fc - 30) / 7),
                fm=fm, fv=fv, Em=Em, Gm=Gm, Es=n(d.get("Es")) or 200000)


def cargas(c, M):
    out = {"capas": {}}
    for k in ("T", "E"):
        tot, capas = 0.0, []
        for ly in c[k]["capas"]:
            if not ly.get("desc"):
                continue
            g, q, e, b, sep, al = (n(ly.get(x)) for x in ("g", "q", "e", "b", "sep", "alpha"))
            base = q if q > 0 else ((g * e * b / sep if (sep > 0 and b > 0) else g * e) if g > 0 else 0)
            qc = base / math.cos(math.radians(al))
            capas.append(dict(ly, qcalc=qc))
            tot += qc
        co = c[k].get("correa")
        if co and co.get("desc") and n(co.get("sep")) > 0:
            qcor = n(co.get("kNm")) / n(co["sep"]) / math.cos(math.radians(n(co.get("alpha"))))
            capas.append({"desc": "Estructura de cubierta: " + co["desc"], "qcalc": qcor})
            tot += qcor
        out["D_" + k] = tot
        out["capas"][k] = capas
    for k in ("Lr_T", "L_E", "L_T", "Lr_E"):
        out[k] = n(c.get(k))
    out["fL"], out["h_est"] = n(c.get("fL")) or 0.5, n(c.get("h_est")) or 0.12
    out["desc_Lr_T"], out["desc_L_E"] = c.get("desc_Lr_T") or "", c.get("desc_L_E") or ""
    for k in ("T", "E"):
        Dp = out["D_" + k] + M["gHA"] * out["h_est"]
        L, Lr = out["L_" + k], out["Lr_" + k]
        U1, U2, U3 = 1.4 * Dp, 1.2 * Dp + 1.6 * L + 0.5 * Lr, 1.2 * Dp + 1.6 * Lr + out["fL"] * L
        out["Dp_" + k], out["U_" + k], out["qu_" + k], out["qs_" + k] = Dp, (U1, U2, U3), max(U1, U2, U3), Dp + L + Lr
    out["muros"] = [dict(m, kNm=n(m.get("g")) * n(m.get("e")) * n(m.get("h"))) for m in c.get("muros", []) if m.get("desc")]
    return out


def _nivel(C, nivel):
    k = "T" if nivel == "TECHO" else "E"
    return C["D_" + k], C["L_" + k], C["Lr_" + k]


# ------------------------------------------------------------------ losas
def losas(lista, M, C):
    res = []
    for s in lista:
        if not s.get("id"):
            continue
        fy, fc, b1 = M["fy"], M["fc"], M["beta1"]
        L, h = n(s["L"]), n(s["h"])
        div = T95[s["tipo"]][s["apoyo"]]
        fac = 1 if fy == 420 else 0.4 + fy / 700
        hmin = L / div * fac * 100
        r = dict(id=s["id"], tipo=s["tipo"], apoyo=s["apoyo"], L=L, h=h, div=div, hmin=hmin, ok_h="CUMPLE" if h >= hmin else "NO CUMPLE", nivel=s["nivel"], esquema=s["esquema"])
        D, Lv, Lr = _nivel(C, s["nivel"])
        Dp = D + M["gHA"] * h / 100
        qu = max(1.4 * Dp, 1.2 * Dp + 1.6 * Lv + 0.5 * Lr, 1.2 * Dp + 1.6 * Lr + C["fL"] * Lv)
        sa, vo = s["esquema"] == "Simplemente apoyada", s["esquema"] == "Voladizo"
        r.update(Dp=Dp, L_uso=Lv, Lr=Lr, qu=qu,
                 Mup=0 if vo else (qu * L * L / 8 if sa else qu * L * L / 11), Mun=qu * L * L / 2 if vo else (0 if sa else qu * L * L / 9),
                 Vu=qu * L if vo else (qu * L / 2 if sa else 1.15 * qu * L / 2), R_ext=qu * L if vo else (qu * L / 2 if sa else 0.425 * qu * L),
                 R_cen=qu * L if vo else (qu * L / 2 if sa else 1.15 * qu * L))
        rmin = rho_min(fy)
        rho_tc = 0.31875 * b1 * fc / fy
        for sec, Mu, phi, sep in (("t", r["Mup"], n(s.get("phi_t")), n(s.get("s_t"))), ("a", r["Mun"], n(s.get("phi_a")), n(s.get("s_a")))):
            d = h - M["cc_l"] / 10 - phi / 20
            Rn, rho, As = flex(Mu, 1000, d * 10, fc, fy)
            Asreq = None if As is None else As / 100
            Asmin = rmin * 1000 * h * 10 / 100
            Asp = PI * phi ** 2 / 4 / sep if (phi > 0 and sep > 0) else None
            phiMn = None if Asp is None else phiMn_(Asp * 100, 1000, d * 10, fc, fy)
            smax = min(3 * h, 45)
            if Mu == 0:
                est = "–"
            elif Asreq is None:
                est = "AUMENTAR h"
            elif Asp is None:
                est = "REVISAR"
            else:
                est = "CUMPLE" if (Asp >= Asreq and Asp >= Asmin and phiMn >= Mu and sep <= smax) else "NO CUMPLE"
            r["flex_" + sec] = dict(d=d, Mu=Mu, Rn=Rn, rho=rho, As_req=Asreq, As_min=Asmin, phi=phi or None, sep=sep or None, As_prov=Asp, phiMn=phiMn, smax=smax, estado=est)
        dt = r["flex_a"]["d"] if s["esquema"] == "Voladizo" else r["flex_t"]["d"]
        phiVc = 0.75 * math.sqrt(fc) / 6 * dt * 10
        phi_r, sep_r = n(s.get("phi_r")), n(s.get("s_r"))
        Asr = PI * phi_r ** 2 / 4 / sep_r if (phi_r > 0 and sep_r > 0) else None
        Asm = rmin * 1000 * h * 10 / 100
        smr = min(5 * h, 45)
        r["corte"] = dict(Vu=r["Vu"], d=dt, phiVc=phiVc, estado="CUMPLE" if r["Vu"] <= phiVc else "NO CUMPLE")
        r["reparto"] = dict(phi=phi_r or None, sep=sep_r or None, As=Asr, As_min=Asm, smax=smr,
                            estado="REVISAR" if Asr is None else ("CUMPLE" if (Asr >= Asm and sep_r <= smr) else "NO CUMPLE"))
        res.append(r)
    return res


# ------------------------------------------------------------------ viguetas y correas
def viguetas(lista, modo, M, C):
    res = []
    for v in lista:
        if not v.get("id"):
            continue
        D, Lv, Lr = _nivel(C, v["nivel"])
        D += n(v.get("pp"))
        q = D + Lv + Lr if modo == "Servicio" else max(1.4 * D, 1.2 * D + 1.6 * Lv + 0.5 * Lr, 1.2 * D + 1.6 * Lr + C["fL"] * Lv)
        ql = q * n(v["sep"])
        Mm = ql * n(v["L"]) ** 2 / 8
        Madm = VIGUETAS[str(v["serie"])]
        res.append(dict(id=v["id"], nivel=v["nivel"], serie=v["serie"], L=n(v["L"]), sep=n(v["sep"]), pp=n(v.get("pp")), q=q, ql=ql, M=Mm, V=ql * n(v["L"]) / 2, Madm=Madm, estado="CUMPLE" if Mm <= Madm else "NO CUMPLE"))
    return res


def correas(lista, C):
    res = []
    for c in lista:
        if not c.get("id"):
            continue
        b, h, w = n(c["b"]), n(c["h"]), n(c["w"])
        D, Lv, Lr = _nivel(C, c["nivel"])
        sep, L, al = n(c["sep"]), n(c["L"]), n(c.get("alpha"))
        q = (D + Lv + Lr) * sep + w
        ca = math.cos(math.radians(al))
        Mm, V = q * ca * L * L / 8, q * ca * L / 2
        sig = Mm / (b * h * h / 6) / 1000
        tau = 1.5 * V / (b * h) / 1000
        E = n(c["E"])
        delta = 5 * q * ca * L ** 4 / (384 * E * 1000 * (b * h ** 3 / 12)) * 1000
        lim = L * 1000 / (n(c.get("x_flecha")) or 300)
        ok = sig <= n(c["Fb"]) and tau <= n(c["Fv"]) and delta <= lim
        res.append(dict(id=c["id"], nivel=c["nivel"], seccion=c["seccion"], b=b, h=h, L=L, sep=sep, q=q, sig=sig, Fb=n(c["Fb"]), tau=tau, Fv=n(c["Fv"]), delta=delta, lim=lim, estado="CUMPLE" if ok else "NO CUMPLE"))
    return res


# ------------------------------------------------------------------ vigas
def vigas(lista, M, C):
    res = []
    fc, fy, fyt, b1, ccv = M["fc"], M["fy"], M["fyt"], M["beta1"], M["cc_vc"]
    for v in lista:
        if not v.get("id"):
            continue
        L, h, bw, phie = n(v["L"]), n(v["h"]), n(v["bw"]), n(v["phi_e"])
        div = T95["Viga o losa nervurada en una dirección"][v["cond"]]
        fac = 1 if fy == 420 else 0.4 + fy / 700
        hmin = L / div * fac * 100
        cmp_, cmn, cv = ESQ[v["esquema"]]
        Dv = M["gHA"] * bw * h / 10000 + n(v.get("D_adic"))
        qu = n(v.get("R_losas")) + max(1.4 * Dv, 1.2 * Dv + 1.6 * n(v.get("L_adic")))
        r = dict(id=v["id"], cond=v["cond"], esquema=v["esquema"], L=L, h=h, bw=bw, phi_e=phie, div=div, hmin=hmin, ok_h="CUMPLE" if h >= hmin else "NO CUMPLE",
                 R_losas=n(v.get("R_losas")), D_adic=n(v.get("D_adic")), L_adic=n(v.get("L_adic")), Dv=Dv, qu=qu, Mup=cmp_ * qu * L * L, Mun=cmn * qu * L * L, Vu=cv * qu * L)
        for sec, Mu, key in (("apoyo", r["Mun"], "flex_apoyo"), ("tramo", r["Mup"], "flex_tramo")):
            nb, phi = n(v[key].get("n")), n(v[key].get("phi"))
            if phi <= 0:
                r[key] = dict(sec=sec, Mu=Mu, n=nb or None, phi=None, estado="–" if Mu == 0 else "REVISAR")
                continue
            d = h - ccv / 10 - phie / 10 - phi / 20
            Rn = Mu * 1e6 / (0.9 * bw * 10 * (d * 10) ** 2) if Mu else 0.0
            t = 1 - 2 * Rn / (0.85 * fc)
            Asreq = None if t < 0 else 0.85 * fc / fy * (1 - math.sqrt(t)) * bw * 10 * d * 10 / 100
            Asmin = 0 if Mu == 0 else max(math.sqrt(fc) / (4 * fy), 1.4 / fy) * bw * 10 * d * 10 / 100
            Asp = nb * PI * phi ** 2 / 400 if nb > 0 else None
            cd = None if Asp is None else Asp * 100 * fy / (0.85 * fc * bw * 10) / b1 / (d * 10)
            phiMn = None if Asp is None else phiMn_(Asp * 100, bw * 10, d * 10, fc, fy)
            sl = (bw * 10 - 2 * ccv - 2 * phie - nb * phi) / (nb - 1) if nb >= 2 else None
            slmin = max(25, phi)
            if Mu == 0:
                est = "–"
            elif Asreq is None:
                est = "AUMENTAR sección"
            elif Asp is None:
                est = "REVISAR"
            else:
                est = "CUMPLE" if (Asp >= Asreq and Asp >= Asmin and phiMn >= Mu and cd <= 0.375 and (sl is None or sl >= slmin)) else "NO CUMPLE"
            r[key] = dict(sec=sec, Mu=Mu, n=nb, phi=phi, d=d, Rn=Rn, As_req=Asreq, As_min=Asmin, As_prov=Asp, cd=cd, phiMn=phiMn, sep_libre=sl, sep_libre_min=slmin, estado=est)
        dd = r["flex_tramo"].get("d")
        if dd is None:
            r["corte"] = dict(estado="REVISAR")
        else:
            Vud = max(0.0, r["Vu"] - qu * dd / 100)
            phiVc = 0.75 * math.sqrt(fc) / 6 * bw * 10 * dd * 10 / 1000
            Vs = max(0.0, Vud / 0.75 - phiVc / 0.75)
            Vsmax = 2 / 3 * math.sqrt(fc) * bw * 10 * dd * 10 / 1000
            avmin = max(math.sqrt(fc) / 16, 0.35) * bw * 10 / fyt
            avs = max(Vs * 1000 / (fyt * dd * 10), avmin) if Vud > phiVc / 2 else avmin
            ram, sep = n(v.get("ramas")), n(v.get("sep"))
            avp = ram * PI * phie ** 2 / 4 / (sep * 10) if (ram > 0 and sep > 0) else None
            smax = (min(dd * 10 / 2, 600) if Vs <= math.sqrt(fc) / 3 * bw * 10 * dd * 10 / 1000 else min(dd * 10 / 4, 300)) / 10
            est = "REVISAR" if avp is None else ("AUMENTAR sección" if Vs > Vsmax else ("CUMPLE" if (avp >= avs and sep <= smax) else "NO CUMPLE"))
            r["corte"] = dict(Vu=r["Vu"], d=dd, Vud=Vud, phiVc=phiVc, Vs=Vs, Vsmax=Vsmax, avs=avs, ramas=ram or None, sep=sep or None, avp=avp, smax=smax, estado=est)
        res.append(r)
    return res


# ------------------------------------------------------------------ columnas (diagrama de interacción)
KS = [100, 3, 2, 1.5, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.02]


def interaccion(b, h, d1, As1, As2, As3, M):
    fc, fy, Es, b1 = M["fc"], M["fy"], M["Es"], M["beta1"]
    d2 = h - d1
    Ast = As1 + As2 + As3
    Po = (0.85 * fc * (b * h - Ast) + fy * Ast) / 1000
    pmax = 0.8 * 0.65 * Po
    pts = []
    for k in KS:
        c = k * h
        a = min(b1 * c, h)
        e1, e3, e2 = (0.003 * (c - x) / c for x in (d1, h / 2, d2))
        fs = [max(-fy, min(fy, Es * e)) for e in (e1, e3, e2)]
        sub = lambda d, f: f - (0.85 * fc if d < a else 0)
        F1, F3, F2 = As1 * sub(d1, fs[0]), As3 * sub(h / 2, fs[1]), As2 * sub(d2, fs[2])
        Cc = 0.85 * fc * b * a
        Pn = (Cc + F1 + F3 + F2) / 1000
        Mn = (Cc * (h / 2 - a / 2) + F1 * (h / 2 - d1) + F2 * (h / 2 - d2)) / 1e6
        et = -e2
        ey = fy / Es
        phi = 0.9 if et >= 0.005 else (0.65 if et <= ey else 0.65 + (et - ey) * 0.25 / (0.005 - ey))
        pts.append(dict(k=k, c=c, a=a, Pn=Pn, Mn=Mn, et=et, phi=phi, phiPn=min(phi * Pn, pmax), phiMn=phi * Mn))
    return Po, pmax, pts


def phiMn_en(Pu, pmax, pts):
    if Pu > pmax:
        return 0.0
    O = [p["phiPn"] for p in pts]
    if Pu <= O[-1]:
        return pts[-1]["phiMn"]
    idx = max(i for i, v in enumerate(O) if v >= Pu)
    if O[idx] == O[idx + 1]:
        return pts[idx]["phiMn"]
    P0, P1 = pts[idx]["phiMn"], pts[idx + 1]["phiMn"]
    return P0 + (P1 - P0) * (O[idx] - Pu) / (O[idx] - O[idx + 1])


def columnas(lista, M, C):
    res = []
    for c in lista:
        if not c.get("id"):
            continue
        b, h, lu = n(c["b"]), n(c["h"]), n(c["lu"])
        pp = 1.2 * M["gHA"] * b * h / 10000 * lu
        Pu = C["qu_T"] * n(c.get("A_T")) + C["qu_E"] * n(c.get("A_E")) + n(c.get("R_vigas")) + n(c.get("Pu_sup")) + pp
        r = dict(id=c["id"], b=b, h=h, lu=lu, A_T=n(c.get("A_T")), A_E=n(c.get("A_E")), R_vigas=n(c.get("R_vigas")), Pu_sup=n(c.get("Pu_sup")), pp=pp, Pu=Pu, Mu=n(c.get("Mu")), k=n(c.get("k")) or 1.0,
                 arriostrado=c.get("arriostrado", "SI"), m1m2=n(c.get("m1m2")))
        nt, nc, phi, phie, s = n(c.get("n_tot")), n(c.get("n_cara")), n(c.get("phi")), n(c.get("phi_e")), n(c.get("s_est"))
        r.update(n_tot=nt or None, n_cara=nc or None, phi=phi or None, phi_e=phie or None, s_est=s or None)
        lam = r["k"] * lu * 100 / (0.3 * h)
        lim = min(40, 34 - 12 * r["m1m2"]) if r["arriostrado"] == "SI" else 22
        r.update(lam=lam, lam_lim=lim, ok_esb="CUMPLE" if lam <= lim else "REVISAR")
        if phi <= 0 or nt <= 0:
            r.update(ok_cuantia="REVISAR", ok_pm="REVISAR", ok_est="REVISAR")
            res.append(r)
            continue
        ab = PI * phi ** 2 / 4
        Ast = nt * ab / 100
        rho = Ast / (b * h) * 100
        dp = (M["cc_vc"] + phie + phi / 2) / 10
        Po, pmax, pts = interaccion(b * 10, h * 10, dp * 10, nc * ab, nc * ab, (nt - 2 * nc) * ab, M)
        phiMn = phiMn_en(Pu, pmax, pts)
        smax = min(16 * phi, 48 * phie, min(b, h) * 10) / 10 if phie > 0 else None
        r.update(Ast=Ast, rho=rho, dp=dp, Po=Po, phiPn_max=pmax, phiMn=phiMn, util=(r["Mu"] / phiMn if phiMn > 0 else None), puntos=pts, smax=smax,
                 ok_cuantia="CUMPLE" if (nt >= 4 and 1 <= rho <= 8) else "NO CUMPLE", ok_pm="CUMPLE" if (Pu <= pmax and r["Mu"] <= phiMn) else "NO CUMPLE",
                 ok_est="REVISAR" if phie <= 0 else ("CUMPLE" if (phie >= (6 if phi <= 20 else 10) and s <= smax) else "NO CUMPLE"))
        res.append(r)
    return res


# ------------------------------------------------------------------ sismo – acción
def sismo1(S, M, C):
    zona, tipo = int(S["zona"]), int(S["tipo_esp"])
    Na, Nv, gr = n(S["Na"]), n(S["Nv"]), GRUPOS[S["grupo"]]
    sis = S["sistema"]
    R0, Cd, Wo = RTAB[sis]
    if sis.startswith("1 - "):
        z = min(2, max(1, 2.5 - 0.5 * n(S.get("Ar"))))
        R = min(7, max(5 / z, (3 * n(S.get("A")) + 5) / z))
    else:
        R = R0
    as_, T3, Cu, *tipos = ZONAS[zona]
    ca, cv = tipos[tipo - 1]
    Ca, Cv = ca * (Na if zona >= 3 else 1), cv * (Nv if zona >= 3 else 1)
    T2 = Cv / (2.5 * Ca)
    T1 = 0.2 * T2
    Cr, x = CRX[S["sist_T"]]
    H = n(S["H"])
    Ta = Cr * H ** x
    Tc = n(S.get("T_calc"))
    T = min(Tc, Cu * Ta) if Tc > 0 else Ta
    Sa = Ca * (1 + 1.5 * T / T1) if T <= T1 else (2.5 * Ca if T <= T2 else (Cv / T if T <= T3 else Cv * T3 / T ** 2))
    C1 = 2.5 * Ca * gr / R if T <= T2 else Sa * gr / R
    Cmin = 0.8 * as_ * Nv * gr / R if zona >= 3 else 0.11 * Ca * gr
    Cs = max(C1, Cmin)
    p = dict(zona=zona, tipo=tipo, Na=Na, Nv=Nv, grupo=S["grupo"], gr=gr, sistema=sis, R=R, Cd=Cd, Wo=Wo, as_=as_, Ca=Ca, Cv=Cv, T1=T1, T2=T2, T3=T3, Cu=Cu, Cr=Cr, x=x, H=H, Ta=Ta, T=T, Sa=Sa,
             C_calc=C1, Cmin=Cmin, C=Cs, Ev=0.5 * Ca * gr, rama="T ≤ T2: meseta del espectro" if T <= T2 else "T > T2: rama descendente", sist_T=S["sist_T"])
    # pesos por nivel
    walls = [dict(w, W=n(w.get("long")) * n(w.get("esp")) * n(w.get("alt")) * M["g_mamp"]) for w in S.get("muros", []) if n(w.get("long")) > 0]
    niveles = []
    for i, lv in enumerate(S["niveles"]):
        A = n(lv.get("A"))
        D, Lv, Lr = _nivel(C, lv.get("tipo", "TECHO")) if A > 0 else (0, 0, 0)
        Dp = D + M["gHA"] * n(lv.get("h_losa")) / 100 if A > 0 else 0
        Luso = (Lv + Lr) if A > 0 else 0
        f1 = F1.get(lv.get("destino"), 0)
        Wl = A * (Dp + f1 * Luso)
        Wm = 0.5 * sum(w["W"] for w in walls if int(n(w.get("piso"))) == i + 1) + 0.5 * sum(w["W"] for w in walls if int(n(w.get("piso"))) == i + 2)
        Wo = n(lv.get("W_otros"))
        niveles.append(dict(nombre=lv.get("nombre"), hk=n(lv.get("hk")), A=A, tipo=lv.get("tipo"), Dp=Dp, L=Luso, f1=f1, W_losa=Wl, W_muros=Wm, W_otros=Wo, W=Wl + Wm + Wo))
    W = sum(l["W"] for l in niveles)
    V0 = Cs * W
    sw = sum(l["W"] * l["hk"] for l in niveles)
    hmax = max(l["hk"] for l in niveles)
    for l in niveles:
        wh = l["W"] * l["hk"]
        l["Wh"] = wh
        l["F"] = 0 if sw == 0 else (V0 * wh / sw if T <= 2 * T2 else 0.9 * V0 * wh / sw + (0.1 * V0 if l["hk"] == hmax else 0))
    for i, l in enumerate(niveles):
        l["V"] = sum(x["F"] for x in niveles[i:])
    nsel = int(n(S.get("nivel_sel")) or 1)
    p.update(niveles=niveles, muros=walls, W=W, V0=V0, nivel_sel=nsel, F_sel=niveles[nsel - 1]["F"])
    return p


# ------------------------------------------------------------------ sismo – distribución en planta
def sismo2(S2, M, S1):
    F = n(S2.get("F")) or S1["F_sel"]
    irr = S2["irregularidad"]
    ea = 0.0 if irr.startswith("Baja") else (0.05 if irr.startswith("Media") else 0.10)
    Lx, Ly = n(S2["Lx"]), n(S2["Ly"])
    cm = [a for a in S2["cm"] if n(a.get("A")) != 0]
    sA = sum(n(a["A"]) for a in cm)
    XcM = sum(n(a["A"]) * n(a["x"]) for a in cm) / sA if sA else 0
    YcM = sum(n(a["A"]) * n(a["y"]) for a in cm) / sA if sA else 0
    els = []
    for e in S2["elementos"]:
        if not e.get("id"):
            continue
        mamp = e["tipo"] == "Muro de mampostería"
        E_, G_ = (M["Em"] if mamp else M["Ec"]) * 1000, (M["Gm"] if mamp else 0.4 * M["Ec"]) * 1000
        t, L, h = n(e.get("e")), n(e.get("L")), n(e.get("h"))
        Ae, Ie = 0.6 * t * L, 0.4 * t * L ** 3 / 12
        if e["tipo"] == "Pórtico u otro (R manual)":
            R = n(e.get("R_manual"))
        else:
            R = 0 if (Ie == 0 or Ae == 0) else 1 / (h ** 3 / (3 * E_ * Ie) + 1.2 * h / (G_ * Ae))
        els.append(dict(id=e["id"], dir=e["dir"], tipo=e["tipo"], e=t, L=L, h=h, pos=n(e.get("pos")), R=R, Ae=Ae, Ie=Ie, E=E_, G=G_))
    sRx = sum(x["R"] for x in els if x["dir"] == "X")
    sRy = sum(x["R"] for x in els if x["dir"] == "Y")
    YcR = sum(x["R"] * x["pos"] for x in els if x["dir"] == "X") / sRx if sRx else 0
    XcR = sum(x["R"] * x["pos"] for x in els if x["dir"] == "Y") / sRy if sRy else 0
    ex, ey = XcM - XcR, YcM - YcR
    eax, eay = ea * Lx, ea * Ly
    ex1, ex2, ey1, ey2 = ex + eax, ex - eax, ey + eay, ey - eay
    for x in els:
        x["off"] = x["pos"] - (YcR if x["dir"] == "X" else XcR)
        x["Rd2"] = x["R"] * x["off"] ** 2
    Ip = sum(x["Rd2"] for x in els)
    for x in els:
        sR = sRx if x["dir"] == "X" else sRy
        x["Vd"] = F * x["R"] / sR if sR else 0
        e1, e2 = (ey1, ey2) if x["dir"] == "X" else (ex1, ex2)
        x["Ft1"] = F * e1 * x["R"] * x["off"] / Ip if Ip else 0
        x["Ft2"] = F * e2 * x["R"] * x["off"] / Ip if Ip else 0
        x["Vu"] = x["Vd"] + max(0, x["Ft1"], x["Ft2"])
    sdx = sum(x["Vd"] for x in els if x["dir"] == "X")
    sdy = sum(x["Vd"] for x in els if x["dir"] == "Y")
    return dict(F=F, irregularidad=irr, ea=ea, Lx=Lx, Ly=Ly, XcM=XcM, YcM=YcM, XcR=XcR, YcR=YcR, sRx=sRx, sRy=sRy, ex=ex, ey=ey, eax=eax, eay=eay, ex1=ex1, ex2=ex2, ey1=ey1, ey2=ey2, Ip=Ip, elementos=els,
                eq_x="OK" if abs(sdx - F) < 0.01 * F else "REVISAR", eq_y="OK" if abs(sdy - F) < 0.01 * F else "REVISAR", sdx=sdx, sdy=sdy)


# ------------------------------------------------------------------ muros
def muros(Mu_in, M, S1, S2):
    fc, fyt = M["fc"], M["fyt"]
    mam, tab = [], []
    for i, x in enumerate(S2["elementos"]):
        if x["tipo"] == "Muro de mampostería":
            ND = n(Mu_in.get("ND", {}).get(x["id"]))
            Ag = x["e"] * x["L"]
            Nmin = ND * (1 - S1["Ev"])
            fo = Nmin / Ag / 1000 if Ag else 0
            Vn = min(M["fv"] + 0.4 * fo, 2 * M["fv"]) * Ag * 1000
            phiVn = 0.8 * Vn
            mam.append(dict(id=x["id"], dir=x["dir"], e=x["e"], L=x["L"], Ag=Ag, ND=ND, Nmin=Nmin, fo=fo, Vu=x["Vu"], Vn=Vn, phiVn=phiVn, ratio=x["Vu"] / phiVn if phiVn else None, estado="CUMPLE" if x["Vu"] <= phiVn else "NO CUMPLE"))
        elif x["tipo"] == "Tabique de H°A°" and i < 6:
            inp = Mu_in.get("tabiques", {}).get(x["id"], {})
            d = 0.8 * x["L"]
            Nu = n(inp.get("Nu"))
            Vc = 0.25 * math.sqrt(fc) * x["e"] * 1000 * d * 1000 / 1000 + Nu * d / (4 * x["L"])
            phi, sep, cort = n(inp.get("phi")), n(inp.get("sep")), n(inp.get("cortinas"))
            rho = cort * PI * phi ** 2 / 4 / (x["e"] * 1000 * sep * 10) if (phi > 0 and sep > 0) else None
            Vs = None if rho is None else rho * fyt * x["e"] * 1000 * d * 1000 / 1000
            Vnmax = 5 / 6 * math.sqrt(fc) * x["e"] * 1000 * d * 1000 / 1000
            phiVn = None if Vs is None else 0.75 * min(Vc + Vs, Vnmax)
            okrho = None if rho is None else ("CUMPLE" if rho >= 0.0025 else "NO CUMPLE")
            est = "REVISAR" if phiVn is None else ("CUMPLE" if (x["Vu"] <= phiVn and okrho == "CUMPLE") else "NO CUMPLE")
            tab.append(dict(id=x["id"], e=x["e"], L=x["L"], d=d, Nu=Nu, Vu=x["Vu"], Vc=Vc, phi=phi or None, sep=sep or None, cort=cort or None, rho=rho, Vs=Vs, Vnmax=Vnmax, phiVn=phiVn, ok_rho=okrho, estado=est))
    return dict(mamposteria=mam, tabiques=tab)


# ------------------------------------------------------------------ voladizos
def voladizos(V, M, S1, C):
    Rv = RTAB["6 - Columnas en voladizo"][0]
    Cc = 2.5 * S1["Ca"] * S1["gr"] / Rv
    cols = []
    for c in V.get("columnas", []):
        if not c.get("id"):
            continue
        b, h, H, Q1 = n(c["b"]), n(c["h"]), n(c["H"]), n(c["Q1"])
        q2 = M["gHA"] * b * h / 10000
        Fs1, Fs2 = Cc * Q1, Cc * q2 * H
        Mu = Fs1 * H + Fs2 * H / 2
        nb, phi, phie = n(c.get("n_barras")), n(c.get("phi")), n(c.get("phi_e"))
        r = dict(id=c["id"], b=b, h=h, H=H, Q1=Q1, q2=q2, Fs1=Fs1, Fs2=Fs2, Mu=Mu, n_barras=nb or None, phi=phi or None, phi_e=phie or None)
        if nb > 0 and phi > 0:
            d = h - (M["cc_vc"] + phie + phi / 2) / 10
            As = nb * PI * phi ** 2 / 4
            pm = 0.9 * As * M["fy"] * (d * 10 - As * M["fy"] / (0.85 * M["fc"] * b * 10) / 2) / 1e6
            r.update(d=d, phiMn=pm, estado="CUMPLE" if pm >= Mu else "NO CUMPLE")
        else:
            r.update(estado="REVISAR")
        cols.append(r)
    comps = []
    for c in V.get("componentes", []):
        if not c.get("desc"):
            continue
        z, Wp = n(c["z"]), n(c["Wp"])
        fhk = 1 + 2 * z / S1["H"]
        Cp = n(c["Ip"]) * S1["Ca"] * n(c["ap"]) * fhk / n(c["Rp"])
        comps.append(dict(desc=c["desc"], Wp=Wp, z=z, ap=n(c["ap"]), Rp=n(c["Rp"]), Ip=n(c["Ip"]), fhk=fhk, Cp=Cp, Fp=Cp * Wp))
    return dict(R=Rv, C=Cc, columnas=cols, componentes=comps)


# ------------------------------------------------------------------ fundaciones
def fundaciones(F, M, C, columnas_res):
    fc, fy = M["fc"], M["fy"]
    cim = []
    for c in F.get("cimientos", []):
        if not c.get("id"):
            continue
        q1, L1, q2, L2, e, h = (n(c.get(k)) for k in ("q1", "L1", "q2", "L2", "e", "h"))
        N = q1 * L1 / 2 + q2 * L2 / 2 + e * h * M["g_mamp"]
        Bnec = max(1.25 * N / M["s_adm"] * 100, e * 100 + 15)
        K, hc = n(c.get("B")), n(c.get("hc"))
        r = dict(id=c["id"], q1=q1, L1=L1, q2=q2, L2=L2, e=e, h=h, N=N, Bnec=Bnec, B=K or None, hc=hc or None)
        if K > 0:
            sig = (N + K / 100 * hc / 100 * M["gHS"]) / (K / 100)
            al = math.degrees(math.atan(hc / max(0.1, (K - e * 100) / 2)))
            r.update(sigma=sig, alpha=al, estado="CUMPLE" if (sig <= M["s_adm"] and K >= Bnec and K >= e * 100 + 15 and al >= 60) else "NO CUMPLE")
        else:
            r["estado"] = "REVISAR"
        cim.append(r)
    bases = []
    for z in F.get("bases", []):
        if not z.get("id"):
            continue
        bc, hc_ = n(z["bc"]), n(z["hc"])
        Pu = n(z.get("Pu")) or (columnas_res[z["idx"]]["Pu"] if z.get("idx") is not None and z["idx"] < len(columnas_res) else 0.0)
        Ps = Pu / 1.4
        Breq = math.sqrt(1.2 * Ps / M["s_adm"]) * 100
        B, h = n(z.get("B")), n(z.get("h"))
        r = dict(id=z["id"], bc=bc, hc=hc_, Pu=Pu, Ps=Ps, Breq=Breq, B=B or None, h=h or None)
        if B > 0 and h > 0:
            Wz = M["gHA"] * (B / 100) ** 2 * h / 100
            Ws = M["g_suelo"] * ((B / 100) ** 2 - bc * hc_ / 10000) * max(0, M["Df"] - h / 100)
            sig = (Ps + Wz + Ws) / (B / 100) ** 2
            r.update(Wz=Wz, Ws=Ws, sigma=sig, estado="CUMPLE" if (sig <= M["s_adm"] and B >= Breq) else "NO CUMPLE")
            phi, sep = n(z.get("phi")), n(z.get("sep"))
            qu = Pu / (B / 100) ** 2
            v = (B - min(bc, hc_)) / 200
            Mu = qu * (B / 100) * v ** 2 / 2
            fl = dict(qu=qu, v=v, Mu=Mu)
            if phi > 0:
                d = h - M["cc_z"] / 10 - 1.5 * phi / 10
                Rn = Mu * 1e6 / (0.9 * B * 10 * (d * 10) ** 2)
                t = 1 - 2 * Rn / (0.85 * fc)
                Asreq = None if t < 0 else 0.85 * fc / fy * (1 - math.sqrt(t)) * B * 10 * d * 10 / 100
                Asmin = 0.0018 * 420 / fy * B * 10 * h * 10 / 100
                Asp = PI * phi ** 2 / 400 * B / sep if sep > 0 else None
                pm = None if Asp is None else phiMn_(Asp * 100, B * 10, d * 10, fc, fy)
                est = "AUMENTAR h" if Asreq is None else ("REVISAR" if Asp is None else ("CUMPLE" if (Asp >= Asreq and Asp >= Asmin and pm >= Mu) else "NO CUMPLE"))
                fl.update(d=d, Rn=Rn, As_req=Asreq, As_min=Asmin, phi=phi, sep=sep or None, As_prov=Asp, phiMn=pm, estado=est)
                Vu1 = max(0.0, qu * (B / 100) * (v - d / 100))
                pVc = 0.75 * math.sqrt(fc) / 6 * B * 10 * d * 10 / 1000
                bo = 2 * ((bc + d) + (hc_ + d)) * 10
                Vup = max(0.0, Pu - qu * (bc + d) * (hc_ + d) / 10000)
                bcr = max(bc, hc_) / min(bc, hc_)
                pVcp = 0.75 * min(1 / 3, (1 + 2 / bcr) / 6, (40 * d * 10 / bo + 2) / 12) * math.sqrt(fc) * bo * d * 10 / 1000
                r["corte"] = dict(Vu1=Vu1, phiVc=pVc, ok1="CUMPLE" if Vu1 <= pVc else "NO CUMPLE", bo=bo, Vup=Vup, phiVcp=pVcp, okp="CUMPLE" if Vup <= pVcp else "NO CUMPLE")
            else:
                fl["estado"] = "REVISAR"
            r["flex"] = fl
        else:
            r["estado"] = "REVISAR"
        bases.append(r)
    return dict(cimientos=cim, bases=bases)


# ------------------------------------------------------------------ orquestador
def calcular(P):
    M = materiales(P["datos"])
    C = cargas(P["cargas"], M)
    R = dict(materiales=M, cargas=C)
    R["losas"] = losas(P.get("losas", []), M, C)
    R["viguetas"] = viguetas(P.get("viguetas", []), P.get("modo_viguetas", "Servicio"), M, C)
    R["correas"] = correas(P.get("correas", []), C)
    R["vigas"] = vigas(P.get("vigas", []), M, C)
    R["columnas"] = columnas(P.get("columnas", []), M, C)
    S1 = sismo1(P["sismo1"], M, C)
    R["sismo1"] = S1
    R["sismo2"] = sismo2(P["sismo2"], M, S1)
    R["muros"] = muros(P.get("muros", {}), M, S1, R["sismo2"])
    R["voladizos"] = voladizos(P.get("voladizos", {}), M, S1, C)
    R["fundaciones"] = fundaciones(P.get("fundaciones", {}), M, C, R["columnas"])
    R["resumen"] = resumen(R)
    return R


def resumen(R):
    def cuenta(ests):
        ests = [e for e in ests if e]
        cum = sum(e in ("CUMPLE", "OK") for e in ests)
        no = sum(e == "NO CUMPLE" for e in ests)
        rev = sum(e.startswith("REVISAR") or e.startswith("AUMENTAR") for e in ests)
        return dict(total=cum + no + rev, cumple=cum, no=no, revisar=rev, estado="NO CUMPLE" if no else ("REVISAR" if rev else ("CUMPLE" if cum else "–")))
    out = []
    ls = [e for l in R["losas"] for e in (l["ok_h"], l["flex_t"]["estado"], l["flex_a"]["estado"], l["corte"]["estado"], l["reparto"]["estado"])]
    out.append(("Losas", cuenta(ls)))
    vs = [e for v in R["vigas"] for e in (v["ok_h"], v["flex_apoyo"]["estado"], v["flex_tramo"]["estado"], v["corte"]["estado"])]
    out.append(("Vigas", cuenta(vs)))
    out.append(("Viguetas pretensadas y correas de madera", cuenta([x["estado"] for x in R["viguetas"]] + [x["estado"] for x in R["correas"]])))
    out.append(("Columnas", cuenta([e for c in R["columnas"] for e in (c["ok_cuantia"], c["ok_pm"], c["ok_esb"], c["ok_est"])])))
    out.append(("Muros (mampostería y tabiques)", cuenta([x["estado"] for x in R["muros"]["mamposteria"]] + [x["estado"] for x in R["muros"]["tabiques"]])))
    fe = [x["estado"] for x in R["fundaciones"]["cimientos"]]
    for b in R["fundaciones"]["bases"]:
        fe += [b["estado"]]
        if "flex" in b:
            fe += [b["flex"]["estado"]]
        if "corte" in b:
            fe += [b["corte"]["ok1"], b["corte"]["okp"]]
    out.append(("Fundaciones", cuenta(fe)))
    out.append(("Columnas en voladizo", cuenta([x["estado"] for x in R["voladizos"]["columnas"]])))
    out.append(("Distribución sísmica (equilibrio)", cuenta([R["sismo2"]["eq_x"], R["sismo2"]["eq_y"]])))
    tot = cuenta([e for _, c in out for e in ["CUMPLE"] * c["cumple"] + ["NO CUMPLE"] * c["no"] + ["REVISAR"] * c["revisar"]])
    return dict(modulos=out, total=tot)
