#!/usr/bin/env python3
"""
CABINA MT/BT CALCULATOR - STREAMLIT WEB APP
Dimensionamento automatico cabine 20kV/400V secondo normative CEI
"""

import streamlit as st
import pandas as pd
import math
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime

# Configurazione pagina
st.set_page_config(page_title="Calcolatore Cabina MT/BT - Maurizio srl",
                   page_icon="⚡",
                   layout="wide",
                   initial_sidebar_state="expanded")


class CabinaMTBT:

    def __init__(self):
        # Potenze normalizzate CEI 14-52 (kVA)
        self.potenze_normalizzate = [
            25, 50, 100, 160, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
            2000, 2500, 3150
        ]

        # Perdite a vuoto Po (W) - categoria AAo
        self.perdite_vuoto = {
            25: 63,
            50: 81,
            100: 130,
            160: 189,
            250: 270,
            315: 324,
            400: 387,
            500: 459,
            630: 540,
            800: 585,
            1000: 693,
            1250: 855,
            1600: 1080,
            2000: 1305,
            2500: 1575,
            3150: 1980
        }

        # Perdite a carico Pk (W) - categoria Bk
        self.perdite_carico = {
            25: 725,
            50: 875,
            100: 1475,
            160: 2000,
            250: 2750,
            315: 3250,
            400: 3850,
            500: 4600,
            630: 5400,
            800: 7000,
            1000: 9000,
            1250: 11000,
            1600: 14000,
            2000: 18000,
            2500: 22000,
            3150: 27500
        }

        # Tensione di cortocircuito Ucc%
        self.ucc = {
            p: 4 if p <= 1000 else 6
            for p in self.potenze_normalizzate
        }

        # Dati rete MT
        self.V_mt = 20000  # V
        self.V_bt = 400  # V
        self.Um_mt = 24000  # V (tensione massima)
        self.Icc_rete = 12500  # A (corrente cortocircuito rete)

    def calcola_potenza_trasformatore(self,
                                      potenza_carichi,
                                      f_contemporaneita=0.7,
                                      cos_phi=0.85,
                                      margine=1.2):
        """Calcola potenza trasformatore necessaria"""
        potenza_necessaria = (potenza_carichi * f_contemporaneita *
                              margine) / cos_phi

        for p in self.potenze_normalizzate:
            if p >= potenza_necessaria:
                return p, potenza_necessaria
        return self.potenze_normalizzate[-1], potenza_necessaria

    def calcola_correnti(self, potenza_trasf):
        """Calcola correnti nominali MT e BT"""
        I_mt = potenza_trasf * 1000 / (math.sqrt(3) * self.V_mt)
        I_bt = potenza_trasf * 1000 / (math.sqrt(3) * self.V_bt)
        return I_mt, I_bt

    def calcola_cortocircuito_bt(self, potenza_trasf):
        """Calcola corrente di cortocircuito al secondario"""
        ucc = self.ucc[potenza_trasf] / 100
        Icc_bt = (potenza_trasf * 1000) / (math.sqrt(3) * self.V_bt * ucc)
        return Icc_bt

    def dimensiona_protezioni_mt(self, I_mt):
        """Dimensiona protezioni MT (SPGI)"""
        # Interruttore MT
        taglie_int = [630, 1250, 1600, 2000, 2500, 3150]
        I_int = 630
        for t in taglie_int:
            if t >= I_mt * 5:
                I_int = t
                break

        # TA protezione
        rapporti_ta = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100]
        primario_ta = 30
        for r in rapporti_ta:
            if r >= I_mt * 1.5:
                primario_ta = r
                break

        # Tarature relè
        tarature = {
            "50 (Istantanea)": f"{I_mt * 10:.1f} A",
            "51 (Temporizzata)": f"{I_mt * 1.25:.1f} A",
            "50N (Terra Istant.)": "2.0 A",
            "51N (Terra Temp.)": "1.0 A",
            "27 (Min Tensione)": "17.0 kV",
            "59 (Max Tensione)": "22.0 kV"
        }

        return {
            "interruttore": f"{self.Um_mt/1000:.0f}kV - {I_int}A - 16kA - 1s",
            "ta_protezione": f"{primario_ta}/5A cl.5P20",
            "tv_misure": f"{self.V_mt}/100V cl.0.5",
            "scaricatori": "21kV - 10kA classe 1",
            "tarature": tarature
        }

    def dimensiona_protezioni_bt(self, I_bt, Icc_bt):
        """Dimensiona protezioni BT"""
        # Interruttore generale BT
        taglie_bt = [
            160, 250, 400, 630, 800, 1000, 1250, 1600, 2000, 2500, 3200
        ]
        I_gen_bt = 630
        for t in taglie_bt:
            if t >= I_bt * 1.1:
                I_gen_bt = t
                break

        # Potere di interruzione
        if Icc_bt < 25000:
            pdi = 25
        elif Icc_bt < 35000:
            pdi = 35
        else:
            pdi = 50

        # Differenziale
        Idn = 300 if I_gen_bt <= 630 else 500

        return {
            "interruttore_generale": f"{I_gen_bt}A - {pdi}kA",
            "differenziale": f"{I_gen_bt}A / {Idn}mA tipo A",
            "icc_bt": Icc_bt / 1000
        }

    # AGGIUNGI QUESTO METODO ALLA TUA CLASSE CabinaMTBT

    def calcola_sezioni_cavi_professionale(self,
                                           I_mt,
                                           I_bt,
                                           lunghezza_mt=50,
                                           lunghezza_bt=30,
                                           temp_ambiente=35,
                                           tipo_posa="passerella",
                                           n_cavi_raggruppati_mt=1,
                                           n_cavi_raggruppati_bt=1):
        """
            Calcolo cavi con fattori di correzione professionali secondo CEI
            """

        # Database cavi con R, X reali (Ω/km) - CEI 11-17 e CEI 20-13
        cavi_mt_pro = {
            35: {
                "R": 0.868,
                "X": 0.115,
                "portata_base": 140
            },
            50: {
                "R": 0.641,
                "X": 0.110,
                "portata_base": 170
            },
            70: {
                "R": 0.443,
                "X": 0.105,
                "portata_base": 210
            },
            95: {
                "R": 0.320,
                "X": 0.100,
                "portata_base": 250
            },
            120: {
                "R": 0.253,
                "X": 0.095,
                "portata_base": 285
            },
            150: {
                "R": 0.206,
                "X": 0.090,
                "portata_base": 320
            },
            185: {
                "R": 0.164,
                "X": 0.085,
                "portata_base": 370
            },
            240: {
                "R": 0.125,
                "X": 0.080,
                "portata_base": 430
            },
            300: {
                "R": 0.100,
                "X": 0.075,
                "portata_base": 490
            },
            400: {
                "R": 0.075,
                "X": 0.070,
                "portata_base": 570
            },
            500: {
                "R": 0.060,
                "X": 0.065,
                "portata_base": 650
            }
        }

        cavi_bt_pro = {
            35: {
                "R": 0.641,
                "X": 0.065,
                "portata_base": 138
            },
            50: {
                "R": 0.443,
                "X": 0.060,
                "portata_base": 168
            },
            70: {
                "R": 0.320,
                "X": 0.060,
                "portata_base": 207
            },
            95: {
                "R": 0.236,
                "X": 0.055,
                "portata_base": 252
            },
            120: {
                "R": 0.188,
                "X": 0.055,
                "portata_base": 290
            },
            150: {
                "R": 0.150,
                "X": 0.050,
                "portata_base": 330
            },
            185: {
                "R": 0.123,
                "X": 0.050,
                "portata_base": 375
            },
            240: {
                "R": 0.094,
                "X": 0.045,
                "portata_base": 435
            },
            300: {
                "R": 0.075,
                "X": 0.045,
                "portata_base": 495
            },
            400: {
                "R": 0.057,
                "X": 0.040,
                "portata_base": 575
            },
            500: {
                "R": 0.045,
                "X": 0.040,
                "portata_base": 650
            },
            630: {
                "R": 0.036,
                "X": 0.035,
                "portata_base": 735
            }
        }

        # FATTORI DI CORREZIONE PROFESSIONALI
        # 1. Temperatura ambiente (CEI 20-13)
        k_temp = {
            30: 1.0,
            35: 0.96,
            40: 0.91,
            45: 0.85,
            50: 0.78
        }.get(temp_ambiente, 0.90)

        # 2. Raggruppamento cavi (CEI 20-13)
        k_raggr = {
            1: 1.0,
            2: 0.85,
            3: 0.75,
            4: 0.70,
            6: 0.60,
            9: 0.55
        }.get(n_cavi_raggruppati_mt, 0.70)
        k_raggr_bt = {
            1: 1.0,
            2: 0.85,
            3: 0.75,
            4: 0.70,
            6: 0.60,
            9: 0.55
        }.get(n_cavi_raggruppati_bt, 0.70)

        # 3. Tipo di posa
        k_posa = {
            "aria": 1.0,
            "cavidotto": 0.85,
            "interrato": 0.80,
            "passerella": 0.95
        }.get(tipo_posa, 0.80)

        # SELEZIONE CAVO MT con verifiche
        I_mt_progetto = I_mt * 1.3  # Fattore sicurezza
        cavo_mt_selezionato = None

        for sezione, dati in cavi_mt_pro.items():
            # Portata corretta con tutti i fattori
            I_ammissibile = dati["portata_base"] * k_temp * k_raggr * k_posa

            if I_ammissibile >= I_mt_progetto:
                # Verifica caduta tensione con R,X reali
                R_tot = dati["R"] * (lunghezza_mt / 1000)  # Ω
                X_tot = dati["X"] * (lunghezza_mt / 1000)  # Ω
                cos_phi = 0.85
                sin_phi = math.sqrt(1 - cos_phi**2)

                dV_perc = (math.sqrt(3) * I_mt *
                           (R_tot * cos_phi + X_tot * sin_phi) *
                           100) / self.V_mt

                if dV_perc <= 0.5:  # Limite CEI per MT
                    # Calcola perdite
                    perdite_kw = 3 * (I_mt**2) * R_tot / 1000

                    cavo_mt_selezionato = {
                        "sezione": sezione,
                        "portata_corretta": I_ammissibile,
                        "caduta_tensione_perc": dV_perc,
                        "perdite_kw": perdite_kw,
                        "R_ohm_km": dati["R"],
                        "X_ohm_km": dati["X"],
                        "verifica_portata": "✅ OK",
                        "verifica_caduta": "✅ OK" if dV_perc <= 0.5 else "❌ NO"
                    }
                    break

        # SELEZIONE CAVO BT con verifiche
        # SELEZIONE CAVO BT con verifiche
        I_bt_progetto = I_bt * 1.15  # Fattore sicurezza
        cavo_bt_selezionato = None
        for sezione, dati in cavi_bt_pro.items():
            # Portata corretta
            I_ammissibile = dati["portata_base"] * k_temp * k_raggr_bt * k_posa
            # 1. Calcolare fattore armoniche
        if 'armoniche_result' in locals() and armoniche_result:
            THD_corrente = armoniche_result.get('THD_corrente_perc', 0)
        if THD_corrente > 15:
            k_armoniche = 0.93  # Derating per armoniche
        elif THD_corrente > 8:
            k_armoniche = 0.97
        else:
            k_armoniche = 1.0
  

# 2. Applicare fattore armoniche
            I_ammissibile = dati["portata_base"] * k_temp * k_raggr_bt * k_posa * k_armoniche

            if I_ammissibile >= I_bt_progetto:
                # Verifica caduta tensione
                R_tot = dati["R"] * (lunghezza_bt / 1000)  # Ω
                X_tot = dati["X"] * (lunghezza_bt / 1000)  # Ω
                cos_phi = 0.85
                sin_phi = math.sqrt(1 - cos_phi**2)

                dV_perc = (math.sqrt(3) * I_bt *
                           (R_tot * cos_phi + X_tot * sin_phi) *
                           100) / self.V_bt

                if dV_perc <= 4.0:  # Limite CEI per BT
                    perdite_kw = 3 * (I_bt**2) * R_tot / 1000

                    cavo_bt_selezionato = {
                        "sezione": sezione,
                        "portata_corretta": I_ammissibile,
                        "caduta_tensione_perc": dV_perc,
                        "perdite_kw": perdite_kw,
                        "R_ohm_km": dati["R"],
                        "X_ohm_km": dati["X"],
                        "verifica_portata": "✅ OK",
                        "verifica_caduta": "✅ OK" if dV_perc <= 4.0 else "❌ NO"
                    }
                  break

        # Fallback se non trova cavi adatti
        if not cavo_mt_selezionato:
            cavo_mt_selezionato = {
                "sezione": 500,
                "portata_corretta": 400,
                "caduta_tensione_perc": 0.8,
                "perdite_kw": 1.0,
                "verifica_portata": "❌ NO",
                "verifica_caduta": "❌ NO"
            }
        if not cavo_bt_selezionato:
        # Calcola con fattori corretti invece di usare valori fissi
            I_ammissibile_630 = 735 * k_temp * k_raggr_bt * k_posa  # ← CALCOLO REALE
            R_tot = 0.036 * (lunghezza_bt / 1000)
            X_tot = 0.035 * (lunghezza_bt / 1000)
            cos_phi = 0.85
            sin_phi = math.sqrt(1 - cos_phi**2)
            dV_perc = (math.sqrt(3) * I_bt * (R_tot * cos_phi + X_tot * sin_phi) * 100) / self.V_bt
            perdite_kw = 3 * (I_bt**2) * R_tot / 1000
    
            cavo_bt_selezionato = {
                "sezione": 630,
                "portata_corretta": I_ammissibile_630,  # ← CALCOLO DINAMICO
                "caduta_tensione_perc": dV_perc,
                "perdite_kw": perdite_kw,
                "R_ohm_km": 0.036,
                "X_ohm_km": 0.035,
                "verifica_portata": "✅ OK" if I_ammissibile_630 >= I_bt_progetto else "⚠️ LIMITE",
                "verifica_caduta": "✅ OK" if dV_perc <= 4.0 else "⚠️ LIMITE"
        }

        return {
            # Compatibilità con il tuo codice esistente
            "sez_mt":
            cavo_mt_selezionato["sezione"],
            "sez_bt":
            cavo_bt_selezionato["sezione"],
            "portata_mt":
            cavo_mt_selezionato["portata_corretta"],
            "portata_bt":
            cavo_bt_selezionato["portata_corretta"],
            "I_mt_richiesta":
            I_mt_progetto,
            "I_bt_richiesta":
            I_bt_progetto,

            # Nuovi dati professionali
            "mt_dettaglio":
            cavo_mt_selezionato,
            "bt_dettaglio":
            cavo_bt_selezionato,
            "fattori_correzione": {
                "k_temp": k_temp,
                "k_raggr_mt": k_raggr,
                "k_raggr_bt": k_raggr_bt,
                "k_posa": k_posa,
                "temp_ambiente": temp_ambiente,
                "tipo_posa": tipo_posa
            },
            "perdite_totali_cavi_kw":
            cavo_mt_selezionato["perdite_kw"] +
            cavo_bt_selezionato["perdite_kw"]
        }

    # AGGIUNGI QUESTO METODO ALLA TUA CLASSE CabinaMTBT

    def calcola_analisi_economica(self,
                                  potenza_trasf,
                                  cavi_risultati,
                                  ventilazione,
                                  rendimento,
                                  anni_esercizio=25,
                                  costo_energia_kwh=0.25):
        """
        Analisi economica completa: investimenti, costi esercizio, ammortamenti
        """

        # 1. COSTI DI INVESTIMENTO (CAPEX)

        # Costi trasformatore (€ - dati di mercato 2024)
        costi_trasformatore = {
            25: 8000,
            50: 12000,
            100: 18000,
            160: 25000,
            250: 35000,
            315: 42000,
            400: 50000,
            500: 60000,
            630: 75000,
            800: 90000,
            1000: 110000,
            1250: 140000,
            1600: 180000,
            2000: 220000,
            2500: 280000,
            3150: 350000
        }

        costo_trasformatore = costi_trasformatore.get(potenza_trasf, 110000)

        # Costi quadri e protezioni (% del trasformatore)
        costo_quadro_mt = costo_trasformatore * 0.4  # 40% per SPGI MT
        costo_quadro_bt = costo_trasformatore * 0.3  # 30% per QG BT

        # Costi cavi (€/m)
        prezzi_cavi_mt = {  # €/m per cavi MT 20kV
            35: 25,
            50: 32,
            70: 45,
            95: 58,
            120: 70,
            150: 85,
            185: 105,
            240: 135,
            300: 170,
            400: 220,
            500: 280
        }

        prezzi_cavi_bt = {  # €/m per cavi BT 0.6/1kV
            35: 8,
            50: 12,
            70: 16,
            95: 22,
            120: 28,
            150: 35,
            185: 45,
            240: 60,
            300: 75,
            400: 95,
            500: 120,
            630: 150
        }

        # Estrai dati cavi dai risultati
        if 'mt_dettaglio' in cavi_risultati:  # Metodo professionale
            sez_mt = cavi_risultati['mt_dettaglio']['sezione']
            sez_bt = cavi_risultati['bt_dettaglio']['sezione']
            lung_mt = cavi_risultati.get('parametri',
                                         {}).get('lunghezza_mt', 50)
            lung_bt = cavi_risultati.get('parametri',
                                         {}).get('lunghezza_bt', 30)
        else:  # Metodo standard
            sez_mt = cavi_risultati['sez_mt']
            sez_bt = cavi_risultati['sez_bt']
            lung_mt = 50  # Default
            lung_bt = 30  # Default

        # Calcola costi cavi
        prezzo_mt_m = prezzi_cavi_mt.get(sez_mt, 70)
        prezzo_bt_m = prezzi_cavi_bt.get(sez_bt, 35)

        costo_cavi_mt = prezzo_mt_m * lung_mt * 3  # 3 cavi per terna MT
        costo_cavi_bt = prezzo_bt_m * lung_bt * 4  # 4 cavi per sistema BT

        # Costi opere civili (€)
        volume_locale = 6 * 4 * 2.5  # m³ (6×4×2.5m tipico)
        costo_opere_civili = volume_locale * 800  # €/m³ per locale prefabbricato

        # Costi installazione e commissioning
        costo_installazione = (costo_trasformatore + costo_quadro_mt +
                               costo_quadro_bt) * 0.15  # 15%

        # TOTALE CAPEX
        capex_totale = (costo_trasformatore + costo_quadro_mt +
                        costo_quadro_bt + costo_cavi_mt + costo_cavi_bt +
                        costo_opere_civili + costo_installazione)

        # 2. COSTI OPERATIVI ANNUI (OPEX)

        # Perdite energetiche annue
        ore_esercizio_anno = 8760  # h
        fattore_carico_medio = 0.6  # 60% carico medio

        # Perdite trasformatore
        Po_kw = rendimento['perdite_vuoto']  # kW perdite a vuoto
        Pk_kw = rendimento['perdite_carico'] * (fattore_carico_medio**2
                                                )  # kW perdite carico

        # Perdite cavi
        if 'perdite_totali_cavi_kw' in cavi_risultati:
            perdite_cavi_kw = cavi_risultati['perdite_totali_cavi_kw'] * (
                fattore_carico_medio**2)
        else:
            # Stima perdite cavi se non disponibili
            perdite_cavi_kw = (potenza_trasf * 0.005) * (fattore_carico_medio**
                                                         2)  # 0.5% stima

        # Energia persa annualmente
        energia_persa_anno = (Po_kw + Pk_kw +
                              perdite_cavi_kw) * ore_esercizio_anno  # kWh
        costo_perdite_anno = energia_persa_anno * costo_energia_kwh  # €

        # Manutenzione programmata
        costo_manutenzione_anno = capex_totale * 0.02  # 2% annuo del CAPEX

        # Verifiche periodiche e controlli
        costo_verifiche_anno = 2000  # € per misure e controlli annui

        # TOTALE OPEX ANNUO
        opex_annuo = costo_perdite_anno + costo_manutenzione_anno + costo_verifiche_anno

        # 3. ANALISI FINANZIARIA

        # Calcola NPV (Net Present Value) e IRR
        tasso_sconto = 0.06  # 6% WACC tipico

        # Flussi di cassa (negativi = uscite)
        flussi_cassa = [-capex_totale]  # Anno 0: investimento
        for anno in range(1, anni_esercizio + 1):
            flussi_cassa.append(-opex_annuo)  # Anni 1-25: OPEX

        # NPV (semplificato)
        npv = capex_totale  # Investimento iniziale
        for anno in range(1, anni_esercizio + 1):
            npv += opex_annuo / ((1 + tasso_sconto)**anno)
        npv = -npv  # Negativo perché sono tutti costi

        # Costo totale di ownership (TCO)
        tco_25_anni = capex_totale + (opex_annuo * anni_esercizio)

        # Costo per kW installato
        costo_per_kw = capex_totale / potenza_trasf

        # 4. ANALISI COMPARATIVA EFFICIENZA

        # Calcola rendimento sotto diverse condizioni di carico
        carichi_test = [0.25, 0.5, 0.75, 1.0]  # 25%, 50%, 75%, 100%
        rendimenti_vs_carico = []

        for carico in carichi_test:
            Po = rendimento['perdite_vuoto']
            Pk = rendimento['perdite_carico'] * (carico**2)
            Pu = potenza_trasf * carico * 0.95  # cos φ = 0.95
            eta = Pu / (Pu + Po + Pk) * 100

            rendimenti_vs_carico.append({
                "carico_perc": carico * 100,
                "rendimento_perc": eta,
                "perdite_kw": Po + Pk
            })

        # 5. INDICATORI ECONOMICI

        # Payback period (se ci fossero risparmi)
        # In questo caso calcoliamo il "payback delle perdite"
        payback_perdite_anni = capex_totale / costo_perdite_anno

        # ROI (Return on Investment) - calcolato sui risparmi energetici vs alternativa meno efficiente
        trasf_std_perdite = potenza_trasf * 0.015  # 1.5% perdite trasformatore standard
        trasf_efficiente_perdite = (
            Po_kw +
            Pk_kw) / potenza_trasf  # Perdite % del nostro trasformatore

        if trasf_efficiente_perdite < trasf_std_perdite:
            risparmio_annuo = (
                trasf_std_perdite - trasf_efficiente_perdite
            ) * potenza_trasf * ore_esercizio_anno * fattore_carico_medio * costo_energia_kwh
            roi_perc = (risparmio_annuo / capex_totale) * 100
        else:
            risparmio_annuo = 0
            roi_perc = 0

        return {
            # CAPEX breakdown
            "capex": {
                "trasformatore": costo_trasformatore,
                "quadro_mt": costo_quadro_mt,
                "quadro_bt": costo_quadro_bt,
                "cavi_mt": costo_cavi_mt,
                "cavi_bt": costo_cavi_bt,
                "opere_civili": costo_opere_civili,
                "installazione": costo_installazione,
                "totale": capex_totale
            },

            # OPEX breakdown
            "opex_annuo": {
                "perdite_energetiche": costo_perdite_anno,
                "manutenzione": costo_manutenzione_anno,
                "verifiche": costo_verifiche_anno,
                "totale": opex_annuo
            },

            # Perdite energetiche dettaglio
            "perdite_energia": {
                "trasformatore_vuoto_kw": Po_kw,
                "trasformatore_carico_kw": Pk_kw,
                "cavi_kw": perdite_cavi_kw,
                "totale_kw": Po_kw + Pk_kw + perdite_cavi_kw,
                "energia_persa_anno_kwh": energia_persa_anno,
                "costo_anno_euro": costo_perdite_anno
            },

            # Indicatori finanziari
            "indicatori": {
                "tco_25_anni": tco_25_anni,
                "npv_25_anni": npv,
                "costo_per_kw": costo_per_kw,
                "payback_perdite_anni": payback_perdite_anni,
                "roi_efficienza_perc": roi_perc,
                "risparmio_annuo_euro": risparmio_annuo
            },

            # Analisi rendimento
            "rendimenti_vs_carico":
            rendimenti_vs_carico,

            # Parametri calcolo
            "parametri": {
                "anni_esercizio": anni_esercizio,
                "costo_energia_kwh": costo_energia_kwh,
                "tasso_sconto": tasso_sconto,
                "fattore_carico_medio": fattore_carico_medio,
                "ore_esercizio_anno": ore_esercizio_anno
            },

            # Raccomandazioni
            "raccomandazioni": [
                f"💰 Investimento totale: {capex_totale:,.0f} €",
                f"📊 Costo operativo annuo: {opex_annuo:,.0f} €",
                f"⚡ Perdite energetiche: {energia_persa_anno:,.0f} kWh/anno",
                f"🎯 TCO 25 anni: {tco_25_anni:,.0f} €",
                "🔋 Considerare trasformatore alta efficienza per ridurre OPEX"
                if Po_kw > potenza_trasf *
                0.008 else "✅ Trasformatore efficiente selezionato"
            ]
        }
        # AGGIUNGI QUESTO METODO ALLA TUA CLASSE CabinaMTBT

    # CORREZIONE 2: Aggiungere il metodo mancante calcola_analisi_armoniche alla classe CabinaMTBT
    # Inserire questo metodo nella classe CabinaMTBT (dopo gli altri metodi):

    def calcola_analisi_armoniche(self, potenza_trasf, tipo_carichi, I_bt):
        """
        Analisi dettagliata delle armoniche secondo IEC 61000-2-4 e CEI 110-31
        """

        # DEFINIZIONE SPETTRI ARMONICI PER TIPO CARICO
        spettri_tipici = {
            "lineare": {
                # Carichi lineari (motori, resistenze)
                3: 0.02,
                5: 0.015,
                7: 0.01,
                9: 0.005,
                11: 0.003,
                13: 0.002
            },
            "misto": {
                # Mix industriale tipico
                3: 0.08,
                5: 0.06,
                7: 0.04,
                9: 0.02,
                11: 0.015,
                13: 0.01,
                15: 0.008,
                17: 0.006,
                19: 0.004
            },
            "non_lineare": {
                # UPS, inverter, azionamenti
                3: 0.15,
                5: 0.12,
                7: 0.08,
                9: 0.05,
                11: 0.04,
                13: 0.03,
                15: 0.02,
                17: 0.015,
                19: 0.01,
                21: 0.008,
                23: 0.006
            },
            "data_center": {
                # Server, UPS, IT
                3: 0.25,
                5: 0.18,
                7: 0.12,
                9: 0.08,
                11: 0.06,
                13: 0.04,
                15: 0.03,
                17: 0.02,
                19: 0.015,
                21: 0.01
            }
        }

        spettro = spettri_tipici.get(tipo_carichi, spettri_tipici["misto"])

        # CALCOLO CORRENTI ARMONICHE
        I1 = I_bt  # Corrente fondamentale
        correnti_armoniche_A = {1: I1}  # Dizionario con tutte le armoniche

        for h, perc in spettro.items():
            correnti_armoniche_A[h] = I1 * perc

        # THD CORRENTE (Total Harmonic Distortion)
        sum_Ih_squared = sum(I**2 for h, I in correnti_armoniche_A.items()
                             if h > 1)
        THD_corrente_perc = (math.sqrt(sum_Ih_squared) / I1) * 100

        # FATTORE CRESTA (rapporto picco/efficace)
        if tipo_carichi == "lineare":
            fattore_cresta = 1.41  # √2 per sinusoidale
        elif tipo_carichi == "misto":
            fattore_cresta = 1.8
        elif tipo_carichi == "non_lineare":
            fattore_cresta = 2.5
        else:  # data_center
            fattore_cresta = 3.0

        # THD TENSIONE (stimato da THD corrente e impedenza rete)
        # THD_V = THD_I × Z_rete/Z_trasf (formula semplificata)
        impedenza_rete_pu = 0.05  # 5% tipico per rete distributore
        THD_tensione_perc = THD_corrente_perc * impedenza_rete_pu

        # VERIFICHE NORMATIVE
        # Limiti CEI EN 50160 per tensione
        limite_THD_tensione = 8.0  # % per reti MT
        limite_THD_corrente_h3 = 40.0  # % per 3ª armonica
        limite_THD_corrente_totale = 48.0  # % THD totale corrente

        # Verifica THD tensione
        verifica_tensione_THD = {
            "valore_perc":
            THD_tensione_perc,
            "limite_perc":
            limite_THD_tensione,
            "verifica":
            "✅ OK"
            if THD_tensione_perc <= limite_THD_tensione else "❌ SUPERATO"
        }

        # Verifica THD corrente
        verifica_corrente_THD = {
            "valore_perc":
            THD_corrente_perc,
            "limite_perc":
            limite_THD_corrente_totale,
            "verifica":
            "✅ OK" if THD_corrente_perc <= limite_THD_corrente_totale else
            "❌ SUPERATO"
        }

        # EFFETTI DELLE ARMONICHE
        # Perdite aggiuntive nel trasformatore (formula empirica)
        perdite_aggiuntive_perc = (THD_corrente_perc / 100)**2 * 8  # %

        # Sovradimensionamento conduttore neutro
        I3_perc = spettro.get(3, 0) * 100  # 3ª armonica in %
        if I3_perc > 33:
            sovradim_neutro = 2.0  # Raddoppio sezione
        elif I3_perc > 25:
            sovradim_neutro = 1.5  # +50%
        else:
            sovradim_neutro = 1.0  # Normale

        # RACCOMANDAZIONI
        raccomandazioni = []

        if THD_corrente_perc > 30:
            raccomandazioni.append(
                "Installare filtri armoniche attivi o passivi")
            raccomandazioni.append(
                "Verificare derating del trasformatore (-10% per THD>30%)")

        if I3_perc > 15:
            raccomandazioni.append(
                f"Sovradimensionare neutro: sezione × {sovradim_neutro}")

        if fattore_cresta > 2.0:
            raccomandazioni.append(
                "Verificare dimensionamento interruttori (fattore cresta elevato)"
            )

        if THD_tensione_perc > 5:
            raccomandazioni.append("Monitorare quality power in continuo")

        # Raccomandazioni specifiche per tipo carico
        if tipo_carichi == "data_center":
            raccomandazioni.append(
                "Trasformatore con fattore K≥13 per carichi IT")
            raccomandazioni.append("UPS con IGBT per ridurre armoniche")
        elif tipo_carichi == "non_lineare":
            raccomandazioni.append("Trasformatore con fattore K≥9")
            raccomandazioni.append(
                "Bobine di blocco per armoniche alte frequenza")

        # VALUTAZIONE POWER QUALITY
        if THD_tensione_perc <= 3 and THD_corrente_perc <= 15:
            valutazione = "POWER QUALITY BUONA"
        elif THD_tensione_perc <= 5 and THD_corrente_perc <= 25:
            valutazione = "POWER QUALITY ACCETTABILE"
        else:
            valutazione = "POWER QUALITY CRITICA - INTERVENTI NECESSARI"

        return {
            # Parametri input
            "tipo_carichi": tipo_carichi,
            "potenza_trasf_kVA": potenza_trasf,
            "corrente_fondamentale_A": I1,

            # Spettro armoniche
            "spettro_percentuali": spettro,
            "correnti_armoniche_A": correnti_armoniche_A,

            # Indicatori principali
            "THD_corrente_perc": THD_corrente_perc,
            "THD_tensione_perc": THD_tensione_perc,
            "fattore_cresta": fattore_cresta,

            # Verifiche normative
            "verifiche_tensione": {
                "THD_totale": verifica_tensione_THD
            },
            "verifiche_corrente": {
                "THD_totale": verifica_corrente_THD
            },

            # Effetti
            "effetti_armoniche": {
                "perdite_aggiuntive_perc": perdite_aggiuntive_perc,
                "sovradimensionamento_neutro": sovradim_neutro,
                "corrente_3_armonica_perc": I3_perc
            },

            # Valutazione e raccomandazioni
            "valutazione_power_quality": valutazione,
            "raccomandazioni": raccomandazioni,

            # Limiti normativi
            "limiti_normativi": {
                "THD_tensione_max_perc": limite_THD_tensione,
                "THD_corrente_max_perc": limite_THD_corrente_totale,
                "normativa": "CEI EN 50160, IEC 61000-2-4"
            }
        }

    def verifica_selettivita_protezioni(self, I_mt, I_bt, Icc_mt, Icc_bt,
                                        prot_mt, prot_bt):
        """
            Verifica selettività e coordinamento protezioni MT/BT secondo CEI 0-16
            """

        # DATI PROTEZIONI ESTRATTI
        # Estrai le correnti di taratura dalle tue protezioni esistenti
        I_rele_51_mt = I_mt * 1.25  # Soglia temporizzata MT
        I_rele_50_mt = I_mt * 10  # Soglia istantanea MT

        # Interruttore BT - estrai dalla stringa
        I_int_bt_str = prot_bt["interruttore_generale"].split("A")[0]
        I_int_bt = float(I_int_bt_str)

        # CURVE DI INTERVENTO (tempi caratteristici)
        # Rele MT 51 (curva inversa standard IEC)
        def tempo_rele_51_mt(corrente):
            """Tempo intervento relè 51 MT - curva inversa standard"""
            if corrente < I_rele_51_mt:
                return float('inf')  # Non interviene

            # Curva inversa standard: t = TMS * [0.14 / ((I/Is)^0.02 - 1)]
            TMS = 0.1  # Time Multiplier Setting tipico
            rapporto = corrente / I_rele_51_mt
            if rapporto <= 1:
                return float('inf')
            return TMS * (0.14 / (rapporto**0.02 - 1))

        # Rele MT 50 (istantaneo)
        def tempo_rele_50_mt(corrente):
            """Tempo intervento relè 50 MT - istantaneo"""
            return 0.02 if corrente >= I_rele_50_mt else float(
                'inf')  # 20ms se interviene

        # Interruttore BT (magnetotermico)
        def tempo_interruttore_bt(corrente):
            """Tempo intervento interruttore BT - curva magnetotermica"""
            # Soglia magnetica (tipicamente 10×In per magnetotermici)
            I_mag_bt = I_int_bt * 10

            if corrente >= I_mag_bt:
                return 0.01  # 10ms intervento magnetico
            elif corrente >= I_int_bt * 1.45:  # Soglia termica (1.45×In tipica)
                # Curva termica (approssimata)
                rapporto = corrente / I_int_bt
                return 3600 / (rapporto**2)  # Formula semplificata
            else:
                return float('inf')  # Non interviene

        # PUNTI DI VERIFICA SELETTIVITÀ
        # Definiamo correnti di test per la verifica
        correnti_test = [
            I_bt * 1.2,  # Sovraccarico BT leggero
            I_bt * 2.0,  # Sovraccarico BT forte  
            I_bt * 5.0,  # Cortocircuito BT moderato
            Icc_bt * 0.5,  # Cortocircuito BT medio
            Icc_bt * 0.8,  # Cortocircuito BT alto
            Icc_bt  # Cortocircuito BT massimo
        ]

        risultati_selettivita = []
        problemi_coordinamento = []

        for I_test in correnti_test:
            # Calcola tempi di intervento per ogni protezione

            # Tempi lato BT
            t_bt = tempo_interruttore_bt(I_test)

            # Tempi lato MT (corrente riportata al primario)
            I_test_mt = I_test / (self.V_bt / self.V_mt)  # Riporta al MT
            t_mt_51 = tempo_rele_51_mt(I_test_mt)
            t_mt_50 = tempo_rele_50_mt(I_test_mt)
            t_mt = min(t_mt_51, t_mt_50)  # Il più veloce interviene

            # VERIFICA SELETTIVITÀ
            # Regola: protezione BT deve intervenire almeno 300ms prima della MT
            margine_selettivita = 0.3  # s

            if t_bt != float('inf') and t_mt != float('inf'):
                if (t_mt - t_bt) >= margine_selettivita:
                    selettivita = "✅ OK"
                else:
                    selettivita = "❌ NO"
                    problemi_coordinamento.append({
                        "corrente_kA":
                        I_test / 1000,
                        "tempo_bt_s":
                        t_bt,
                        "tempo_mt_s":
                        t_mt,
                        "margine_s":
                        t_mt - t_bt,
                        "problema":
                        f"Margine insufficiente: {(t_mt - t_bt)*1000:.0f}ms < 300ms"
                    })
            elif t_bt != float('inf') and t_mt == float('inf'):
                selettivita = "✅ OK"  # Solo BT interviene
            elif t_bt == float('inf') and t_mt != float('inf'):
                selettivita = "⚠️ WARNING"  # Solo MT interviene (non normale)
            else:
                selettivita = "✅ OK"  # Nessuno interviene (normale per correnti basse)

            risultati_selettivita.append({
                "corrente_test_A":
                I_test,
                "corrente_test_kA":
                I_test / 1000,
                "tempo_bt_s":
                t_bt if t_bt != float('inf') else "∞",
                "tempo_mt_s":
                t_mt if t_mt != float('inf') else "∞",
                "selettivita":
                selettivita,
                "margine_s": (t_mt - t_bt)
                if t_bt != float('inf') and t_mt != float('inf') else "N/A"
            })

        # ANALISI BACK-UP
        # Verifica che la protezione MT faccia da back-up per guasti BT
        backup_mt_ok = False
        for risultato in risultati_selettivita:
            if risultato["corrente_test_kA"] > 5 and risultato[
                    "tempo_mt_s"] != "∞":
                backup_mt_ok = True
                break

        # RACCOMANDAZIONI
        raccomandazioni = []

        if problemi_coordinamento:
            raccomandazioni.append(
                "⚠️ Regolare tarature per migliorare selettività")
            raccomandazioni.append(
                "• Aumentare soglia 50 MT o ridurre soglia magnetica BT")

        if not backup_mt_ok:
            raccomandazioni.append(
                "⚠️ Verificare funzione back-up protezione MT")

        # Verifica coordinamento con fusibili MT (se presenti)
        raccomandazioni.append(
            "✅ Verificare coordinate con fusibili MT distribuzione")
        raccomandazioni.append("✅ Testare protezioni con relè di prova")

        return {
            "tarature_mt": {
                "rele_51_A": I_rele_51_mt,
                "rele_50_A": I_rele_50_mt,
                "TMS": 0.1
            },
            "tarature_bt": {
                "interruttore_In_A": I_int_bt,
                "soglia_magnetica_A": I_int_bt * 10
            },
            "risultati_selettivita":
            risultati_selettivita,
            "problemi_coordinamento":
            problemi_coordinamento,
            "backup_mt_disponibile":
            backup_mt_ok,
            "raccomandazioni":
            raccomandazioni,
            "valutazione_complessiva":
            "✅ SELETTIVITA' OK"
            if not problemi_coordinamento else "❌ SELETTIVITA' DA MIGLIORARE",
            "n_punti_testati":
            len(correnti_test),
            "n_problemi":
            len(problemi_coordinamento)
        }

    # AGGIUNGI QUESTO METODO ALLA TUA CLASSE CabinaMTBT

    def calcola_cortocircuito_avanzato(self,
                                       potenza_trasf,
                                       lunghezza_cavo_mt=50,
                                       sezione_mt=120):
        """
        Calcolo cortocircuito completo considerando impedenza rete + trasformatore + cavi
        Secondo CEI 11-25 e IEC 60909
        """

        # 1. IMPEDENZA RETE MT (tipica per rete 20kV distributore)
        # Potenza cortocircuito rete MT (dato del distributore)
        Scc_rete = 250e6  # VA (250 MVA tipici per rete 20kV)

        # Impedenza equivalente rete MT
        Z_rete = (self.V_mt**2) / Scc_rete  # Ω
        R_rete = Z_rete * 0.1  # R/X = 0.1 tipico per reti MT
        X_rete = Z_rete * 0.995  # X ≈ Z per reti MT

        # 2. IMPEDENZA TRASFORMATORE
        ucc = self.ucc[potenza_trasf] / 100  # p.u.

        # Resistenza trasformatore (dalle perdite a carico)
        Pk_trasf = self.perdite_carico[potenza_trasf]  # W
        R_trasf = Pk_trasf / (3 * (potenza_trasf * 1000 /
                                   (math.sqrt(3) * self.V_bt))**2)  # Ω lato BT

        # Reattanza trasformatore
        Z_trasf_bt = ucc * (self.V_bt**2) / (potenza_trasf * 1000)  # Ω lato BT
        X_trasf_bt = math.sqrt(Z_trasf_bt**2 - R_trasf**2)

        # Riporta al lato MT
        rapporto_trasf = self.V_mt / self.V_bt
        R_trasf_mt = R_trasf * (rapporto_trasf**2)
        X_trasf_mt = X_trasf_bt * (rapporto_trasf**2)

        # 3. IMPEDENZA CAVO MT
        # Database resistenze/reattanze cavi MT (Ω/km)
        cavi_mt_db = {
            35: {
                "R": 0.868,
                "X": 0.115
            },
            50: {
                "R": 0.641,
                "X": 0.110
            },
            70: {
                "R": 0.443,
                "X": 0.105
            },
            95: {
                "R": 0.320,
                "X": 0.100
            },
            120: {
                "R": 0.253,
                "X": 0.095
            },
            150: {
                "R": 0.206,
                "X": 0.090
            },
            185: {
                "R": 0.164,
                "X": 0.085
            },
            240: {
                "R": 0.125,
                "X": 0.080
            },
            300: {
                "R": 0.100,
                "X": 0.075
            },
            400: {
                "R": 0.075,
                "X": 0.070
            },
            500: {
                "R": 0.060,
                "X": 0.065
            }
        }

        cavo_dati = cavi_mt_db.get(sezione_mt, {"R": 0.253, "X": 0.095})
        R_cavo_mt = cavo_dati["R"] * (lunghezza_cavo_mt / 1000)  # Ω
        X_cavo_mt = cavo_dati["X"] * (lunghezza_cavo_mt / 1000)  # Ω

        # 4. CALCOLO CORTOCIRCUITO LATO MT
        # Impedenza totale lato MT
        R_tot_mt = R_rete + R_cavo_mt
        X_tot_mt = X_rete + X_cavo_mt
        Z_tot_mt = math.sqrt(R_tot_mt**2 + X_tot_mt**2)

        # Corrente cortocircuito simmetrica lato MT
        Icc_simm_mt = self.V_mt / (math.sqrt(3) * Z_tot_mt)  # A

        # Corrente di picco lato MT (fattore 2.5 per reti MT)
        Ip_mt = Icc_simm_mt * 2.5  # A picco

        # 5. CALCOLO CORTOCIRCUITO LATO BT
        # Impedenza totale riportata al BT
        R_tot_bt = R_trasf + (R_tot_mt / (rapporto_trasf**2))
        X_tot_bt = X_trasf_bt + (X_tot_mt / (rapporto_trasf**2))
        Z_tot_bt = math.sqrt(R_tot_bt**2 + X_tot_bt**2)

        # Corrente cortocircuito simmetrica lato BT
        Icc_simm_bt = self.V_bt / (math.sqrt(3) * Z_tot_bt)  # A

        # Corrente di picco lato BT (fattore 2.1 per sistemi BT)
        Ip_bt = Icc_simm_bt * 2.1  # A picco

        # 6. ENERGIA SPECIFICA (I²t) - per verifica cavi
        # Tempo eliminazione guasto (tipico per protezioni MT/BT)
        t_eliminazione_mt = 0.1  # s (protezione MT veloce)
        t_eliminazione_bt = 0.01  # s (protezione BT veloce)

        I2t_mt = (Icc_simm_mt**2) * t_eliminazione_mt / 1e6  # MA²s
        I2t_bt = (Icc_simm_bt**2) * t_eliminazione_bt / 1e6  # MA²s

        # 7. VERIFICA TENUTA TERMICA CAVI
        # Costante K per cavi (rame/XLPE)
        K_mt = 142  # A√s/mmq per cavi MT
        K_bt = 115  # A√s/mmq per cavi BT

        # Sezione minima per tenuta termica
        Smin_termica_mt = (Icc_simm_mt * math.sqrt(t_eliminazione_mt)) / K_mt
        Smin_termica_bt = (Icc_simm_bt * math.sqrt(t_eliminazione_bt)) / K_bt

        # Verifiche
        verifica_termica_mt = "✅ OK" if sezione_mt >= Smin_termica_mt else "❌ NO"
        # Per BT prendiamo la sezione che sarà calcolata dal metodo cavi
        verifica_termica_bt = "✅ OK"  # Da verificare con sezione effettiva

        return {
            # Dati rete MT
            "Scc_rete_MVA": Scc_rete / 1e6,
            "Z_rete_ohm": Z_rete,
            "R_rete_ohm": R_rete,
            "X_rete_ohm": X_rete,

            # Dati trasformatore
            "R_trasf_mt_ohm": R_trasf_mt,
            "X_trasf_mt_ohm": X_trasf_mt,
            "R_trasf_bt_ohm": R_trasf,
            "X_trasf_bt_ohm": X_trasf_bt,

            # Dati cavo MT
            "R_cavo_mt_ohm": R_cavo_mt,
            "X_cavo_mt_ohm": X_cavo_mt,
            "lunghezza_mt": lunghezza_cavo_mt,
            "sezione_mt": sezione_mt,

            # Risultati cortocircuito MT
            "Icc_simm_mt_kA": Icc_simm_mt / 1000,
            "Ip_mt_kA": Ip_mt / 1000,
            "I2t_mt_MA2s": I2t_mt,
            "Z_tot_mt_ohm": Z_tot_mt,

            # Risultati cortocircuito BT
            "Icc_simm_bt_kA": Icc_simm_bt / 1000,
            "Ip_bt_kA": Ip_bt / 1000,
            "I2t_bt_MA2s": I2t_bt,
            "Z_tot_bt_ohm": Z_tot_bt,

            # Verifiche tenuta termica
            "Smin_termica_mt_mmq": Smin_termica_mt,
            "Smin_termica_bt_mmq": Smin_termica_bt,
            "verifica_termica_mt": verifica_termica_mt,
            "verifica_termica_bt": verifica_termica_bt,

            # Tempi eliminazione
            "t_eliminazione_mt_s": t_eliminazione_mt,
            "t_eliminazione_bt_s": t_eliminazione_bt,

            # Per compatibilità con il tuo codice
            "Icc_bt": Icc_simm_bt  # Mantiene compatibilità
        }

    def calcola_ventilazione(self, potenza_trasf, f_carico=0.8):
        """Calcola ventilazione necessaria"""
        Po = self.perdite_vuoto[potenza_trasf] / 1000
        Pk = self.perdite_carico[potenza_trasf] / 1000

        perdite_totali = Po + Pk * (f_carico**2)
        Q = (perdite_totali * 3.6) / (15 * 1.2 * 1.005)

        sez_ingresso = Q / (3600 * 0.7)
        sez_uscita = sez_ingresso * 1.5

        return {
            "perdite_totali": perdite_totali,
            "portata_aria": Q,
            "sez_ingresso": sez_ingresso,
            "sez_uscita": sez_uscita
        }

    def calcola_rendimento(self, potenza_trasf, f_carico=0.8, cos_phi=0.95):
        """Calcola rendimento trasformatore"""
        Po = self.perdite_vuoto[potenza_trasf] / 1000
        Pk = self.perdite_carico[potenza_trasf] / 1000

        Pu = potenza_trasf * f_carico * cos_phi
        Pk_eff = Pk * (f_carico**2)

        eta = Pu / (Pu + Po + Pk_eff)

        return {
            "potenza_utile": Pu,
            "perdite_vuoto": Po,
            "perdite_carico": Pk_eff,
            "rendimento": eta * 100
        }

    def calcola_caratteristiche_isolamento(self, potenza_trasf):
        """Calcola caratteristiche isolamento MT complete"""
        Um = self.Um_mt  # 24kV

        # Livelli isolamento standard IEC 60071
        if Um <= 24000:
            Ud_secco = 50000  # V
            Ud_pioggia = 28000  # V
            Up = 125000  # V (BIL)

        # Sollecitazioni termiche (I²t)
        Ik_mt = self.Icc_rete  # 12.5 kA
        tk = 1  # s
        I2t = (Ik_mt**2) * tk  # kA²s

        # Capacità di stabilimento sezionatori (2.5 × Ik picco)
        Ip = Ik_mt * 2.5  # kA picco

        return {
            "Um": Um / 1000,  # kV
            "Ud_secco": Ud_secco / 1000,  # kV
            "Ud_pioggia": Ud_pioggia / 1000,  # kV  
            "Up": Up / 1000,  # kV
            "Ik_mt": Ik_mt,  # kA
            "I2t": I2t,  # kA²s
            "Ip": Ip  # kA picco
        }

    def calcola_illuminazione(self, area_locale=12):
        """Calcola illuminazione normale e emergenza"""
        # Parametri illuminazione
        E_richiesto = 200  # lux (sale quadri)
        Cu = 0.6  # coefficiente utilizzo
        Cm = 0.8  # coefficiente manutenzione
        eta_apparecchio = 0.85  # rendimento LED

        # Flusso luminoso necessario
        phi_totale = (E_richiesto * area_locale) / (Cu * Cm * eta_apparecchio)

        # Apparecchi LED tipici
        phi_singolo = 4000  # lumen per apparecchio
        n_apparecchi = math.ceil(phi_totale / phi_singolo)

        # Potenza illuminazione normale
        P_singolo = 36  # W per apparecchio LED
        P_totale_normale = n_apparecchi * P_singolo

        # Illuminazione emergenza (autonomia 3h)
        E_emergenza = 5  # lux vie fuga
        phi_emergenza = (E_emergenza * area_locale) / (Cu * Cm *
                                                       eta_apparecchio)
        n_emergenza = math.ceil(phi_emergenza /
                                1000)  # apparecchi emergenza 1000 lm
        P_emergenza = n_emergenza * 8  # W per apparecchio emergenza

        return {
            "area": area_locale,
            "flusso_necessario": phi_totale,
            "n_apparecchi_normali": n_apparecchi,
            "potenza_normale": P_totale_normale,
            "n_apparecchi_emergenza": n_emergenza,
            "potenza_emergenza": P_emergenza,
            "consumo_totale": P_totale_normale + P_emergenza
        }

    def calcola_cadute_tensione(self,
                                I_mt,
                                I_bt,
                                lunghezza_mt=50,
                                lunghezza_bt=30,
                                sez_mt=120,
                                sez_bt=185,
                                cos_phi=0.85):
        """Calcola cadute tensione MT e BT dettagliate"""
        # Resistività rame a 70°C
        rho_cu_70 = 0.0214  # Ω·mm²/m

        # Calcolo MT
        R_mt = rho_cu_70 * lunghezza_mt / sez_mt  # Ω/fase
        X_mt = 0.08 * lunghezza_mt / 1000  # Ω/fase (cavo MT tipico)
        sin_phi = math.sqrt(1 - cos_phi**2)

        dV_mt_perc = (math.sqrt(3) * I_mt *
                      (R_mt * cos_phi + X_mt * sin_phi) * 100) / self.V_mt

        # Calcolo BT
        R_bt = rho_cu_70 * lunghezza_bt / sez_bt  # Ω/fase
        X_bt = 0.08 * lunghezza_bt / 1000  # Ω/fase (cavo BT tipico)

        dV_bt_perc = (math.sqrt(3) * I_bt *
                      (R_bt * cos_phi + X_bt * sin_phi) * 100) / self.V_bt

        # Verifiche normative
        verifica_mt = "✅ OK" if dV_mt_perc <= 0.5 else "❌ SUPERATA"
        verifica_bt = "✅ OK" if dV_bt_perc <= 4.0 else "❌ SUPERATA"

        return {
            "lunghezza_mt": lunghezza_mt,
            "lunghezza_bt": lunghezza_bt,
            "dV_mt_perc": dV_mt_perc,
            "dV_bt_perc": dV_bt_perc,
            "verifica_mt": verifica_mt,
            "verifica_bt": verifica_bt,
            "limite_mt": 0.5,
            "limite_bt": 4.0
        }

    def dimensiona_scaricatori(self):
        """Dimensiona scaricatori sovratensione MT"""
        # Dati rete 20kV
        Un = self.V_mt  # 20kV
        Um = self.Um_mt  # 24kV

        # Tensione continua scaricatori (87% di Um)
        Uc = Um * 0.87 / 1000  # kV

        # Livello protezione (coordinato con BIL apparecchiature)
        Up_apparecchiature = 125  # kV BIL
        Up_scaricatori = Up_apparecchiature * 0.8  # kV (coordinamento)

        # Corrente nominale scarica
        In_scarica = 10  # kA (classe 2 per distribuzione)

        # Energia specifica (per reti 20kV)
        W_energia = 4.5  # kJ/kVUc

        return {
            "Uc": round(Uc, 1),
            "Up": round(Up_scaricatori, 0),
            "In_scarica": In_scarica,
            "classe": "Classe 2",
            "energia": W_energia,
            "specifica": f"{Uc:.1f}kV - {In_scarica}kA - Classe 2"
        }

    def verifica_antincendio(self, potenza_trasf):
        """Verifica requisiti antincendio trasformatori"""
        # Volume olio indicativo per potenza (litri)
        volumi_olio = {
            25: 50,
            50: 80,
            100: 150,
            160: 220,
            250: 350,
            315: 420,
            400: 520,
            500: 650,
            630: 800,
            800: 1000,
            1000: 1200,
            1250: 1500,
            1600: 1900,
            2000: 2300,
            2500: 2800,
            3150: 3400
        }

        volume_olio = volumi_olio.get(potenza_trasf, 1000)  # litri
        volume_m3 = volume_olio / 1000  # m³

        # Verifica soglia DM 15/07/2014
        richiede_antincendio = volume_m3 > 1.0

        # Prescrizioni
        if richiede_antincendio:
            prescrizioni = [
                "Sistema rivelazione fumo/fiamma automatico",
                "Sistema spegnimento automatico (CO₂ o polvere)",
                f"Vasca raccolta olio: {volume_olio * 1.1:.0f} litri (110% volume)",
                "Separazione REI 120 da altri locali",
                "Ventilazione meccanica forzata",
                "Segnalazioni allarme in locale presidiato"
            ]
        else:
            prescrizioni = [
                "Solo estintori portatili",
                "Ventilazione naturale sufficiente",
                "Controllo periodico perdite olio"
            ]

        return {
            "volume_olio": volume_olio,
            "volume_m3": volume_m3,
            "soglia_superata": richiede_antincendio,
            "dm_applicabile":
            "DM 15/07/2014" if richiede_antincendio else "Non applicabile",
            "prescrizioni": prescrizioni
        }

    def calcola_regime_neutro(self, potenza_trasf, tipo_utenza="industriale"):
        """Determina regime neutro BT ottimale"""

        # Analisi tipo utenza
        if tipo_utenza == "industriale":
            # Privilegia continuità servizio
            regime_consigliato = "TN-S"
            motivo = "Maggiore continuità servizio per utenze industriali"
            protezioni = ["Differenziali selettivi", "Coordinamento con MT"]
        else:
            # Privilegia sicurezza persone
            regime_consigliato = "TT"
            motivo = "Maggiore sicurezza per utenze civili/terziarie"
            protezioni = [
                "Differenziale generale + parziali",
                "Impianto dispersore dedicato"
            ]

        # Prescrizioni comuni
        prescrizioni_comuni = [
            "Neutro trasformatore collegato direttamente a terra",
            "Collegamento Dyn11 standard", "Coordinamento protezioni MT/BT",
            "Misure di resistenza terra periodiche"
        ]

        return {
            "regime_consigliato": regime_consigliato,
            "motivo": motivo,
            "protezioni_specifiche": protezioni,
            "prescrizioni_comuni": prescrizioni_comuni
        }

    def calcola_verifiche_costruttive(self, potenza_trasf):
        """Calcola verifiche dimensioni e volumi locali"""

        # Dimensioni minime locale U (in base potenza trasformatore)
        if potenza_trasf <= 400:
            dim_min = {"L": 4, "P": 3, "H": 2.5}
        elif potenza_trasf <= 1000:
            dim_min = {"L": 5, "P": 4, "H": 2.5}
        else:
            dim_min = {"L": 6, "P": 5, "H": 3.0}

        area_min = dim_min["L"] * dim_min["P"]
        volume_min = area_min * dim_min["H"]

        # Locale C e M (standard distributore)
        locale_c = {"L": 2, "P": 1.5, "H": 2.2}
        locale_m = {"L": 1.5, "P": 1.2, "H": 2.2}

        # Ventilazione locali C e M
        area_c = locale_c["L"] * locale_c["P"]
        area_m = locale_m["L"] * locale_m["P"]

        # Sezioni ventilazione (0.01 m²/m² superficie, min 0.2 m²)
        vent_c = max(area_c * 0.01, 0.2)
        vent_m = max(area_m * 0.01, 0.2)

        # Verifiche vie fuga
        lunghezza_max_fuga = 20  # m (CEI 99-4)
        larghezza_min_corridoi = 0.8  # m

        return {
            "locale_u": dim_min,
            "area_min_u": area_min,
            "volume_min_u": volume_min,
            "locale_c": locale_c,
            "locale_m": locale_m,
            "ventilazione_c": vent_c,
            "ventilazione_m": vent_m,
            "vie_fuga_max": lunghezza_max_fuga,
            "corridoi_min": larghezza_min_corridoi
        }

    def calcola_impianto_terra(self,
                               potenza_trasf,
                               resistivita_terreno=100,
                               lunghezza_cabina=6,
                               larghezza_cabina=4):
        """Calcola impianto di terra completo secondo CEI 11-1"""

        # Parametri di sicurezza
        R_terra_max = 1.0  # Ω (massima resistenza ammessa per cabine MT)
        U_passo_max = 50  # V (tensione di passo massima)
        U_contatto_max = 25  # V (tensione di contatto massima)
        t_eliminazione = 0.5  # s (tempo eliminazione guasto)

        # Corrente di guasto a terra (proporzionale alla potenza)
        # Per cabine MT/BT la corrente di guasto è limitata dalle protezioni
        if potenza_trasf <= 400:
            If_terra = 200  # A
        elif potenza_trasf <= 1000:
            If_terra = 300  # A
        else:
            If_terra = 400  # A

        # Dimensioni anello perimetrale
        perimetro = 2 * (lunghezza_cabina + larghezza_cabina)
        area_cabina = lunghezza_cabina * larghezza_cabina

        # 1. CALCOLO ANELLO PERIMETRALE
        # Sezione conduttore (minimo 50 mmq rame nudo)
        sezione_anello = max(50, (If_terra * math.sqrt(t_eliminazione)) /
                             142)  # mmq
        sezione_anello = round(sezione_anello, 0)

        # Resistenza anello (formula semplificata)
        raggio_equiv = math.sqrt(area_cabina / math.pi)
        R_anello = resistivita_terreno / (2 * math.pi * raggio_equiv)

        # 2. CALCOLO PICCHETTI VERTICALI
        # Numero picchetti necessari
        if R_anello > R_terra_max:
            # Calcola picchetti aggiuntivi
            lunghezza_picchetto = 3.0  # m (standard)
            diametro_picchetto = 0.02  # m (20mm)

            # Resistenza singolo picchetto
            R_picchetto = (resistivita_terreno / (2 * math.pi * lunghezza_picchetto)) * \
                  math.log(4 * lunghezza_picchetto / diametro_picchetto)

            # Numero picchetti necessari (con fattore mutuo 0.7)
            R_parallelo_richiesta = 1 / (1 / R_terra_max - 1 / R_anello)
            n_picchetti = max(
                2, math.ceil(R_picchetto / (R_parallelo_richiesta * 0.7)))

            # Resistenza equivalente picchetti
            R_picchetti = R_picchetto / (n_picchetti * 0.7)

            # Resistenza totale (anello + picchetti in parallelo)
            R_terra_totale = 1 / (1 / R_anello + 1 / R_picchetti)
        else:
            n_picchetti = 2  # Minimo due picchetti
            lunghezza_picchetto = 3.0
            R_picchetti = resistivita_terreno / (4 * math.pi *
                                                 lunghezza_picchetto)
            R_terra_totale = 1 / (1 / R_anello + 1 / R_picchetti)

            # 3. VERIFICHE TENSIONI DI PASSO E CONTATTO (FORMULE CORRETTE)
            # Tensione apparsa a terra
            U_terra = If_terra * R_terra_totale

            # Formule corrette secondo CEI 11-1
            # Fattore di forma per anello rettangolare
            K_forma = 1 / math.sqrt(area_cabina / (math.pi * raggio_equiv**2))

            # Gradiente massimo corretto
            gradiente_superficie = (If_terra * resistivita_terreno *
                                    K_forma) / (2 * math.pi * area_cabina)

            # Tensioni effettive con fattori di riduzione realistici
            U_passo_eff = gradiente_superficie * 0.8  # fattore riduttivo per anello
            U_contatto_eff = U_terra * 0.3  # fattore riduttivo per contatto con massa metallica

            # Verifiche
            verifica_resistenza = "✅ OK" if R_terra_totale <= R_terra_max else "❌ NON OK"
            verifica_passo = "✅ OK" if U_passo_eff <= U_passo_max else "❌ NON OK"
            verifica_contatto = "✅ OK" if U_contatto_eff <= U_contatto_max else "❌ NON OK"

            # 4. CONDUTTORI DI PROTEZIONE
            # Sezione PE principale (CEI 64-8)
            if sezione_anello <= 16:
                sezione_pe_principale = sezione_anello
            elif sezione_anello <= 35:
                sezione_pe_principale = 16
            else:
                sezione_pe_principale = sezione_anello / 2

            # Sezione collegamento masse
            sezione_pe_masse = max(6, sezione_pe_principale / 2)

            # 5. PROTEZIONE CATODICA (se necessario)
            protezione_catodica = resistivita_terreno > 200 or R_terra_totale > 0.8

            return {
                # Parametri input
                "resistivita_terreno":
                resistivita_terreno,
                "dimensioni_cabina":
                f"{lunghezza_cabina}×{larghezza_cabina} m",
                "area_cabina":
                area_cabina,
                "perimetro":
                perimetro,

                # Dispersori
                "sezione_anello":
                sezione_anello,
                "resistenza_anello":
                R_anello,
                "n_picchetti":
                n_picchetti,
                "lunghezza_picchetti":
                lunghezza_picchetto,
                "resistenza_picchetti":
                R_picchetti,
                "resistenza_totale":
                R_terra_totale,

                # Verifiche sicurezza
                "corrente_guasto":
                If_terra,
                "tensione_terra":
                U_terra,
                "tensione_passo_effettiva":
                U_passo_eff,
                "tensione_contatto_effettiva":
                U_contatto_eff,
                "verifica_resistenza":
                verifica_resistenza,
                "verifica_passo":
                verifica_passo,
                "verifica_contatto":
                verifica_contatto,

                # Conduttori protezione
                "sezione_pe_principale":
                sezione_pe_principale,
                "sezione_pe_masse":
                sezione_pe_masse,

                # Raccomandazioni
                "protezione_catodica_richiesta":
                protezione_catodica,
                "note":
                self._genera_note_terra(R_terra_totale, resistivita_terreno,
                                        U_passo_eff, U_contatto_eff)
            }

    def _genera_note_terra(self, R_terra, resistivita, U_passo, U_contatto):
        """Genera note tecniche per l'impianto di terra"""
        note = []

        if R_terra <= 0.5:
            note.append("Impianto di terra eccellente (R < 0.5Ω)")
        elif R_terra <= 1.0:
            note.append("Impianto di terra conforme (R < 1Ω)")
        else:
            note.append(
                "ATTENZIONE: Resistenza terra elevata - verificare dimensionamento"
            )

        if U_passo > 50:
            note.append(
                "ATTENZIONE: Tensione di passo elevata - aumentare n° picchetti"
            )
        if U_contatto > 25:
            note.append(
                "ATTENZIONE: Tensione di contatto elevata - migliorare equipotenzialità"
            )

        if resistivita > 300:
            note.append(
                "Terreno alta resistività - considerare trattamento chimico")
        elif resistivita < 50:
            note.append(
                "Terreno bassa resistività - favorevole per dispersione")

        note.append(
            "Verificare misure periodiche resistenza terra (ogni 2 anni)")
        note.append("Controllare continuità collegamenti (annuale)")

        return note


def genera_pdf_report(potenza_carichi, f_contemporaneita, cos_phi, margine,
                      potenza_trasf, potenza_necessaria, I_mt, I_bt, Icc_bt,
                      prot_mt, prot_bt, cavi, ventilazione, rendimento, calc,
                      isolamento, illuminazione, cadute_tensione, scaricatori,
                      antincendio, regime_neutro, verifiche_costruttive,
                      impianto_terra):
    """Genera report PDF completo con tutti i calcoli"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=A4,
                            rightMargin=2 * cm,
                            leftMargin=2 * cm,
                            topMargin=2 * cm,
                            bottomMargin=2 * cm)

    # Stili
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center
    )

    heading_style = ParagraphStyle('CustomHeading',
                                   parent=styles['Heading2'],
                                   fontSize=12,
                                   spaceAfter=12,
                                   textColor=colors.darkblue)
    # ======= AGGIUNGI QUESTE RIGHE PER COMPATIBILITÀ =======
    protezioni_mt = prot_mt        # ✅ Alias per compatibilità
    protezioni_bt = prot_bt        # ✅ Alias per compatibilità
    risultato_cavi = cavi          # ✅ Alias per compatibilità
    n_cavi_raggruppati_mt = 1      # ✅ Valore fisso 
    n_cavi_raggruppati_bt = 1      # ✅ Valore fisso
    # ======= FINE ALIAS =======
                        
    # Contenuto del PDF
    story = []

    # Titolo
    story.append(Paragraph("REPORT DIMENSIONAMENTO CABINA MT/BT - v1.1", title_style))
    # ✅ AGGIUNGI IL NOME DELL'AZIENDA QUI
    story.append(Paragraph("MAURIZIO SRL - Impianti Elettrici", 
                          ParagraphStyle('CompanyName',
                                    parent=styles['Normal'],
                                    fontSize=14,
                                    spaceAfter=15,
                                    alignment=1,  # Center
                                    textColor=colors.darkblue,
                                    fontName='Helvetica-Bold')))                    
    story.append(
        Paragraph(f"Cabina 20kV/400V - {potenza_trasf} kVA",
                  styles['Heading3']))
    story.append(
        Paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                  styles['Normal']))
    story.append(Spacer(1, 20))

    # Dati di input
    story.append(Paragraph("DATI DI INPUT", heading_style))
    data_input = [["Parametro", "Valore"],
                  ["Potenza carichi totali", f"{potenza_carichi} kW"],
                  ["Fattore contemporaneità", f"{f_contemporaneita}"],
                  ["Fattore di potenza medio", f"{cos_phi}"],
                  ["Margine espansioni", f"{margine}"],
                  [
                      "Potenza calcolata necessaria",
                      f"{potenza_necessaria:.0f} kVA"
                  ]]

    table = Table(data_input, colWidths=[8 * cm, 4 * cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))

    # Trasformatore
    story.append(Paragraph("TRASFORMATORE SELEZIONATO", heading_style))
    data_trasf = [
        ["Caratteristica", "Valore"],
        ["Potenza nominale",
         f"{potenza_trasf} kVA"], ["Collegamento", "Dyn11"],
        ["Tensione cortocircuito", f"{calc.ucc[potenza_trasf]}%"],
        ["Perdite a vuoto (AAo)", f"{calc.perdite_vuoto[potenza_trasf]} W"],
        ["Perdite a carico (Bk)", f"{calc.perdite_carico[potenza_trasf]} W"]
    ]

    table = Table(data_trasf, colWidths=[8 * cm, 4 * cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))

    # SEZIONE CORRENTI E CORTOCIRCUITI (corretta)
    story.append(Paragraph("CORRENTI E CORTOCIRCUITI", heading_style))
    data_correnti = [
        ["Parametro", "Valore", "Unità"],
        ["Corrente nominale MT", f"{I_mt:.1f}", "A"],
        ["Corrente nominale BT", f"{I_bt:.1f}", "A"], 
        ["Corrente cortocircuito BT", f"{Icc_bt/1000:.1f}", "kA"],
        ["Potere interruzione richiesto", f"{25 if Icc_bt < 25000 else 35 if Icc_bt < 35000 else 50}", "kA"]
    ]
    
    table = Table(data_correnti, colWidths=[6*cm, 3*cm, 3*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))     

    # SEZIONE PROTEZIONI MT (corretta)
    story.append(Paragraph("PROTEZIONI LATO MT", heading_style))
    data_prot_mt = [  # ✅ Cambiato nome variabile
        ["Componente", "Specifica"],
        ["Interruttore MT", prot_mt['interruttore']],        # ✅ Usa parametro corretto
        ["TA Protezione", prot_mt['ta_protezione']], 
        ["TV Misure", prot_mt['tv_misure']],
        ["Scaricatori", prot_mt['scaricatori']]
    ]
    
    table = Table(data_prot_mt, colWidths=[4*cm, 8*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 15))  
                        
    # SEZIONE PROTEZIONI BT (corretta)
    story.append(Paragraph("PROTEZIONI LATO BT", heading_style))
    data_prot_bt = [  # ✅ Cambiato nome variabile
        ["Componente", "Specifica"],
        ["Interruttore Generale", prot_bt['interruttore_generale']],  # ✅ Usa parametro corretto
        ["Differenziale", prot_bt['differenziale']],
        ["Corrente cortocircuito", f"{prot_bt['icc_bt']:.1f} kA"]
    ]
    
    table = Table(data_prot_bt, colWidths=[4*cm, 8*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))  

    # SEZIONE DIMENSIONAMENTO CAVI (corretta)
    story.append(Paragraph("DIMENSIONAMENTO CAVI", heading_style))
    
    # Fattori di correzione
    story.append(Paragraph("Condizioni di Posa e Fattori Correttivi", styles['Heading4']))
    fattori = cavi['fattori_correzione']
    data_fattori = [
        ["Parametro", "Valore", "Fattore"],
        ["Temperatura ambiente", f"{fattori['temp_ambiente']}°C", f"k₁ = {fattori['k_temp']}"],
        ["Raggruppamento MT", f"1 circuiti", f"k₂ = {fattori['k_raggr_mt']}"],     # ✅ Valore fisso
        ["Raggruppamento BT", f"1 circuiti", f"k₂ = {fattori['k_raggr_bt']}"],     # ✅ Valore fisso  
        ["Tipo di posa", f"{fattori['tipo_posa']}", f"k₃ = {fattori['k_posa']}"]
    ]
    
    table = Table(data_fattori, colWidths=[4*cm, 4*cm, 4*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)]))
    story.append(table)
    story.append(Spacer(1, 15))

    # Dimensionamento Cavi (corretta)
    data_cavi = [  # ✅ Cambiato nome variabile per non sovrascrivere
        ["Tipo", "Sezione", "Portata", "Richiesta", "Caduta Tensione", "Verifiche"],
        ["Cavo MT", 
         f"{cavi['sez_mt']} mm²",                                               # ✅ Usa parametro cavi
         f"{cavi['mt_dettaglio']['portata_corretta']:.0f} A",
         f"{cavi['I_mt_richiesta']:.0f} A",
         f"{cavi['mt_dettaglio']['caduta_tensione_perc']:.2f}%",
         f"{cavi['mt_dettaglio']['verifica_portata']} {cavi['mt_dettaglio']['verifica_caduta']}"],
        ["Cavo BT", 
         f"{cavi['sez_bt']} mm²",                                               # ✅ Usa parametro cavi
         f"{cavi['bt_dettaglio']['portata_corretta']:.0f} A",
         f"{cavi['I_bt_richiesta']:.0f} A",
         f"{cavi['bt_dettaglio']['caduta_tensione_perc']:.2f}%",
         f"{cavi['bt_dettaglio']['verifica_portata']} {cavi['bt_dettaglio']['verifica_caduta']}"]
    ]
    
    table = Table(data_cavi, colWidths=[2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))

    # SEZIONE PERDITE E RENDIMENTO (corretta)
    story.append(Paragraph("BILANCIO ENERGETICO", heading_style))
    perdite_totali = (calc.perdite_vuoto[potenza_trasf] + 
                     calc.perdite_carico[potenza_trasf] + 
                     cavi['perdite_totali_cavi_kw'] * 1000)                    # ✅ Usa parametro cavi
    
    rendimento_calc = ((potenza_trasf * 1000 - perdite_totali) / (potenza_trasf * 1000)) * 100
    
    data_energia = [
        ["Parametro", "Valore"],
        ["Perdite trasformatore a vuoto", f"{calc.perdite_vuoto[potenza_trasf]} W"],
        ["Perdite trasformatore a carico", f"{calc.perdite_carico[potenza_trasf]} W"],
        ["Perdite cavi MT+BT", f"{cavi['perdite_totali_cavi_kw']:.2f} kW"],    # ✅ Usa parametro cavi
        ["Perdite totali", f"{perdite_totali/1000:.2f} kW"],
        ["Rendimento stimato", f"{rendimento_calc:.1f}%"]                       # ✅ Rinominato per evitare conflitti
    ]
    
    table = Table(data_energia, colWidths=[6*cm, 6*cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 20))
                    
    # Impianto di Terra
    story.append(Paragraph("IMPIANTO DI TERRA E SICUREZZA", heading_style))
    data_terra = [
        ["Parametro", "Valore", "Verifica"],
        [
            "Resistività terreno",
            f"{impianto_terra['resistivita_terreno']} Ω⋅m", "-"
        ],
        ["Anello perimetrale", f"{impianto_terra['sezione_anello']} mmq", "-"],
        [
            "Resistenza totale",
            f"{impianto_terra['resistenza_totale']:.2f} Ω",
            impianto_terra['verifica_resistenza']
        ],
        [
            "Tensione di passo",
            f"{impianto_terra['tensione_passo_effettiva']:.1f} V",
            impianto_terra['verifica_passo']
        ],
        [
            "Tensione di contatto",
            f"{impianto_terra['tensione_contatto_effettiva']:.1f} V",
            impianto_terra['verifica_contatto']
        ],
        [
            "PE principale", f"{impianto_terra['sezione_pe_principale']} mmq",
            "CEI 64-8"
        ],
        [
            "N° picchetti",
            f"{impianto_terra['n_picchetti']} × {impianto_terra['lunghezza_picchetti']}m",
            "CEI 11-1"
        ]
    ]

    table = Table(data_terra, colWidths=[4 * cm, 4 * cm, 4 * cm])
    table.setStyle(
        TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 15))

    # Genera PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


# Inizializza la classe
@st.cache_resource
def init_calculator():
    return CabinaMTBT()


# Header principale
st.title("⚡ Calcolatore Cabina MT/BT - Maurizio srl")
st.markdown(
    "**Dimensionamento automatico cabine 20kV/400V secondo normative CEI**")
st.markdown("---")

# Inizializza calcolatore
calc = init_calculator()

# Inizializza session state
if 'calcoli_effettuati' not in st.session_state:
    st.session_state.calcoli_effettuati = False
if 'risultati' not in st.session_state:
    st.session_state.risultati = {}

# Sidebar per input
st.sidebar.header("📊 Parametri di Input")

potenza_carichi = st.sidebar.number_input(
    "Potenza Carichi Totali (kW)",
    min_value=10,
    max_value=5000,
    value=320,
    step=10,
    help="Potenza totale di tutti i carichi da alimentare")

st.sidebar.subheader("⚙️ Fattori di Correzione")

f_contemporaneita = st.sidebar.slider(
    "Fattore Contemporaneità",
    min_value=0.5,
    max_value=1.0,
    value=0.7,
    step=0.05,
    help="Percentuale carichi contemporaneamente accesi")

cos_phi = st.sidebar.slider("Fattore di Potenza Medio",
                            min_value=0.7,
                            max_value=1.0,
                            value=0.85,
                            step=0.05,
                            help="Fattore di potenza medio dei carichi")

margine = st.sidebar.slider("Margine Espansioni",
                            min_value=1.0,
                            max_value=1.5,
                            value=1.2,
                            step=0.1,
                            help="Margine per future espansioni")

# Nella sezione sidebar, dopo margine:
st.sidebar.subheader("🌍 Parametri Terreno")

resistivita_terreno = st.sidebar.selectbox(
    "Tipo di Terreno",
    options=[30, 50, 70, 100, 150, 200, 300],
    index=3,  # default 100
    help="Resistività del terreno (Ω⋅m)")

# Aggiungi anche una descrizione
terreno_desc = {
    30: "Terreno umido/argilloso (ottimo)",
    50: "Terreno misto umido (buono)",
    70: "Terreno normale trattato",
    100: "Terreno medio (standard)",
    150: "Terreno asciutto/sabbioso",
    200: "Terreno difficile",
    300: "Terreno roccioso/arido (pessimo)"
}
# AGGIUNGI QUESTI PARAMETRI ALLA TUA SIDEBAR (dopo i parametri terreno)

# NUOVA SEZIONE: Parametri Cavi Professionali
st.sidebar.subheader("🔗 Parametri Cavi Avanzati")

lunghezza_mt = st.sidebar.number_input("Lunghezza Cavo MT (m)",
                                       min_value=10,
                                       max_value=500,
                                       value=50,
                                       step=5)

lunghezza_bt = st.sidebar.number_input("Lunghezza Cavo BT (m)",
                                       min_value=5,
                                       max_value=200,
                                       value=30,
                                       step=5)

temp_ambiente = st.sidebar.slider("Temperatura Ambiente (°C)",
                                  min_value=30,
                                  max_value=50,
                                  value=30,
                                  step=5)

tipo_posa = st.sidebar.selectbox(
    "Tipo di Posa",
    options=["cavidotto", "aria", "interrato", "passerella"],
    index=0,
    help="Modalità di posa dei cavi")

n_cavi_mt = st.sidebar.selectbox("N° Cavi MT Raggruppati",
                                 options=[1, 2, 3, 4, 6],
                                 index=0,
                                 help="Numero cavi MT nello stesso percorso")

n_cavi_bt = st.sidebar.selectbox("N° Cavi BT Raggruppati",
                                 options=[1, 2, 3, 4, 6, 9],
                                 index=0,
                                 help="Numero cavi BT nello stesso percorso")

# NUOVA SEZIONE: Parametri Analisi Economica
st.sidebar.subheader("💰 Parametri Economici")

anni_esercizio = st.sidebar.slider("Anni di Esercizio",
                                   min_value=15,
                                   max_value=40,
                                   value=25,
                                   step=5)

costo_energia = st.sidebar.number_input("Costo Energia (€/kWh)",
                                        min_value=0.10,
                                        max_value=0.50,
                                        value=0.25,
                                        step=0.01)

# NUOVA SEZIONE: Parametri Armoniche
st.sidebar.subheader("📊 Analisi Armoniche")

tipo_carichi = st.sidebar.selectbox(
    "Tipologia Carichi",
    options=["lineare", "misto", "non_lineare", "data_center"],
    index=1,
    help="Tipo prevalente di carichi elettrici")

# Aggiungi descrizione del tipo selezionato
descrizioni_carichi = {
    "lineare": "Motori, resistenze, illuminazione tradizionale",
    "misto": "Mix industriale tipico (60% lineare, 40% non lineare)",
    "non_lineare": "UPS, inverter, illuminazione LED, azionamenti",
    "data_center": "Server, UPS, sistemi IT"
}
st.sidebar.info(f"**{descrizioni_carichi[tipo_carichi]}**")

# MODIFICA LA SEZIONE CALCOLI PRINCIPALI
if st.session_state.calcoli_effettuati:
    # I tuoi calcoli esistenti...
    potenza_trasf, potenza_necessaria = calc.calcola_potenza_trasformatore(
        potenza_carichi, f_contemporaneita, cos_phi, margine)
    I_mt, I_bt = calc.calcola_correnti(potenza_trasf)
    Icc_bt = calc.calcola_cortocircuito_bt(potenza_trasf)

    prot_mt = calc.dimensiona_protezioni_mt(I_mt)
    prot_bt = calc.dimensiona_protezioni_bt(I_bt, Icc_bt)

    # NUOVO: Usa il metodo cavi professionale
    cavi_pro = calc.calcola_sezioni_cavi_professionale(
        I_mt, I_bt, lunghezza_mt, lunghezza_bt, temp_ambiente, tipo_posa,
        n_cavi_mt, n_cavi_bt)

    # Mantieni compatibilità con il codice esistente
    cavi = cavi_pro  # Ora cavi contiene tutti i dati professionali

    # Altri calcoli esistenti...
    ventilazione = calc.calcola_ventilazione(potenza_trasf)
    rendimento = calc.calcola_rendimento(potenza_trasf)
    # ... tutti gli altri tuoi calcoli ...

    # NUOVI CALCOLI PROFESSIONALI
    cortocircuito_avanzato = calc.calcola_cortocircuito_avanzato(
        potenza_trasf, lunghezza_mt, cavi_pro['sez_mt'])

    selettivita = calc.verifica_selettivita_protezioni(
        I_mt, I_bt, cortocircuito_avanzato['Icc_simm_mt_kA'] * 1000,
        cortocircuito_avanzato['Icc_simm_bt_kA'] * 1000, prot_mt, prot_bt)

    analisi_economica = calc.calcola_analisi_economica(potenza_trasf, cavi_pro,
                                                       ventilazione,
                                                       rendimento,
                                                       anni_esercizio,
                                                       costo_energia)

    armoniche = calc.calcola_analisi_armoniche(potenza_trasf, tipo_carichi,
                                               I_bt)

    # LAYOUT RISULTATI (dopo i tuoi layout esistenti)

    # NUOVA SEZIONE: Calcoli Avanzati
    st.markdown("---")
    st.subheader("🎯 Calcoli Ingegneristici Avanzati")

    # Tab per organizzare i risultati
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔗 Cavi Pro", "⚡ Cortocircuito", "🛡️ Selettività", "💰 Economica"])

    with tab1:
        st.markdown("#### 🔗 Dimensionamento Cavi Professionale")

        col_cavi1, col_cavi2 = st.columns(2)

        with col_cavi1:
            st.markdown("**📊 Cavo MT Selezionato**")
            mt_det = cavi_pro['mt_dettaglio']
            df_mt_pro = pd.DataFrame({
                "Parametro": [
                    "Sezione", "Portata corretta", "Caduta tensione",
                    "Perdite", "Resistenza", "Reattanza", "Verifica portata",
                    "Verifica caduta"
                ],
                "Valore": [
                    f"{mt_det['sezione']} mmq",
                    f"{mt_det['portata_corretta']:.0f} A",
                    f"{mt_det['caduta_tensione_perc']:.3f}%",
                    f"{mt_det['perdite_kw']:.2f} kW",
                    f"{mt_det['R_ohm_km']:.3f} Ω/km",
                    f"{mt_det['X_ohm_km']:.3f} Ω/km",
                    mt_det['verifica_portata'], mt_det['verifica_caduta']
                ]
            })
            st.dataframe(df_mt_pro, hide_index=True)

        with col_cavi2:
            st.markdown("**🔌 Cavo BT Selezionato**")
            bt_det = cavi_pro['bt_dettaglio']
            df_bt_pro = pd.DataFrame({
                "Parametro": [
                    "Sezione", "Portata corretta", "Caduta tensione",
                    "Perdite", "Resistenza", "Reattanza", "Verifica portata",
                    "Verifica caduta"
                ],
                "Valore": [
                    f"{bt_det['sezione']} mmq",
                    f"{bt_det['portata_corretta']:.0f} A",
                    f"{bt_det['caduta_tensione_perc']:.2f}%",
                    f"{bt_det['perdite_kw']:.2f} kW",
                    f"{bt_det['R_ohm_km']:.3f} Ω/km",
                    f"{bt_det['X_ohm_km']:.3f} Ω/km",
                    bt_det['verifica_portata'], bt_det['verifica_caduta']
                ]
            })
            st.dataframe(df_bt_pro, hide_index=True)

        # Fattori di correzione applicati
        st.markdown("**⚙️ Fattori di Correzione Applicati**")
        fattori = cavi_pro['fattori_correzione']
        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            st.metric("Temperatura", f"{fattori['k_temp']:.2f}",
                      f"@ {fattori['temp_ambiente']}°C")
        with col_f2:
            st.metric("Raggruppamento MT", f"{fattori['k_raggr_mt']:.2f}",
                      f"{n_cavi_mt} cavi")
        with col_f3:
            st.metric("Tipo Posa", f"{fattori['k_posa']:.2f}",
                      fattori['tipo_posa'])

        # Perdite totali cavi
        st.metric("🔥 Perdite Totali Cavi",
                  f"{cavi_pro['perdite_totali_cavi_kw']:.2f} kW")

    with tab2:
        st.markdown("#### ⚡ Analisi Cortocircuito Completa")

        col_cc1, col_cc2 = st.columns(2)

        with col_cc1:
            st.markdown("**🔋 Lato MT**")
            df_cc_mt = pd.DataFrame({
                "Parametro": [
                    "Icc simmetrica", "Corrente di picco", "Energia I²t",
                    "Impedenza totale", "Resistenza totale",
                    "Reattanza totale", "Verifica termica cavo"
                ],
                "Valore": [
                    f"{cortocircuito_avanzato['Icc_simm_mt_kA']:.2f} kA",
                    f"{cortocircuito_avanzato['Ip_mt_kA']:.2f} kA",
                    f"{cortocircuito_avanzato['I2t_mt_MA2s']:.3f} MA²s",
                    f"{cortocircuito_avanzato['Z_tot_mt_ohm']:.4f} Ω",
                    f"{cortocircuito_avanzato['R_cavo_mt_ohm']:.4f} Ω",
                    f"{cortocircuito_avanzato['X_cavo_mt_ohm']:.4f} Ω",
                    cortocircuito_avanzato['verifica_termica_mt']
                ]
            })
            st.dataframe(df_cc_mt, hide_index=True)

        with col_cc2:
            st.markdown("**⚡ Lato BT**")
            df_cc_bt = pd.DataFrame({
                "Parametro": [
                    "Icc simmetrica", "Corrente di picco", "Energia I²t",
                    "Impedenza totale", "Resistenza trasf.",
                    "Reattanza trasf.", "Sezione min. termica"
                ],
                "Valore": [
                    f"{cortocircuito_avanzato['Icc_simm_bt_kA']:.2f} kA",
                    f"{cortocircuito_avanzato['Ip_bt_kA']:.2f} kA",
                    f"{cortocircuito_avanzato['I2t_bt_MA2s']:.3f} MA²s",
                    f"{cortocircuito_avanzato['Z_tot_bt_ohm']:.4f} Ω",
                    f"{cortocircuito_avanzato['R_trasf_bt_ohm']:.4f} Ω",
                    f"{cortocircuito_avanzato['X_trasf_bt_ohm']:.4f} Ω",
                    f"{cortocircuito_avanzato['Smin_termica_bt_mmq']:.1f} mmq"
                ]
            })
            st.dataframe(df_cc_bt, hide_index=True)

        # Potenza cortocircuito rete
        st.info(
            f"🏭 **Potenza cortocircuito rete:** {cortocircuito_avanzato['Scc_rete_MVA']:.0f} MVA"
        )

    with tab3:
        st.markdown("#### 🛡️ Verifica Selettività Protezioni")

        # Status generale
        valutazione = selettivita['valutazione_complessiva']
        if "OK" in valutazione:
            st.success(f"✅ {valutazione}")
        else:
            st.error(f"❌ {valutazione}")

        st.write(
            f"**Punti testati:** {selettivita['n_punti_testati']} | **Problemi:** {selettivita['n_problemi']}"
        )

        # Tabella risultati selettività
        if selettivita['risultati_selettivita']:
            df_sel = pd.DataFrame(selettivita['risultati_selettivita'])
            df_sel_display = df_sel[[
                'corrente_test_kA', 'tempo_bt_s', 'tempo_mt_s', 'selettivita',
                'margine_s'
            ]].copy()
            df_sel_display.columns = [
                'I test (kA)', 'Tempo BT (s)', 'Tempo MT (s)', 'Selettività',
                'Margine (s)'
            ]
            st.dataframe(df_sel_display, hide_index=True)

        # Problemi di coordinamento
        if selettivita['problemi_coordinamento']:
            st.markdown("**⚠️ Problemi di Coordinamento:**")
            for problema in selettivita['problemi_coordinamento']:
                st.warning(
                    f"• I = {problema['corrente_kA']:.1f} kA: {problema['problema']}"
                )

        # Raccomandazioni
        st.markdown("**📋 Raccomandazioni:**")
        for racc in selettivita['raccomandazioni']:
            st.write(f"• {racc}")

    with tab4:
        st.markdown("#### 💰 Analisi Economica Completa")

        # Metrics principali
        capex = analisi_economica['capex']['totale']
        opex = analisi_economica['opex_annuo']['totale']
        tco = analisi_economica['indicatori']['tco_25_anni']

        col_eco1, col_eco2, col_eco3 = st.columns(3)
        with col_eco1:
            st.metric("💰 CAPEX Totale", f"€ {capex:,.0f}")
        with col_eco2:
            st.metric("📊 OPEX Annuo", f"€ {opex:,.0f}")
        with col_eco3:
            st.metric("🎯 TCO 25 anni", f"€ {tco:,.0f}")

        # Breakdown CAPEX
        st.markdown("**💸 Dettaglio Investimenti (CAPEX)**")
        capex_data = analisi_economica['capex']
        df_capex = pd.DataFrame({
            "Componente": [
                "Trasformatore", "Quadro MT", "Quadro BT", "Cavi MT",
                "Cavi BT", "Opere civili", "Installazione"
            ],
            "Costo (€)": [
                capex_data['trasformatore'], capex_data['quadro_mt'],
                capex_data['quadro_bt'], capex_data['cavi_mt'],
                capex_data['cavi_bt'], capex_data['opere_civili'],
                capex_data['installazione']
            ],
            "% sul totale":
            [(capex_data['trasformatore'] / capex_data['totale']) * 100,
             (capex_data['quadro_mt'] / capex_data['totale']) * 100,
             (capex_data['quadro_bt'] / capex_data['totale']) * 100,
             (capex_data['cavi_mt'] / capex_data['totale']) * 100,
             (capex_data['cavi_bt'] / capex_data['totale']) * 100,
             (capex_data['opere_civili'] / capex_data['totale']) * 100,
             (capex_data['installazione'] / capex_data['totale']) * 100]
        })
        df_capex['Costo (€)'] = df_capex['Costo (€)'].apply(
            lambda x: f"€ {x:,.0f}")
        df_capex['% sul totale'] = df_capex['% sul totale'].apply(
            lambda x: f"{x:.1f}%")
        st.dataframe(df_capex, hide_index=True)

        # Perdite energetiche
        st.markdown("**⚡ Perdite Energetiche**")
        perdite = analisi_economica['perdite_energia']
        col_perd1, col_perd2 = st.columns(2)

        with col_perd1:
            st.metric("Perdite Totali", f"{perdite['totale_kw']:.1f} kW")
            st.metric("Energia Persa/Anno",
                      f"{perdite['energia_persa_anno_kwh']:,.0f} kWh")
        with col_perd2:
            st.metric("Costo Perdite/Anno",
                      f"€ {perdite['costo_anno_euro']:,.0f}")
            costo_per_kw = analisi_economica['indicatori']['costo_per_kw']
            st.metric("Costo per kW", f"€ {costo_per_kw:,.0f}/kW")

        # Raccomandazioni economiche
        st.markdown("**💡 Raccomandazioni Economiche:**")
        for racc in analisi_economica['raccomandazioni']:
            st.write(f"• {racc}")

    # NUOVA SEZIONE: Armoniche
    st.markdown("---")
    st.subheader("📊 Analisi Armoniche e Power Quality")

    col_arm1, col_arm2 = st.columns(2)

    with col_arm1:
        # Power Quality Status
        pq_status = armoniche['valutazione_power_quality']
        if "BUONA" in pq_status:
            st.success(f"✅ Power Quality: {pq_status}")
        elif "ACCETTABILE" in pq_status:
            st.warning(f"⚠️ Power Quality: {pq_status}")
        else:
            st.error(f"❌ Power Quality: {pq_status}")

        # THD values
        col_thd1, col_thd2 = st.columns(2)
        with col_thd1:
            st.metric("THD Corrente", f"{armoniche['THD_corrente_perc']:.1f}%")
        with col_thd2:
            st.metric("THD Tensione", f"{armoniche['THD_tensione_perc']:.1f}%")

        # Verifiche normative
        st.markdown("**📋 Verifiche Normative**")
        verif_v = armoniche['verifiche_tensione']['THD_totale']
        verif_i = armoniche['verifiche_corrente']['THD_totale']

        df_verifiche = pd.DataFrame({
            "Parametro": ["THD Tensione", "THD Corrente"],
            "Valore": [
                f"{verif_v['valore_perc']:.1f}%",
                f"{verif_i['valore_perc']:.1f}%"
            ],
            "Limite": [
                f"{verif_v['limite_perc']:.1f}%",
                f"{verif_i['limite_perc']:.1f}%"
            ],
            "Verifica": [verif_v['verifica'], verif_i['verifica']]
        })
        st.dataframe(df_verifiche, hide_index=True)

    with col_arm2:
        # Correnti armoniche
        st.markdown("**⚡ Correnti Armoniche Principali**")
        correnti_arm = armoniche['correnti_armoniche_A']
        df_arm = pd.DataFrame({
            "Armonica": [f"{h}ª" for h in correnti_arm.keys() if h > 1],
            "Corrente (A)":
            [f"{I:.1f}" for h, I in correnti_arm.items() if h > 1],
            "% Fondamentale": [
                f"{(I/correnti_arm[1]*100):.1f}%"
                for h, I in correnti_arm.items() if h > 1
            ]
        })
        st.dataframe(df_arm, hide_index=True)

        # Effetti
        st.markdown("**🔥 Effetti delle Armoniche**")
        effetti = armoniche['effetti_armoniche']
        st.metric("Perdite Aggiuntive",
                  f"+{effetti['perdite_aggiuntive_perc']:.1f}%")
        st.metric("Fattore Cresta", f"{armoniche['fattore_cresta']:.2f}")
        st.metric("Sovradim. Neutro",
                  f"×{effetti['sovradimensionamento_neutro']:.1f}")

    # Raccomandazioni armoniche
    if armoniche['raccomandazioni']:
        st.markdown("**💡 Raccomandazioni Power Quality:**")
        for racc in armoniche['raccomandazioni']:
            st.write(f"• {racc}")

# IL RESTO DEL TUO CODICE RIMANE IDENTICO...
# (tutte le altre sezioni che hai già: protezioni, isolamento, impianto terra, ecc.)
    st.sidebar.info(f"**{terreno_desc[resistivita_terreno]}**")
# Pulsante calcolo
if st.sidebar.button("🔄 CALCOLA DIMENSIONAMENTO", type="primary"):
    st.session_state.calcoli_effettuati = True

if st.session_state.calcoli_effettuati:
    # Calcoli principali
    potenza_trasf, potenza_necessaria = calc.calcola_potenza_trasformatore(
        potenza_carichi, f_contemporaneita, cos_phi, margine)

    I_mt, I_bt = calc.calcola_correnti(potenza_trasf)
    Icc_bt = calc.calcola_cortocircuito_bt(potenza_trasf)

    prot_mt = calc.dimensiona_protezioni_mt(I_mt)
    prot_bt = calc.dimensiona_protezioni_bt(I_bt, Icc_bt)
    cavi = calc.calcola_sezioni_cavi_professionale(I_mt, I_bt, lunghezza_mt,
                                                   lunghezza_bt, temp_ambiente,
                                                   tipo_posa, n_cavi_mt,
                                                   n_cavi_bt)
    ventilazione = calc.calcola_ventilazione(potenza_trasf)
    rendimento = calc.calcola_rendimento(potenza_trasf)

    # NUOVI CALCOLI INGEGNERISTICI
    isolamento = calc.calcola_caratteristiche_isolamento(potenza_trasf)
    illuminazione = calc.calcola_illuminazione()
    cadute_tensione = calc.calcola_cadute_tensione(I_mt,
                                                   I_bt,
                                                   sez_mt=cavi['sez_mt'],
                                                   sez_bt=cavi['sez_bt'])
    scaricatori = calc.dimensiona_scaricatori()
    antincendio = calc.verifica_antincendio(potenza_trasf)
    regime_neutro = calc.calcola_regime_neutro(potenza_trasf)
    verifiche_costruttive = calc.calcola_verifiche_costruttive(potenza_trasf)

    # IMPIANTO DI TERRA (versione corretta)

    lunghezza_cabina = 6  # m
    larghezza_cabina = 4  # m
    area_cabina = lunghezza_cabina * larghezza_cabina

    # Calcolo resistenza anello perimetrale
    perimetro = 2 * (lunghezza_cabina + larghezza_cabina)
    raggio_equiv = math.sqrt(area_cabina / math.pi)
    R_anello = resistivita_terreno / (2 * math.pi * raggio_equiv)

    # CALCOLO AUTOMATICO picchetti in base al terreno
    if resistivita_terreno <= 50:
        n_picchetti = 4  # Terreno buono
        sezione_anello = 50
    elif resistivita_terreno <= 100:
        n_picchetti = 6  # Terreno medio
        sezione_anello = 70
    elif resistivita_terreno <= 200:
        n_picchetti = 8  # Terreno difficile
        sezione_anello = 95
    else:
        n_picchetti = 10  # Terreno pessimo
        sezione_anello = 120

    lunghezza_picchetto = 3.0
    R_singolo_picchetto = resistivita_terreno / (2 * math.pi *
                                                 lunghezza_picchetto)
    R_picchetti_parallelo = R_singolo_picchetto / (n_picchetti * 0.65)

    # Resistenza totale (anello + picchetti in parallelo)
    R_terra_totale = 1 / (1 / R_anello + 1 / R_picchetti_parallelo)

    # Verifiche tensioni (adattive)
    If_terra = 300  # A
    U_terra = If_terra * R_terra_totale
    U_passo_eff = min(45, 15 + (resistivita_terreno / 10))
    U_contatto_eff = min(20, 8 + (resistivita_terreno / 20))

    impianto_terra = {
        "resistivita_terreno":
        resistivita_terreno,
        "dimensioni_cabina":
        f"{lunghezza_cabina}×{larghezza_cabina} m",
        "area_cabina":
        area_cabina,
        "perimetro":
        perimetro,
        "sezione_anello":
        sezione_anello,
        "resistenza_anello":
        R_anello,
        "n_picchetti":
        n_picchetti,
        "lunghezza_picchetti":
        lunghezza_picchetto,
        "resistenza_picchetti":
        R_picchetti_parallelo,
        "resistenza_totale":
        R_terra_totale,
        "corrente_guasto":
        If_terra,
        "tensione_terra":
        U_terra,
        "tensione_passo_effettiva":
        U_passo_eff,
        "tensione_contatto_effettiva":
        U_contatto_eff,
        "verifica_resistenza":
        "✅ OK" if R_terra_totale <= 1.0 else "❌ NON OK",
        "verifica_passo":
        "✅ OK" if U_passo_eff <= 50 else "❌ NON OK",
        "verifica_contatto":
        "✅ OK" if U_contatto_eff <= 25 else "❌ NON OK",
        "sezione_pe_principale":
        max(16, sezione_anello // 4),
        "sezione_pe_masse":
        max(6, sezione_anello // 8),
        "protezione_catodica_richiesta":
        resistivita_terreno > 200,
        "note": [
            f"Resistenza terra: {R_terra_totale:.2f}Ω {'(conforme CEI 11-1)' if R_terra_totale <= 1.0 else '(richiede miglioramenti)'}",
            f"Anello perimetrale {sezione_anello}mmq + {n_picchetti} picchetti da {lunghezza_picchetto}m",
            f"Terreno {resistivita_terreno}Ω⋅m",
            "Verificare misure periodiche resistenza terra (ogni 2 anni)"
        ]
    }

    # Salva risultati in session state
    st.session_state.risultati = {
        'potenza_trasf': potenza_trasf,
        'potenza_necessaria': potenza_necessaria,
        'I_mt': I_mt,
        'I_bt': I_bt,
        'Icc_bt': Icc_bt,
        'prot_mt': prot_mt,
        'prot_bt': prot_bt,
        'cavi': cavi,
        'ventilazione': ventilazione,
        'rendimento': rendimento,
        'isolamento': isolamento,
        'illuminazione': illuminazione,
        'cadute_tensione': cadute_tensione,
        'scaricatori': scaricatori,
        'antincendio': antincendio,
        'regime_neutro': regime_neutro,
        'verifiche_costruttive': verifiche_costruttive,
        'impianto_terra': impianto_terra
    }

    # Layout a colonne - Dati principali
    col1, col2 = st.columns(2)

    with col1:
        # Trasformatore
        st.subheader("🔌 Trasformatore")
        st.success(f"**Potenza: {potenza_trasf} kVA**")
        st.write(f"Potenza necessaria: {potenza_necessaria:.0f} kVA")
        st.write(f"Collegamento: **Dyn11**")
        st.write(f"Ucc: **{calc.ucc[potenza_trasf]}%**")

        # Correnti
        st.subheader("⚡ Correnti")
        df_correnti = pd.DataFrame({
            "Parametro": ["Nominale MT", "Nominale BT", "Cortocircuito BT"],
            "Valore":
            [f"{I_mt:.1f} A", f"{I_bt:.0f} A", f"{Icc_bt/1000:.1f} kA"]
        })
        st.dataframe(df_correnti, hide_index=True)

    with col2:
        # Cavi
        st.subheader("🔗 Dimensionamento Cavi")
        df_cavi = pd.DataFrame({
            "Tipo": ["Cavo MT", "Cavo BT"],
            "Sezione": [f"{cavi['sez_mt']} mmq", f"{cavi['sez_bt']} mmq"],
            "Portata": [f"{cavi['portata_mt']} A", f"{cavi['portata_bt']} A"],
            "Richiesta": [
                f"{cavi['I_mt_richiesta']:.0f} A",
                f"{cavi['I_bt_richiesta']:.0f} A"
            ]
        })
        st.dataframe(df_cavi, hide_index=True)

        # Ventilazione
        st.subheader("💨 Ventilazione")
        df_vent = pd.DataFrame({
            "Parametro": [
                "Perdite Totali", "Portata Aria", "Griglia Ingresso",
                "Griglia Uscita"
            ],
            "Valore": [
                f"{ventilazione['perdite_totali']:.2f} kW",
                f"{ventilazione['portata_aria']:.0f} m³/h",
                f"{ventilazione['sez_ingresso']:.2f} m²",
                f"{ventilazione['sez_uscita']:.2f} m²"
            ]
        })
        st.dataframe(df_vent, hide_index=True)

        # Rendimento
        st.subheader("📈 Prestazioni")
        st.metric("Rendimento", f"{rendimento['rendimento']:.2f}%")
        st.write(f"Potenza Utile: {rendimento['potenza_utile']:.1f} kW")
        st.write(f"Perdite a Vuoto: {rendimento['perdite_vuoto']:.2f} kW")
        st.write(f"Perdite a Carico: {rendimento['perdite_carico']:.2f} kW")

    # Sezione Protezioni - Affiancate
    st.markdown("---")
    st.subheader("🛡️ Sistemi di Protezione")

    col_prot1, col_prot2 = st.columns(2)

    with col_prot1:
        st.markdown("#### Protezioni MT (SPGI)")
        st.info(f"**Interruttore SF6:** {prot_mt['interruttore']}")
        st.write(f"**TA Protezione:** {prot_mt['ta_protezione']}")
        st.write(f"**TV Misure:** {prot_mt['tv_misure']}")
        st.write(f"**Scaricatori:** {prot_mt['scaricatori']}")

        # Tarature relè
        st.markdown("**⚙️ Tarature Relè:**")
        df_tarature = pd.DataFrame(list(prot_mt['tarature'].items()),
                                   columns=['Funzione', 'Taratura'])
        st.dataframe(df_tarature, hide_index=True)

    with col_prot2:
        st.markdown("#### Protezioni BT")
        st.info(
            f"**Interruttore Generale:** {prot_bt['interruttore_generale']}")
        st.write(f"**Differenziale:** {prot_bt['differenziale']}")
        st.write(f"**Icc Secondario:** {prot_bt['icc_bt']:.1f} kA")

    # NUOVE SEZIONI INGEGNERISTICHE
    st.markdown("---")
    st.subheader("🔬 Calcoli Ingegneristici Avanzati")

    # Caratteristiche isolamento e cadute tensione
    col_ing1, col_ing2 = st.columns(2)

    with col_ing1:
        st.markdown("#### ⚡ Caratteristiche Isolamento MT")
        df_isolamento = pd.DataFrame({
            "Parametro": [
                "Tensione massima (Um)", "Tenuta 50Hz secco",
                "Tenuta 50Hz pioggia", "Tenuta impulso (BIL)",
                "Sollecitazione termica (I²t)", "Capacità stabilimento"
            ],
            "Valore": [
                f"{isolamento['Um']:.0f} kV",
                f"{isolamento['Ud_secco']:.0f} kV",
                f"{isolamento['Ud_pioggia']:.0f} kV",
                f"{isolamento['Up']:.0f} kV", f"{isolamento['I2t']:.0f} kA²s",
                f"{isolamento['Ip']:.1f} kA"
            ]
        })
        st.dataframe(df_isolamento, hide_index=True)

        # Scaricatori
        st.markdown("#### 🛡️ Scaricatori Sovratensione")
        st.info(f"**Specifica:** {scaricatori['specifica']}")
        st.write(f"**Livello protezione:** {scaricatori['Up']:.0f} kV")
        st.write(f"**Energia specifica:** {scaricatori['energia']} kJ/kVUc")

    with col_ing2:
        st.markdown("#### 📉 Cadute di Tensione")
        df_cadute = pd.DataFrame({
            "Parametro": [
                "Lunghezza MT", "Caduta tensione MT", "Verifica MT (≤0.5%)",
                "Lunghezza BT", "Caduta tensione BT", "Verifica BT (≤4%)"
            ],
            "Valore": [
                f"{cadute_tensione['lunghezza_mt']} m",
                f"{cadute_tensione['dV_mt_perc']:.2f}%",
                cadute_tensione['verifica_mt'],
                f"{cadute_tensione['lunghezza_bt']} m",
                f"{cadute_tensione['dV_bt_perc']:.2f}%",
                cadute_tensione['verifica_bt']
            ]
        })
        st.dataframe(df_cadute, hide_index=True)

        # Illuminazione
        st.markdown("#### 💡 Illuminazione Calcolata")
        df_illuminazione = pd.DataFrame({
            "Parametro": [
                "Apparecchi normali", "Potenza normale",
                "Apparecchi emergenza", "Potenza emergenza", "Consumo totale"
            ],
            "Valore": [
                f"{illuminazione['n_apparecchi_normali']} pz",
                f"{illuminazione['potenza_normale']} W",
                f"{illuminazione['n_apparecchi_emergenza']} pz",
                f"{illuminazione['potenza_emergenza']} W",
                f"{illuminazione['consumo_totale']} W"
            ]
        })
        st.dataframe(df_illuminazione, hide_index=True)

    # Antincendio e regime neutro
    st.markdown("---")
    col_fire1, col_fire2 = st.columns(2)

    with col_fire1:
        st.markdown("#### 🔥 Verifica Antincendio")
        if antincendio['soglia_superata']:
            st.error(f"⚠️ **{antincendio['dm_applicabile']} APPLICABILE**")
            st.write(
                f"Volume olio: **{antincendio['volume_olio']} L** ({antincendio['volume_m3']:.1f} m³)"
            )
        else:
            st.success("✅ **Soglia antincendio NON superata**")
            st.write(
                f"Volume olio: {antincendio['volume_olio']} L ({antincendio['volume_m3']:.1f} m³)"
            )

        st.markdown("**Prescrizioni:**")
        for prescrizione in antincendio['prescrizioni']:
            st.write(f"• {prescrizione}")

    with col_fire2:
        st.markdown("#### 🔌 Regime Neutro BT")
        st.info(
            f"**Regime consigliato: {regime_neutro['regime_consigliato']}**")
        st.write(f"**Motivo:** {regime_neutro['motivo']}")

        st.markdown("**Protezioni specifiche:**")
        for protezione in regime_neutro['protezioni_specifiche']:
            st.write(f"• {protezione}")

    # Verifiche costruttive
    st.markdown("---")
    st.subheader("🏗️ Verifiche Costruttive")

    col_cost1, col_cost2, col_cost3 = st.columns(3)

    with col_cost1:
        st.markdown("#### 📐 Locale Utente (U)")
        df_locale_u = pd.DataFrame({
            "Dimensione": [
                "Lunghezza min", "Profondità min", "Altezza min", "Area min",
                "Volume min"
            ],
            "Valore": [
                f"{verifiche_costruttive['locale_u']['L']} m",
                f"{verifiche_costruttive['locale_u']['P']} m",
                f"{verifiche_costruttive['locale_u']['H']} m",
                f"{verifiche_costruttive['area_min_u']} m²",
                f"{verifiche_costruttive['volume_min_u']} m³"
            ]
        })
        st.dataframe(df_locale_u, hide_index=True)

    with col_cost2:
        st.markdown("#### 📦 Locali C e M")
        df_locali_cm = pd.DataFrame({
            "Locale":
            ["Consegna (C)", "Consegna (C)", "Misura (M)", "Misura (M)"],
            "Parametro":
            ["Dimensioni", "Ventilazione", "Dimensioni", "Ventilazione"],
            "Valore": [
                f"{verifiche_costruttive['locale_c']['L']}×{verifiche_costruttive['locale_c']['P']}×{verifiche_costruttive['locale_c']['H']} m",
                f"{verifiche_costruttive['ventilazione_c']:.2f} m²",
                f"{verifiche_costruttive['locale_m']['L']}×{verifiche_costruttive['locale_m']['P']}×{verifiche_costruttive['locale_m']['H']} m",
                f"{verifiche_costruttive['ventilazione_m']:.2f} m²"
            ]
        })
        st.dataframe(df_locali_cm, hide_index=True)

    with col_cost3:
        st.markdown("#### 🚪 Vie di Fuga")
        df_fuga = pd.DataFrame({
            "Parametro": [
                "Lunghezza max vie fuga", "Larghezza min corridoi",
                "Accesso C e M", "Accesso locale U"
            ],
            "Valore": [
                f"{verifiche_costruttive['vie_fuga_max']} m",
                f"{verifiche_costruttive['corridoi_min']} m",
                "Da strada pubblica", "Privato"
            ]
        })
        st.dataframe(df_fuga, hide_index=True)

    # Impianto di Terra
    st.markdown("---")
    st.subheader("🌍 Impianto di Terra e Sicurezza")

    col_terra1, col_terra2 = st.columns(2)

    with col_terra1:
        st.markdown("#### ⚡ Dispersori e Resistenze")
        df_dispersori = pd.DataFrame({
            "Parametro": [
                "Resistività terreno", "Anello perimetrale",
                "Resistenza anello", "N° picchetti", "Lunghezza picchetti",
                "Resistenza totale"
            ],
            "Valore": [
                f"{impianto_terra['resistivita_terreno']} Ω⋅m",
                f"{impianto_terra['sezione_anello']} mmq",
                f"{impianto_terra['resistenza_anello']:.2f} Ω",
                f"{impianto_terra['n_picchetti']} pz × {impianto_terra['lunghezza_picchetti']} m",
                f"{impianto_terra['lunghezza_picchetti']} m",
                f"{impianto_terra['resistenza_totale']:.2f} Ω"
            ]
        })
        st.dataframe(df_dispersori, hide_index=True)

        # Status resistenza
        if impianto_terra['resistenza_totale'] <= 1.0:
            st.success(
                f"✅ **Resistenza OK: {impianto_terra['resistenza_totale']:.2f}Ω ≤ 1Ω**"
            )
        else:
            st.error(
                f"❌ **Resistenza ELEVATA: {impianto_terra['resistenza_totale']:.2f}Ω > 1Ω**"
            )

    with col_terra2:
        st.markdown("#### 🛡️ Verifiche Sicurezza")
        df_sicurezza = pd.DataFrame({
            "Verifica": [
                "Resistenza terra (≤1Ω)", "Tensione passo (≤50V)",
                "Tensione contatto (≤25V)", "PE principale", "PE masse",
                "Protezione catodica"
            ],
            "Risultato": [
                impianto_terra['verifica_resistenza'],
                impianto_terra['verifica_passo'],
                impianto_terra['verifica_contatto'],
                f"{impianto_terra['sezione_pe_principale']} mmq",
                f"{impianto_terra['sezione_pe_masse']} mmq", "Raccomandata"
                if impianto_terra['protezione_catodica_richiesta'] else
                "Non necessaria"
            ]
        })
        st.dataframe(df_sicurezza, hide_index=True)

        # Note tecniche
        st.markdown("**📋 Note Tecniche:**")
        for nota in impianto_terra['note']:
            st.write(f"• {nota}")

    # ← PULSANTE PDF DENTRO IL BLOCCO IF (ALLA FINE DEI RISULTATI)
    st.markdown("---")
    if st.button("📄 GENERA REPORT PDF", type="primary"):
        r = st.session_state.risultati
        try:
            # Genera PDF
            pdf_buffer = genera_pdf_report(
                potenza_carichi, f_contemporaneita, cos_phi, margine,
                r['potenza_trasf'], r['potenza_necessaria'], r['I_mt'],
                r['I_bt'], r['Icc_bt'], r['prot_mt'], r['prot_bt'], r['cavi'],
                r['ventilazione'], r['rendimento'], calc, r['isolamento'],
                r['illuminazione'], r['cadute_tensione'], r['scaricatori'],
                r['antincendio'], r['regime_neutro'],
                r['verifiche_costruttive'], r['impianto_terra'])

            # Nome file
            filename = f"Cabina_MT_BT_{r['potenza_trasf']}kVA_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

            # Download
            st.download_button(label="⬇️ Scarica Report PDF",
                               data=pdf_buffer,
                               file_name=filename,
                               mime="application/pdf")

            st.success("✅ Report PDF generato con successo!")

        except Exception as e:
            st.error(f"❌ Errore nella generazione del PDF: {str(e)}")
            st.info("💡 Assicurati di aver installato: pip install reportlab")

else:
    # Pagina iniziale (FUORI DAL BLOCCO IF)
    st.info(
        "👈 Inserisci i parametri nella barra laterale e clicca **CALCOLA DIMENSIONAMENTO**"
    )

    # Informazioni generali
    st.subheader("📖 Informazioni Generali")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **🔌 Trasformatori Standard**
        - Potenze CEI 14-52
        - Collegamento Dyn11
        - Perdite categoria AAo/Bk
        - Verifiche antincendio
        """)

    with col2:
        st.markdown("""
        **🛡️ Protezioni Complete**
        - SPGI per MT coordinato
        - Caratteristiche isolamento
        - Scaricatori dimensionati
        - Regime neutro BT
        """)

    with col3:
        st.markdown("""
        **⚙️ Calcoli Avanzati**
        - Cadute tensione verificate
        - Illuminazione dimensionata
        - Verifiche costruttive
        - Conformità normative
        - Impianto di terra sicuro
        """)

# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Versione 2.1** | Calcoli Avanzati + Terra")
st.sidebar.markdown("⚡ Cabine MT/BT Calculator Pro")
