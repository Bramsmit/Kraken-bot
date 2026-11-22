# Bescherming tegen verder leeglopen (22 nov 2026)

De vier lopende posities blijven liggen. Hun sell op de winstvloer blijft staan
zolang het verlies vanaf de instap kleiner is dan 60%. Op de koersen van
22 nov 2026 is die grens nog niet bereikt.

## Wat de run doet

- Een positie met kostenbasis van minstens $25 houdt zijn slot en zijn sell,
  ook als de marktwaarde onder $25 zakt. Er wordt niet bijgekocht.
- Een positie mét openingsdatum wordt verkocht bij 15% verlies of na 14 dagen.
  De verkoop ligt onder de instap en is geen post-only order, anders vult hij
  niet in een dalende markt.
- Een positie zonder openingsdatum (CRV, ADA, UNI, BCH) wordt alleen verkocht
  als de prijs op of onder 40% van de instap staat.
- Nieuwe aankopen gaan niet door zolang de laatste equity meer dan 15% onder
  de hoogste waarde in `data/kraken_equity.csv` staat.
