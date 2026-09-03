# Hauptlauf-Netzwerkdesign – Streamlit-Demo

Interaktive Demo zum Hauptlauf in der Straßenlogistik (Vorlauf → **Hauptlauf** → Nachlauf):
gegeben mehrere Depots mit täglicher Sendungsnachfrage zwischen Depot-Paaren – welche
Depot-Paare bekommen eine feste, tägliche Hauptlauf-Linie (LKW nach Fahrplan), und welche
Sendungen werden stattdessen über ein Zwischen-Depot umgeschlagen, um sich eine ohnehin
fahrende Linie zu teilen? Teil des Portfolios für die Website
"Sebastian Hanisch – Operations Research und Machine Learning", nach Tourenplanung,
3D-Packungsoptimierung, Liniennetz-Design (Min-Cost-Flow) und Seefracht-Konsolidierung.

## Warum diese Demo anders ist als die bisherigen

Bisherige Demos vergleichen entweder mehrere selbst gebaute Heuristiken untereinander
(Seefracht-Konsolidierung) oder eine eigene Implementierung gegen eine exakte
LP-Referenz ohne Ganzzahl-Entscheidungen (Liniennetz-Design, reiner Min-Cost-Flow). Hier
kommen beide Elemente zusammen UND das Problem selbst ist gemischt-ganzzahlig: **welche
Linie überhaupt gebaut wird** ist eine diskrete Ja/Nein-Entscheidung (mit Fixkosten), nicht
nur eine Flussmenge. Das ist ein echtes **Fixed-Charge (Multicommodity) Network Design
Problem**, NP-schwer (Magnanti & Wong, *Network design and transportation planning: Models
and algorithms*, 1984; Crainic, *Service Network Design in Freight Transportation*, 2000).

## Modellierung

Vereinfachung (bewusst, siehe [linehaul_network.py](linehaul_network.py)): jede Sendung
nutzt höchstens **einen** Umschlagpunkt (Direktversand oder Versand über genau einen Hub) –
realistisch für Stückgutspedition, wo mehr als ein Umschlag pro Sendung unüblich ist. Das
macht aus der Routenwahl eine **diskrete Auswahl** aus einem festen Kandidatensatz je
Sendung, statt eines allgemeinen Mehrgüterflusses mit beliebig langen Pfaden. Ein
explizites Hop-Limit ist trotzdem nicht nötig: die Umschlagkosten disziplinieren die
Pfadlänge bereits ökonomisch von selbst – mehr Umschläge lohnen sich nur, wenn die
eingesparten Fixkosten die zusätzliche Umschlaggebühr übersteigen. Mehrere Sendungen
können sich dieselbe Hauptlauf-Linie teilen (der Konsolidierungshebel), ein LKW bedient
vereinfachend beide Richtungen mit je voller Kapazität.

## Methodik – vier Verfahren im Vergleich

- **Alles direkt** (Baseline): jede Sendung fährt direkt, keine Bündelung.
- **Hub-and-Spoke**: alle Sendungen laufen über einen einzigen, best gewählten Hub
  (Best-of-*n*-Suche über alle Depots als Hub-Kandidat).
- **Greedy-Verbesserung**: lokale Koordinatenabstiegssuche über einzelne Sendungen,
  gestartet von "Alles direkt", *allen* möglichen Einzel-Hub-Konfigurationen (nicht nur
  dem besten) und einer sequenziellen Grenzkosten-Konstruktion in beiden Sortier-
  richtungen (siehe Funde unten). Das jeweils beste Endergebnis gewinnt, dadurch gilt
  garantiert `greedy_cost <= min(alles_direkt, hub_and_spoke)`. Anschließend ein
  Politur-Schritt mit paarweisen Sendungs-Tauschzügen (siehe Fund 3 unten).
- **Exakt** (Google OR-Tools, `pywraplp`/SCIP): löst das vollständige gemischt-ganzzahlige
  Modell exakt – Referenz und Cross-Check für alle drei Heuristiken.

Die Primäransicht zeigt **dynamisch** die bei den aktuellen Reglereinstellungen tatsächlich
günstigste Heuristik (`best = min(candidates, key=...)`) – kein Verfahren wird bevorzugt.

## Funde: warum `greedy_construction` mehrere Startpunkte statt eines braucht

### 1. Lokale Suche nur vom besten Einzel-Hub aus reicht nicht

Erste Fassung von `greedy_construction` startete die Verbesserungssuche nur von den
Ergebnissen von "Alles direkt" und der **besten** Hub-and-Spoke-Konfiguration. Über 20
Zufallsinstanzen (7 Depots, Standardkosten) zeigte sich eine mittlere Optimalitätslücke
zum exakten Optimum von **4,4 %**, im Einzelfall bis zu **13,4 %**.

**Ursache:** die Verbesserungssuche bewegt sich nur über Einzeländerungen (eine Sendung
wechselt die Route) – von einem lokal bereits guten Startpunkt aus bleibt sie leicht in
einem lokalen Optimum hängen, das ein anderer, zunächst schlechterer Startpunkt gar nicht
erst erreicht. Konkretes Beispiel (7 Depots, Seed 2): Verbesserungssuche nur vom besten
Einzel-Hub aus landet bei 6.767 €, dieselbe Suche von *allen* Einzel-Hub-Konfigurationen
aus (das jeweils beste Endergebnis) findet 6.425 € – 5,1 % besser, bei Rechenzeiten im
zweistelligen Millisekundenbereich (`test_greedy_benefits_from_exploring_every_hub_as_starting_point`).

**Fix:** `greedy_construction` startet von *allen* Einzel-Hub-Konfigurationen statt nur
der besten, zusätzlich zu "Alles direkt". Dadurch sinkt die mittlere Optimalitätslücke
über dieselben 20 Instanzen auf **3,5 %**, die maximale auf **10,8 %**.

### 2. Nachfrage: warum nicht Monobeam statt Greedy?

Naheliegender Vergleich zur Seefracht-Demo, die für ihr Bin-Packing-Problem eine
**Monobeam**-Konstruktion einsetzt (Lemons et al., *Beam Search: Faster and Monotonic*,
ICAPS 2022 – Slots eines Beams werden sequenziell aus einem gemeinsamen Kandidatenpool
gefüllt, nachweisbar monoton in der Beam-Breite). Der Mechanismus passt strukturell:
so wie die Packreihenfolge bei der Seefracht-Demo bestimmt, ob ein Packstück eine
bereits offene Kiste kostenlos mitnutzt, bestimmt hier die Bearbeitungsreihenfolge der
Sendungen, ob eine Sendung eine bereits eröffnete Hauptlauf-Linie kostenlos mitnutzt oder
eine neue Fixkosten-Linie auslöst – echte Ordnungsabhängigkeit, keine künstliche Analogie.

Der Unterschied: `greedy_construction` ist eine lokale Verbesserungssuche über einer
bereits vollständigen Lösung (Koordinatenabstieg), keine sequenzielle Konstruktion – für
Monobeam fehlte das nötige Fundament. Deshalb zuerst geprüft, ob eine solche sequenzielle
Konstruktion überhaupt etwas findet, das die bestehenden Startpunkte übersehen: eine
First-Fit-Decreasing-artige **Grenzkosten-Konstruktion** (`marginal_cost_construction`)
verarbeitet Sendungen nach Nachfrage sortiert (auf- oder absteigend) und wählt je Sendung
die Route mit den geringsten Grenzkosten unter Wiederverwendung bereits eröffneter Linien.

**Für sich allein deutlich schlechter** als das bestehende Greedy (18 von 20 Instanzen
verliert die reine Konstruktion gegen das bereits mehrfach gestartete Greedy) – aber **als
zusätzlicher Startpunkt für dieselbe Verbesserungssuche** schließt sie eine echte,
zusätzliche Lücke: über dieselben 20 Instanzen sinkt die mittlere Optimalitätslücke von
3,5 % auf **3,0 %**, die maximale von 10,8 % auf **9,8 %**, bei vernachlässigbarer
Mehrzeit (< 0,5 s selbst bei 9 Depots). Konkretes Beispiel (Seed 1): Verbesserungssuche
von "Alles direkt" und allen Hub-Konfigurationen aus bleibt bei 6.913 € hängen, mit der
Grenzkosten-Konstruktion als zusätzlichem Startpunkt erreicht Greedy das exakte Optimum
(6.508 €) (`test_greedy_benefits_from_marginal_cost_construction_as_starting_point`).

**Fazit:** die Suche selbst lohnt sich (Monobeam wäre also keine Fehlinvestition gewesen),
aber der volle Monobeam-Apparat (gemeinsamer Kandidatenpool, Slot-für-Slot-Entnahme,
Beweis der Monotonie in der Beam-Breite) ist für den erzielten Zusatznutzen bislang nicht
gerechtfertigt – dieselbe Verbesserung ließ sich mit einer einfachen zusätzlichen
Konstruktionsheuristik erreichen. Bei manchen Instanzen bleibt trotzdem eine spürbare
Lücke zum Optimum, siehe Fund 3.

### 3. Paarweise Tauschzüge statt nur Einzeländerungen

Auf Nutzerwunsch geprüft: lohnt sich eine Erweiterung der lokalen Suche selbst, statt
weiterer Startpunkte? `_local_search` ändert je Zug nur EINE Sendung – bei
Fixkosten-je-LKW-Sprüngen gibt es aber Fälle, in denen weder Sendung A noch Sendung B
allein umzurouten hilft, wohl aber BEIDE gemeinsam (z. B. weil erst ihre gemeinsame
Verlagerung eine Linie ganz unter die Ein-LKW-Schwelle drückt, oder umgekehrt zwei
Sendungen zusammen eine bereits fast volle Linie gerade noch ohne zusätzlichen LKW
aufnehmen). Genau diese Lücke übersieht reiner Koordinatenabstieg strukturell.

**Performance-Falle zuerst gefunden und behoben, bevor der eigentliche Nutzen geprüft
werden konnte:** eine naive paarweise Suche (für jedes Sendungspaar alle Routenkombi-
nationen ausprobieren, Kosten jeweils per vollständiger Neubewertung) brauchte bei
9 Depots und hoher Nachfragedichte bis zu **7,5 s** – weit über dem Budget. Ursache: jede
Kostenneubewertung ist O(Sendungsanzahl), bei quadratisch vielen Sendungspaaren addiert
sich das schnell. Fix: **inkrementelle** Kostenberechnung (`_pair_swap_delta`) – nur die
paar Linien, die die beiden betroffenen Sendungen tatsächlich berühren, werden neu
bewertet, nicht das gesamte Netzwerk. Auf 300 zufälligen Kandidatenpaaren exakt
deckungsgleich mit der vollständigen Neubewertung geprüft
(`test_pairwise_swap_delta_matches_full_recomputation`), danach lag der Worst Case
(9 Depots, maximale Nachfragedichte) bei **1,8 s** statt 7,5 s.

**Ergebnis, nachdem die Suche schnell genug war:** als abschließender Politur-Schritt
nach der bestehenden Multi-Start-Suche angewendet (nicht auf jeden der elf Startpunkte
einzeln, sondern nur auf das jeweils beste Endergebnis – hält die Mehrkosten klein).
Über dieselben 20 Testinstanzen sinkt die mittlere Optimalitätslücke von **3,0 % auf
1,6 %**, die maximale von **9,8 % auf 7,7 %**, 9 von 20 Instanzen verbessert, mehrere
treffen danach exakt das Optimum. Der bisher hartnäckige Fall (Seed 7, das Default-Preset
im UI) verbessert sich von 9.765 € auf 9.200 € – die Lücke schrumpft von 9,8 % auf 3,5 %,
schließt sich aber nicht vollständig (`test_greedy_benefits_from_pairwise_swap_polish`).

**Bewusst NICHT umgesetzt:** Dreier- oder höhere Tauschzüge, oder paarweise Suche als
zusätzlicher Startpunkt statt reiner Politur – beides würde die Rechenzeit weiter
erhöhen, ohne dass bisher geprüft wurde, ob der Zusatznutzen das rechtfertigt (dieselbe
Frage müsste vor einer Erweiterung erst wieder per Sweep beantwortet werden, nicht
angenommen werden).

## Kipppunkt-Analyse: wann lohnt sich Bündelung?

Systematisch vermessen (7 Depots, Seed 7, Standard-Nachfragedichte 0,5):

**Fixkosten je Linie und km** (bei festen Umschlagkosten 1,5 €/Einheit) – die Ersparnis
von Greedy gegenüber "Alles direkt" wächst mit den Fixkosten, wie erwartet:

| Fixkosten (€/km) | Alles direkt | Hub-and-Spoke | Greedy | Ersparnis ggü. Direkt |
|---|---|---|---|---|
| 2 | 3.558 € | 4.356 € | 2.929 € | 17,7 % |
| 5 | 6.080 € | 6.167 € | 4.345 € | 28,5 % |
| 10 | 10.283 € | 9.186 € | 6.883 € | 33,1 % |
| 15 | 14.487 € | 12.204 € | 9.200 € | 36,5 % |
| 20 | 18.690 € | 15.223 € | 11.102 € | 40,6 % |
| 25 | 22.893 € | 18.242 € | 13.312 € | 41,9 % |
| 30 | 27.097 € | 21.260 € | 16.239 € | 40,1 % |

Bei niedrigen Fixkosten (2 €/km) verliert Hub-and-Spoke sogar gegen "Alles direkt"
(4.356 € > 3.558 €) – der erzwungene Umweg über einen einzigen Hub lohnt sich nicht, wenn
Direktlinien ohnehin günstig sind. Genau dafür ist Greedy da: es findet trotzdem die
bessere Mischung aus Direkt- und Hub-Routen (2.929 €, hier sogar exakt das Optimum) statt
stur auf Hub-and-Spoke zu bauen. Preset "Geringe Fixkosten (Hub schadet)" zeigt das direkt.

**Umschlagkosten** (bei festen Fixkosten 15 €/km) – schwächerer, aber sichtbarer Effekt:

| Umschlagkosten (€/Einheit) | Hub-and-Spoke | Greedy | Ersparnis ggü. Direkt |
|---|---|---|---|
| 0,5 | 11.964 € | 8.752 € | 39,6 % |
| 1 | 12.084 € | 9.140 € | 36,9 % |
| 2 | 12.324 € | 9.247 € | 36,2 % |
| 5 | 13.045 € | 9.693 € | 33,1 % |
| 8 | 13.766 € | 9.578 € | 33,9 % |
| 12 | 14.728 € | 9.894 € | 31,7 % |

Hub-and-Spoke verschlechtert sich mit steigenden Umschlagkosten deutlich schneller als
Greedy – Greedy kann bei teurem Umschlag gezielt auf Direktrouten ausweichen, während
Hub-and-Spoke strukturell an "alles über einen Hub" gebunden bleibt. Preset "Teurer
Umschlag" macht diesen Unterschied sichtbar.

## Laufzeit des exakten Lösers

### Fund: die ursprüngliche "<1,5 s"-Angabe galt nur bei Standard-Nachfragedichte

Die erste Laufzeitmessung (3 Zufallsinstanzen je Depotzahl) lief ausschließlich bei der
Standard-Nachfragedichte 0,5 und ergab durchgehend < 1,5 s bis 9 Depots - deshalb wurde
der Depot-Regler auf 4–9 begrenzt und `EXACT_SOLVE_TIME_LIMIT_SECONDS` auf 15 gesetzt. Das
war unvollständig: die Nachfragedichte ist ein zweiter, unabhängiger Regler (0,2–1,0), der
dieselbe Depotzahl deutlich mehr Sendungen erzeugen lässt - und genau das treibt die
Schwierigkeit des gemischt-ganzzahligen Modells. Nachgemessen (3 Instanzen je Zelle, ohne
Zeitlimit, `SCIP`-Backend):

| Depots | Dichte 0,5 | Dichte 0,7 | Dichte 0,9 | Dichte 1,0 |
|---|---|---|---|---|
| 6 | 0,13 s | 0,15 s | 0,30 s | 0,06 s |
| 7 | 0,03 s | 0,60 s | 0,93 s | 0,93 s |
| 8 | 0,52 s | 1,88 s | 1,90 s | 2,23 s |
| 9 | 0,73 s | 1,54 s | **14,08 s** | **19,75 s** (1 von 3 nicht bewiesen optimal) |

Bei 9 Depots UND hoher Nachfragedichte (beide Regler unabhängig auf ihrem jeweiligen
Maximum erreichbar) explodiert die Laufzeit - mit dem alten 15s-Zeitlimit hätte die App bei
jeder Regler-Interaktion in dieser Ecke bis zu 15 s eingefroren.

### Warum kein größenbasierter Cutoff, sondern eine feste Zeitschranke

Naheliegend wäre gewesen, die exakte Lösung oberhalb einer Sendungsanzahl-Schwelle
automatisch zu überspringen. Genauere Messung (mehrere Seeds je Sendungsanzahl) zeigt aber:
**Schwierigkeit korreliert nicht sauber mit der Größe.** Beispiel bei 9 Depots: eine
Instanz mit 26 Sendungen brauchte 5,0 s, eine andere mit 32 Sendungen nur 2,4 s - erwartbar
für ein NP-schweres Branch-and-Bound-Problem, dessen Worst Case nicht monoton in der
Eingabegröße ist. Ein Schwellenwert wäre also entweder zu großzügig (lässt seltene, aber
reale Ausreißer bei kleineren Größen durch) oder zu konservativ (schließt viele eigentlich
schnell lösbare größere Instanzen unnötig aus).

**Fix:** `EXACT_SOLVE_TIME_LIMIT_SECONDS` (`linehaul_constants.py`) von 15 auf **4 Sekunden**
reduziert - das begrenzt die Wartezeit bei JEDER Instanzgröße robust, unabhängig davon, ob
sie zufällig hart oder leicht ist. In einem Raster über 6–9 Depots × 4 Nachfragedichten
(80 Instanzen) erreichten bei 4 s Zeitlimit 70/80 das bewiesene Optimum, die restlichen
10 (ausschließlich bei 9 Depots + Dichte ≥ 0,9) liefern die beste innerhalb des Zeitlimits
gefundene, nicht bewiesen optimale Lösung. Das ist kein stiller Fehler: `app.py` kennzeichnet
dieses Ergebnis bereits korrekt als "Zeitlimit erreicht, beste gefundene Lösung" statt es
fälschlich als Optimum auszugeben - diese Unterscheidung war schon vor dem Fund vorhanden,
nur eben zu selten sichtbar, weil das 15s-Zeitlimit die App stattdessen einfrieren ließ, statt
schnell (aber ehrlich unbewiesen) zu antworten.
`test_exact_solve_respects_its_time_budget_at_worst_case_ui_settings` (9 Depots, Dichte 1,0)
hält das neue Zeitbudget fest.

**Bewusst NICHT umgesetzt:** ein dynamisches Zeitlimit oder ein größenbasierter Cutoff (siehe
oben, durch die fehlende Größen-Härte-Korrelation nicht robust begründbar), oder eine
gegenseitige Begrenzung der Regler (z. B. Nachfragedichte bei 9 Depots kappen) - beides würde
Komplexität in die ohnehin schon unabhängigen `SETTING_SPECS`-Regler tragen, für einen
Nutzen, den die einfache feste Zeitschranke bereits abdeckt.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf: Sidebar, Primäransicht, Methodenvergleich, Formulierungs-Expander |
| `linehaul_constants.py` | Defaults, Regler-Grenzen, `PRESETS` |
| `linehaul_presets.py` | `SettingSpec`/`SETTING_SPECS`, Permalink-Logik, Presets, Zufalls-Seed-Button |
| `linehaul_scenario.py` | Zufällige Depotpositionen und Nachfragematrix |
| `linehaul_network.py` | Problem-Instanz: Commodities, Kandidatenlinien, Routen (Direkt/via Hub) |
| `linehaul_heuristics.py` | Alles direkt, Hub-and-Spoke, Greedy-Verbesserung |
| `linehaul_reference_solver.py` | Exakter MIP-Löser (OR-Tools `pywraplp`, SCIP) |
| `linehaul_evaluation.py` | Kostenaufschlüsselung, Vergleichstabelle |
| `linehaul_visualization.py` | Netzwerkkarte, Kostenaufschlüsselungs-Chart (Plotly) |
| `linehaul_pdf_export.py` | PDF-Netzwerkplan (`fpdf2`) |
| `linehaul_ui_panel.py` | Wiederverwendbares Panel je Methode |
| `tests/` | Instanzaufbau, Heuristik-Eigenschaften, MIP-Cross-Check inkl. handgerechneter Kleinstinstanz |

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von
[Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning.
Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
