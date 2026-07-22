# -*- coding: utf-8 -*-
"""
mundial_dashboard.py

Version parametrizada de postmatch_v3-GPT2.py (script de referencia en
"/Users/jairobuenaventura/Downloads/Fútbol - Análisis y Partidos/postmatch_v3-GPT2.py",
NO modificado) para generar el CSV de eventos + los 4 PNG del dashboard
post-partido (Dashboard, Player_Dashboard, KPI_Summary, Tactical_Insights)
para cualquier partido de WhoScored/FotMob, sin tocar constantes hardcodeadas
en el módulo.

Uso:
    from mundial_dashboard import generar_reporte
    resumen = generar_reporte(
        whoscored_html="ruta/al/whoscored.html",
        fotmob_html="ruta/al/fotmob.html",
        gw_label="Dieciseisavos",
        output_dir="ruta/de/salida",
        generar_imagenes=True,   # False = solo generar el CSV (mas rapido, sin matplotlib)
    )
"""

import sys
sys.path.insert(0, '/Users/jairobuenaventura/Desktop/touchline')
from fotmob_parser import extraer_datos_fotmob

# -*- coding: utf-8 -*-
"""PostMatch_v3.ipynb
Match Report — Datos de OPTA vía WhoScored
Versión mejorada y corregida
"""

# ─── INSTALACIÓN (ejecutar solo una vez) ──────────────────────────────────────
# !pip install mplsoccer highlight_text

# ─── IMPORTS ──────────────────────────────────────────────────────────────────
import ast
import json
import os
import re
import warnings
from datetime import datetime
from io import BytesIO

import matplotlib as mpl
mpl.use('Agg')  # backend headless: necesario para correr fuera de un notebook
import matplotlib.image as mpimg
import matplotlib.patches as patches
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.cbook import get_sample_data
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.font_manager import FontProperties
from matplotlib.gridspec import GridSpec
from matplotlib.markers import MarkerStyle
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patheffects import Normal, withStroke
from matplotlib.ticker import MaxNLocator
from matplotlib import rcParams
from mplsoccer import Pitch, VerticalPitch
from mplsoccer.utils import FontManager
from PIL import Image
from sklearn.cluster import KMeans
from highlight_text import ax_text
from scipy.spatial import ConvexHull
from matplotlib.patches import Polygon

warnings.filterwarnings('ignore')

# ─── COLORES DEL MATCH REPORT ─────────────────────────────────────────────────
pd.set_option('display.max_columns', None)

green    = '#69f900'
red      = '#ff4b44'
blue     = '#56CEE0'
violet   = '#FF0080'
bg_color = '#FFFFFF'
line_color = '#000000'

# ─── COLORES POR EQUIPO ───────────────────────────────────────────────────────
# Formato: 'Nombre exacto del equipo en WhoScored': {'home': color_local, 'away': color_visitante}
# Temporada 2025/26

TEAM_COLORS = {
    # ── LA LIGA ───────────────────────────────────────────────────────────────
    'Barcelona':            {'home': '#A50044', 'away': '#98F516'},
    'Real Madrid':          {'home': '#FFFFFF', 'away': '#00529F'},
    'Atletico Madrid':      {'home': '#CB3524', 'away': '#FFFFFF'},
    'Sevilla':              {'home': '#D2122E', 'away': '#FFFFFF'},
    'Valencia':             {'home': '#EE7B00', 'away': '#FFFFFF'},
    'Villarreal':           {'home': '#FFD700', 'away': '#004F9F'},
    'Real Sociedad':        {'home': '#0067B1', 'away': '#FFFFFF'},
    'Athletic Club':        {'home': '#EE2523', 'away': '#FFFFFF'},
    'Real Betis':           {'home': '#00A650', 'away': '#FFFFFF'},
    'Osasuna':              {'home': '#D2122E', 'away': '#003DA5'},
    'Girona':               {'home': '#CD1719', 'away': '#FFFFFF'},
    'Mallorca':             {'home': '#E2001A', 'away': '#000000'},
    'Celta Vigo':           {'home': '#81C0E0', 'away': '#003DA5'},
    'Getafe':               {'home': '#003DA5', 'away': '#FFFFFF'},
    'Rayo Vallecano':       {'home': '#FFFFFF', 'away': '#E2001A'},
    'Espanyol':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Alaves':               {'home': '#1A5FA8', 'away': '#FFFFFF'},
    'Las Palmas':           {'home': '#FFD700', 'away': '#003DA5'},
    'Valladolid':           {'home': '#6A0DAD', 'away': '#FFFFFF'},
    'Leganes':              {'home': '#003DA5', 'away': '#FFFFFF'},

    # ── PREMIER LEAGUE ────────────────────────────────────────────────────────
    'Manchester City':      {'home': '#6CABDD', 'away': '#FFFFFF'},
    'Arsenal':              {'home': '#EF0107', 'away': '#FFFFFF'},
    'Liverpool':            {'home': '#C8102E', 'away': '#00B2A9'},
    'Chelsea':              {'home': '#034694', 'away': '#FFFFFF'},
    'Manchester United':    {'home': '#DA291C', 'away': '#FFFFFF'},
    'Tottenham':            {'home': '#FFFFFF', 'away': '#132257'},
    'Newcastle':            {'home': '#241F20', 'away': '#FFFFFF'},
    'Aston Villa':          {'home': '#95BFE5', 'away': '#670E36'},
    'West Ham':             {'home': '#7A263A', 'away': '#1BB1E7'},
    'Brighton':             {'home': '#0057B8', 'away': '#FFFFFF'},
    'Brentford':            {'home': '#E30613', 'away': '#FFFFFF'},
    'Fulham':               {'home': '#FFFFFF', 'away': '#000000'},
    'Wolves':               {'home': '#FDB913', 'away': '#231F20'},
    'Everton':              {'home': '#003399', 'away': '#FFFFFF'},
    'Crystal Palace':       {'home': '#1B458F', 'away': '#C4122E'},
    'Nottingham Forest':    {'home': '#DD0000', 'away': '#FFFFFF'},
    'Bournemouth':          {'home': '#DA291C', 'away': '#000000'},
    'Leicester':            {'home': '#003090', 'away': '#FDBE11'},
    'Ipswich':              {'home': '#003090', 'away': '#FFFFFF'},
    'Southampton':          {'home': '#D71920', 'away': '#FFFFFF'},

    # ── SERIE A ───────────────────────────────────────────────────────────────
    'Inter Milan':          {'home': '#010E80', 'away': '#FFFFFF'},
    'AC Milan':             {'home': '#FB090B', 'away': '#FFFFFF'},
    'Juventus':             {'home': '#000000', 'away': '#FFFFFF'},
    'Napoli':               {'home': '#12A0C3', 'away': '#FFFFFF'},
    'Roma':                 {'home': '#8E1F2F', 'away': '#FFD700'},
    'Lazio':                {'home': '#87D8F7', 'away': '#FFFFFF'},
    'Atalanta':             {'home': '#1E3F7B', 'away': '#FFFFFF'},
    'Fiorentina':           {'home': '#5B2D8E', 'away': '#FFFFFF'},
    'Bologna':              {'home': '#C8102E', 'away': '#003DA5'},
    'Torino':               {'home': '#8B1A1A', 'away': '#FFFFFF'},
    'Udinese':              {'home': '#FFFFFF', 'away': '#000000'},
    'Genoa':                {'home': '#C8102E', 'away': '#003DA5'},
    'Cagliari':             {'home': '#C8102E', 'away': '#003DA5'},
    'Verona':               {'home': '#FFD700', 'away': '#003DA5'},
    'Venezia':              {'home': '#000000', 'away': '#FF6600'},
    'Parma':                {'home': '#FFD700', 'away': '#003DA5'},
    'Como':                 {'home': '#003DA5', 'away': '#FFFFFF'},
    'Empoli':               {'home': '#003DA5', 'away': '#FFFFFF'},
    'Lecce':                {'home': '#FFD700', 'away': '#C8102E'},
    'Monza':                {'home': '#E31837', 'away': '#FFFFFF'},

    # ── BUNDESLIGA ────────────────────────────────────────────────────────────
    'Bayern Munich':        {'home': '#DC052D', 'away': '#FFFFFF'},
    'Borussia Dortmund':    {'home': '#FDE100', 'away': '#000000'},
    'Bayer Leverkusen':     {'home': '#E32221', 'away': '#FFFFFF'},
    'RB Leipzig':           {'home': '#DD0741', 'away': '#FFFFFF'},
    'Eintracht Frankfurt':  {'home': '#E1000F', 'away': '#000000'},
    'Borussia Monchengladbach': {'home': '#FFFFFF', 'away': '#000000'},
    'Stuttgart':            {'home': '#E32221', 'away': '#FFFFFF'},
    'Wolfsburg':            {'home': '#65B32E', 'away': '#FFFFFF'},
    'Hoffenheim':           {'home': '#1961AC', 'away': '#FFFFFF'},
    'Freiburg':             {'home': '#E32221', 'away': '#000000'},
    'Werder Bremen':        {'home': '#1D9053', 'away': '#FFFFFF'},
    'Union Berlin':         {'home': '#E32221', 'away': '#FFFFFF'},
    'Mainz':                {'home': '#E32221', 'away': '#FFFFFF'},
    'Augsburg':             {'home': '#BA3733', 'away': '#FFFFFF'},
    'Heidenheim':           {'home': '#E32221', 'away': '#003DA5'},
    'Holstein Kiel':        {'home': '#003DA5', 'away': '#FFFFFF'},
    'St. Pauli':            {'home': '#9B3D2B', 'away': '#FFFFFF'},
    'Bochum':               {'home': '#003DA5', 'away': '#FFFFFF'},

    # ── LIGUE 1 ───────────────────────────────────────────────────────────────
    'Paris Saint-Germain':  {'home': '#004170', 'away': '#FFFFFF'},
    'Olympique Marseille':  {'home': '#2CBFEF', 'away': '#FFFFFF'},
    'Olympique Lyonnais':   {'home': '#FFFFFF', 'away': '#003DA5'},
    'Monaco':               {'home': '#E4002B', 'away': '#FFFFFF'},
    'Lille':                {'home': '#E32221', 'away': '#FFFFFF'},
    'Nice':                 {'home': '#E32221', 'away': '#000000'},
    'Lens':                 {'home': '#FFD700', 'away': '#E32221'},
    'Rennes':               {'home': '#E32221', 'away': '#000000'},
    'Strasbourg':           {'home': '#003DA5', 'away': '#FFFFFF'},
    'Brest':                {'home': '#E32221', 'away': '#FFFFFF'},
    'Nantes':               {'home': '#FFD700', 'away': '#003DA5'},
    'Toulouse':             {'home': '#6A0DAD', 'away': '#FFFFFF'},
    'Reims':                {'home': '#E32221', 'away': '#FFFFFF'},
    'Montpellier':          {'home': '#F6811F', 'away': '#003DA5'},
    'Le Havre':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Auxerre':              {'home': '#003DA5', 'away': '#FFFFFF'},
    'Angers':               {'home': '#000000', 'away': '#FFFFFF'},
    'Saint-Etienne':        {'home': '#00A650', 'away': '#FFFFFF'},

    # ── UEFA CHAMPIONS LEAGUE / UEL / UECL (equipos frecuentes) ──────────────
    'Porto':                {'home': '#003DA5', 'away': '#FFFFFF'},
    'Benfica':              {'home': '#E32221', 'away': '#FFFFFF'},
    'Sporting CP':          {'home': '#00A650', 'away': '#FFFFFF'},
    'Ajax':                 {'home': '#E32221', 'away': '#FFFFFF'},
    'PSV Eindhoven':        {'home': '#E32221', 'away': '#FFFFFF'},
    'Feyenoord':            {'home': '#E32221', 'away': '#FFFFFF'},
    'Celtic':               {'home': '#00A650', 'away': '#FFFFFF'},
    'Rangers':              {'home': '#003DA5', 'away': '#FFFFFF'},
    'Shakhtar Donetsk':     {'home': '#FF6600', 'away': '#000000'},
    'Dynamo Kyiv':          {'home': '#003DA5', 'away': '#FFFFFF'},
    'Red Bull Salzburg':    {'home': '#DD0741', 'away': '#FFFFFF'},
    'Galatasaray':          {'home': '#E32221', 'away': '#FFD700'},
    'Fenerbahce':           {'home': '#FFD700', 'away': '#003DA5'},
    'Besiktas':             {'home': '#000000', 'away': '#FFFFFF'},
    'Club Brugge':          {'home': '#003DA5', 'away': '#000000'},
    'Anderlecht':           {'home': '#6A0DAD', 'away': '#FFFFFF'},
    'Slavia Prague':        {'home': '#E32221', 'away': '#FFFFFF'},
    'Viktoria Plzen':       {'home': '#003DA5', 'away': '#E32221'},
    'Young Boys':           {'home': '#FFD700', 'away': '#000000'},
    'Basel':                {'home': '#E32221', 'away': '#003DA5'},

    # ── MLS ───────────────────────────────────────────────────────────────────
    'Inter Miami':          {'home': '#F7B5CD', 'away': '#231F20'},
    'LA Galaxy':            {'home': '#00245D', 'away': '#FFD700'},
    'LAFC':                 {'home': '#000000', 'away': '#C39E6D'},
    'Seattle Sounders':     {'home': '#5D9732', 'away': '#003DA5'},
    'Portland Timbers':     {'home': '#00482B', 'away': '#FFFFFF'},
    'Atlanta United':       {'home': '#80000A', 'away': '#FFFFFF'},
    'New York City FC':     {'home': '#6CABDD', 'away': '#FFFFFF'},
    'New York Red Bulls':   {'home': '#ED1E36', 'away': '#FFFFFF'},
    'Columbus Crew':        {'home': '#FEDD00', 'away': '#000000'},
    'Toronto FC':           {'home': '#E31837', 'away': '#FFFFFF'},
    'CF Montreal':          {'home': '#003DA5', 'away': '#FFFFFF'},
    'New England Revolution': {'home': '#CE0E2D', 'away': '#FFFFFF'},
    'DC United':            {'home': '#000000', 'away': '#EF3E42'},
    'Chicago Fire':         {'home': '#E32221', 'away': '#FFFFFF'},
    'Minnesota United':     {'home': '#8CD2F4', 'away': '#231F20'},
    'Colorado Rapids':      {'home': '#862633', 'away': '#FFFFFF'},
    'Real Salt Lake':       {'home': '#B30838', 'away': '#013A81'},
    'FC Dallas':            {'home': '#E32221', 'away': '#003DA5'},
    'Houston Dynamo':       {'home': '#FF6B00', 'away': '#000000'},
    'Sporting KC':          {'home': '#002B5C', 'away': '#FFFFFF'},
    'Vancouver Whitecaps':  {'home': '#009BC8', 'away': '#FFFFFF'},
    'San Jose Earthquakes': {'home': '#0D4C8B', 'away': '#FFFFFF'},
    'Orlando City':         {'home': '#633492', 'away': '#FDE192'},
    'Nashville SC':         {'home': '#ECE83A', 'away': '#1F1646'},
    'Austin FC':            {'home': '#00B140', 'away': '#000000'},
    'Charlotte FC':         {'home': '#1A85C8', 'away': '#FFFFFF'},
    'St. Louis City':       {'home': '#CE0E2D', 'away': '#FFFFFF'},
    'San Diego FC':         {'home': '#003DA5', 'away': '#FFFFFF'},

    # ── COPA LIBERTADORES — ARGENTINA ─────────────────────────────────────────
    'River Plate':          {'home': '#FFFFFF', 'away': '#E32221'},
    'Boca Juniors':         {'home': '#003DA5', 'away': '#FFD700'},
    'Racing Club':          {'home': '#003DA5', 'away': '#FFFFFF'},
    'Independiente':        {'home': '#E32221', 'away': '#003DA5'},
    'San Lorenzo':          {'home': '#E32221', 'away': '#003DA5'},
    'Lanus':                {'home': '#9B1A21', 'away': '#FFFFFF'},
    'Estudiantes':          {'home': '#E32221', 'away': '#FFFFFF'},
    'Huracan':              {'home': '#E32221', 'away': '#FFFFFF'},
    'Talleres':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Velez Sarsfield':      {'home': '#003DA5', 'away': '#FFFFFF'},

    # ── COPA LIBERTADORES — BRASIL ────────────────────────────────────────────
    'Flamengo':             {'home': '#E32221', 'away': '#000000'},
    'Palmeiras':            {'home': '#006437', 'away': '#FFFFFF'},
    'Corinthians':          {'home': '#000000', 'away': '#FFFFFF'},
    'Santos':               {'home': '#FFFFFF', 'away': '#000000'},
    'Sao Paulo':            {'home': '#E32221', 'away': '#FFFFFF'},
    'Gremio':               {'home': '#003DA5', 'away': '#000000'},
    'Internacional':        {'home': '#E32221', 'away': '#FFFFFF'},
    'Atletico Mineiro':     {'home': '#000000', 'away': '#FFFFFF'},
    'Fluminense':           {'home': '#8B0000', 'away': '#FFFFFF'},
    'Cruzeiro':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Vasco da Gama':        {'home': '#000000', 'away': '#FFFFFF'},
    'Botafogo':             {'home': '#000000', 'away': '#FFFFFF'},
    'Atletico Paranaense':  {'home': '#E32221', 'away': '#000000'},

    # ── LIGA BETPLAY — COLOMBIA ───────────────────────────────────────────────
    'Millonarios':          {'home': '#003DA5', 'away': '#FFFFFF'},
    'America de Cali':      {'home': '#E32221', 'away': '#FFFFFF'},
    'Atletico Nacional':    {'home': '#006437', 'away': '#FFFFFF'},
    'Independiente Medellin': {'home': '#E32221', 'away': '#003DA5'},
    'Junior':               {'home': '#E32221', 'away': '#FFD700'},
    'Santa Fe':             {'home': '#E32221', 'away': '#FFFFFF'},
    'Deportivo Cali':       {'home': '#006437', 'away': '#FFFFFF'},
    'Deportes Tolima':      {'home': '#E32221', 'away': '#FFD700'},
    'Envigado':             {'home': '#FF6B00', 'away': '#000000'},
    'Once Caldas':          {'home': '#FFFFFF', 'away': '#000000'},
    'Patriotas':            {'home': '#003DA5', 'away': '#E32221'},
    'Boyaca Chico':         {'home': '#003DA5', 'away': '#FFFFFF'},
    'La Equidad':           {'home': '#E32221', 'away': '#003DA5'},
    'Bucaramanga':          {'home': '#E32221', 'away': '#FFD700'},
    'Jaguares':             {'home': '#FFD700', 'away': '#003DA5'},
    'Pereira':              {'home': '#E32221', 'away': '#FFFFFF'},
    'Alianza FC':           {'home': '#E32221', 'away': '#000000'},

    # ── SELECCIONES — MUNDIAL 2026 (48 equipos, grupos correctos) ────────────
    # Grupo A: Mexico, South Korea, South Africa, Czechia
    'Mexico':               {'home': '#0A9841', 'away': '#F33946'},
    'South Korea':               {'home': '#C60C30', 'away': '#000000'},
    'South Africa':         {'home': '#FFC525', 'away': '#01963A'},
    'Czechia':               {'home': '#D7141A', 'away': '#003DA5'},

    # Grupo B: Canada, Switzerland, Qatar, Bosnia and Herzegovina
    'Canada':               {'home': '#C5281C', 'away': '#2D2A26'},
    'Switzerland':          {'home': '#FF0000', 'away': '#000000'},
    'Qatar':               {'home': '#8D1B3D', 'away': '#F5F5DC'},
    'Bosnia and Herzegovina':               {'home': '#003DA5', 'away': '#FFDD00'},

    # Grupo C: Brazil, Morocco, Scotland, Haiti
    'Brazil':               {'home': '#FDDC02', 'away': '#193375'},
    'Morocco':              {'home': '#EB1E28', 'away': '#40AC79'},
    'Scotland':             {'home': '#003DA5', 'away': '#E8927C'},
    'Haiti':                {'home': '#003087', 'away': '#D21034'},

    # Grupo D: USA, Australia, Paraguay, Turkiye
    'USA':               {'home': '#002868', 'away': '#B22234'},
    'United States':               {'home': '#002868', 'away': '#B22234'},
    'Australia':            {'home': '#FFD700', 'away': '#006400'},
    'Paraguay':             {'home': '#CC001C', 'away': '#00619E'},
    'Turkiye':               {'home': '#E30A17', 'away': '#003DA5'},
    'Turkey':               {'home': '#E30A17', 'away': '#003DA5'},

    # Grupo E: Germany, Ecuador, Ivory Coast, Curacao
    'Germany':              {'home': '#DD0000', 'away': '#000000'},
    'Ecuador':              {'home': '#FFCE00', 'away': '#002255'},
    'Ivory Coast':          {'home': '#F77F00', 'away': '#009A44'},
    'Curacao':               {'home': '#003DA5', 'away': '#F7941D'},

    # Grupo F: Netherlands, Japan, Tunisia, Sweden
    'Netherlands':          {'home': '#F36C21', 'away': '#1E3D8F'},
    'Japan':               {'home': '#0D3F91', 'away': '#E30016'},
    'Tunisia':               {'home': '#E70013', 'away': '#000000'},
    'Sweden':               {'home': '#006AA7', 'away': '#FECC02'},

    # Grupo G: Belgium, Iran, Egypt, New Zealand
    'Belgium':              {'home': '#E30613', 'away': '#1D1D1B'},
    'Iran':               {'home': '#239F40', 'away': '#FFFFFF'},
    'Egypt':               {'home': '#C8102E', 'away': '#000000'},
    'New Zealand':          {'home': '#FFFFFF', 'away': '#000000'},

    # Grupo H: Spain, Uruguay, Saudi Arabia, Cape Verde
    'Spain':                {'home': '#FF0028', 'away': '#003DA5'},
    'Uruguay':              {'home': '#5AAAFA', 'away': '#000000'},
    'Saudi Arabia':               {'home': '#006C35', 'away': '#FFFFFF'},
    'Cape Verde':               {'home': '#003893', 'away': '#F5A623'},

    # Grupo I: France, Senegal, Norway, Iraq
    'France':               {'home': '#002395', 'away': '#FFFFFF'},
    'Senegal':               {'home': '#11A335', 'away': '#FFDC00'},
    'Norway':               {'home': '#EF2B2D', 'away': '#003DA5'},
    'Iraq':               {'home': '#007A3D', 'away': '#C8102E'},

    # Grupo J: Argentina, Austria, Algeria, Jordan
    'Argentina':               {'home': '#74ACDF', 'away': '#3BA0CB'},
    'Austria':               {'home': '#ED2939', 'away': '#000000'},
    'Algeria':               {'home': '#006233', 'away': '#D4213D'},
    'Jordan':               {'home': '#007A3D', 'away': '#C8102E'},

    # Grupo K: Portugal, Colombia, Uzbekistan, DR Congo
    'Portugal':             {'home': '#006600', 'away': '#FF0000'},
    'Colombia':             {'home': '#F6E200', 'away': '#045DA3'},
    'Uzbekistan':           {'home': '#FFFFFF', 'away': '#1EB53A'},
    'DR Congo':             {'home': '#007FFF', 'away': '#CE1126'},
    'Democratic Republic of Congo': {'home': '#007FFF', 'away': '#CE1126'},

    # Grupo L: England, Croatia, Panama, Ghana
    'England':              {'home': '#FFFFFF', 'away': '#003DA5'},
    'Croatia':              {'home': '#FF0000', 'away': '#003DA5'},
    'Panama':               {'home': '#E32221', 'away': '#003DA5'},
    'Ghana':               {'home': '#019537', 'away': '#000001'},

    # ── SELECCIONES ADICIONALES (Eliminatorias / Amistosos) ───────────────────
    'Venezuela':            {'home': '#CF142B', 'away': '#FFFFFF'},
    'Chile':                {'home': '#D52B1E', 'away': '#FFFFFF'},
    'Peru':                 {'home': '#D91023', 'away': '#FFFFFF'},
    'Bolivia':              {'home': '#D52B1E', 'away': '#FFD700'},
    'Jamaica':              {'home': '#000000', 'away': '#FFD700'},
    'El Salvador':          {'home': '#003DA5', 'away': '#FFFFFF'},
    'Cuba':                 {'home': '#003DA5', 'away': '#FFFFFF'},
    'Honduras':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Costa Rica':           {'home': '#002B7F', 'away': '#FFFFFF'},
    'Trinidad and Tobago':  {'home': '#CE1126', 'away': '#000000'},
    'Mali':                 {'home': '#14B53A', 'away': '#FFFFFF'},
    'Zambia':               {'home': '#198A00', 'away': '#FF6600'},
    'Kenya':                {'home': '#006600', 'away': '#FFFFFF'},
    'Wales':                {'home': '#C8102E', 'away': '#FFFFFF'},
    'Republic of Ireland':  {'home': '#169B62', 'away': '#FFFFFF'},
    'Czech Republic':       {'home': '#D7141A', 'away': '#FFFFFF'},
    'Romania':              {'home': '#002B7F', 'away': '#FFD700'},
    'Greece':               {'home': '#003DA5', 'away': '#FFFFFF'},
    'Russia':               {'home': '#D52B1E', 'away': '#FFFFFF'},
    'China':                {'home': '#DE2910', 'away': '#FFDE00'},
    'UAE':                  {'home': '#00732F', 'away': '#FFFFFF'},
    'Indonesia':            {'home': '#CE1126', 'away': '#FFFFFF'},
    'Thailand':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Denmark':              {'home': '#C60C30', 'away': '#FFFFFF'},
    'Ukraine':              {'home': '#005BBB', 'away': '#FFD500'},
    'Poland':               {'home': '#FFFFFF', 'away': '#DC143C'},
    'Serbia':               {'home': '#C6363C', 'away': '#003DA5'},
    'Nigeria':              {'home': '#008751', 'away': '#FFFFFF'},
    'Cameroon':             {'home': '#007A5E', 'away': '#CE1126'},
    'Slovakia':             {'home': '#003DA5', 'away': '#FFFFFF'},
    'Italy':                {'home': '#003DA5', 'away': '#FFFFFF'},
}

def _get_team_color(team_name: str, side: str, fallback: str) -> str:
    """Retorna el color del equipo según si juega de local o visitante."""
    entry = TEAM_COLORS.get(team_name, {})
    return entry.get(side, fallback)



def generar_reporte(whoscored_html, fotmob_html, gw_label, output_dir, generar_imagenes=True):
    """Genera el CSV de eventos y (opcionalmente) los 4 PNG del dashboard para un partido.

    Devuelve un dict resumen con marcador, PLAYER_HOME/PLAYER_AWAY elegidos, xG/xGOT y si
    se usaron datos de FotMob o el fallback 0.0.
    """
    os.makedirs(output_dir, exist_ok=True)

    """# Carga de datos — Configuración del partido"""

    # ╔══════════════════════════════════════════════════════════╗
    # ║           INGRESA AQUÍ TUS DATOS DEL PARTIDO            ║
    # ╠══════════════════════════════════════════════════════════╣

    WHOSCORED_HTML = whoscored_html
    gw = gw_label

    # ─── CARGA DESDE WHOSCORED ────────────────────────────────────────────────────
    import json  # sys, os, re, numpy y pandas ya están importados a nivel de módulo

    def _load_whoscored(html_path):
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        data_txt = re.findall(r'(?<=require\.config\.params\["args"\].=.)[\s\S]*?;', html)[0]
        for key in ["matchId", "matchCentreData", "matchCentreEventTypeJson", "formationIdNameMappings"]:
            data_txt = data_txt.replace(key, f'"{key}"')
        data_txt = data_txt.replace("};", "}")
        return json.loads(data_txt)

    def _extract_display(val):
        if isinstance(val, dict):
            return val.get('displayName', val)
        if isinstance(val, str):
            m = re.search(r"'displayName':\s*'([^']+)'", val)
            return m.group(1) if m else val
        return val

    def _short_name(full_name):
        if not isinstance(full_name, str):
            return full_name
        parts = full_name.split()
        if len(parts) == 1:   return full_name
        elif len(parts) == 2: return parts[0][0] + ". " + parts[1]
        else:                 return parts[0][0] + ". " + parts[1][0] + ". " + " ".join(parts[2:])

    print("📂 Cargando HTML de WhoScored...")
    raw = _load_whoscored(WHOSCORED_HTML)
    data = raw

    # ── Equipos ───────────────────────────────────────────────────────────────────
    hteamID   = data["matchCentreData"]["home"]["teamId"]
    ateamID   = data["matchCentreData"]["away"]["teamId"]
    hteamName = data["matchCentreData"]["home"]["name"]
    ateamName = data["matchCentreData"]["away"]["name"]
    teams_dict = {hteamID: hteamName, ateamID: ateamName}

    # ── xG/xGOT automático desde FotMob ────────────────────────────────────────
    import unicodedata as _ud

    def _norm_team(s):
        s = str(s).strip().lower()
        s = "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")
        return s

    _ES_EN_TEAM_MAP = {
        "sudafrica": "south africa", "canada": "canada", "brasil": "brazil",
        "japon": "japan", "alemania": "germany", "paraguay": "paraguay",
        "paises bajos": "netherlands", "marruecos": "morocco", "mexico": "mexico",
        "ecuador": "ecuador", "belgica": "belgium", "senegal": "senegal",
        "colombia": "colombia", "ghana": "ghana", "estados unidos": "united states",
        "francia": "france", "suecia": "sweden", "espana": "spain",
        "austria": "austria", "suiza": "switzerland", "argelia": "algeria",
        "portugal": "portugal", "croacia": "croatia", "inglaterra": "england",
        "republica democratica del congo": "dr congo", "costa de marfil": "ivory coast",
        "noruega": "norway", "argentina": "argentina", "cabo verde": "cape verde",
        "australia": "australia", "egipto": "egypt", "bosnia": "bosnia and herzegovina",
    }

    fotmob_used = False
    hxg = axg = hxgot = axgot = 0.0
    try:
        datos_fotmob = extraer_datos_fotmob(fotmob_html)
        fm_home_en = _ES_EN_TEAM_MAP.get(_norm_team(datos_fotmob["home_nombre"]), _norm_team(datos_fotmob["home_nombre"]))
        fm_away_en = _ES_EN_TEAM_MAP.get(_norm_team(datos_fotmob["away_nombre"]), _norm_team(datos_fotmob["away_nombre"]))
        ws_home_en = _norm_team(hteamName)
        ws_away_en = _norm_team(ateamName)
        if fm_home_en == ws_home_en and fm_away_en == ws_away_en:
            fm_stats_home, fm_stats_away = datos_fotmob["home"], datos_fotmob["away"]
        elif fm_home_en == ws_away_en and fm_away_en == ws_home_en:
            fm_stats_home, fm_stats_away = datos_fotmob["away"], datos_fotmob["home"]
        else:
            print(f"⚠️  No se pudo emparejar con certeza los nombres de FotMob "
                  f"({datos_fotmob['home_nombre']} / {datos_fotmob['away_nombre']}) con los de "
                  f"WhoScored ({hteamName} / {ateamName}); se asume el mismo orden home/away.")
            fm_stats_home, fm_stats_away = datos_fotmob["home"], datos_fotmob["away"]

        if fm_stats_home.get("xg") is not None and fm_stats_away.get("xg") is not None:
            hxg = float(fm_stats_home["xg"])
            axg = float(fm_stats_away["xg"])
            fotmob_used = True
        if fm_stats_home.get("xgot") is not None and fm_stats_away.get("xgot") is not None:
            hxgot = float(fm_stats_home["xgot"])
            axgot = float(fm_stats_away["xgot"])
        else:
            hxgot, axgot = hxg, axg
    except Exception as e:
        print(f"⚠️  No se pudieron extraer datos de FotMob ({fotmob_html}): {e}. Usando xG=0.0 como fallback.")
        fotmob_used = False
        hxg = axg = hxgot = axgot = 0.0

    # ── Selección automática de PLAYER_HOME / PLAYER_AWAY por calificación WhoScored ──
    def _pick_top_rated_player(players_list):
        best_name, best_rating = None, -1.0
        for p in players_list:
            if p.get("position") == "GK":
                continue
            ratings = ((p.get("stats") or {}).get("ratings")) or {}
            if not ratings:
                continue
            try:
                last_minute_key = max(ratings.keys(), key=lambda k: float(k))
                rating_val = float(ratings[last_minute_key])
            except (ValueError, TypeError):
                continue
            if rating_val > best_rating:
                best_rating, best_name = rating_val, p.get("name")
        if best_name is None:
            for p in players_list:
                if p.get("position") != "GK":
                    return p.get("name")
        return best_name

    PLAYER_HOME = _pick_top_rated_player(data["matchCentreData"]["home"]["players"])
    PLAYER_AWAY = _pick_top_rated_player(data["matchCentreData"]["away"]["players"])

    # ── Liga, jornada y fecha (automático desde el HTML) ─────────────────────────
    try:
        league = data["matchCentreData"].get("league", "")
        if not league:
            title_match = re.search(r'<title>([^<]+)</title>', open(WHOSCORED_HTML, encoding='utf-8', errors='ignore').read())
            league = title_match.group(1).split('-')[-1].strip() if title_match else "—"
        # Acortar año: "LaLiga 2025/2026" → "LaLiga 25/26"
        league = re.sub(r'(\d{2})(\d{2})/(\d{2})(\d{2})', r'\2/\4', league)
    except:
        league = "—"

    try:
        date_raw = data["matchCentreData"].get("startTime", data["matchCentreData"].get("localTime", ""))
        if date_raw:
            from datetime import datetime
            dt = datetime.strptime(date_raw[:10], "%Y-%m-%d")
            MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                      "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
            date = f"{dt.day} {MONTHS[dt.month-1]}, {dt.year}"
        else:
            date = "—"
    except:
        date = "—"

    # ── Jugadores ─────────────────────────────────────────────────────────────────
    home_pl = pd.DataFrame(data["matchCentreData"]["home"]["players"])
    home_pl["teamId"] = hteamID
    away_pl = pd.DataFrame(data["matchCentreData"]["away"]["players"])
    away_pl["teamId"] = ateamID
    players_df = pd.concat([home_pl, away_pl], ignore_index=True)
    drop_cols = ["height","weight","age","isManOfTheMatch","field","stats",
                 "subbedInPlayerId","subbedOutPeriod","subbedOutExpandedMinute",
                 "subbedInPeriod","subbedInExpandedMinute","subbedOutPlayerId"]
    players_df.drop(columns=[c for c in drop_cols if c in players_df.columns], inplace=True)

    # ── Eventos ───────────────────────────────────────────────────────────────────
    events_dict = data["matchCentreData"]["events"]
    events_dict = [e for e in events_dict if _extract_display(e.get("period")) != "PenaltyShootout"]
    df = pd.DataFrame(events_dict)
    df["type"]        = df["type"].apply(_extract_display)
    df["outcomeType"] = df["outcomeType"].apply(_extract_display)
    df["period"]      = df["period"].apply(_extract_display)

    # ── xT ────────────────────────────────────────────────────────────────────────
    xT_raw = pd.read_csv("https://raw.githubusercontent.com/mckayjohns/youtube-videos/main/data/xT_Grid.csv", header=None)
    xT = np.array(xT_raw)
    xT_rows, xT_cols = xT.shape

    dfxT = df.copy()
    dfxT = dfxT[~dfxT["qualifiers"].astype(str).str.contains("Corner|ThrowIn", na=False)]
    dfxT = dfxT[(dfxT["type"] == "Pass") & (dfxT["outcomeType"] == "Successful")]
    dfxT["x1_bin"] = pd.cut(dfxT["x"], bins=xT_cols, labels=False)
    dfxT["y1_bin"] = pd.cut(dfxT["y"], bins=xT_rows, labels=False)
    dfxT["x2_bin"] = pd.cut(dfxT["endX"], bins=xT_cols, labels=False)
    dfxT["y2_bin"] = pd.cut(dfxT["endY"], bins=xT_rows, labels=False)
    dfxT["start_zone_value_xT"] = dfxT[["x1_bin","y1_bin"]].apply(lambda r: xT[int(r.iloc[1])][int(r.iloc[0])], axis=1)
    dfxT["end_zone_value_xT"]   = dfxT[["x2_bin","y2_bin"]].apply(lambda r: xT[int(r.iloc[1])][int(r.iloc[0])], axis=1)
    dfxT["xT"] = dfxT["end_zone_value_xT"] - dfxT["start_zone_value_xT"]
    xt_drop = ["id","eventId","minute","second","teamId","x","y","expandedMinute","period","type",
               "outcomeType","qualifiers","satisfiedEventsTypes","isTouch","playerId","endX","endY",
               "relatedEventId","relatedPlayerId","blockedX","blockedY","goalMouthZ","goalMouthY",
               "isShot","x1_bin","y1_bin","x2_bin","y2_bin"]
    dfxT.drop(columns=[c for c in xt_drop if c in dfxT.columns], inplace=True)
    df = df.reset_index().rename(columns={"index": "_idx"})
    dfxT = dfxT.reset_index().rename(columns={"index": "_idx"})
    df = df.merge(dfxT[["_idx","start_zone_value_xT","end_zone_value_xT","xT"]], on="_idx", how="left")
    df.drop(columns=["_idx"], inplace=True)

    df["teamName"] = df["teamId"].map(teams_dict)
    for col in ["x","endX"]:
        if col in df.columns: df[col] = df[col] * 1.05
    for col in ["y","endY","goalMouthY"]:
        if col in df.columns: df[col] = df[col] * 0.68

    # ── Pases progresivos ─────────────────────────────────────────────────────────
    df["pro"] = np.where(
        (df["type"] == "Pass") & (df["outcomeType"] == "Successful") & (df["x"] > 42),
        np.sqrt((105 - df["x"])**2 + (34 - df["y"])**2) - np.sqrt((105 - df["endX"])**2 + (34 - df["endY"])**2),
        0
    )

    df = df.merge(players_df[["playerId","name","shirtNo","position","isFirstEleven"]], on="playerId", how="left")
    df["shortName"] = df["name"].apply(_short_name)

    # ── Goles ─────────────────────────────────────────────────────────────────────
    homedf = df[df["teamId"] == hteamID]
    awaydf = df[df["teamId"] == ateamID]
    hgoal_count = (len(homedf[(homedf["type"]=="Goal") & (~homedf["qualifiers"].astype(str).str.contains("OwnGoal"))]) +
                   len(awaydf[(awaydf["type"]=="Goal") & (awaydf["qualifiers"].astype(str).str.contains("OwnGoal"))]))
    agoal_count = (len(awaydf[(awaydf["type"]=="Goal") & (~awaydf["qualifiers"].astype(str).str.contains("OwnGoal"))]) +
                   len(homedf[(homedf["type"]=="Goal") & (homedf["qualifiers"].astype(str).str.contains("OwnGoal"))]))

    hxT = homedf["xT"].sum().round(2)
    axT = awaydf["xT"].sum().round(2)

    # ── Colores automáticos ───────────────────────────────────────────────────────
    hcol = _get_team_color(hteamName, 'home', '#F50900')
    acol = _get_team_color(ateamName, 'away', '#0115F5')
    col1 = hcol  # alias para compatibilidad
    col2 = acol  # alias para compatibilidad

    file_header = f"{hteamName}_vs_{ateamName}".replace(" ", "_")

    # ── Guardar CSV ───────────────────────────────────────────────────────────────
    df.to_csv(os.path.join(output_dir, f'{file_header}.csv'), index=False)

    print(f"✅ {hteamName} {hgoal_count} - {agoal_count} {ateamName}")
    print(f"📅 {date} | {league}" + (f" | Jornada {gw}" if gw != '—' else ""))
    print(f"🎨 Local: {hcol}  |  Visitante: {acol}")
    print(f"⚡ {len(df)} eventos cargados | {len(players_df)} jugadores")

    resumen = {
        "file_header": file_header,
        "hteamName": hteamName, "ateamName": ateamName,
        "hgoal_count": hgoal_count, "agoal_count": agoal_count,
        "PLAYER_HOME": PLAYER_HOME, "PLAYER_AWAY": PLAYER_AWAY,
        "hxg": hxg, "axg": axg, "hxgot": hxgot, "axgot": axgot,
        "fotmob_used": fotmob_used,
        "n_eventos": len(df), "n_jugadores": len(players_df),
        "imagenes_generadas": False,
    }
    if not generar_imagenes:
        print("⏸️  generar_imagenes=False: CSV guardado, PNGs NO generados todavía.")
        return resumen



    def get_short_name(full_name):
        return _short_name(full_name)

    def get_passes_df(events_dict):
        df = pd.DataFrame(events_dict)
        df['eventType'] = df['type'].apply(lambda x: x.get('displayName', x) if isinstance(x, dict) else x)
        df['outcomeType'] = df['outcomeType'].apply(lambda x: x.get('displayName', x) if isinstance(x, dict) else x)
        df["receiver"] = df["playerId"].shift(-1)
        passes_ids = df.index[df['eventType'] == 'Pass']
        df_passes = df.loc[passes_ids, ["id", "x", "y", "endX", "endY", "teamId", "playerId", "receiver", "eventType", "outcomeType"]]

        return df_passes

    passes_df = get_passes_df(events_dict)
    path_eff = [path_effects.Stroke(linewidth=3, foreground=bg_color), path_effects.Normal()]

    def get_passes_between_df(team_id, passes_df, players_df):
        passes_df = passes_df[passes_df["teamId"] == team_id]
        # usar el df ya procesado en lugar de reconstruir desde events_dict
        dfteam = df[df['teamId'] == team_id] if df is not None else pd.DataFrame()
        passes_df = passes_df.merge(players_df[["playerId", "isFirstEleven"]], on='playerId', how='left')
        # calcular las posiciones medias para los pases de los jugadores
        average_locs_and_count_df = (dfteam.groupby('playerId').agg({'x': ['median'], 'y': ['median', 'count']}))
        average_locs_and_count_df.columns = ['pass_avg_x', 'pass_avg_y', 'count']
        average_locs_and_count_df = average_locs_and_count_df.merge(players_df[['playerId', 'name', 'shirtNo', 'position', 'isFirstEleven']], on='playerId', how='left')
        average_locs_and_count_df = average_locs_and_count_df.set_index('playerId')
        # # calcular el número de pases entre cada posición (usando min/max para obtener pases en ambos sentidos)
        passes_player_ids_df = passes_df.loc[:, ['id', 'playerId', 'receiver', 'teamId']]
        passes_player_ids_df['pos_max'] = (passes_player_ids_df[['playerId', 'receiver']].max(axis='columns'))
        passes_player_ids_df['pos_min'] = (passes_player_ids_df[['playerId', 'receiver']].min(axis='columns'))
        # obtener los pases entre jugadores
        passes_between_df = passes_player_ids_df.groupby(['pos_min', 'pos_max']).id.count().reset_index()
        passes_between_df.rename({'id': 'pass_count'}, axis='columns', inplace=True)
        # Agrega la ubicación de cada jugador para que tengamos las posiciones inicial y final de las líneas
        passes_between_df = passes_between_df.merge(average_locs_and_count_df, left_on='pos_min', right_index=True)
        passes_between_df = passes_between_df.merge(average_locs_and_count_df, left_on='pos_max', right_index=True, suffixes=['', '_end'])

        return passes_between_df, average_locs_and_count_df

    home_team_id = hteamID
    home_passes_between_df, home_average_locs_and_count_df = get_passes_between_df(home_team_id, passes_df, players_df)
    away_team_id = ateamID
    away_passes_between_df, away_average_locs_and_count_df = get_passes_between_df(away_team_id, passes_df, players_df)

    def pass_network_visualization(ax,
                                   passes_between_df,
                                   average_locs_and_count_df,
                                   col,
                                   team_id,
                                   flipped=False):

        # ===============================
        # MÉTRICAS AUTOMÁTICAS DEL PARTIDO
        # ===============================
        total_passes  = int(passes_between_df['pass_count'].sum())

        # Precisión de pase
        team_df = df[df['teamId'] == team_id]
        total_team_passes = len(team_df[team_df['type'] == 'Pass'])
        successful_passes = len(team_df[(team_df['type'] == 'Pass') & (team_df['outcomeType'] == 'Successful')])
        pass_accuracy = round((successful_passes / total_team_passes * 100), 1) if total_team_passes > 0 else 0

        # PPDA del rival automático
        rival_id = ateamID if team_id == hteamID else hteamID
        rival_df = df[df['teamId'] == rival_id]
        rival_passes = len(rival_df[
            (rival_df['type'] == 'Pass') &
            (rival_df['outcomeType'] == 'Successful') &
            (rival_df['x'] < 50)
        ])
        own_defensive = len(team_df[
            (team_df['type'].isin(['Tackle', 'Interception', 'BlockedPass', 'BallRecovery'])) &
            (team_df['x'] > 50)
        ])
        ppda = round(rival_passes / own_defensive, 1) if own_defensive > 0 else 0.0

        if ppda < 8:
            pressure_label = "PRESIÓN ALTA"
        elif ppda < 12:
            pressure_label = "PRESIÓN MEDIA"
        else:
            pressure_label = "PRESIÓN BAJA"

        # ===============================
        # FILTRAR CONEXIONES IMPORTANTES
        # ===============================
        threshold = passes_between_df.pass_count.quantile(0.80)
        passes_between_df = passes_between_df[
            passes_between_df.pass_count >= threshold
        ].copy()

        # ===============================
        # ESCALA AGRESIVA DE LÍNEAS: 1 + 12 * normalized
        # ===============================
        normalized_passes = (
            passes_between_df.pass_count / passes_between_df.pass_count.max()
        )
        passes_between_df['width'] = 1 + 12 * normalized_passes

        # ===============================
        # TRANSPARENCIA 0.15 → 0.85
        # ===============================
        MIN_TRANSPARENCY = 0.15
        MAX_TRANSPARENCY = 0.85
        color = np.array(to_rgba(col))
        color = np.tile(color, (len(passes_between_df), 1))
        c_transparency = (
            normalized_passes * (MAX_TRANSPARENCY - MIN_TRANSPARENCY) + MIN_TRANSPARENCY
        )
        color[:, 3] = c_transparency

        # ===============================
        # CAMPO
        # ===============================
        pitch = Pitch(
            pitch_type='uefa', goal_type='box', goal_alpha=.5,
            corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2
        )
        pitch.draw(ax=ax)

        # ===============================
        # CONVEX HULL — solo titulares top 50% participación
        # ===============================
        field_players = average_locs_and_count_df[
            (average_locs_and_count_df['position'] != 'GK') &
            (average_locs_and_count_df['isFirstEleven'] == True) &
            (average_locs_and_count_df['count'] >= average_locs_and_count_df['count'].quantile(0.50))
        ].copy()

        if len(field_players) >= 3:
            points = field_players[['pass_avg_x', 'pass_avg_y']].values
            hull = ConvexHull(points)
            hull_points = points[hull.vertices]
            polygon = Polygon(
                hull_points, closed=True, facecolor=col, edgecolor=col,
                linestyle='--', linewidth=1.2, alpha=0.06, zorder=0
            )
            ax.add_patch(polygon)

        # ===============================
        # CENTRO DE CREACIÓN — jugadores top 30%
        # Etiqueta en esquina opuesta a los jugadores para no interferir
        # ===============================
        hub_players = average_locs_and_count_df[
            average_locs_and_count_df['count'] >= average_locs_and_count_df['count'].quantile(0.70)
        ]
        if len(hub_players) > 0:
            creation_x = np.average(hub_players['pass_avg_x'], weights=hub_players['count'])
            creation_y = np.average(hub_players['pass_avg_y'], weights=hub_players['count'])
            pitch.scatter(creation_x, creation_y, s=1800, color=col, alpha=0.18, ax=ax, zorder=2)
            pitch.scatter(creation_x, creation_y, s=300, color=col, edgecolor='white', linewidth=2.5, ax=ax, zorder=8)
            # Local: etiqueta en esquina superior derecha (zona de portero rival)
            # Visitante: etiqueta en esquina superior izquierda (antes de invertir)
            if team_id == hteamID:
                lx, ly = 98, 62
            else:
                lx, ly = 7, 62
            ax.annotate('Centro de\ncreación', xy=(creation_x, creation_y),
                        xytext=(lx, ly),
                        fontsize=9, fontweight='bold', color=col,
                        ha='center', va='bottom',
                        bbox=dict(facecolor=bg_color, edgecolor=col, linewidth=0.8,
                                  alpha=0.9, boxstyle='round,pad=0.3'),
                        arrowprops=dict(arrowstyle='->', color=col, lw=1.0, alpha=0.7))
        # ===============================
        # LÍNEAS DE PASE
        # ===============================
        pitch.lines(
            passes_between_df.pass_avg_x, passes_between_df.pass_avg_y,
            passes_between_df.pass_avg_x_end, passes_between_df.pass_avg_y_end,
            lw=passes_between_df.width, color=color, zorder=1, ax=ax
        )

        # ===============================
        # NODOS — escala agresiva: 500 + 3500 * normalized_touches
        # ===============================
        max_count = average_locs_and_count_df['count'].max()
        for _, row in average_locs_and_count_df.iterrows():
            normalized_touches = row['count'] / max_count
            node_size = 500 + 3500 * normalized_touches
            if row['isFirstEleven']:
                pitch.scatter(row['pass_avg_x'], row['pass_avg_y'],
                              s=node_size, marker='o', color=bg_color, edgecolor=col,
                              linewidth=3.5, alpha=1, ax=ax, zorder=3)
            else:
                pitch.scatter(row['pass_avg_x'], row['pass_avg_y'],
                              s=node_size * 0.70, marker='o', color=bg_color, edgecolor=col,
                              linewidth=2, alpha=0.55, ax=ax, zorder=3)

        # ===============================
        # NOMBRES ABREVIADOS con fondo
        # Offset dinámico para reducir solapamientos
        # ===============================
        for _, row in average_locs_and_count_df.iterrows():
            parts = str(row['name']).split()
            if len(parts) == 1:
                label = parts[0]
            elif len(parts) == 2:
                label = f"{parts[0][0]}. {parts[1]}"
            else:
                label = f"{parts[0][0]}. {parts[-1]}"

            if row['pass_avg_y'] > 66:
                y_offset = 16
                va = 'bottom'
            else:
                y_offset = -18
                va = 'top'

            pitch.annotate(
                label, xy=(row.pass_avg_x, row.pass_avg_y),
                xytext=(0, y_offset), textcoords='offset points',
                ha='center', va=va, fontsize=11, fontweight='bold', color=col,
                ax=ax, zorder=5, bbox=dict(facecolor=bg_color, edgecolor='none', alpha=0.85)
            )

        # ===============================
        # ALTURA MEDIA — línea + etiqueta ABAJO del campo
        # ===============================
        team_height = average_locs_and_count_df.pass_avg_x.mean()
        ax.axvline(x=team_height, color=col, linestyle='--', alpha=0.35, linewidth=3)

        # ===============================
        # ALTURA DEFENSIVA — línea + etiqueta ABAJO del campo
        # ===============================
        defensive_players = average_locs_and_count_df[
            average_locs_and_count_df['position'].isin(['DC', 'DCR', 'DCL', 'DR', 'DL', 'RB', 'LB', 'CB'])
        ]
        if len(defensive_players) > 0:
            defensive_height = defensive_players['pass_avg_x'].mean()
            ax.axvline(x=defensive_height, color='#ff6b6b', linestyle='-.', linewidth=3, alpha=0.8)
            compactness = team_height - defensive_height
        else:
            defensive_height = team_height
            compactness = 0

        # Offset horizontal si las líneas están muy cerca (< 8m)
        too_close = abs(team_height - defensive_height) < 8
        th_offset = -3 if not too_close else (-3 if team_height > defensive_height else 3)
        dh_offset = -3 if not too_close else (-3 if defensive_height < team_height else 3)
        th_ha = 'center' if not too_close else ('right' if team_height > defensive_height else 'left')
        dh_ha = 'center' if not too_close else ('left' if defensive_height < team_height else 'right')

        # Etiqueta altura media
        ax.text(team_height + th_offset, -3, f'{team_height:.1f}m', color=col, fontsize=11,
                ha=th_ha, va='top', fontweight='bold',
                bbox=dict(facecolor=bg_color, edgecolor=col, linewidth=0.8,
                          alpha=0.95, boxstyle='round,pad=0.3'))
        ax.text(team_height + th_offset, -8, 'Altura media', color=col, fontsize=9,
                ha=th_ha, va='top', style='italic')

        # Etiqueta línea defensiva
        if len(defensive_players) > 0:
            ax.text(defensive_height + dh_offset, -3, f'{defensive_height:.1f}m', color='#ff6b6b',
                    fontsize=11, ha=dh_ha, va='top', fontweight='bold',
                    bbox=dict(facecolor=bg_color, edgecolor='#ff6b6b', linewidth=0.8,
                              alpha=0.95, boxstyle='round,pad=0.3'))
            ax.text(defensive_height + dh_offset, -8, 'Línea defensiva', color='#ff6b6b',
                    fontsize=9, ha=dh_ha, va='top', style='italic')

        # ===============================
        # MÉTRICAS — espacio en blanco arriba del campo
        # transform=ax.transAxes: coordenadas 0-1 relativas al ax
        # y=1.04 queda justo encima del campo, siempre visible
        # Funciona igual para local y visitante sin necesidad de invertir
        # ===============================
        ax.text(0.5, 1.04,
                f"RED DE PASES  |  {total_passes} conexiones  |  Precisión: {pass_accuracy}%  |  Compacidad: {compactness:.1f}m",
                fontsize=10, color=line_color, ha='center', fontweight='bold',
                transform=ax.transAxes,
                bbox=dict(facecolor=bg_color, edgecolor='none', alpha=0.8))
        ax.text(0.5, 1.01,
                f"PPDA Rival: {ppda}  —  {pressure_label}  |  Altura defensiva: {defensive_height:.1f}m",
                fontsize=9, color=line_color, ha='center',
                transform=ax.transAxes,
                bbox=dict(facecolor=bg_color, edgecolor='none', alpha=0.8))

        # ===============================
        # DIRECCIÓN DE ATAQUE
        # ===============================
        if team_id == hteamID:
            ax.text(-2, -5, "Dirección ataque --->", color=col, size=15, ha='left', va='center')
        else:
            ax.text(-2, 105, "<--- Dirección ataque", color=col, size=15, ha='right', va='center')

        # ===============================
        # INVERTIR CAMPO PARA EQUIPO VISITANTE
        # ===============================
        if team_id == ateamID:
            ax.invert_xaxis()
            ax.invert_yaxis()

        return pitch

    """Bloque defensivo"""

    def get_defensive_action_df(events_dict):
        df = pd.DataFrame(events_dict)
        df['eventType'] = df['type'].apply(lambda x: x.get('displayName', x) if isinstance(x, dict) else x)
        df['outcomeType'] = df['outcomeType'].apply(lambda x: x.get('displayName', x) if isinstance(x, dict) else x)

        # filtrar sólo acciones defensivas
        defensive_actions_ids = df.index[(df['eventType'] == 'Aerial') & (df['x'] <= 80) |
                                         (df['eventType'] == 'BallRecovery') |
                                         (df['eventType'] == 'BlockedPass') |
                                         (df['eventType'] == 'Challenge') |
                                         (df['eventType'] == 'Clearance') |
                                         (df['eventType'] == 'Error') |
                                         (df['eventType'] == 'Foul') |
                                         (df['eventType'] == 'Interception') |
                                         (df['eventType'] == 'Tackle')]
        df_defensive_actions = df.loc[defensive_actions_ids, ["id", "x", "y", "teamId", "playerId", "eventType", "outcomeType"]]

        return df_defensive_actions

    defensive_actions_df = get_defensive_action_df(events_dict)

    def get_da_count_df(team_id, defensive_actions_df, players_df):
        defensive_actions_df = defensive_actions_df[defensive_actions_df["teamId"] == team_id]
        # añadir columna con sólo los jugadores del 11 inicial
        defensive_actions_df = defensive_actions_df.merge(players_df[["playerId", "isFirstEleven"]], on='playerId', how='left')
        # calcular posiciones medias de los jugadores
        average_locs_and_count_df = (defensive_actions_df.groupby('playerId').agg({'x': ['median'], 'y': ['median', 'count']}))
        average_locs_and_count_df.columns = ['x', 'y', 'count']
        average_locs_and_count_df = average_locs_and_count_df.merge(players_df[['playerId', 'name', 'shirtNo', 'position', 'isFirstEleven']], on='playerId', how='left')
        average_locs_and_count_df = average_locs_and_count_df.set_index('playerId')

        return  average_locs_and_count_df

    defensive_home_average_locs_and_count_df = get_da_count_df(hteamID, defensive_actions_df, players_df)
    defensive_away_average_locs_and_count_df = get_da_count_df(ateamID, defensive_actions_df, players_df)
    defensive_home_average_locs_and_count_df = defensive_home_average_locs_and_count_df[defensive_home_average_locs_and_count_df['position'] != 'GK']
    defensive_away_average_locs_and_count_df = defensive_away_average_locs_and_count_df[defensive_away_average_locs_and_count_df['position'] != 'GK']

    def defensive_block(ax, average_locs_and_count_df, title, team_id, col):
      defensive_actions_team_df = defensive_actions_df[defensive_actions_df["teamId"] == team_id]
      pitch = Pitch(pitch_type='opta', pitch_color=bg_color, line_color=line_color, linewidth=2,
                    line_zorder=2, corner_arcs=True, goal_type='box', goal_alpha=.5)
      pitch.draw(ax=ax)
      ax.set_facecolor(bg_color)

      # Mapa de calor de acciones defensivas
      color = np.array(to_rgba(col))
      flamingo_cmap = LinearSegmentedColormap.from_list("Flamingo - 100 colors", [bg_color, col], N=500)
      kde = pitch.kdeplot(defensive_actions_team_df.x, defensive_actions_team_df.y,
                          ax=ax, fill=True, levels=5000, thresh=0.02, cut=4, cmap=flamingo_cmap)

      # Dispersión de acciones defensivas
      da_scatter = pitch.scatter(defensive_actions_team_df.x, defensive_actions_team_df.y,
                                  s=10, marker='x', color='orange', alpha=0.2, ax=ax)

      # ── NODOS escalados por participación defensiva ──────────────────────────────
      max_count = average_locs_and_count_df['count'].max()
      for _, row in average_locs_and_count_df.iterrows():
          normalized = row['count'] / max_count
          node_size = 500 + 3500 * normalized
          if row['isFirstEleven']:
              pitch.scatter(row['x'], row['y'],
                            s=node_size, marker='o',
                            color=bg_color, edgecolor=col,
                            linewidth=3.5, alpha=1, zorder=3, ax=ax)
          else:
              pitch.scatter(row['x'], row['y'],
                            s=node_size * 0.70, marker='o',
                            color=bg_color, edgecolor=col,
                            linewidth=2, alpha=0.55, zorder=3, ax=ax)

      # ── NOMBRES ABREVIADOS con fondo y offset dinámico ───────────────────────────
      for _, row in average_locs_and_count_df.iterrows():
          parts = str(row['name']).split()
          if len(parts) == 1:
              label = parts[0]
          elif len(parts) == 2:
              label = f"{parts[0][0]}. {parts[1]}"
          else:
              label = f"{parts[0][0]}. {parts[-1]}"

          if row['y'] > 66:
              y_offset = 16
              va = 'bottom'
          else:
              y_offset = -18
              va = 'top'

          pitch.annotate(
              label, xy=(row.x, row.y),
              xytext=(0, y_offset), textcoords='offset points',
              ha='center', va=va, fontsize=11, fontweight='bold', color=col,
              ax=ax, zorder=5, bbox=dict(facecolor=bg_color, edgecolor='none', alpha=0.85)
          )

      # ── ALTURA MEDIA DEFENSIVA ────────────────────────────────────────────────────
      dah = average_locs_and_count_df['x'].mean().round(2)
      dah_show = (dah * 1.05).round(2)
      ax.axvline(x=dah, color=col, linestyle='--', alpha=0.5, linewidth=2)

      # ── TÍTULOS ───────────────────────────────────────────────────────────────────
      if team_id == hteamID:
          ax.text(-2, -5, "Dirección ataque --->", color=hcol, size=15, ha='left', va='center')
          ax.text(dah + 1, -5, f"{dah_show}m", fontsize=15, color=col, ha='left', va='center',
                  bbox=dict(facecolor=bg_color, edgecolor=col, linewidth=0.8, alpha=0.9, boxstyle='round,pad=0.3'))
          ax.set_title(f"Posición defensiva media - Equipo local", color=line_color,
                       fontsize=30, fontweight='bold', path_effects=path_eff)
      else:
          ax.invert_xaxis()
          ax.invert_yaxis()
          ax.text(-2, 105, "<--- Dirección ataque", color=acol, size=15, ha='right', va='center')
          ax.text(dah + 1, 105, f"{dah_show}m", fontsize=15, color=col, ha='right', va='center',
                  bbox=dict(facecolor=bg_color, edgecolor=col, linewidth=0.8, alpha=0.9, boxstyle='round,pad=0.3'))
          ax.set_title(f"Posición defensiva media - Equipo visitante", color=line_color,
                       fontsize=30, fontweight='bold', path_effects=path_eff)

      return pitch

    """Pases progresivos"""

    # Filtrar los pases sin córners
    mask = df['teamId'] == ateamID
    dfapp = df[mask]
    dfapp = dfapp.loc[dfapp['type'] == "Pass"]
    dfapp = dfapp[~dfapp['qualifiers'].astype(str).str.contains('Corner')]

    mask = df['teamId'] == hteamID
    dfhpp = df[mask]
    dfhpp = dfhpp.loc[dfhpp['type'] == "Pass"]
    dfhpp = dfhpp[~dfhpp['qualifiers'].astype(str).str.contains('Corner')]

    def draw_progressive_pass_map(ax, df, title, col):
        pitch = Pitch(pitch_type='uefa', pitch_color=bg_color, line_color=line_color, linewidth=2,
                              corner_arcs=True, goal_type='box', goal_alpha=.5)
        pitch.draw(ax=ax)

        if title == ateamName:
          ax.invert_xaxis()
          ax.invert_yaxis()

        # filtrar sólo pases progresivos
        dfpro = df[df['pro'] >= 9.144]
        pro_count = len(dfpro)

        # calcular los conteos
        left_pro = len(dfpro[dfpro['y']>=45.33])
        mid_pro = len(dfpro[(dfpro['y']>=22.67) & (dfpro['y']<45.33)])
        right_pro = len(dfpro[(dfpro['y']>=0) & (dfpro['y']<22.67)])
        left_percentage = int((left_pro/pro_count)*100) if pro_count > 0 else 0
        mid_percentage = int((mid_pro/pro_count)*100) if pro_count > 0 else 0
        right_percentage = int((right_pro/pro_count)*100) if pro_count > 0 else 0

        ax.hlines(22.67, xmin=0, xmax=105, colors=line_color, linestyle='dashed', alpha=0.35)
        ax.hlines(45.33, xmin=0, xmax=105, colors=line_color, linestyle='dashed', alpha=0.35)

        # mostrar el texto en el campo
        if col == hcol:
          ax.text(27, 11.335, f'{right_pro}\n({right_percentage}%)', color=hcol, fontsize=24, va='center', ha='center')
          ax.text(27, 34, f'{mid_pro}\n({mid_percentage}%)', color=hcol, fontsize=24, va='center', ha='center')
          ax.text(27, 56.675, f'{left_pro}\n({left_percentage}%)', color=hcol, fontsize=24, va='center', ha='center')
        else:
          ax.text(27, 11.335, f'{right_pro}\n({right_percentage}%)', color=acol, fontsize=24, va='center', ha='center')
          ax.text(27, 34, f'{mid_pro}\n({mid_percentage}%)', color=acol, fontsize=24, va='center', ha='center')
          ax.text(27, 56.675, f'{left_pro}\n({left_percentage}%)', color=acol, fontsize=24, va='center', ha='center')

        # trazar los pases
        pro_pass = pitch.lines(dfpro.x, dfpro.y, dfpro.endX, dfpro.endY, lw=3.5, transparent=True, comet=True, color=col, ax=ax, alpha=0.5)
        # trazar algunos scatters al final de cada pase
        pro_pass_end = pitch.scatter(dfpro.endX, dfpro.endY, s=35, edgecolor=col, linewidth=1, color=bg_color, zorder=2, ax=ax)

        counttext = f"{pro_count} Pases progresivos"

        # Títulos y otros textos
        if col == hcol:
          ax.text(0,-5, "Dirección ataque --->", color=hcol, size=15, ha='left', va='center')
          ax.set_title(f"Equipo local:{counttext}", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)
        else:
          ax.text(0,73, "<--- Dirección ataque", color=acol, size=15, ha='right', va='center')
          ax.set_title(f"Equipo visitante:{counttext}", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)

    """*Zonas* peligrosas de pases"""

    # filtrar pases sin córners
    dfhp = df.loc[df['teamId'] == hteamID]
    dfhp = dfhp.loc[dfhp['type'] == "Pass"]
    dfhp = dfhp.loc[dfhp['outcomeType'] == "Successful"]
    dfhp = dfhp[~dfhp['qualifiers'].astype(str).str.contains('Corner')]

    dfap = df.loc[df['teamId'] == ateamID]
    dfap = dfap.loc[dfap['type'] == "Pass"]
    dfap = dfap.loc[dfap['outcomeType'] == "Successful"]
    dfap = dfap[~dfap['qualifiers'].astype(str).str.contains('Corner')]

    def draw_pass_map(ax, df, title, col):
        pitch = Pitch(pitch_type='uefa', pitch_color=bg_color, line_color=line_color,  linewidth=2,
                              corner_arcs=True, goal_type='box', goal_alpha=.5)
        pitch.draw(ax=ax)
        ax.set_facecolor(bg_color)
        if title == ateamName:
          ax.invert_xaxis()
          ax.invert_yaxis()


        z14 = 0
        hs = 0

        # iterando cada pase y de acuerdo con las condiciones trazando solo pases de zona 14 e intervalos
        for index, row in df.iterrows():
            if row['endX'] >= 70 and row['endX'] <= 88.54 and row['endY'] >= 22.66 and row['endY'] <= 45.32:
                arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', alpha=0.75, mutation_scale=20, color='orange', linewidth=1.5)
                ax.add_patch(arrow)
                z14 += 1
            if row['endX'] >= 70 and row['endY'] >= 11.33 and row['endY'] <= 22.66:
                arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', alpha=0.75, mutation_scale=20, color=col, linewidth=1.5)
                ax.add_patch(arrow)
                hs += 1
            if row['endX'] >= 70 and row['endY'] >= 45.32 and row['endY'] <= 56.95:
                arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', alpha=0.75, mutation_scale=20, color=col, linewidth=1.5)
                ax.add_patch(arrow)
                hs += 1

        # colorear zonas del campo
        y_z14 = [22.66, 22.66, 45.32, 45.32]
        x_z14 = [70, 88.54, 88.54, 70]
        ax.fill(x_z14, y_z14, 'orange', alpha=0.2, label='Zone14')

        y_rhs = [11.33, 11.33, 22.66, 22.66]
        x_rhs = [70, 105, 105, 70]
        ax.fill(x_rhs, y_rhs, col, alpha=0.2, label='HalfSpaces')

        y_lhs = [45.32, 45.32, 56.95, 56.95]
        x_lhs = [70, 105, 105, 70]
        ax.fill(x_lhs, y_lhs, col, alpha=0.2, label='HalfSpaces')

        # mostrando los conteos de una manera atractiva
        z14name = "Zona 14"
        hsname = "Intervalos"
        z14count = f"{z14}"
        hscount = f"{hs}"
        ax.scatter(16.46, 13.85, color=col, s=15000, edgecolor=line_color, linewidth=2, alpha=1, marker='h')
        ax.scatter(16.46, 54.15, color='orange', s=15000, edgecolor=line_color, linewidth=2, alpha=1, marker='h')
        ax.text(16.46, 13.85-4, hsname, fontsize=20, color=line_color, ha='center', va='center', path_effects=path_eff)
        ax.text(16.46, 54.15-4, z14name, fontsize=20, color=line_color, ha='center', va='center', path_effects=path_eff)
        ax.text(16.46, 13.85+2, hscount, fontsize=40, color=line_color, ha='center', va='center', path_effects=path_eff)
        ax.text(16.46, 54.15+2, z14count, fontsize=40, color=line_color, ha='center', va='center', path_effects=path_eff)

        # Títulos y otros textos
        if col == hcol:
          ax.text(0,-5, "Dirección ataque --->", color=hcol, size=15, ha='left', va='center')
          ax.set_title(f"Zona 14 e Intervalos - Equipo local", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)
        else:
          ax.text(0,73, "<--- Dirección ataque", color=acol, size=15, ha='right', va='center')
          ax.set_title(f"Zona 14 e Intervalos - Equipo visitante", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)

    """Zona final de pases"""

    # filtrar sólo pases efectivos
    mask2 = (df['teamId'] == hteamID) & (df['type'] == 'Pass') & (df['outcomeType'] == 'Successful')
    hdfPEZ = df[mask2]
    mask2 = (df['teamId'] == ateamID) & (df['type'] == 'Pass') & (df['outcomeType'] == 'Successful')
    adfPEZ = df[mask2]

    # configurar el mapa de colores
    pearl_earring_cmaph = LinearSegmentedColormap.from_list("Pearl Earring - 10 colors",
                                                           [bg_color, hcol], N=20)
    pearl_earring_cmapa = LinearSegmentedColormap.from_list("Pearl Earring - 10 colors",
                                                           [bg_color, acol], N=20)

    path_eff = [path_effects.Stroke(linewidth=3, foreground=bg_color),
                path_effects.Normal()]

    def Pass_end_zone(ax, df, title, cm, tcm):
        pitch = Pitch(pitch_type='uefa', line_color=line_color, goal_type='box', goal_alpha=.5, corner_arcs=True, line_zorder=2, pitch_color=bg_color, linewidth=2)
        pitch.draw(ax=ax)
        if title == ateamName:
          ax.invert_xaxis()
          ax.invert_yaxis()

        pearl_earring_cmap = cm
        # agrupando los puntos de datos
        bin_statistic = pitch.bin_statistic_positional(df.endX, df.endY, statistic='count', positional='full', normalize=True)
        pitch.heatmap_positional(bin_statistic, ax=ax, cmap=pearl_earring_cmap, edgecolors=bg_color)
        pitch.scatter(df.endX, df.endY, c='gray', s=5, ax=ax)
        labels = pitch.label_heatmap(bin_statistic, color=line_color, fontsize=30, ax=ax, ha='center', va='center', str_format='{:.0%}', path_effects=path_eff)
        teamName = title

        # Títulos y otros textos
        if tcm == hcol:
          ax.text(0,-5, "Dirección ataque --->", color=hcol, size=15, ha='left', va='center')
          ax.set_title(f"Zonas principales de pase - Equipo local", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)
        else:
          ax.text(0,73, "<--- Dirección ataque", color=acol, size=15, ha='right', va='center')
          ax.set_title(f"Zonas principales de pase - Equipo visitante", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)

    """Zonas de creación de oportunidades"""

    # filtrar sólo pases clave
    mask3 = (df['teamId'] == hteamID) & (df['qualifiers'].astype(str).str.contains('KeyPass', na=False))
    dfchch = df[mask3]
    mask3 = (df['teamId'] == ateamID) & (df['qualifiers'].astype(str).str.contains('KeyPass', na=False))
    dfchca = df[mask3]

    # personalizar colores
    pearl_earring_cmaph = LinearSegmentedColormap.from_list("Pearl Earring - 10 colors", [bg_color, hcol], N=20)
    pearl_earring_cmapa = LinearSegmentedColormap.from_list("Pearl Earring - 10 colors", [bg_color, acol], N=20)

    path_eff = [path_effects.Stroke(linewidth=3, foreground=bg_color), path_effects.Normal()]

    def Chance_creating_zone(ax, df, title, cm, tcm):
        pitch = Pitch(pitch_type='uefa', line_color=line_color, goal_type='box', goal_alpha=.5, corner_arcs=True, line_zorder=2, pitch_color=bg_color, linewidth=2)
        pitch.draw(ax=ax)
        if title == ateamName:
          ax.invert_xaxis()
          ax.invert_yaxis()

        cc = 0
        pearl_earring_cmap = cm
        bin_statistic = pitch.bin_statistic_positional(df.x, df.y, statistic='count', positional='full', normalize=False)
        pitch.heatmap_positional(bin_statistic, ax=ax, cmap=pearl_earring_cmap, edgecolors='gray')
        pitch.scatter(df.x, df.y, c='gray', s=5, ax=ax)
        for index, row in df.iterrows():
          if 'IntentionalGoalAssist' in row['qualifiers']:
            arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', mutation_scale=20, color=green, linewidth=1.25, alpha=1)
            ax.add_patch(arrow)
            cc += 1
          else :
            arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', mutation_scale=20, color=violet, linewidth=1.25, alpha=1)
            ax.add_patch(arrow)
            cc += 1
        labels = pitch.label_heatmap(bin_statistic, color=line_color, fontsize=30, ax=ax, ha='center', va='center', str_format='{:.0f}', path_effects=path_eff)
        teamName = title

        # Títulos y otros textos
        if tcm == hcol:
          ax.text(105,-3.5, "flecha lila = pases clave\nflecha verde = asistencia", color=hcol, size=15, ha='right', va='center')
          ax.text(0,-5, "Dirección ataque --->", color=hcol, size=15, ha='left', va='center')
          ax.text(52.5,70, f"Oportunidades claras creadas = {cc}", color=tcm, fontsize=15, ha='center', va='center')
          ax.set_title(f"Zonas de creación de más peligro", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)
        else:
          ax.text(105,71.5, "flecha lila = pases clave\nflecha verde = asistencia", color=acol, size=15, ha='left', va='center')
          ax.text(0,73, "<--- Dirección ataque", color=acol, size=15, ha='right', va='center')
          ax.text(52.5,-2, f"Oportunidades claras creadas = {cc}", color=tcm, fontsize=15, ha='center', va='center')
          ax.set_title(f"Zonas de creación de más peligro", color=line_color, fontsize=30, fontweight='bold', path_effects=path_eff)

    """Mapa de tiros"""

    # filtrando sólo disparos
    mask4 = (df['type'] == 'Goal') | (df['type'] == 'MissedShots') | (df['type'] == 'SavedShot') | (df['type'] == 'ShotOnPost')
    Shotsdf = df[mask4]
    Shotsdf.reset_index(drop=True, inplace=True)

    # filtrando según el tipo de tiro
    hShotsdf = Shotsdf[Shotsdf['teamId']==hteamID]
    aShotsdf = Shotsdf[Shotsdf['teamId']==ateamID]
    hSavedf = hShotsdf[(hShotsdf['type']=='SavedShot') & (~hShotsdf['qualifiers'].astype(str).str.contains(': 82,'))]
    aSavedf = aShotsdf[(aShotsdf['type']=='SavedShot') & (~aShotsdf['qualifiers'].astype(str).str.contains(': 82,'))]
    hogdf = hShotsdf[(hShotsdf['teamId']==hteamID) & (hShotsdf['qualifiers'].astype(str).str.contains('OwnGoal'))]
    aogdf = aShotsdf[(aShotsdf['teamId']==ateamID) & (aShotsdf['qualifiers'].astype(str).str.contains('OwnGoal'))]

    # estadísticas de tiros
    hTotalShots = len(hShotsdf)
    aTotalShots = len(aShotsdf)
    hShotsOnT = len(hSavedf) + hgoal_count
    aShotsOnT = len(aSavedf) + agoal_count
    hxGpSh = round(hxg/hTotalShots, 2) if hTotalShots > 0 else 0
    axGpSh = round(axg/aTotalShots, 2) if aTotalShots > 0 else 0
    # punto central de la portería
    given_point = (105, 34)
    # Cálculo de distancias
    home_shot_distances = np.sqrt((hShotsdf['x'] - given_point[0])**2 + (hShotsdf['y'] - given_point[1])**2)
    home_average_shot_distance = round(home_shot_distances.mean(),2)
    away_shot_distances = np.sqrt((aShotsdf['x'] - given_point[0])**2 + (aShotsdf['y'] - given_point[1])**2)
    away_average_shot_distance = round(away_shot_distances.mean(),2)

    def plot_shotmap(ax):
        pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.5, corner_arcs=True, pitch_color=bg_color, linewidth=2, line_color=line_color)
        pitch.draw(ax=ax)
        # sin grandes ocasiones para el equipo local
        hGoalData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'Goal') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        hPostData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'ShotOnPost') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        hSaveData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'SavedShot') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        hMissData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'MissedShots') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        # sólo grandes ocasiones del equipo local
        Big_C_hGoalData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'Goal') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_hPostData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'ShotOnPost') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_hSaveData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'SavedShot') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_hMissData = Shotsdf[(Shotsdf['teamId'] == hteamID) & (Shotsdf['type'] == 'MissedShots') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        # tiros normales equipo local
        sc2 = pitch.scatter((105-hPostData.x), (68-hPostData.y), s=200, edgecolors=hcol, c=hcol, marker='o', ax=ax)
        sc3 = pitch.scatter((105-hSaveData.x), (68-hSaveData.y), s=200, edgecolors=hcol, c='None', hatch='///////', marker='o', ax=ax)
        sc4 = pitch.scatter((105-hMissData.x), (68-hMissData.y), s=200, edgecolors=hcol, c='None', marker='o', ax=ax)
        sc1 = pitch.scatter((105-hGoalData.x), (68-hGoalData.y), s=350, edgecolors='green', linewidths=0.6, c='None', marker='football', zorder=3, ax=ax)
        sc1_og = pitch.scatter((105-hogdf.x), (68-hogdf.y), s=350, edgecolors='orange', linewidths=0.6, c='None', marker='football', zorder=3, ax=ax)
        # mejores ocasiones dispersas equipo local
        bc_sc2 = pitch.scatter((105-Big_C_hPostData.x), (68-Big_C_hPostData.y), s=500, edgecolors=hcol, c=hcol, marker='o', ax=ax)
        bc_sc3 = pitch.scatter((105-Big_C_hSaveData.x), (68-Big_C_hSaveData.y), s=500, edgecolors=hcol, c='None', hatch='///////', marker='o', ax=ax)
        bc_sc4 = pitch.scatter((105-Big_C_hMissData.x), (68-Big_C_hMissData.y), s=500, edgecolors=hcol, c='None', marker='o', ax=ax)
        bc_sc1 = pitch.scatter((105-Big_C_hGoalData.x), (68-Big_C_hGoalData.y), s=650, edgecolors='green', linewidths=0.6, c='None', marker='football', ax=ax)

        # sin grandes ocasiones para el equipo local
        aGoalData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'Goal') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        aPostData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'ShotOnPost') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        aSaveData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'SavedShot') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        aMissData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'MissedShots') & (~Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        # sólo grandes ocasiones del equipo local
        Big_C_aGoalData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'Goal') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_aPostData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'ShotOnPost') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_aSaveData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'SavedShot') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        Big_C_aMissData = Shotsdf[(Shotsdf['teamId'] == ateamID) & (Shotsdf['type'] == 'MissedShots') & (Shotsdf['qualifiers'].astype(str).str.contains('BigChance'))]
        # tiros normales equipo local
        sc6 = pitch.scatter(aPostData.x, aPostData.y, s=200, edgecolors=acol, c=acol, marker='o', ax=ax)
        sc7 = pitch.scatter(aSaveData.x, aSaveData.y, s=200, edgecolors=acol, c='None', hatch='///////', marker='o', ax=ax)
        sc8 = pitch.scatter(aMissData.x, aMissData.y, s=200, edgecolors=acol, c='None', marker='o', ax=ax)
        sc5 = pitch.scatter(aGoalData.x, aGoalData.y, s=350, edgecolors='green', linewidths=0.6, c='None', marker='football', zorder=3, ax=ax)
        sc5_og = pitch.scatter((aogdf.x), (aogdf.y), s=350, edgecolors='orange', linewidths=0.6, c='None', marker='football', zorder=3, ax=ax)
        # mejores ocasiones dispersas equipo local
        bc_sc6 = pitch.scatter(Big_C_aPostData.x, Big_C_aPostData.y, s=500, edgecolors=acol, c=acol, marker='o', ax=ax)
        bc_sc7 = pitch.scatter(Big_C_aSaveData.x, Big_C_aSaveData.y, s=500, edgecolors=acol, c='None', hatch='///////', marker='o', ax=ax)
        bc_sc8 = pitch.scatter(Big_C_aMissData.x, Big_C_aMissData.y, s=500, edgecolors=acol, c='None', marker='o', ax=ax)
        bc_sc5 = pitch.scatter(Big_C_aGoalData.x, Big_C_aGoalData.y, s=650, edgecolors='green', linewidths=0.6, c='None', marker='football', ax=ax)

        # Estadísticas diagrama
        shooting_stats_title = [55, 55-(1*7), 55-(2*7), 55-(3*7), 55-(4*7), 55-(5*7), 55-(6*7)]
        shooting_stats_home = [hgoal_count, hxg, hxgot, hTotalShots, hShotsOnT, hxGpSh, home_average_shot_distance]
        shooting_stats_away = [agoal_count, axg, axgot, aTotalShots, aShotsOnT, axGpSh, away_average_shot_distance]

        # A veces ambos equipos terminan el partido 0-0, luego normalizar los datos se convierte en un problema, por eso esta parte del código.
        if hgoal_count+agoal_count == 0:
          hgoal = 10
          agoal = 10
        else:
          hgoal = (hgoal_count/(hgoal_count+agoal_count))*20
          agoal = (agoal_count/(hgoal_count+agoal_count))*20

        def _sr(a, b, scale=20):
            return (a / (a + b)) * scale if (a + b) > 0 else 0

        shooting_stats_normalized_home = [
            hgoal, _sr(hxg, axg), _sr(hxgot, axgot),
            _sr(hTotalShots, aTotalShots), _sr(hShotsOnT, aShotsOnT),
            _sr(hxGpSh, axGpSh), _sr(home_average_shot_distance, away_average_shot_distance)
        ]
        shooting_stats_normalized_away = [
            agoal, _sr(axg, hxg), _sr(axgot, hxgot),
            _sr(aTotalShots, hTotalShots), _sr(aShotsOnT, hShotsOnT),
            _sr(axGpSh, hxGpSh), _sr(away_average_shot_distance, home_average_shot_distance)
        ]

        # definiendo punto de inicio
        start_x = 42.5
        start_x_for_away = [x + 42.5 for x in shooting_stats_normalized_home]
        ax.barh(shooting_stats_title, shooting_stats_normalized_home, height=5, color=hcol, left=start_x)
        ax.barh(shooting_stats_title, shooting_stats_normalized_away, height=5, left=start_x_for_away, color=acol)
        # Desactivar elementos relacionados con ejes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False)
        ax.set_xticks([])
        ax.set_yticks([])

        # generar textos
        ax.text(52.5, 55, "Goles", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(1*7), "xG", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(2*7), "xGOT", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(3*7), "Tiros", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(4*7), "A puerta", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(5*7), "xG/Tiros", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')
        ax.text(52.5, 55-(6*7), "Dis.Med.", color=bg_color, fontsize=18, ha='center', va='center', fontweight='bold')

        ax.text(41.5, 55, f"{hgoal_count}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(1*7), f"{hxg}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(2*7), f"{hxgot}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(3*7), f"{hTotalShots}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(4*7), f"{hShotsOnT}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(5*7), f"{hxGpSh}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')
        ax.text(41.5, 55-(6*7), f"{home_average_shot_distance}", color=line_color, fontsize=18, ha='right', va='center', fontweight='bold')

        ax.text(63.5, 55, f"{agoal_count}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(1*7), f"{axg}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(2*7), f"{axgot}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(3*7), f"{aTotalShots}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(4*7), f"{aShotsOnT}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(5*7), f"{axGpSh}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')
        ax.text(63.5, 55-(6*7), f"{away_average_shot_distance}", color=line_color, fontsize=18, ha='left', va='center', fontweight='bold')

        # Títulos y otros textos
        ax.text(0, 70, f"Tiros equipo local", color=hcol, size=25, ha='left', fontweight='bold', path_effects=path_eff)
        ax.text(105, 70, f"Tiros equipo visitante", color=acol, size=25, ha='right', fontweight='bold', path_effects=path_eff)
        highlight_text = [{'color':hcol}, {'color':acol}]
        ax_text(52.5, 116, f"<{hteamName} {hgoal_count}> - <{agoal_count} {ateamName}>", color=line_color, fontsize=52, fontweight='bold',
                highlight_textprops=highlight_text, ha='center', va='center', ax=ax)
        ax.text(52.5, 110, "________________________________________________________________________________________________________________________________________________________________________________________________________________________________",
              color=line_color, fontsize=20, va='center', ha='center')
        ax.text(52.5, 125, "________________________________________________________________________________________________________________________________________________________________________________________________________________________________",
              color=line_color, fontsize=20, va='center', ha='center')
        ax.text(52.5, 103, f"Jornada {gw} | {league} | {date}", color=line_color, fontsize=25, ha='center', va='center')

    """**Portero** rendimiento"""

    def plot_goalPost(ax):
      hShotsdf = Shotsdf[Shotsdf['teamId']==hteamID].copy()
      aShotsdf = Shotsdf[Shotsdf['teamId']==ateamID].copy()
      # convertir los puntos de datos de acuerdo con la dimensión del campo, porque los postes de la portería se trazan dentro del campo usando la dimensión del campo
      hShotsdf['goalMouthZ'] = hShotsdf['goalMouthZ']*0.75
      aShotsdf['goalMouthZ'] = (aShotsdf['goalMouthZ']*0.75) + 38

      hShotsdf['goalMouthY'] = (37.66 - hShotsdf['goalMouthY'])*12.295
      aShotsdf['goalMouthY'] = (37.66 - aShotsdf['goalMouthY'])*12.295

      # Trazar un campo invisible usando el color del campo y el color de la línea del mismo color, porque los postes se trazan dentro del campo usando la dimensión del campo.
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=bg_color, linewidth=2)
      pitch.draw(ax=ax)

      # líneas de portería visitante
      ax.plot([0, 0], [-1, 30], color=line_color, linewidth=5)
      ax.plot([0, 90], [30, 30], color=line_color, linewidth=5)
      ax.plot([90, 90], [30, -1], color=line_color, linewidth=5)
      ax.plot([-2, 92], [-2, -2], color=line_color, linewidth=3)
      # líneas de portería local
      ax.plot([0, 0], [37, 68], color=line_color, linewidth=5)
      ax.plot([0, 90], [68, 68], color=line_color, linewidth=5)
      ax.plot([90, 90], [68, 37], color=line_color, linewidth=5)
      ax.plot([-2, 92], [36, 36], color=line_color, linewidth=3)

      # filtrar según tipo de disparo
      hSavedf = hShotsdf[(hShotsdf['type']=='SavedShot') & (~hShotsdf['qualifiers'].astype(str).str.contains(': 82,'))]
      hGoaldf = hShotsdf[(hShotsdf['type']=='Goal') & (~hShotsdf['qualifiers'].astype(str).str.contains('OwnGoal'))]
      hPostdf = hShotsdf[hShotsdf['type']=='ShotOnPost']
      aSavedf = aShotsdf[(aShotsdf['type']=='SavedShot') & (~aShotsdf['qualifiers'].astype(str).str.contains(': 82,'))]
      aGoaldf = aShotsdf[(aShotsdf['type']=='Goal') & (~aShotsdf['qualifiers'].astype(str).str.contains('OwnGoal'))]
      aPostdf = aShotsdf[aShotsdf['type']=='ShotOnPost']

      # dispersando esos tiros
      sc1 = pitch.scatter(hSavedf.goalMouthY, hSavedf.goalMouthZ, marker='o', c='None', edgecolor=acol, hatch='/////', s=400, ax=ax)
      sc2 = pitch.scatter(hGoaldf.goalMouthY, hGoaldf.goalMouthZ, marker='football', c='None', edgecolors='green', s=550, ax=ax)
      sc3 = pitch.scatter(hPostdf.goalMouthY, hPostdf.goalMouthZ, marker='o', c='None', edgecolors='orange', hatch='/////', s=400, ax=ax)
      sc4 = pitch.scatter(aSavedf.goalMouthY, aSavedf.goalMouthZ, marker='o', c='None', edgecolor=hcol, hatch='/////', s=400, ax=ax)
      sc5 = pitch.scatter(aGoaldf.goalMouthY, aGoaldf.goalMouthZ, marker='football', c='None', edgecolors='green', s=550, ax=ax)
      sc6 = pitch.scatter(aPostdf.goalMouthY, aPostdf.goalMouthZ, marker='o', c='None', edgecolors='orange', hatch='/////', s=400, ax=ax)

      # Títulos y otros textos
      ax.text(0, 70, f"Paradas - Portero local", color=hcol, fontsize=30, ha='left', fontweight='bold')
      ax.text(0, -3, f"Paradas - Portero visitante", color=acol, fontsize=30, ha='left', va='top', fontweight='bold')

      ax.text(92, 68, f"xG = {axgot}\nParadas = {len(aSavedf)}\nGoles concedidos = {len(aGoaldf)}\nGoles evitados = {round(axgot - len(aGoaldf),2)}",
              color=hcol, fontsize=15, va='top', ha='left')
      ax.text(92, 30, f"xG = {hxgot}\nParadas = {len(hSavedf)}\nGoles concedidos = {len(hGoaldf)}\nGoles evitados = {round(hxgot - len(hGoaldf),2)}",
              color=acol, fontsize=15, va='top', ha='left')

      sc7  = pitch.scatter(94, 48, marker='o', c='None', edgecolor=hcol, hatch='/////', s=150, ax=ax)
      sc8  = pitch.scatter(94, 53, marker='football', c='None', edgecolors='green', s=150, ax=ax)
      sc9  = pitch.scatter(94, 43, marker='o', c='None', edgecolors='orange', hatch='/////', s=150, ax=ax)
      sc10 = pitch.scatter(94, 10, marker='o', c='None', edgecolor=acol, hatch='/////', s=150, ax=ax)
      sc11 = pitch.scatter(94, 15, marker='football', c='None', edgecolors='green', s=150, ax=ax)
      sc12 = pitch.scatter(94, 5, marker='o', c='None', edgecolors='orange', hatch='/////', s=150, ax=ax)

      ax.text(96, 53, "Goles concedidos", color='green', fontsize=15, va='center')
      ax.text(96, 48, "Tiros parados", color=hcol, fontsize=15, va='center')
      ax.text(96, 43, "Tiros al poste", color='orange', fontsize=15, va='center')

      ax.text(96, 15, "Goles concedidos", color='green', fontsize=15, va='center')
      ax.text(96, 10, "Tiros parados", color=acol, fontsize=15, va='center')
      ax.text(96, 5, "Tiros al poste", color='orange', fontsize=15, va='center')

    """*Momentum* del partido según xT"""

    Momentumdf = df.copy()
    # Multiplicar los valores xT del equipo visitante por -1 para trazarlos en el lado opuesto.
    # Al operar sobre una copia, este paso es idempotente: se puede re-ejecutar sin acumular errores.
    Momentumdf.loc[Momentumdf['teamId'] == ateamID, 'start_zone_value_xT'] *= -1
    # tomando xT promedio por minuto
    Momentumdf = Momentumdf.groupby('minute')['start_zone_value_xT'].mean()
    Momentumdf = Momentumdf.reset_index()
    Momentumdf.columns = ['minute', 'average_xT']
    Momentumdf['average_xT'].fillna(0, inplace=True)

    def plot_Momentum(ax):
      # Establecer colores basados en valores positivos o negativos
      colors = [hcol if x > 0 else acol for x in Momentumdf['average_xT']]

      # hacer una lista de los minutos en los que se marcan los goles
      hgoal_list = homedf[(homedf['type'] == 'Goal') & (~homedf['qualifiers'].astype(str).str.contains('OwnGoal'))]['minute'].tolist()
      agoal_list = awaydf[(awaydf['type'] == 'Goal') & (~awaydf['qualifiers'].astype(str).str.contains('OwnGoal'))]['minute'].tolist()
      hog_list = homedf[(homedf['type'] == 'Goal') & (homedf['qualifiers'].astype(str).str.contains('OwnGoal'))]['minute'].tolist()
      aog_list = awaydf[(awaydf['type'] == 'Goal') & (awaydf['qualifiers'].astype(str).str.contains('OwnGoal'))]['minute'].tolist()

      # trazar dibujo de balón cuando se marcan goles
      highest_xT = Momentumdf['average_xT'].max()
      lowest_xT = Momentumdf['average_xT'].min()
      highest_minute = Momentumdf['minute'].max()
      hscatter_y = [highest_xT]*len(hgoal_list)
      ascatter_y = [lowest_xT]*len(agoal_list)
      hogscatter_y = [highest_xT]*len(aog_list)
      aogscatter_y = [lowest_xT]*len(hog_list)

      ax.scatter(hgoal_list, hscatter_y, s=250, c='None', edgecolor='green', hatch='////', marker='o')
      ax.scatter(agoal_list, ascatter_y, s=250, c='None', edgecolor='green', hatch='////', marker='o')
      ax.scatter(hog_list, aogscatter_y, s=250, c='None', edgecolor='orange', hatch='////', marker='o')
      ax.scatter(aog_list, hogscatter_y, s=250, c='None', edgecolor='orange', hatch='////', marker='o')

      # Creando el diagrama de barras
      ax.bar(Momentumdf['minute'], Momentumdf['average_xT'], color=colors)
      ax.axvline(45, color='gray', linewidth=2, linestyle='dashed')
      ax.set_facecolor(bg_color)
      # Ocultar espinas
      ax.spines['top'].set_visible(False)
      ax.spines['right'].set_visible(False)
      ax.spines['left'].set_visible(False)
      ax.spines['bottom'].set_visible(False)
      # Ocultar ticks
      ax.tick_params(axis='both', which='both', length=0)
      ax.tick_params(axis='x', colors=line_color)
      ax.tick_params(axis='y', colors=line_color)
      # Añadir etiquetas y títulos
      ax.set_xlabel('Minuto', color=line_color, fontsize=20)
      ax.set_ylabel('xT por minuto', color=line_color, fontsize=20)
      ax.axhline(y=0, color=line_color, alpha=1, linewidth=2)

      ax.text(highest_minute+1,highest_xT, f"Equipo local\nxT: {hxT}", color=hcol, fontsize=20, va='bottom', ha='left')
      ax.text(highest_minute+1,lowest_xT,  f"Equipo visitante\nxT: {axT}", color=acol, fontsize=20, va='top', ha='left')

      ax.set_title('xT - Control/Dominio del juego', color=line_color, fontsize=30, fontweight='bold')

    fig, ax = plt.subplots()
    plot_Momentum(ax)

    """**Estadísticas** Pases"""

    # Aquí he calculado muchas estadísticas, todas ellas no las pude mostrar en la visualización debido a la falta de espacios, pero las mantuve en el código.
    #Posesión%
    hpossdf = df[(df['teamId']==hteamID) & (df['type']=='Pass')]
    apossdf = df[(df['teamId']==ateamID) & (df['type']=='Pass')]
    hposs = round((len(hpossdf)/(len(hpossdf)+len(apossdf)))*100,2)
    aposs = round((len(apossdf)/(len(hpossdf)+len(apossdf)))*100,2)
    #% de inclinación del campo
    hftdf = df[(df['teamId']==hteamID) & (df['isTouch']==1) & (df['x']>=70)]
    aftdf = df[(df['teamId']==ateamID) & (df['isTouch']==1) & (df['x']>=70)]
    hft = round((len(hftdf)/(len(hftdf)+len(aftdf)))*100,2)
    aft = round((len(aftdf)/(len(hftdf)+len(aftdf)))*100,2)
    # pases totales
    htotalPass = len(df[(df['teamId']==hteamID) & (df['type']=='Pass')])
    atotalPass = len(df[(df['teamId']==ateamID) & (df['type']=='Pass')])
    # pases efectivos
    hAccPass = len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['outcomeType']=='Successful')])
    aAccPass = len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['outcomeType']=='Successful')])
    # balones largos
    hLongB = len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Longball')) & (~df['qualifiers'].astype(str).str.contains('Corner')) & (~df['qualifiers'].astype(str).str.contains('Cross'))])
    aLongB = len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Longball')) & (~df['qualifiers'].astype(str).str.contains('Corner')) & (~df['qualifiers'].astype(str).str.contains('Cross'))])
    # balones largos efectivos
    hAccLongB = len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Longball')) & (df['outcomeType']=='Successful') & (~df['qualifiers'].astype(str).str.contains('Corner')) & (~df['qualifiers'].astype(str).str.contains('Cross'))])
    aAccLongB = len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Longball')) & (df['outcomeType']=='Successful') & (~df['qualifiers'].astype(str).str.contains('Corner')) & (~df['qualifiers'].astype(str).str.contains('Cross'))])
    # centros
    hCrss= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross'))])
    aCrss= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross'))])
    # centros efectivos
    hAccCrss= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross')) & (df['outcomeType']=='Successful')])
    aAccCrss= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross')) & (df['outcomeType']=='Successful')])
    # tiros libres
    hfk= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Freekick'))])
    afk= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Freekick'))])
    # Corner
    hCor= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Corner'))])
    aCor= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Corner'))])
    # saque de banda
    htins= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('ThrowIn'))])
    atins= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('ThrowIn'))])
    # saque de centro
    hglkk= len(df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('GoalKick'))])
    aglkk= len(df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('GoalKick'))])
    # regate
    htotalDrb = len(df[(df['teamId']==hteamID) & (df['type']=='TakeOn') & (df['qualifiers'].astype(str).str.contains('Offensive'))])
    atotalDrb = len(df[(df['teamId']==ateamID) & (df['type']=='TakeOn') & (df['qualifiers'].astype(str).str.contains('Offensive'))])
    # entrada efectiva
    hAccDrb = len(df[(df['teamId']==hteamID) & (df['type']=='TakeOn') & (df['qualifiers'].astype(str).str.contains('Offensive')) & (df['outcomeType']=='Successful')])
    aAccDrb = len(df[(df['teamId']==ateamID) & (df['type']=='TakeOn') & (df['qualifiers'].astype(str).str.contains('Offensive')) & (df['outcomeType']=='Successful')])
    # Longitud del saque de meta
    home_goalkick = df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('GoalKick'))].copy()
    away_goalkick = df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('GoalKick'))].copy()
    # Función para extraer el valor de 'Length' — funciona tanto con dicts como con strings
    def extract_length(qualifiers):
        if isinstance(qualifiers, list):
            items = qualifiers
        else:
            try:
                items = ast.literal_eval(str(qualifiers))
            except Exception:
                return None
        for item in items:
            t = item.get('type', {})
            name = t.get('displayName', '') if isinstance(t, dict) else ''
            if name == 'Length':
                try:
                    return float(item.get('value', 0))
                except (ValueError, TypeError):
                    return None
        return None
    home_goalkick['length'] = home_goalkick['qualifiers'].apply(extract_length).astype(float)
    away_goalkick['length'] = away_goalkick['qualifiers'].apply(extract_length).astype(float)
    hglkl = round(home_goalkick['length'].mean(), 2)
    aglkl = round(away_goalkick['length'].mean(), 2)

    """Defensive Stats"""

    # entradas
    htkl = len(df[(df['teamId']==hteamID) & (df['type']=='Tackle')])
    atkl = len(df[(df['teamId']==ateamID) & (df['type']=='Tackle')])
    # entradas ganadas
    htklw = len(df[(df['teamId']==hteamID) & (df['type']=='Tackle') & (df['outcomeType']=='Successful')])
    atklw = len(df[(df['teamId']==ateamID) & (df['type']=='Tackle') & (df['outcomeType']=='Successful')])
    # anticipacion
    hintc= len(df[(df['teamId']==hteamID) & (df['type']=='Interception')])
    aintc= len(df[(df['teamId']==ateamID) & (df['type']=='Interception')])
    # despeje
    hclr= len(df[(df['teamId']==hteamID) & (df['type']=='Clearance')])
    aclr= len(df[(df['teamId']==ateamID) & (df['type']=='Clearance')])
    # juego aéreo
    harl= len(df[(df['teamId']==hteamID) & (df['type']=='Aerial')])
    aarl= len(df[(df['teamId']==ateamID) & (df['type']=='Aerial')])
    # juego aéreo ganado
    harlw= len(df[(df['teamId']==hteamID) & (df['type']=='Aerial') & (df['outcomeType']=='Successful')])
    aarlw= len(df[(df['teamId']==ateamID) & (df['type']=='Aerial') & (df['outcomeType']=='Successful')])
    # recuperación de balón
    hblrc= len(df[(df['teamId']==hteamID) & (df['type']=='BallRecovery')])
    ablrc= len(df[(df['teamId']==ateamID) & (df['type']=='BallRecovery')])
    # pase bloqueado
    hblkp= len(df[(df['teamId']==hteamID) & (df['type']=='BlockedPass')])
    ablkp= len(df[(df['teamId']==ateamID) & (df['type']=='BlockedPass')])
    # fuera de juego
    hofs= len(df[(df['teamId']==hteamID) & (df['type']=='OffsideGiven')])
    aofs= len(df[(df['teamId']==ateamID) & (df['type']=='OffsideGiven')])
    # falta
    hfoul= len(df[(df['teamId']==hteamID) & (df['type']=='Foul')])
    afoul= len(df[(df['teamId']==ateamID) & (df['type']=='Foul')])

    def plotting_match_stats(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=bg_color, linewidth=2)
      pitch.draw(ax=ax)

      # trazando el cuadro del título
      head_y = [62,68,68,62]
      head_x = [0,0,105,105]
      ax.fill(head_x, head_y, bg_color)
      ax.text(52.5,64.5, "Estadísticas", ha='center', va='center', color=line_color, fontsize=25, fontweight='bold', path_effects=path_eff)

      # Stats bar diagrama
      stats_title = [58, 58-(1*6), 58-(2*6), 58-(3*6), 58-(4*6), 58-(5*6), 58-(6*6), 58-(7*6), 58-(8*6), 58-(9*6), 58-(10*6)] # y co-ordinate values of the bars
      stats_home = [hposs, hft, htotalPass, hLongB, hCor, hglkl, htkl, hintc, hclr, harl, hblrc]
      stats_away = [aposs, aft, atotalPass, aLongB, aCor, aglkl, atkl, aintc, aclr, aarl, ablrc]

      def _safe_ratio(a, b, scale=45):
          return -(a / (a + b)) * scale if (a + b) > 0 else 0
      def _safe_ratio_pos(a, b, scale=45):
          return (a / (a + b)) * scale if (a + b) > 0 else 0

      stats_normalized_home = [
          _safe_ratio(hposs, aposs), _safe_ratio(hft, aft),
          _safe_ratio(htotalPass, atotalPass), _safe_ratio(hLongB, aLongB),
          _safe_ratio(hCor, aCor), _safe_ratio(hglkl, aglkl),
          _safe_ratio(htkl, atkl), _safe_ratio(hintc, aintc),
          _safe_ratio(hclr, aclr), _safe_ratio(harl, aarl), _safe_ratio(hblrc, ablrc)
      ]
      stats_normalized_away = [
          _safe_ratio_pos(aposs, hposs), _safe_ratio_pos(aft, hft),
          _safe_ratio_pos(atotalPass, htotalPass), _safe_ratio_pos(aLongB, hLongB),
          _safe_ratio_pos(aCor, hCor), _safe_ratio_pos(aglkl, hglkl),
          _safe_ratio_pos(atkl, htkl), _safe_ratio_pos(aintc, hintc),
          _safe_ratio_pos(aclr, hclr), _safe_ratio_pos(aarl, harl), _safe_ratio_pos(ablrc, hblrc)
      ]

      start_x = 52.5
      ax.barh(stats_title, stats_normalized_home, height=4, color=hcol, left=start_x)
      ax.barh(stats_title, stats_normalized_away, height=4, left=start_x, color=acol)
      # Desactivar elementos relacionados con ejes
      ax.spines['top'].set_visible(False)
      ax.spines['right'].set_visible(False)
      ax.spines['bottom'].set_visible(False)
      ax.spines['left'].set_visible(False)
      ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False)
      ax.set_xticks([])
      ax.set_yticks([])

      # Trazando los textos
      ax.text(52.5, 58, "Posesión", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(1*6), "Inclinación", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(2*6), "Pases (Buenos)", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(3*6), "Balones Largos (Buenos)", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(4*6), "Córners", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(5*6), "Distancia Pases portero", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(6*6), "Entradas (Ganadas)", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(7*6), "Anticipaciones", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(8*6), "Despejes", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(9*6), "Duelos aéreos (Ganados)", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)
      ax.text(52.5, 58-(10*6), "Recuperaciones", color=line_color, fontsize=17, ha='center', va='center', fontweight='bold', path_effects=path_eff)

      ax.text(7.5, 58, f"{int(hposs)}%", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(1*6), f"{int(hft)}%", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(2*6), f"{htotalPass}({hAccPass})", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(3*6), f"{hLongB}({hAccLongB})", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(4*6), f"{hCor}", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(5*6), f"{hglkl}", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(6*6), f"{htkl}({htklw})", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(7*6), f"{hintc}", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(8*6), f"{hclr}", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(9*6), f"{harl}({harlw})", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')
      ax.text(7.5, 58-(10*6), f"{hblrc}", color=line_color, fontsize=20, ha='right', va='center', fontweight='bold')

      ax.text(97.5, 58, f"{int(aposs)}%", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(1*6), f"{int(aft)}%", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(2*6), f"{atotalPass}({aAccPass})", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(3*6), f"{aLongB}({aAccLongB})", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(4*6), f"{aCor}", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(5*6), f"{aglkl}", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(6*6), f"{atkl}({atklw})", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(7*6), f"{aintc}", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(8*6), f"{aclr}", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(9*6), f"{aarl}({aarlw})", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')
      ax.text(97.5, 58-(10*6), f"{ablrc}", color=line_color, fontsize=20, ha='left', va='center', fontweight='bold')

    """Robos altos"""

    def HighTO(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
      pitch.draw(ax=ax)
      ax.set_ylim(-0.5,68.5)
      ax.set_xlim(-0.5,105.5)

      # Filtrar las pérdidas de balón altas (ganar la posesión dentro del radio de 40 m de la portería contraria).
      home_TO = df[(df['teamId']==hteamID) & ((df['type']=='BallRecovery') | (df['type']=='Interception')) & (df['x']>=70)].copy()
      away_TO = df[(df['teamId']==ateamID) & ((df['type']=='BallRecovery') | (df['type']=='Interception')) & (df['x']>=70)].copy()

      home_TO['distance'] = ((home_TO['x'] - 105)**2 + (home_TO['y'] - 34)**2)**0.5
      home_TO = home_TO[home_TO['distance']<=40]
      away_TO['distance'] = ((away_TO['x'] - 105)**2 + (away_TO['y'] - 34)**2)**0.5
      away_TO = away_TO[away_TO['distance']<=40]

      hto_count = len(home_TO)
      ato_count = len(away_TO)

      # esparciendo el filtrado anterior
      ax.scatter((105-home_TO.x), (68-home_TO.y), s=250, c=hcol, edgecolor=line_color, marker='o', linewidth=2)
      ax.scatter((away_TO.x), (away_TO.y), s=250, c=acol, edgecolor=line_color, marker='o', linewidth=2)

      # marcando el círculo central del campo
      left_circle = plt.Circle((0,34), 40, color=hcol, fill=True, alpha=0.25, linestyle='dashed')
      ax.add_artist(left_circle)
      right_circle = plt.Circle((105,34), 40, color=acol, fill=True, alpha=0.25, linestyle='dashed')
      ax.add_artist(right_circle)
      # Establecer la relación de aspecto para que sea igual
      ax.set_aspect('equal', adjustable='box')
      # Títulos y otros textos
      ax.text(0, 70, f"Equipo local\nRobos más altos: {hto_count}", color=hcol, size=25, ha='left', fontweight='bold')
      ax.text(105, 70, f"Equipo visitante\nRobos más altos: {ato_count}", color=acol, size=25, ha='right', fontweight='bold')

    """Centros"""

    def Crosses(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
      pitch.draw(ax=ax)
      ax.set_ylim(-0.5,68.5)
      ax.set_xlim(-0.5,105.5)

      home_cross = df[(df['teamId']==hteamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross')) & (~df['qualifiers'].astype(str).str.contains('Corner'))]
      away_cross = df[(df['teamId']==ateamID) & (df['type']=='Pass') & (df['qualifiers'].astype(str).str.contains('Cross')) & (~df['qualifiers'].astype(str).str.contains('Corner'))]

      hsuc = 0
      hunsuc = 0
      asuc = 0
      aunsuc = 0

      # iterando a través de cada paso y coloreando según sea exitoso o no
      for index, row in home_cross.iterrows():
        if row['outcomeType'] == 'Successful':
          arrow = patches.FancyArrowPatch((105-row['x'], 68-row['y']), (105-row['endX'], 68-row['endY']), arrowstyle='->', mutation_scale=15, color='green', linewidth=1.5, alpha=1)      # the x and y points are substracted from pitch length and width
          ax.add_patch(arrow)                                                                                                                                                             # to show both home and away passes in the same pitch
          hsuc += 1
        else:
          arrow = patches.FancyArrowPatch((105-row['x'], 68-row['y']), (105-row['endX'], 68-row['endY']), arrowstyle='->', mutation_scale=10, color='red', linewidth=1.5, alpha=.65)
          ax.add_patch(arrow)
          hunsuc += 1

      for index, row in away_cross.iterrows():
        if row['outcomeType'] == 'Successful':
          arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', mutation_scale=15, color='green', linewidth=1.5, alpha=1)
          ax.add_patch(arrow)
          asuc += 1
        else:
          arrow = patches.FancyArrowPatch((row['x'], row['y']), (row['endX'], row['endY']), arrowstyle='->', mutation_scale=10, color='red', linewidth=1.5, alpha=.65)
          ax.add_patch(arrow)
          aunsuc += 1

      # títulos y otros textos
      home_left = len(home_cross[home_cross['y']>=34])
      home_right = len(home_cross[home_cross['y']<34])
      away_left = len(away_cross[away_cross['y']>=34])
      away_right = len(away_cross[away_cross['y']<34])

      ax.text(51, 2, f"Centros desde\nIzquierda: {home_left}", color=hcol, fontsize=15, va='bottom', ha='right')
      ax.text(51, 66, f"Centros desde\nDerecha: {home_right}", color=hcol, fontsize=15, va='top', ha='right')
      ax.text(54, 66, f"Centros desde\nIzquierda: {away_left}", color=acol, fontsize=15, va='top', ha='left')
      ax.text(54, 2, f"Centros desde\nDerecha: {away_right}", color=acol, fontsize=15, va='bottom', ha='left')

      ax.text(0,-2, f"Eficaces: {hsuc}", color='green', fontsize=20, ha='left', va='top')
      ax.text(0,-5.5, f"Ineficaces: {hunsuc}", color='red', fontsize=20, ha='left', va='top')
      ax.text(105,-2, f"Eficaces: {asuc}", color='green', fontsize=20, ha='right', va='top')
      ax.text(105,-5.5, f"Ineficaces: {aunsuc}", color='red', fontsize=20, ha='right', va='top')

      ax.text(0, 70, f"Centros Equipo local", color=hcol, size=25, ha='left', fontweight='bold')
      ax.text(105, 70, f"Centros Equipo visitante", color=acol, size=25, ha='right', fontweight='bold')

      ax.text(52.5, -20, "________________________________________________________________________________________________________________________________________________________________________________________________________________________________",
              color=line_color, fontsize=20, va='center', ha='center')

    """# Match report equipo

    ---


    """

    # Hacer una trama grande que tenga 18 subtramas en 6 filas y 3 columnas.
    fig, axs = plt.subplots(6,3, figsize=(48,64), facecolor=bg_color)
    # Gráfico de redes de pases
    pass_network_visualization(axs[0,0], home_passes_between_df, home_average_locs_and_count_df, hcol, home_team_id)
    plot_shotmap(axs[0,1]) # shotmap
    pass_network_visualization(axs[0,2], away_passes_between_df, away_average_locs_and_count_df, acol, away_team_id)
    # Gráfico bloque defensivo
    defensive_block(axs[1,0], defensive_home_average_locs_and_count_df, hteamName, hteamID, hcol)
    plot_goalPost(axs[1,1]) # goalpost
    defensive_block(axs[1,2], defensive_away_average_locs_and_count_df, ateamName, ateamID, acol)
    # Gráfico pases progresivos
    draw_progressive_pass_map(axs[2,0], dfhpp, hteamName, hcol)
    plot_Momentum(axs[2,1]) # match momentum
    draw_progressive_pass_map(axs[2,2], dfapp, ateamName, acol)
    # Zonas finales de pase con peligro
    draw_pass_map(axs[3,0], dfhp, hteamName, hcol)
    plotting_match_stats(axs[3,1]) # estadísticas del partido
    draw_pass_map(axs[3,2], dfap, ateamName, acol)
    # Zonas de pase final
    Pass_end_zone(axs[4,0], hdfPEZ, hteamName, pearl_earring_cmaph, hcol)
    HighTO(axs[4,1]) # robos altos
    Pass_end_zone(axs[4,2], adfPEZ, ateamName, pearl_earring_cmapa, acol)
    # Zons de creación de peligro
    Chance_creating_zone(axs[5,0], dfchch, hteamName, pearl_earring_cmaph, hcol)
    Crosses(axs[5,1]) # centros
    Chance_creating_zone(axs[5,2], dfchca, ateamName, pearl_earring_cmapa, acol)

    # Mientras trabajo en Google Colab, usando esta parte del código descargo el archivo de imagen final del panel en mi PC.
    fig_main = fig
    fig_main.savefig(os.path.join(output_dir, f'{file_header}_Dashboard.png'), bbox_inches='tight')
    plt.close(fig_main)
    print("✅ Dashboard principal guardado")

    """#Funciones del match report de jugadores

    ---

    ** Jugador Estadísticas
    """

    # Get unique players
    home_unique_players = homedf['name'].unique()
    away_unique_players = awaydf['name'].unique()

    # Initialize an empty dictionary to store home players different type of shot sequence counts
    home_shot_seq_counts = {'name': home_unique_players, 'Shots': [], 'Shot Assist': [], 'Buildup to shot': []}

    # Putting counts in those lists
    for name in home_unique_players:
        home_shot_seq_counts['Shots'].append(len(df[(df['name'] == name) & ((df['type']=='MissedShot') | (df['type']=='SavedShot') | (df['type']=='ShotOnPost') | (df['type']=='Goal'))]))
        home_shot_seq_counts['Shot Assist'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))
        home_shot_seq_counts['Buildup to shot'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).shift(-1).str.contains('KeyPass', na=False))]))

    # converting that list into a dataframe
    home_sh_sq_df = pd.DataFrame(home_shot_seq_counts)
    home_sh_sq_df['total'] = home_sh_sq_df['Shots']+home_sh_sq_df['Shot Assist']+home_sh_sq_df['Buildup to shot']
    home_sh_sq_df = home_sh_sq_df.sort_values(by='total', ascending=False)
    home_sh_sq_df.reset_index(drop=True, inplace=True)
    home_sh_sq_df = home_sh_sq_df.head(5)
    home_sh_sq_df['shortName'] = home_sh_sq_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store away players different type of shot sequence counts
    away_shot_seq_counts = {'name': away_unique_players, 'Shots': [], 'Shot Assist': [], 'Buildup to shot': []}

    for name in away_unique_players:
        away_shot_seq_counts['Shots'].append(len(df[(df['name'] == name) & ((df['type']=='MissedShot') | (df['type']=='SavedShot') | (df['type']=='ShotOnPost') | (df['type']=='Goal'))]))
        away_shot_seq_counts['Shot Assist'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))
        away_shot_seq_counts['Buildup to shot'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).shift(-1).str.contains('KeyPass', na=False))]))

    away_sh_sq_df = pd.DataFrame(away_shot_seq_counts)
    away_sh_sq_df['total'] = away_sh_sq_df['Shots']+away_sh_sq_df['Shot Assist']+away_sh_sq_df['Buildup to shot']
    away_sh_sq_df = away_sh_sq_df.sort_values(by='total', ascending=False)
    away_sh_sq_df.reset_index(drop=True, inplace=True)
    away_sh_sq_df = away_sh_sq_df.head(5)
    away_sh_sq_df['shortName'] = away_sh_sq_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store home players different type of pass counts
    home_pass_types_counts = {'name': home_unique_players, 'Progressive Passes': [], 'LineBreaking Pass': [], 'Key Passes': []}

    for name in home_unique_players:
        home_pass_types_counts['Progressive Passes'].append(len(df[(df['name'] == name) & (df['pro'] > 9.144)]))
        home_pass_types_counts['LineBreaking Pass'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('Throughball'))]))
        home_pass_types_counts['Key Passes'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))

    home_passer_df = pd.DataFrame(home_pass_types_counts)
    home_passer_df['total'] = home_passer_df['Progressive Passes']+home_passer_df['LineBreaking Pass']+home_passer_df['Key Passes']
    home_passer_df = home_passer_df.sort_values(by='total', ascending=False)
    home_passer_df.reset_index(drop=True, inplace=True)
    home_passer_df = home_passer_df.head(5)
    home_passer_df['shortName'] = home_passer_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store away players different type of pass counts
    away_pass_types_counts = {'name': away_unique_players, 'Progressive Passes': [], 'LineBreaking Pass': [], 'Key Passes': []}

    for name in away_unique_players:
        away_pass_types_counts['Progressive Passes'].append(len(df[(df['name'] == name) & (df['pro'] > 9.144)]))
        away_pass_types_counts['LineBreaking Pass'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['outcomeType'] == 'Successful') & (df['qualifiers'].astype(str).str.contains('Throughball'))]))
        away_pass_types_counts['Key Passes'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))

    away_passer_df = pd.DataFrame(away_pass_types_counts)
    away_passer_df['total'] = away_passer_df['Progressive Passes']+away_passer_df['LineBreaking Pass']+away_passer_df['Key Passes']
    away_passer_df = away_passer_df.sort_values(by='total', ascending=False)
    away_passer_df.reset_index(drop=True, inplace=True)
    away_passer_df = away_passer_df.head(5)
    away_passer_df['shortName'] = away_passer_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store home players different type of defensive actions counts
    home_defensive_actions_counts = {'name': home_unique_players, 'Tackles': [], 'Interceptions': [], 'Clearance': []}

    for name in home_unique_players:
        home_defensive_actions_counts['Tackles'].append(len(df[(df['name'] == name) & (df['type'] == 'Tackle') & (df['outcomeType']=='Successful')]))
        home_defensive_actions_counts['Interceptions'].append(len(df[(df['name'] == name) & (df['type'] == 'Interception')]))
        home_defensive_actions_counts['Clearance'].append(len(df[(df['name'] == name) & (df['type'] == 'Clearance')]))

    home_defender_df = pd.DataFrame(home_defensive_actions_counts)
    home_defender_df['total'] = home_defender_df['Tackles']+home_defender_df['Interceptions']+home_defender_df['Clearance']
    home_defender_df = home_defender_df.sort_values(by='total', ascending=False)
    home_defender_df.reset_index(drop=True, inplace=True)
    home_defender_df = home_defender_df.head(5)
    home_defender_df['shortName'] = home_defender_df['name'].apply(get_short_name)

    # Initialize an empty dictionary to store away players different type of defensive actions counts
    away_defensive_actions_counts = {'name': away_unique_players, 'Tackles': [], 'Interceptions': [], 'Clearance': []}

    for name in away_unique_players:
        away_defensive_actions_counts['Tackles'].append(len(df[(df['name'] == name) & (df['type'] == 'Tackle') & (df['outcomeType']=='Successful')]))
        away_defensive_actions_counts['Interceptions'].append(len(df[(df['name'] == name) & (df['type'] == 'Interception')]))
        away_defensive_actions_counts['Clearance'].append(len(df[(df['name'] == name) & (df['type'] == 'Clearance')]))

    away_defender_df = pd.DataFrame(away_defensive_actions_counts)
    away_defender_df['total'] = away_defender_df['Tackles']+away_defender_df['Interceptions']+away_defender_df['Clearance']
    away_defender_df = away_defender_df.sort_values(by='total', ascending=False)
    away_defender_df.reset_index(drop=True, inplace=True)
    away_defender_df = away_defender_df.head(5)
    away_defender_df['shortName'] = away_defender_df['name'].apply(get_short_name)

    # Get unique players (same things as before, but this time both home and away teams combined)
    unique_players = df['name'].unique()


    # Initialize an empty dictionary to store players different type of shot sequence counts
    shot_seq_counts = {'name': unique_players, 'Shots': [], 'Shot Assist': [], 'Buildup to shot': []}

    for name in unique_players:
        shot_seq_counts['Shots'].append(len(df[(df['name'] == name) & (df['type'].isin(['MissedShots', 'SavedShot', 'ShotOnPost', 'Goal']))]))
        shot_seq_counts['Shot Assist'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))
        shot_seq_counts['Buildup to shot'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).shift(-1).str.contains('KeyPass', na=False))]))

    sh_sq_df = pd.DataFrame(shot_seq_counts)
    sh_sq_df['total'] = sh_sq_df['Shots']+sh_sq_df['Shot Assist']+sh_sq_df['Buildup to shot']
    sh_sq_df = sh_sq_df.sort_values(by='total', ascending=False)
    sh_sq_df.reset_index(drop=True, inplace=True)
    sh_sq_df = sh_sq_df.head(10)
    sh_sq_df['shortName'] = sh_sq_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store players different type of pass counts
    pass_types_counts = {'name': unique_players, 'Progressive Passes': [], 'LineBreaking Pass': [], 'Key Passes': []}

    for name in unique_players:
        pass_types_counts['Progressive Passes'].append(len(df[(df['name'] == name) & (df['pro'] > 9.144)]))
        pass_types_counts['LineBreaking Pass'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('Throughball'))]))
        pass_types_counts['Key Passes'].append(len(df[(df['name'] == name) & (df['type'] == 'Pass') & (df['qualifiers'].astype(str).str.contains('KeyPass'))]))

    passer_df = pd.DataFrame(pass_types_counts)
    passer_df['total'] = passer_df['Progressive Passes']+passer_df['LineBreaking Pass']+passer_df['Key Passes']
    passer_df = passer_df.sort_values(by='total', ascending=False)
    passer_df.reset_index(drop=True, inplace=True)
    passer_df = passer_df.head(10)
    passer_df['shortName'] = passer_df['name'].apply(get_short_name)


    # Initialize an empty dictionary to store players different type of defensive actions counts
    defensive_actions_counts = {'name': unique_players, 'Tackles': [], 'Interceptions': [], 'Clearance': []}

    for name in unique_players:
        defensive_actions_counts['Tackles'].append(len(df[(df['name'] == name) & (df['type'] == 'Tackle') & (df['outcomeType']=='Successful')]))
        defensive_actions_counts['Interceptions'].append(len(df[(df['name'] == name) & (df['type'] == 'Interception')]))
        defensive_actions_counts['Clearance'].append(len(df[(df['name'] == name) & (df['type'] == 'Clearance')]))

    defender_df = pd.DataFrame(defensive_actions_counts)
    defender_df['total'] = defender_df['Tackles']+defender_df['Interceptions']+defender_df['Clearance']
    defender_df = defender_df.sort_values(by='total', ascending=False)
    defender_df.reset_index(drop=True, inplace=True)
    defender_df = defender_df.head(10)
    defender_df['shortName'] = defender_df['name'].apply(get_short_name)

    """Mapa de pases"""

    def home_player_passmap(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
      pitch.draw(ax=ax)

      home_player_name = PLAYER_HOME
      home_playerdf = df[(df['name']==home_player_name) & (df['type']=='Pass')]

      pass_comp = home_playerdf[home_playerdf['outcomeType']=='Successful']
      pass_incomp = home_playerdf[home_playerdf['outcomeType']=='Unsuccessful']
      kp = home_playerdf[home_playerdf['qualifiers'].astype(str).str.contains('KeyPass')]
      assist = home_playerdf[home_playerdf['qualifiers'].astype(str).str.contains('GoalAssist')]

      comp = pitch.lines(pass_comp.x, pass_comp.y, pass_comp.endX, pass_comp.endY, lw=3, transparent=True, comet=True, color=hcol, ax=ax, alpha=0.65)
      incomp = pitch.lines(pass_incomp.x, pass_incomp.y, pass_incomp.endX, pass_incomp.endY, lw=3, transparent=True, comet=True, color='gray', ax=ax, alpha=0.25)
      keypass = pitch.lines(kp.x, kp.y, kp.endX, kp.endY, lw=4, transparent=True, comet=True, color=violet, ax=ax, alpha=0.9)
      aline = pitch.lines(assist.x, assist.y, assist.endX, assist.endY, lw=4, transparent=True, comet=True, color=green, ax=ax, alpha=1)

      sc1 = pitch.scatter(pass_comp.endX, pass_comp.endY, s=30, color=bg_color, edgecolor=hcol, zorder=2, ax=ax)
      sc2 = pitch.scatter(pass_incomp.endX, pass_incomp.endY, s=30, color=bg_color, edgecolor='gray', alpha=0.25, zorder=2, ax=ax)
      sc3 = pitch.scatter(kp.endX, kp.endY, s=40, color=bg_color, edgecolor=violet, linewidth=1.5, zorder=2, ax=ax)
      sc4 = pitch.scatter(assist.endX, assist.endY, s=50, color=bg_color, edgecolor=green, linewidth=1.5, zorder=2, ax=ax)

      ax.text(50, -3, f'Pase eficaz: {len(pass_comp)}', color=hcol, va='center', ha='left', fontsize=12)
      ax.text(80, -3, f'Pase ineficaz: {len(pass_incomp)}', color='gray', va='center', ha='left', fontsize=12)
      ax.text(50, -8, f'Pase clave: {len(kp)}', color=violet, va='center', ha='left', fontsize=12)
      ax.text(80, -8, f'Asistencia: {len(assist)}', color=green, va='center', ha='left', fontsize=12)

      home_name_show = _short_name(PLAYER_HOME)
      ax.text(0,-5, "Dirección ataque ----->", color=hcol, fontsize=15, va='center', ha='left')
      ax.set_title(f"{home_name_show} Mapa de pases", color=hcol, fontsize=25, fontweight='bold')

    def away_player_passmap(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
      pitch.draw(ax=ax)
      ax.invert_xaxis()
      ax.invert_yaxis()

      # taking the selected away player and plotting his passmap
      away_player_name = PLAYER_AWAY
      away_playerdf = df[(df['name']==away_player_name) & (df['type']=='Pass')]

      pass_comp = away_playerdf[away_playerdf['outcomeType']=='Successful']
      pass_incomp = away_playerdf[away_playerdf['outcomeType']=='Unsuccessful']
      kp = away_playerdf[away_playerdf['qualifiers'].astype(str).str.contains('KeyPass')]
      assist = away_playerdf[away_playerdf['qualifiers'].astype(str).str.contains('GoalAssist')]

      comp = pitch.lines(pass_comp.x, pass_comp.y, pass_comp.endX, pass_comp.endY, lw=3, transparent=True, comet=True, color=acol, ax=ax, alpha=0.65)
      incomp = pitch.lines(pass_incomp.x, pass_incomp.y, pass_incomp.endX, pass_incomp.endY, lw=3, transparent=True, comet=True, color='gray', ax=ax, alpha=0.25)
      keypass = pitch.lines(kp.x, kp.y, kp.endX, kp.endY, lw=4, transparent=True, comet=True, color=violet, ax=ax, alpha=0.9)
      aline = pitch.lines(assist.x, assist.y, assist.endX, assist.endY, lw=4, transparent=True, comet=True, color=green, ax=ax, alpha=1)

      sc1 = pitch.scatter(pass_comp.endX, pass_comp.endY, s=30, color=bg_color, edgecolor=acol, zorder=2, ax=ax)
      sc2 = pitch.scatter(pass_incomp.endX, pass_incomp.endY, s=30, color=bg_color, edgecolor='gray', alpha=0.25, zorder=2, ax=ax)
      sc3 = pitch.scatter(kp.endX, kp.endY, s=40, color=bg_color, edgecolor=violet, linewidth=1.5, zorder=2, ax=ax)
      sc4 = pitch.scatter(assist.endX, assist.endY, s=50, color=bg_color, edgecolor=green, linewidth=1.5, zorder=2, ax=ax)

      ax.text(50, 71, f'Pase eficaz: {len(pass_comp)}', color=acol, va='center', ha='right', fontsize=12)
      ax.text(80, 71, f'Pase ineficaz: {len(pass_incomp)}', color='gray', va='center', ha='right', fontsize=12)
      ax.text(50, 76, f'Pase clave: {len(kp)}', color=violet, va='center', ha='right', fontsize=12)
      ax.text(80, 76, f'Asistencia: {len(assist)}', color=green, va='center', ha='right', fontsize=12)

      away_name_show = _short_name(PLAYER_AWAY)
      ax.text(0,73, "<----- Dirección ataque", color=acol, fontsize=15, va='center', ha='right')
      ax.set_title(f"{away_name_show} Mapa de pases", color=acol, fontsize=25, fontweight='bold')

    """Acciones defensivas de jugadores"""

    def home_player_def_acts(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, line_zorder=2, linewidth=2)
      pitch.draw(ax=ax)
      ax.set_ylim(-13,68.5)

      # taking the selected home player and plotting his defensive actions
      home_player_name = PLAYER_HOME
      home_playerdf = df[(df['name']==home_player_name)]

      hp_tk = home_playerdf[home_playerdf['type']=='Tackle']
      hp_intc = home_playerdf[(home_playerdf['type']=='Interception') | (home_playerdf['type']=='BlockedPass')]
      hp_br = home_playerdf[home_playerdf['type']=='BallRecovery']
      hp_cl = home_playerdf[home_playerdf['type']=='Clearance']
      hp_fl = home_playerdf[home_playerdf['type']=='Foul']
      hp_ar = home_playerdf[(home_playerdf['type']=='Aerial') & (home_playerdf['qualifiers'].astype(str).str.contains('Defensive'))]

      sc1 = pitch.scatter(hp_tk.x, hp_tk.y, s=250, c=hcol, lw=2.5, edgecolor=hcol, marker='+', hatch='/////', ax=ax)
      sc2 = pitch.scatter(hp_intc.x, hp_intc.y, s=250, c='None', lw=2.5, edgecolor=hcol, marker='s', hatch='/////', ax=ax)
      sc3 = pitch.scatter(hp_br.x, hp_br.y, s=250, c='None', lw=2.5, edgecolor=hcol, marker='o', hatch='/////', ax=ax)
      sc4 = pitch.scatter(hp_cl.x, hp_cl.y, s=250, c='None', lw=2.5, edgecolor=hcol, marker='d', hatch='/////', ax=ax)
      sc5 = pitch.scatter(hp_fl.x, hp_fl.y, s=250, c=hcol, lw=2.5, edgecolor=hcol, marker='x', hatch='/////', ax=ax)
      sc6 = pitch.scatter(hp_ar.x, hp_ar.y, s=250, c='None', lw=2.5, edgecolor=hcol, marker='^', hatch='/////', ax=ax)

      sc7 =  pitch.scatter(51, -3, s=150, c=hcol, lw=2.5, edgecolor=hcol, marker='+', hatch='/////', ax=ax)
      sc8 =  pitch.scatter(51, -7, s=150, c='None', lw=2.5, edgecolor=hcol, marker='s', hatch='/////', ax=ax)
      sc9 =  pitch.scatter(51, -11, s=150, c='None', lw=2.5, edgecolor=hcol, marker='o', hatch='/////', ax=ax)
      sc10 = pitch.scatter(78, -3, s=150, c='None', lw=2.5, edgecolor=hcol, marker='d', hatch='/////', ax=ax)
      sc11 = pitch.scatter(78, -7, s=150, c=hcol, lw=2.5, edgecolor=hcol, marker='x', hatch='/////', ax=ax)
      sc12 = pitch.scatter(78, -11, s=150, c='None', lw=2.5, edgecolor=hcol, marker='^', hatch='/////', ax=ax)

      ax.text(53, -3, "Entrada", color=hcol, ha='left', va='center', fontsize=13)
      ax.text(53, -7, "Anticipación", color=hcol, ha='left', va='center', fontsize=13)
      ax.text(53, -11, "Recuperación", color=hcol, ha='left', va='center', fontsize=13)
      ax.text(81, -3, "Despeje", color=hcol, ha='left', va='center', fontsize=13)
      ax.text(81, -7, "Falta", color=hcol, ha='left', va='center', fontsize=13)
      ax.text(81, -11, "Duelo aéreo", color=hcol, ha='left', va='center', fontsize=13)

      home_name_show = _short_name(PLAYER_HOME)
      ax.text(0,-5, "Dirección ataque ----->", color=hcol, fontsize=15, va='center', ha='left')
      ax.set_title(f"{home_name_show} Acciones defensivas", color=hcol, fontsize=25, fontweight='bold')

    def away_player_def_acts(ax):
      pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, line_zorder=2, linewidth=2)
      pitch.draw(ax=ax)
      ax.set_ylim(-0.5,81)
      ax.invert_xaxis()
      ax.invert_yaxis()

      # taking the selected away player and plotting his defensive actions
      away_player_name = PLAYER_AWAY
      away_playerdf = df[(df['name']==away_player_name)]

      ap_tk = away_playerdf[away_playerdf['type']=='Tackle']
      ap_intc = away_playerdf[(away_playerdf['type']=='Interception') | (away_playerdf['type']=='BlockedPass')]
      ap_br = away_playerdf[away_playerdf['type']=='BallRecovery']
      ap_cl = away_playerdf[away_playerdf['type']=='Clearance']
      ap_fl = away_playerdf[away_playerdf['type']=='Foul']
      ap_ar = away_playerdf[(away_playerdf['type']=='Aerial') & (away_playerdf['qualifiers'].astype(str).str.contains('Defensive'))]

      sc1 = pitch.scatter(ap_tk.x, ap_tk.y, s=250, c=acol, lw=2.5, edgecolor=acol, marker='+', hatch='/////', ax=ax)
      sc2 = pitch.scatter(ap_intc.x, ap_intc.y, s=250, c='None', lw=2.5, edgecolor=acol, marker='s', hatch='/////', ax=ax)
      sc3 = pitch.scatter(ap_br.x, ap_br.y, s=250, c='None', lw=2.5, edgecolor=acol, marker='o', hatch='/////', ax=ax)
      sc4 = pitch.scatter(ap_cl.x, ap_cl.y, s=250, c='None', lw=2.5, edgecolor=acol, marker='d', hatch='/////', ax=ax)
      sc5 = pitch.scatter(ap_fl.x, ap_fl.y, s=250, c=acol, lw=2.5, edgecolor=acol, marker='x', hatch='/////', ax=ax)
      sc6 = pitch.scatter(ap_ar.x, ap_ar.y, s=250, c='None', lw=2.5, edgecolor=acol, marker='^', hatch='/////', ax=ax)

      sc7 =  pitch.scatter(51, 71, s=150, c=acol, lw=2.5, edgecolor=acol, marker='+', hatch='/////', ax=ax)
      sc8 =  pitch.scatter(51, 75, s=150, c='None', lw=2.5, edgecolor=acol, marker='s', hatch='/////', ax=ax)
      sc9 =  pitch.scatter(51, 79, s=150, c='None', lw=2.5, edgecolor=acol, marker='o', hatch='/////', ax=ax)
      sc10 = pitch.scatter(78, 71, s=150, c='None', lw=2.5, edgecolor=acol, marker='d', hatch='/////', ax=ax)
      sc11 = pitch.scatter(78, 75, s=150, c=acol, lw=2.5, edgecolor=acol, marker='x', hatch='/////', ax=ax)
      sc12 = pitch.scatter(78, 79, s=150, c='None', lw=2.5, edgecolor=acol, marker='^', hatch='/////', ax=ax)

      ax.text(53, 71, "Entrada", color=acol, ha='right', va='center', fontsize=13)
      ax.text(53, 75, "Anticipación", color=acol, ha='right', va='center', fontsize=13)
      ax.text(53, 79, "Recuperación", color=acol, ha='right', va='center', fontsize=13)
      ax.text(81, 71, "Despeje", color=acol, ha='right', va='center', fontsize=13)
      ax.text(81, 75, "Falta", color=acol, ha='right', va='center', fontsize=13)
      ax.text(81, 79, "Duelo aéreo", color=acol, ha='right', va='center', fontsize=13)

      away_name_show = _short_name(PLAYER_AWAY)
      ax.text(0,73, "<----- Dirección ataque", color=acol, fontsize=15, va='center', ha='right')
      ax.set_title(f"{away_name_show} Acciones defensivas", color=acol, fontsize=25, fontweight='bold')

    """Receptores de pases"""

    def home_passes_recieved(ax):
        pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
        pitch.draw(ax=ax)

        name = PLAYER_HOME
        name_show = _short_name(name)
        filtered_rows = df[(df['type'] == 'Pass') & (df['outcomeType'] == 'Successful') & (df['name'].shift(-1) == name)]
        keypass_recieved_df = filtered_rows[filtered_rows['qualifiers'].astype(str).str.contains('KeyPass')]
        assist_recieved_df = filtered_rows[filtered_rows['qualifiers'].astype(str).str.contains('IntentionalGoalAssist')]
        pr = len(filtered_rows)
        kpr = len(keypass_recieved_df)

        lc1 = pitch.lines(filtered_rows.x, filtered_rows.y, filtered_rows.endX, filtered_rows.endY, lw=3, transparent=True, comet=True,color=hcol, ax=ax, alpha=0.5)
        lc2 = pitch.lines(keypass_recieved_df.x, keypass_recieved_df.y, keypass_recieved_df.endX, keypass_recieved_df.endY, lw=4, transparent=True, comet=True,color=violet, ax=ax, alpha=0.75)
        lc3 = pitch.lines(assist_recieved_df.x, assist_recieved_df.y, assist_recieved_df.endX, assist_recieved_df.endY, lw=4, transparent=True, comet=True,color=green, ax=ax, alpha=0.75)
        sc1 = pitch.scatter(filtered_rows.endX, filtered_rows.endY, s=30, edgecolor=hcol, linewidth=1, color=bg_color, zorder=2, ax=ax)
        sc2 = pitch.scatter(keypass_recieved_df.endX, keypass_recieved_df.endY, s=40, edgecolor=violet, linewidth=1.5, color=bg_color, zorder=2, ax=ax)
        sc3 = pitch.scatter(assist_recieved_df.endX, assist_recieved_df.endY, s=50, edgecolors=green, linewidths=1, marker='football', c=bg_color, zorder=2, ax=ax)

        avg_endY = filtered_rows['endY'].median()
        avg_endX = filtered_rows['endX'].median()
        ax.axvline(x=avg_endX, ymin=0, ymax=68, color='gray', linestyle='--', alpha=0.6, linewidth=2)
        ax.axhline(y=avg_endY, xmin=0, xmax=105, color='gray', linestyle='--', alpha=0.6, linewidth=2)
        ax.set_title(f"{name_show} Pases recibidos", color=hcol, fontsize=25, fontweight='bold')
        highlight_text=[{'color':violet}]
        ax_text(52.5,70, f'Pases recibidos:{pr+kpr} <(Pases clave recibidos:{kpr})>', color=line_color, fontsize=15, ha='center', va='center', highlight_textprops=highlight_text, ax=ax)
        ax.text(0,-5, "Dirección ataque ----->", color=hcol, fontsize=15, va='center', ha='left')

        return pitch

    def away_passes_recieved(ax):
        pitch = Pitch(pitch_type='uefa', goal_type='box', goal_alpha=.75, corner_arcs=True, pitch_color=bg_color, line_color=line_color, linewidth=2)
        pitch.draw(ax=ax)
        ax.invert_xaxis()
        ax.invert_yaxis()

        # plotting the selected away player pass receiving
        name = PLAYER_AWAY
        name_show = _short_name(name)
        filtered_rows = df[(df['type'] == 'Pass') & (df['outcomeType'] == 'Successful') & (df['name'].shift(-1) == name)]
        keypass_recieved_df = filtered_rows[filtered_rows['qualifiers'].astype(str).str.contains('KeyPass')]
        assist_recieved_df = filtered_rows[filtered_rows['qualifiers'].astype(str).str.contains('IntentionalGoalAssist')]
        pr = len(filtered_rows)
        kpr = len(keypass_recieved_df)

        lc1 = pitch.lines(filtered_rows.x, filtered_rows.y, filtered_rows.endX, filtered_rows.endY, lw=3, transparent=True, comet=True,color=acol, ax=ax, alpha=0.5)
        lc2 = pitch.lines(keypass_recieved_df.x, keypass_recieved_df.y, keypass_recieved_df.endX, keypass_recieved_df.endY, lw=4, transparent=True, comet=True,color=violet, ax=ax, alpha=0.75)
        lc3 = pitch.lines(assist_recieved_df.x, assist_recieved_df.y, assist_recieved_df.endX, assist_recieved_df.endY, lw=4, transparent=True, comet=True,color=green, ax=ax, alpha=0.75)
        sc1 = pitch.scatter(filtered_rows.endX, filtered_rows.endY, s=30, edgecolor=acol, linewidth=1, color=bg_color, zorder=2, ax=ax)
        sc2 = pitch.scatter(keypass_recieved_df.endX, keypass_recieved_df.endY, s=40, edgecolor=violet, linewidth=1.5, color=bg_color, zorder=2, ax=ax)
        sc3 = pitch.scatter(assist_recieved_df.endX, assist_recieved_df.endY, s=50, edgecolors=green, linewidths=1, marker='football', c=bg_color, zorder=2, ax=ax)

        avg_endX = filtered_rows['endX'].median()
        avg_endY = filtered_rows['endY'].median()
        ax.axvline(x=avg_endX, ymin=0, ymax=68, color='gray', linestyle='--', alpha=0.6, linewidth=2)
        ax.axhline(y=avg_endY, xmin=0, xmax=105, color='gray', linestyle='--', alpha=0.6, linewidth=2)
        ax.set_title(f"{name_show} Pases recibidos", color=acol, fontsize=25, fontweight='bold')
        highlight_text=[{'color':violet}]
        ax_text(52.5,-2, f'Pases recibidos:{pr+kpr} <(Pases clave recibidos:{kpr})>', color=line_color, fontsize=15, ha='center', va='center', highlight_textprops=highlight_text, ax=ax)
        ax.text(0,73, "<----- Dirección ataque", color=acol, fontsize=15, va='center', ha='right')

        return pitch

    """Gráfico de barras"""

    def sh_sq_bar(ax):
      top10_sh_sq = sh_sq_df.nlargest(10, 'total')['shortName'].tolist()

      shsq_sh = sh_sq_df.nlargest(10, 'total')['Shots'].tolist()
      shsq_sa = sh_sq_df.nlargest(10, 'total')['Shot Assist'].tolist()
      shsq_bs = sh_sq_df.nlargest(10, 'total')['Buildup to shot'].tolist()

      left1 = [w + x for w, x in zip(shsq_sh, shsq_sa)]

      ax.barh(top10_sh_sq, shsq_sh, label='Tiro', color=col1, left=0)
      ax.barh(top10_sh_sq, shsq_sa, label='Asist. a tiro', color=violet, left=shsq_sh)
      ax.barh(top10_sh_sq, shsq_bs, label='Const. a tiro', color=col2, left=left1)

      # Add counts in the middle of the bars (if count > 0)
      for i, player in enumerate(top10_sh_sq):
          for j, count in enumerate([shsq_sh[i], shsq_sa[i], shsq_bs[i]]):
              if count > 0:
                  x_position = sum([shsq_sh[i], shsq_sa[i]][:j]) + count / 2
                  ax.text(x_position, i, str(count), ha='center', va='center', color=line_color, fontsize=13, fontweight='bold')

      max_x = sh_sq_df['total'].iloc()[0]
      x_coord = [2 * i for i in range(1, int(max_x/2))]
      for x in x_coord:
          ax.axvline(x=x, color='gray', linestyle='--', zorder=2, alpha=0.5)

      ax.set_facecolor(bg_color)
      ax.tick_params(axis='x', colors=line_color, labelsize=15)
      ax.tick_params(axis='y', colors=line_color, labelsize=15)
      ax.xaxis.label.set_color(line_color)
      ax.yaxis.label.set_color(line_color)
      for spine in ax.spines.values():
        spine.set_edgecolor(bg_color)

      ax.set_title(f"Participación en tiros", color=line_color, fontsize=20, fontweight='bold')
      ax.legend()

    def passer_bar(ax):
      top10_passers = passer_df.nlargest(10, 'total')['shortName'].tolist()

      passers_pp = passer_df.nlargest(10, 'total')['Progressive Passes'].tolist()
      passers_tp = passer_df.nlargest(10, 'total')['LineBreaking Pass'].tolist()
      passers_kp = passer_df.nlargest(10, 'total')['Key Passes'].tolist()

      left1 = [w + x for w, x in zip(passers_pp, passers_tp)]

      ax.barh(top10_passers, passers_pp, label='Pase progr.', color=col1, left=0)
      ax.barh(top10_passers, passers_tp, label='Pase área', color=col2, left=passers_pp)
      ax.barh(top10_passers, passers_kp, label='Pase clave', color=violet, left=left1)

      # Add counts in the middle of the bars (if count > 0)
      for i, player in enumerate(top10_passers):
          for j, count in enumerate([passers_pp[i], passers_tp[i], passers_kp[i]]):
              if count > 0:
                  x_position = sum([passers_pp[i], passers_tp[i]][:j]) + count / 2
                  ax.text(x_position, i, str(count), ha='center', va='center', color=line_color, fontsize=13, fontweight='bold')

      max_x = passer_df['total'].iloc()[0]
      x_coord = [2 * i for i in range(1, int(max_x/2))]
      for x in x_coord:
          ax.axvline(x=x, color='gray', linestyle='--', zorder=2, alpha=0.5)

      ax.set_facecolor(bg_color)
      ax.tick_params(axis='x', colors=line_color, labelsize=15)
      ax.tick_params(axis='y', colors=line_color, labelsize=15)
      ax.xaxis.label.set_color(line_color)
      ax.yaxis.label.set_color(line_color)
      for spine in ax.spines.values():
        spine.set_edgecolor(bg_color)

      ax.set_title(f"Top10 Pasadores", color=line_color, fontsize=20, fontweight='bold')
      ax.legend()
      ax.text((max_x/2), 12, "Top jugadores individuales", color=line_color, fontsize=30, va='center', ha='center')
      ax.text((max_x/2)+0.25, 11.4, "___________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________",
              color=line_color, va='center', ha='center')
      highlight_text = [{'color':hcol}, {'color':acol}]
      ax_text((max_x/2),13.5, f"<{hteamName} {hgoal_count}> - <{agoal_count} {ateamName}>", ha='center', va='center',
              fontweight='bold',fontsize=50, color=line_color, highlight_textprops=highlight_text, ax=ax)


    def defender_bar(ax):
      top10_defenders = defender_df.nlargest(10, 'total')['shortName'].tolist()

      defender_tk = defender_df.nlargest(10, 'total')['Tackles'].tolist()
      defender_in = defender_df.nlargest(10, 'total')['Interceptions'].tolist()
      defender_ar = defender_df.nlargest(10, 'total')['Clearance'].tolist()

      left1 = [w + x for w, x in zip(defender_tk, defender_in)]

      ax.barh(top10_defenders, defender_tk, label='Entrada', color=col1, left=0)
      ax.barh(top10_defenders, defender_in, label='Anticipación', color=violet, left=defender_tk)
      ax.barh(top10_defenders, defender_ar, label='Despeje', color=col2, left=left1)

      # Add counts in the middle of the bars (if count > 0)
      for i, player in enumerate(top10_defenders):
          for j, count in enumerate([defender_tk[i], defender_in[i], defender_ar[i]]):
              if count > 0:
                  x_position = sum([defender_tk[i], defender_in[i]][:j]) + count / 2
                  ax.text(x_position, i, str(count), ha='center', va='center', color=line_color, fontsize=13, fontweight='bold')

      max_x = defender_df['total'].iloc()[0]
      x_coord = [2 * i for i in range(1, int(max_x/2))]
      for x in x_coord:
          ax.axvline(x=x, color='gray', linestyle='--', zorder=2, alpha=0.5)

      ax.set_facecolor(bg_color)
      ax.tick_params(axis='x', colors=line_color, labelsize=15)
      ax.tick_params(axis='y', colors=line_color, labelsize=15)
      ax.xaxis.label.set_color(line_color)
      ax.yaxis.label.set_color(line_color)
      for spine in ax.spines.values():
        spine.set_edgecolor(bg_color)

      ax.text((max_x/2)+0.25, -2, "___________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________",
              color=line_color, va='center', ha='center')

      ax.set_title(f"Top 10 estadísticas defensivas", color=line_color, fontsize=20, fontweight='bold')
      ax.legend()

    """# Descargar match report del jugador

    ---


    """

    fig_player, axs = plt.subplots(3,3, figsize=(35,25), facecolor=bg_color)

    home_player_passmap(axs[0,0])
    passer_bar(axs[0,1])
    away_player_passmap(axs[0,2])
    home_passes_recieved(axs[1,0])
    sh_sq_bar(axs[1,1])
    away_passes_recieved(axs[1,2])
    home_player_def_acts(axs[2,0])
    defender_bar(axs[2,1])
    away_player_def_acts(axs[2,2])

    fig_player.savefig(os.path.join(output_dir, f'{file_header}_Player_Dashboard.png'), bbox_inches='tight')
    plt.close(fig_player)
    print("✅ Player Dashboard guardado")


    # ═══════════════════════════════════════════════════════════════════════════════
    # DASHBOARD 3 — RESUMEN KPI
    # ═══════════════════════════════════════════════════════════════════════════════

    # Calcular métricas para KPIs
    h_total_passes    = len(homedf[homedf['type']=='Pass'])
    a_total_passes    = len(awaydf[awaydf['type']=='Pass'])
    h_succ_passes     = len(homedf[(homedf['type']=='Pass') & (homedf['outcomeType']=='Successful')])
    a_succ_passes     = len(awaydf[(awaydf['type']=='Pass') & (awaydf['outcomeType']=='Successful')])
    h_pass_acc        = round(h_succ_passes / h_total_passes * 100, 1) if h_total_passes > 0 else 0
    a_pass_acc        = round(a_succ_passes / a_total_passes * 100, 1) if a_total_passes > 0 else 0

    h_prog_passes     = len(homedf[(homedf['type']=='Pass') & (homedf['pro'] >= 9.144)])
    a_prog_passes     = len(awaydf[(awaydf['type']=='Pass') & (awaydf['pro'] >= 9.144)])

    h_recoveries      = len(homedf[homedf['type']=='BallRecovery'])
    a_recoveries      = len(awaydf[awaydf['type']=='BallRecovery'])

    h_final_third     = len(homedf[(homedf['type']=='Pass') & (homedf['outcomeType']=='Successful') & (homedf['endX'] >= 70)])
    a_final_third     = len(awaydf[(awaydf['type']=='Pass') & (awaydf['outcomeType']=='Successful') & (awaydf['endX'] >= 70)])

    h_poss            = round(h_total_passes / (h_total_passes + a_total_passes) * 100, 1) if (h_total_passes + a_total_passes) > 0 else 0
    a_poss            = round(100 - h_poss, 1)

    # PPDA de cada equipo
    h_rival_passes    = len(awaydf[(awaydf['type']=='Pass') & (awaydf['outcomeType']=='Successful') & (awaydf['x'] < 50)])
    h_own_def         = len(homedf[(homedf['type'].isin(['Tackle','Interception','BlockedPass','BallRecovery'])) & (homedf['x'] > 50)])
    h_ppda            = round(h_rival_passes / h_own_def, 1) if h_own_def > 0 else 0

    a_rival_passes    = len(homedf[(homedf['type']=='Pass') & (homedf['outcomeType']=='Successful') & (homedf['x'] < 50)])
    a_own_def         = len(awaydf[(awaydf['type'].isin(['Tackle','Interception','BlockedPass','BallRecovery'])) & (awaydf['x'] > 50)])
    a_ppda            = round(a_rival_passes / a_own_def, 1) if a_own_def > 0 else 0

    # Altura defensiva de cada equipo
    h_def_pl = home_average_locs_and_count_df[home_average_locs_and_count_df['position'].isin(['DC','DCR','DCL','DR','DL','RB','LB','CB'])] if 'home_average_locs_and_count_df' in dir() else pd.DataFrame()
    a_def_pl = away_average_locs_and_count_df[away_average_locs_and_count_df['position'].isin(['DC','DCR','DCL','DR','DL','RB','LB','CB'])] if 'away_average_locs_and_count_df' in dir() else pd.DataFrame()
    h_def_height = round(h_def_pl['pass_avg_x'].mean() * 1.05, 1) if len(h_def_pl) > 0 else 0
    a_def_height = round(a_def_pl['pass_avg_x'].mean() * 1.05, 1) if len(a_def_pl) > 0 else 0

    fig_kpi = plt.figure(figsize=(32, 20), facecolor=bg_color)
    fig_kpi.patch.set_facecolor(bg_color)

    # Título
    fig_kpi.text(0.5, 0.95, f"{hteamName}  {hgoal_count} — {agoal_count}  {ateamName}",
                 ha='center', fontsize=36, fontweight='bold', color=line_color)
    fig_kpi.text(0.5, 0.91, f"{league}  |  {date}  |  Resumen de métricas",
                 ha='center', fontsize=18, color='#666666')

    # Línea separadora
    fig_kpi.add_artist(plt.Line2D([0.05, 0.95], [0.88, 0.88], color=line_color, linewidth=1, alpha=0.3))

    # ── KPIs grandes (fila superior) ──────────────────────────────────────────────
    kpis_top = [
        ('Posesión', f'{h_poss}%', f'{a_poss}%'),
        ('Precisión de pase', f'{h_pass_acc}%', f'{a_pass_acc}%'),
        ('PPDA rival', f'{h_ppda}', f'{a_ppda}'),
        ('Altura defensiva', f'{h_def_height}m', f'{a_def_height}m'),
    ]

    for i, (label, hval, aval) in enumerate(kpis_top):
        x = 0.12 + i * 0.20
        # Valor local
        fig_kpi.text(x, 0.78, hval, ha='center', fontsize=42, fontweight='bold', color=hcol)
        # Etiqueta
        fig_kpi.text(x, 0.71, label, ha='center', fontsize=14, color=line_color)
        # Valor visitante
        fig_kpi.text(x, 0.64, aval, ha='center', fontsize=42, fontweight='bold', color=acol)

    # Leyenda local/visitante
    fig_kpi.text(0.02, 0.78, hteamName, ha='left', fontsize=16, fontweight='bold', color=hcol, rotation=90, va='center')
    fig_kpi.text(0.02, 0.64, ateamName, ha='left', fontsize=16, fontweight='bold', color=acol, rotation=90, va='center')

    # Línea separadora
    fig_kpi.add_artist(plt.Line2D([0.05, 0.95], [0.60, 0.60], color=line_color, linewidth=1, alpha=0.3))

    # ── KPIs secundarios (fila inferior) ──────────────────────────────────────────
    kpis_bot = [
        ('Total pases', f'{h_total_passes}', f'{a_total_passes}'),
        ('Pases progresivos', f'{h_prog_passes}', f'{a_prog_passes}'),
        ('Recuperaciones', f'{h_recoveries}', f'{a_recoveries}'),
        ('Entradas al último tercio', f'{h_final_third}', f'{a_final_third}'),
        ('xG', f'{hxg}', f'{axg}'),
        ('xGOT', f'{hxgot}', f'{axgot}'),
    ]

    for i, (label, hval, aval) in enumerate(kpis_bot):
        x = 0.09 + i * 0.15
        fig_kpi.text(x, 0.50, hval, ha='center', fontsize=30, fontweight='bold', color=hcol)
        fig_kpi.text(x, 0.44, label, ha='center', fontsize=12, color=line_color)
        fig_kpi.text(x, 0.38, aval, ha='center', fontsize=30, fontweight='bold', color=acol)

    fig_kpi.text(0.98, 0.02, '@jairo-buenaventura', ha='right', fontsize=10, color='#999999')

    fig_kpi.savefig(os.path.join(output_dir, f'{file_header}_KPI_Summary.png'), bbox_inches='tight', facecolor=bg_color)
    plt.close(fig_kpi)
    print("✅ KPI Summary guardado")


    # ═══════════════════════════════════════════════════════════════════════════════
    # DASHBOARD 4 — INSIGHTS TÁCTICOS (texto automático)
    # ═══════════════════════════════════════════════════════════════════════════════

    def _pressure_label(ppda):
        if ppda < 8:   return "presión alta"
        elif ppda < 12: return "presión media"
        else:           return "bloque bajo"

    def _block_label(def_height):
        if def_height > 55:   return "bloque alto"
        elif def_height > 45: return "bloque medio"
        else:                  return "bloque bajo"

    def _compact_label(compactness):
        if compactness < 8:   return "muy compacto"
        elif compactness < 15: return "compacto"
        else:                  return "largo"

    # Encontrar el jugador con más pases progresivos
    h_prog_leader = homedf[(homedf['type']=='Pass') & (homedf['pro'] >= 9.144)].groupby('name').size()
    a_prog_leader = awaydf[(awaydf['type']=='Pass') & (awaydf['pro'] >= 9.144)].groupby('name').size()
    h_top_prog = h_prog_leader.idxmax() if len(h_prog_leader) > 0 else '—'
    a_top_prog = a_prog_leader.idxmax() if len(a_prog_leader) > 0 else '—'

    # Nombre abreviado
    def _short(name):
        parts = str(name).split()
        if len(parts) <= 1: return name
        return f"{parts[0][0]}. {parts[-1]}"

    h_compact = round(home_average_locs_and_count_df['pass_avg_x'].mean() * 1.05 - h_def_height, 1) if len(h_def_pl) > 0 else 0
    a_compact = round(away_average_locs_and_count_df['pass_avg_x'].mean() * 1.05 - a_def_height, 1) if len(a_def_pl) > 0 else 0

    insights_home = [
        f"• {hteamName} jugó con {_block_label(h_def_height)} (altura defensiva: {h_def_height}m).",
        f"• Su bloque fue {_compact_label(h_compact)} — compacidad vertical de {h_compact}m.",
        f"• Presión sobre el rival: {_pressure_label(h_ppda)} (PPDA: {h_ppda}).",
        f"• Precisión de pase: {h_pass_acc}% sobre {h_total_passes} pases totales.",
        f"• Principal generador de juego progresivo: {_short(h_top_prog)} ({h_prog_leader.max() if len(h_prog_leader) > 0 else 0} pases progresivos).",
        f"• Entradas al último tercio: {h_final_third}.",
    ]

    insights_away = [
        f"• {ateamName} jugó con {_block_label(a_def_height)} (altura defensiva: {a_def_height}m).",
        f"• Su bloque fue {_compact_label(a_compact)} — compacidad vertical de {a_compact}m.",
        f"• Presión sobre el rival: {_pressure_label(a_ppda)} (PPDA: {a_ppda}).",
        f"• Precisión de pase: {a_pass_acc}% sobre {a_total_passes} pases totales.",
        f"• Principal generador de juego progresivo: {_short(a_top_prog)} ({a_prog_leader.max() if len(a_prog_leader) > 0 else 0} pases progresivos).",
        f"• Entradas al último tercio: {a_final_third}.",
    ]

    fig_ins = plt.figure(figsize=(32, 20), facecolor=bg_color)
    fig_ins.patch.set_facecolor(bg_color)

    # Título
    fig_ins.text(0.5, 0.95, f"{hteamName}  {hgoal_count} — {agoal_count}  {ateamName}",
                 ha='center', fontsize=36, fontweight='bold', color=line_color)
    fig_ins.text(0.5, 0.91, f"{league}  |  {date}  |  Análisis táctico",
                 ha='center', fontsize=18, color='#666666')
    fig_ins.add_artist(plt.Line2D([0.05, 0.95], [0.88, 0.88], color=line_color, linewidth=1, alpha=0.3))

    # Panel local
    fig_ins.text(0.05, 0.83, hteamName, fontsize=22, fontweight='bold', color=hcol)
    for i, line in enumerate(insights_home):
        fig_ins.text(0.05, 0.76 - i * 0.08, line, fontsize=15, color=line_color, wrap=True)

    # Línea divisoria vertical
    fig_ins.add_artist(plt.Line2D([0.5, 0.5], [0.10, 0.88], color=line_color, linewidth=1, alpha=0.3))

    # Panel visitante
    fig_ins.text(0.53, 0.83, ateamName, fontsize=22, fontweight='bold', color=acol)
    for i, line in enumerate(insights_away):
        fig_ins.text(0.53, 0.76 - i * 0.08, line, fontsize=15, color=line_color, wrap=True)

    fig_ins.text(0.98, 0.02, '@jairo-buenaventura', ha='right', fontsize=10, color='#999999')

    fig_ins.savefig(os.path.join(output_dir, f'{file_header}_Tactical_Insights.png'), bbox_inches='tight', facecolor=bg_color)
    print("✅ Tactical Insights guardado")

    resumen["imagenes_generadas"] = True
    return resumen
